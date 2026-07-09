import pytest
import uuid
import asyncio
import httpx
import json
from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.logging import correlation_id_ctx

# ---------------------------------------------------------------------------
# 1. CONCURRENCY ISOLATION TEST
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_correlation_id_concurrency_isolation():
    """
    Simulates 50 concurrent requests and verifies that ContextVar
    isolation works correctly under high concurrency (each has a unique ID).
    """
    async with httpx.AsyncClient(app=app, base_url="https://testserver") as client:
        tasks = [client.get("/health") for _ in range(50)]
        responses = await asyncio.gather(*tasks)
        
        corr_ids = [resp.headers.get("X-Correlation-ID") for resp in responses]
        assert all(corr_ids), "All responses must have a correlation ID"
        assert len(set(corr_ids)) == 50, "All correlation IDs must be unique"


# ---------------------------------------------------------------------------
# 2. END-TO-END PROPAGATION TEST
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_telemetry_propagation_matches_header():
    """
    Verifies that the correlation ID in the request header matches
    the correlation ID stored in the database's OperationalEvent.
    """
    from backend.app.core.database import get_db
    
    db_mock = AsyncMock()
    zone_mock = MagicMock()
    zone_mock.id = uuid.uuid4()
    zone_mock.name = "Gate A"
    zone_mock.safe_capacity = 1000
    zone_mock.current_occupancy = 500
    
    def db_execute_side_effect(query):
        q_str = str(query).lower()
        res_mock = MagicMock()
        if "zone" in q_str and "snapshot" not in q_str and "event" not in q_str:
            res_mock.scalars().first.return_value = zone_mock
        else:
            res_mock.scalars().first.return_value = None
            res_mock.scalars().all.return_value = []
        return res_mock
    db_mock.execute.side_effect = db_execute_side_effect
    
    app.dependency_overrides[get_db] = lambda: db_mock
    try:
        async with httpx.AsyncClient(app=app, base_url="https://testserver") as client:
            correlation_id = str(uuid.uuid4())
            headers = {
                "X-API-Key": settings.API_KEY,
                "X-Correlation-ID": correlation_id
            }
            
            with patch("backend.app.services.recommend.generate_and_validate_recommendations") as mock_rec:
                mock_rec.return_value = MagicMock(id=uuid.uuid4())
                
                response = await client.post(
                    "/api/v1/telemetry",
                    headers=headers,
                    json={
                        "zone_id": str(zone_mock.id),
                        "sensor_type": "camera",
                        "count": 900
                    }
                )
                assert response.status_code == status.HTTP_202_ACCEPTED
                assert response.headers.get("X-Correlation-ID") == correlation_id
                
                # Verify that the created OperationalEvent has the matching correlation_id
                added_event = None
                for call in db_mock.add.call_args_list:
                    obj = call[0][0]
                    from backend.app.models.models import OperationalEvent
                    if isinstance(obj, OperationalEvent):
                        added_event = obj
                        break
                
                assert added_event is not None
                assert str(added_event.correlation_id) == correlation_id
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 3. ERROR FLOW PROPAGATION TEST
# ---------------------------------------------------------------------------
def test_correlation_id_on_unauthorized_error():
    """
    Verifies that unauthenticated / failing requests still receive an X-Correlation-ID header.
    """
    client = TestClient(app)
    response = client.post("/api/v1/telemetry", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) > 0


# ---------------------------------------------------------------------------
# 4. CONTEXT CLEANLINESS TEST
# ---------------------------------------------------------------------------
def test_context_cleanliness_after_request():
    """
    Verifies that the correlation ID ContextVar is reset and cleared after request completion.
    """
    client = TestClient(app)
    assert correlation_id_ctx.get() == ""
    response = client.get("/health")
    assert response.status_code == 200
    # ContextVar must have been reset to empty default
    assert correlation_id_ctx.get() == ""


# ---------------------------------------------------------------------------
# 5. LOG CONSISTENCY TEST
# ---------------------------------------------------------------------------
def test_log_consistency(caplog):
    """
    Verifies that the structured JSON log output contains the correct request details and correlation ID.
    """
    client = TestClient(app)
    with caplog.at_level("INFO"):
        response = client.get("/health")
        assert response.status_code == 200
        corr_id = response.headers.get("X-Correlation-ID")
        assert corr_id is not None
        
        found = False
        for record in caplog.records:
            if "Request completed" in record.message:
                found = True
                from backend.app.core.logging import JSONFormatter
                formatter = JSONFormatter()
                formatted = formatter.format(record)
                
                log_data = json.loads(formatted)
                assert log_data["correlation_id"] == corr_id
                assert log_data["endpoint"] == "/health"
                assert log_data["method"] == "GET"
                assert log_data["status_code"] == 200
                assert "latency_ms" in log_data
                assert "client_ip" in log_data
                assert "user_agent" in log_data
        
        assert found, "Request completed log not found"

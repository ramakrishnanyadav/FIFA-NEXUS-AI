import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.main import app
from backend.app.core.config import settings

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "healthy"
    assert "api_key_configured" in body
    assert isinstance(body["api_key_configured"], bool)

# ---------------------------------------------------------------------------
# API Key Verification & Negative Authentication Tests
# ---------------------------------------------------------------------------
def test_unauthorized_post_endpoints(client):
    # Test POST /api/v1/telemetry without API key
    resp = client.post("/api/v1/telemetry", json={
        "zone_id": str(uuid.uuid4()),
        "sensor_type": "camera",
        "count": 100
    })
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Test POST /api/v1/recommendations/apply without API key
    resp = client.post(f"/api/v1/recommendations/{uuid.uuid4()}/apply")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Test POST /api/v1/events without API key
    resp = client.post("/api/v1/events", json={
        "source": "test",
        "event_type": "TEST_EVENT",
        "payload": {}
    })
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Test POST /api/v1/assistant/chat without API key
    resp = client.post("/api/v1/assistant/chat", json={"message": "hello"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

def test_invalid_api_key_header(client):
    headers = {"X-API-Key": "wrong_key_123"}
    resp = client.post("/api/v1/telemetry", headers=headers, json={
        "zone_id": str(uuid.uuid4()),
        "sensor_type": "camera",
        "count": 100
    })
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

# ---------------------------------------------------------------------------
# Invalid Schema / Missing Fields (HTTP 422)
# ---------------------------------------------------------------------------
def test_invalid_telemetry_schema(client):
    headers = {"X-API-Key": "fifanexus_api_key_2026"}
    # Missing count
    resp = client.post("/api/v1/telemetry", headers=headers, json={
        "zone_id": str(uuid.uuid4()),
        "sensor_type": "camera"
    })
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Invalid sensor type (Literal validation)
    resp = client.post("/api/v1/telemetry", headers=headers, json={
        "zone_id": str(uuid.uuid4()),
        "sensor_type": "invalid_sensor",
        "count": 100
    })
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Negative count
    resp = client.post("/api/v1/telemetry", headers=headers, json={
        "zone_id": str(uuid.uuid4()),
        "sensor_type": "camera",
        "count": -5
    })
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

# ---------------------------------------------------------------------------
# Rate Limiting Tests (HTTP 429)
# ---------------------------------------------------------------------------
def test_rate_limiter_write_limits(client):
    import time
    from backend.app.core.rate_limit import write_limiter
    headers = {"X-API-Key": "fifanexus_api_key_2026"}
    
    # Fill up the write rate limiter with recent timestamps to trigger 429
    now = time.time()
    # TestClient requests can show up as client host 127.0.0.1, testclient, or unknown
    for key in ["127.0.0.1:fifanexus_api_key_2026", "testclient:fifanexus_api_key_2026", "unknown:fifanexus_api_key_2026"]:
        write_limiter.requests[key] = [now] * 35
    
    resp = client.post("/api/v1/telemetry", headers=headers, json={
        "zone_id": str(uuid.uuid4()),
        "sensor_type": "camera",
        "count": 100
    })
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Too many requests" in resp.json()["detail"]
    
    # Clear limiter after test
    for key in ["127.0.0.1:fifanexus_api_key_2026", "testclient:fifanexus_api_key_2026", "unknown:fifanexus_api_key_2026"]:
        write_limiter.requests[key] = []

# ---------------------------------------------------------------------------
# GET Zones, Tasks, and Events
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_zones_endpoint(client):
    # Mock database session return values
    zone_mock = MagicMock()
    zone_mock.id = uuid.uuid4()
    zone_mock.stadium_id = uuid.uuid4()
    zone_mock.name = "Gate A"
    zone_mock.zone_type = "GATE"
    zone_mock.safe_capacity = 1200
    zone_mock.current_occupancy = 100
    zone_mock.deleted_at = None
    
    db_execute_mock = MagicMock()
    db_execute_mock.scalars().all.return_value = [zone_mock]
    
    db_mock = AsyncMock()
    db_mock.execute.return_value = db_execute_mock

    from backend.app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: db_mock
    try:
        response = client.get("/api/v1/zones")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Gate A"
        assert data[0]["safe_capacity"] == 1200
    finally:
        app.dependency_overrides.pop(get_db, None)

@pytest.mark.asyncio
async def test_get_tasks_endpoint(client):
    task_mock = MagicMock()
    task_mock.id = uuid.uuid4()
    task_mock.recommendation_id = uuid.uuid4()
    task_mock.assigned_user_id = uuid.uuid4()
    task_mock.assigned_role = "VOLUNTEER"
    task_mock.details = "Deploy signage at Gate A"
    task_mock.status = "PENDING"
    task_mock.created_at = datetime.utcnow()
    task_mock.updated_at = datetime.utcnow()

    db_execute_mock = MagicMock()
    db_execute_mock.scalars().all.return_value = [task_mock]

    db_mock = AsyncMock()
    db_mock.execute.return_value = db_execute_mock

    from backend.app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: db_mock
    try:
        response = client.get("/api/v1/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["details"] == "Deploy signage at Gate A"
        assert data[0]["assigned_role"] == "VOLUNTEER"
    finally:
        app.dependency_overrides.pop(get_db, None)

# ---------------------------------------------------------------------------
# 404 Endpoint Not Found
# ---------------------------------------------------------------------------
def test_404_not_found(client):
    response = client.get("/api/v1/non_existent_route")
    assert response.status_code == status.HTTP_404_NOT_FOUND


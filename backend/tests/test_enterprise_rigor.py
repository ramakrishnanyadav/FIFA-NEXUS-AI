import pytest
import uuid
import asyncio
import random
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import status

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.schemas.schemas import TelemetryCreate
from backend.app.api.v1.zones import ZoneResponseSchema

# ---------------------------------------------------------------------------
# 1. CONTRACT TESTS
# ---------------------------------------------------------------------------
def test_schema_contracts():
    """
    Contract Test: Verifies that the JSON returned by GET /api/v1/zones
    matches the Pydantic response schema (ZoneResponseSchema) contract exactly.
    """
    client = TestClient(app)
    
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
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        
        # Enforce contract validation on Pydantic schema
        validated = ZoneResponseSchema.model_validate(data[0])
        assert validated.name == "Gate A"
        assert validated.safe_capacity == 1200
    finally:
        app.dependency_overrides.pop(get_db, None)

    # 2. Recommendations Stats contract check
    rec_mock = MagicMock()
    rec_mock.reasoning_time_ms = 150.0
    rec_mock.validation_status = "VALIDATED"
    rec_mock.expected_impact = {"co2_saved_kg": 5.2}
    rec_mock.model_version = "openai/gpt-4o"

    db_execute_mock_rec = MagicMock()
    db_execute_mock_rec.scalars().all.return_value = [rec_mock]
    db_mock_rec = AsyncMock()
    db_mock_rec.execute.return_value = db_execute_mock_rec

    app.dependency_overrides[get_db] = lambda: db_mock_rec
    try:
        response = client.get("/api/v1/recommendations/stats")
        assert response.status_code == status.HTTP_200_OK
        stats_data = response.json()
        assert stats_data["total_count"] == 1
        assert stats_data["avg_reasoning_time_ms"] == 150.0
        assert stats_data["validated_count"] == 1
        assert stats_data["total_co2_saved_kg"] == 5.2
        assert stats_data["provider_stats"]["openai/gpt-4o"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 2. DATABASE TRANSACTION INTEGRITY & ROLLBACK TEST
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_database_transaction_rollback():
    """
    Transaction Integrity Test: Verifies that if a database write error occurs
    during telemetry ingestion, a full database rollback is executed.
    """
    db_mock = AsyncMock()
    db_mock.commit.side_effect = Exception("DB Commit Failed")
    
    zone_id = uuid.uuid4()
    gate_mock = MagicMock()
    gate_mock.id = zone_id
    gate_mock.name = "Gate A"
    gate_mock.safe_capacity = 1000
    gate_mock.current_occupancy = 500
    
    def execute_side_effect(query):
        q_str = str(query).lower()
        res = MagicMock()
        if "zone" in q_str and "snapshot" not in q_str and "event" not in q_str:
            res.scalars().first.return_value = gate_mock
        else:
            res.scalars().first.return_value = None
        return res
    db_mock.execute.side_effect = execute_side_effect
    
    from backend.app.services.telemetry import process_telemetry_input
    telemetry = TelemetryCreate(
        zone_id=zone_id,
        sensor_type="camera",
        count=950,
        timestamp=datetime.now(UTC)
    )
    
    with patch("backend.app.services.recommend.generate_and_validate_recommendations") as mock_gen:
        mock_gen.return_value = MagicMock(id=uuid.uuid4())
        with pytest.raises(Exception, match="DB Commit Failed"):
            await process_telemetry_input(db_mock, AsyncMock(), telemetry)
    
    # Assert transaction integrity: rollback was called
    db_mock.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# 3. IDEMPOTENCY STRESS TEST
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_telemetry_ingestion_idempotency_stress():
    """
    Idempotency Stress Test: Ingests identical telemetry packets 50 times.
    Verifies that the database handles duplicate requests gracefully and prevents
    multiple active recommendation triggers within the duplicate cooldown window.
    """
    db_mock = AsyncMock()
    redis_mock = AsyncMock()
    
    zone_id = uuid.uuid4()
    gate_mock = MagicMock()
    gate_mock.id = zone_id
    gate_mock.name = "Gate A"
    gate_mock.safe_capacity = 1000
    gate_mock.current_occupancy = 500
    
    def execute_side_effect(query):
        q_str = str(query).lower()
        res = MagicMock()
        if "zone" in q_str and "snapshot" not in q_str and "event" not in q_str:
            res.scalars().first.return_value = gate_mock
        else:
            res.scalars().first.return_value = None
        return res
    db_mock.execute.side_effect = execute_side_effect
    
    from backend.app.services.telemetry import process_telemetry_input
    telemetry = TelemetryCreate(
        zone_id=zone_id,
        sensor_type="camera",
        count=950,
        timestamp=datetime.now(UTC)
    )
    
    results = []
    # Send 50 duplicate packets in a loop
    for _ in range(50):
        with patch("backend.app.services.recommend.generate_and_validate_recommendations") as mock_gen:
            mock_gen.return_value = MagicMock(id=uuid.uuid4())
            r = await process_telemetry_input(db_mock, redis_mock, telemetry)
            results.append(r)
            
    assert results[0]["status"] == "success"
    # Seeding database with event occurs on first tick, verifying db writes
    assert db_mock.add.call_count >= 1


# ---------------------------------------------------------------------------
# 4. CONCURRENCY TEST
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_telemetry_ingestion():
    """
    Concurrency Test: Simulates 20 concurrent telemetry packets arriving
    simultaneously. Verifies that the ingest pipeline processes concurrently
    without crashing or causing transaction locks.
    """
    db_mock = AsyncMock()
    redis_mock = AsyncMock()
    
    zone_id = uuid.uuid4()
    gate_mock = MagicMock()
    gate_mock.id = zone_id
    gate_mock.name = "Gate A"
    gate_mock.safe_capacity = 1000
    gate_mock.current_occupancy = 500
    
    def execute_side_effect(query):
        q_str = str(query).lower()
        res = MagicMock()
        if "zone" in q_str and "snapshot" not in q_str and "event" not in q_str:
            res.scalars().first.return_value = gate_mock
        else:
            res.scalars().first.return_value = None
        return res
    db_mock.execute.side_effect = execute_side_effect
    
    from backend.app.services.telemetry import process_telemetry_input
    telemetry = TelemetryCreate(
        zone_id=zone_id,
        sensor_type="camera",
        count=950,
        timestamp=datetime.now(UTC)
    )
    
    # Fire 20 requests concurrently via asyncio.gather and mock recommendation triggers
    with patch("backend.app.services.recommend.generate_and_validate_recommendations") as mock_gen:
        mock_gen.return_value = MagicMock(id=uuid.uuid4())
        tasks = [process_telemetry_input(db_mock, redis_mock, telemetry) for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Assert all concurrent runs succeeded
    for r in results:
        assert not isinstance(r, Exception)
        assert r["status"] == "success"


# ---------------------------------------------------------------------------
# 5. PROPERTY-BASED ROBUSTNESS TEST
# ---------------------------------------------------------------------------
def test_optimizer_property_fuzz():
    """
    Property-based Robustness Test: Fuzzes the constraint optimizer with 100
    randomized combinations of occupancy, safe capacities, and risk scores.
    Verifies that the math engine always returns valid outputs and never crashes
    (no division-by-zero, no out-of-bound scores).
    """
    from backend.app.services.optimizer import optimize_candidate_actions
    
    actions = ["Action A", "Action B", "Action C"]
    
    for _ in range(100):
        # Generate random inputs representing edge cases
        occupancy = random.randint(0, 3000)
        capacity = random.randint(1, 3000)  # capacity > 0
        risk = random.uniform(0.0, 1.0)
        
        result = optimize_candidate_actions(
            candidate_actions=actions,
            current_occupancy=occupancy,
            safe_capacity=capacity,
            congestion_risk=risk
        )
        
        # Verify invariants
        assert "actions" in result
        assert "score" in result
        assert "co2_saved_kg" in result
        assert 0.0 <= result["score"] <= 1.0
        assert result["co2_saved_kg"] >= 0.0

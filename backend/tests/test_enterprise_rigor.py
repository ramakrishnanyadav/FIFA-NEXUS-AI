import pytest
import uuid
import asyncio
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
    multiple active recommendation triggers within the duplicate cooldown window
    using a real in-memory SQLite database session.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from backend.app.core.database import Base
    from backend.app.models.models import Zone, ZoneOccupancySnapshot, OperationalEvent
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    tables = [
        Zone.__table__,
        ZoneOccupancySnapshot.__table__,
        OperationalEvent.__table__
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
        
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    # Seed a real Zone
    zone_id = uuid.uuid4()
    async with async_session() as session:
        zone = Zone(
            id=zone_id,
            stadium_id=uuid.uuid4(),
            name="Gate A",
            zone_type="GATE",
            safe_capacity=1000,
            current_occupancy=500
        )
        session.add(zone)
        await session.commit()

    from backend.app.services.telemetry import process_telemetry_input
    timestamp = datetime.now(UTC)
    telemetry = TelemetryCreate(
        zone_id=zone_id,
        sensor_type="camera",
        count=950,
        timestamp=timestamp
    )
    
    results = []
    # Send 50 duplicate packets sequentially using the same SQLite database session maker
    with patch("backend.app.services.recommend.generate_and_validate_recommendations") as mock_gen:
        mock_gen.return_value = MagicMock(id=uuid.uuid4())
        
        for _ in range(50):
            async with async_session() as session:
                r = await process_telemetry_input(session, AsyncMock(), telemetry)
                results.append(r)
                
    # Verify the first call succeeds and triggers a CROWD_DENSITY_HIGH event
    assert results[0]["status"] == "success"
    assert results[0]["event_triggered"] == "CROWD_DENSITY_HIGH"
    
    # Verify that the subsequent 49 calls bypass duplicate ingestion (idempotency safety check)
    for i in range(1, 50):
        assert results[i]["status"] == "success"
        assert "Duplicate ingestion bypassed" in results[i]["message"]
        assert results[i]["event_triggered"] is None
        
    # Verify database state: exactly 1 snapshot and 1 event created
    async with async_session() as session:
        from sqlalchemy.future import select
        snaps = (await session.execute(select(ZoneOccupancySnapshot))).scalars().all()
        events = (await session.execute(select(OperationalEvent))).scalars().all()
        
        assert len(snaps) == 1
        assert len(events) == 1


# ---------------------------------------------------------------------------
# 4. CONCURRENCY TEST
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_telemetry_ingestion():
    """
    Concurrency Test: Simulates 20 concurrent telemetry packets arriving
    simultaneously. Verifies that the ingest pipeline processes concurrently
    and handles state updates robustly using a real shared-memory SQLite database.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from backend.app.core.database import Base
    from backend.app.models.models import Zone, ZoneOccupancySnapshot, OperationalEvent
    
    # Configure shared-cache memory DB to support concurrent session connections
    engine = create_async_engine("sqlite+aiosqlite:///file:memdb_concurrent?mode=memory&cache=shared&uri=true", future=True)
    tables = [
        Zone.__table__,
        ZoneOccupancySnapshot.__table__,
        OperationalEvent.__table__
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
        
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    # Seed the Zone
    zone_id = uuid.uuid4()
    async with async_session() as session:
        zone = Zone(
            id=zone_id,
            stadium_id=uuid.uuid4(),
            name="Gate A",
            zone_type="GATE",
            safe_capacity=1000,
            current_occupancy=500
        )
        session.add(zone)
        await session.commit()
        
    from backend.app.services.telemetry import process_telemetry_input
    
    # We generate 20 requests with unique timestamps so they are not rejected as duplicates
    # but run concurrently against the database
    tasks = []
    with patch("backend.app.services.recommend.generate_and_validate_recommendations") as mock_gen:
        mock_gen.return_value = MagicMock(id=uuid.uuid4())
        
        for i in range(20):
            # Unique timestamp per concurrent task
            from datetime import timedelta
            t = datetime.now(UTC) + timedelta(seconds=i)
            telemetry = TelemetryCreate(
                zone_id=zone_id,
                sensor_type="camera",
                count=950 + i,
                timestamp=t
            )
            # Create a separate session for each concurrent task
            async def run_task(telemetry_data):
                async with async_session() as session:
                    return await process_telemetry_input(session, AsyncMock(), telemetry_data)
            tasks.append(run_task(telemetry))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
    # Assert all concurrent runs succeeded without transaction locks or crashes
    for r in results:
        assert not isinstance(r, Exception), f"Concurrent task raised an exception: {r}"
        assert r["status"] == "success"
        
    # Verify that snapshots were successfully recorded in the database
    async with async_session() as session:
        from sqlalchemy.future import select
        snaps = (await session.execute(select(ZoneOccupancySnapshot))).scalars().all()
        assert len(snaps) == 20



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
    
    for i in range(100):
        # Generate deterministic inputs representing edge cases without PRNG
        occupancy = (i * 37) % 3001
        capacity = 1 + ((i * 59) % 3000)
        risk = (i * 13 % 100) / 100.0
        
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

"""
Targeted branch coverage tests for the four weakest modules.

These tests exercise error paths, 404/500 branches, and offline fallback logic that
are currently uncovered, pushing total branch coverage meaningfully higher.

Each pytest.raises block contains exactly one invocation (S5783).
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from backend.app.api.v1.tasks import list_tasks, update_task_status, task_generator
from backend.app.api.v1.events import list_operational_events, create_manual_event, event_generator
from backend.app.api.v1.recommendations import (
    apply_recommendation,
    submit_feedback,
    get_recommendation_stats,
    list_recommendations,
)
from backend.app.api.v1.telemetry import ingest_telemetry
from backend.app.schemas.schemas import (
    TaskUpdate,
    OperationalEventCreate,
    RecommendationFeedback,
    TelemetryCreate,
)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
TASK_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
REC_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ZONE_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _empty_db():
    """DB mock that returns no rows."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalars.return_value.first.return_value = None
    db.execute.return_value = result
    return db


def _error_db():
    """DB mock that raises on execute."""
    db = AsyncMock()
    db.execute.side_effect = Exception("DB exploded")
    return db


def _redis():
    return AsyncMock()


# ---------------------------------------------------------------------------
# 1. tasks.py - list_tasks 500 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_tasks_db_error_raises_500():
    db = _error_db()
    with pytest.raises(HTTPException) as exc:
        await list_tasks(db)
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# 2. tasks.py - update_task_status 404 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_task_status_not_found_raises_404():
    db = _empty_db()
    task_update = TaskUpdate(status="COMPLETED")
    redis = _redis()
    with pytest.raises(HTTPException) as exc:
        await update_task_status(
            task_id=TASK_ID,
            task_update=task_update,
            db=db,
            redis_client=redis,
            _="mock-api-key",
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# 3. tasks.py - update_task_status 500 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_task_status_db_error_raises_500():
    db = _error_db()
    task_update = TaskUpdate(status="COMPLETED")
    redis = _redis()
    with pytest.raises(HTTPException) as exc:
        await update_task_status(
            task_id=TASK_ID,
            task_update=task_update,
            db=db,
            redis_client=redis,
            _="mock-api-key",
        )
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# 4. events.py - list_operational_events 500 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_events_db_error_raises_500():
    db = _error_db()
    with pytest.raises(HTTPException) as exc:
        await list_operational_events(db=db)
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# 5. events.py - create_manual_event 500 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_manual_event_db_error_raises_500():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit.side_effect = Exception("commit failed")
    redis = _redis()
    event_in = OperationalEventCreate(
        zone_id=ZONE_ID,
        source="CAMERA",
        event_type="CROWD_DENSITY_HIGH",
        payload={"density": 0.97},
    )
    with pytest.raises(HTTPException) as exc:
        await create_manual_event(
            event_in=event_in,
            db=db,
            redis_client=redis,
            _="mock-api-key",
        )
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# 6. recommendations.py - apply 404 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_apply_recommendation_not_found_raises_404():
    db = _empty_db()
    redis = _redis()
    with pytest.raises(HTTPException) as exc:
        await apply_recommendation(
            recommendation_id=REC_ID,
            db=db,
            redis_client=redis,
            _="mock-api-key",
            idempotency_key=None,
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# 7. recommendations.py - apply POLICY_VIOLATION returns 400
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_apply_recommendation_policy_violation_returns_400():
    rec_mock = MagicMock()
    rec_mock.validation_status = "POLICY_VIOLATION"
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = rec_mock
    db.execute.return_value = result
    redis = _redis()
    with pytest.raises(HTTPException) as exc:
        await apply_recommendation(
            recommendation_id=REC_ID,
            db=db,
            redis_client=redis,
            _="mock-api-key",
            idempotency_key=None,
        )
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# 8. recommendations.py - apply already_approved short-circuits to 200
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_apply_recommendation_already_approved():
    rec_mock = MagicMock()
    rec_mock.validation_status = "APPROVED"
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = rec_mock
    db.execute.return_value = result
    redis = _redis()
    response = await apply_recommendation(
        recommendation_id=REC_ID,
        db=db,
        redis_client=redis,
        _="mock-api-key",
        idempotency_key=None,
    )
    assert response["status"] == "already_applied"


# ---------------------------------------------------------------------------
# 9. recommendations.py - submit_feedback 404 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_submit_feedback_not_found_raises_404():
    db = _empty_db()
    feedback = RecommendationFeedback(
        accepted=True,
        applied=True,
        feedback_rating=4,
        feedback_comments="Good call",
    )
    with pytest.raises(HTTPException) as exc:
        await submit_feedback(
            recommendation_id=REC_ID,
            feedback=feedback,
            db=db,
            _="mock-api-key",
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# 10. recommendations.py - submit_feedback 500 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_submit_feedback_db_error_raises_500():
    db = _error_db()
    feedback = RecommendationFeedback(
        accepted=False,
        applied=False,
        feedback_rating=2,
        feedback_comments="Failed",
    )
    with pytest.raises(HTTPException) as exc:
        await submit_feedback(
            recommendation_id=REC_ID,
            feedback=feedback,
            db=db,
            _="mock-api-key",
        )
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# 11. recommendations.py - get_recommendation_stats 500 branch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_recommendation_stats_db_error_raises_500():
    db = _error_db()
    with pytest.raises(HTTPException) as exc:
        await get_recommendation_stats(db=db)
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# 12. telemetry router - 404 when zone not found
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ingest_telemetry_zone_not_found_raises_404():
    telemetry = TelemetryCreate(zone_id=ZONE_ID, sensor_type="turnstile", count=10)
    db = AsyncMock()
    redis = AsyncMock()
    with patch(
        "backend.app.api.v1.telemetry.process_telemetry_input",
        new=AsyncMock(return_value={"status": "error", "message": "Zone not found"})
    ):
        with pytest.raises(HTTPException) as exc:
            await ingest_telemetry(telemetry=telemetry, db=db, redis_client=redis, _="mock-api-key")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# 13. telemetry router - 500 on unexpected exception
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ingest_telemetry_unexpected_error_raises_500():
    telemetry = TelemetryCreate(zone_id=ZONE_ID, sensor_type="camera", count=0)
    db = AsyncMock()
    redis = AsyncMock()
    with patch(
        "backend.app.api.v1.telemetry.process_telemetry_input",
        new=AsyncMock(side_effect=RuntimeError("unexpected"))
    ):
        with pytest.raises(HTTPException) as exc:
            await ingest_telemetry(telemetry=telemetry, db=db, redis_client=redis, _="mock-api-key")
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# 14. task_generator - local fallback (USE_REDIS=False path)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_task_generator_local_fallback_yields_connected():
    """Exercises the USE_REDIS=False branch of the SSE task generator."""
    redis = AsyncMock()
    with patch("backend.app.core.database.USE_REDIS", False):
        gen = task_generator(redis)
        first_event = await gen.__anext__()
    assert "Connected" in first_event
    await gen.aclose()


# ---------------------------------------------------------------------------
# 15. task_generator - Redis subscribe raises, falls back to local queue
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_task_generator_redis_fail_falls_back_to_local():
    """Exercises the Redis-subscribe-exception fallback branch."""
    redis = AsyncMock()
    pubsub_mock = AsyncMock()
    pubsub_mock.subscribe.side_effect = Exception("Redis down")
    redis.pubsub.return_value = pubsub_mock
    with patch("backend.app.core.database.USE_REDIS", True):
        gen = task_generator(redis)
        first_event = await gen.__anext__()
    assert "Fallback" in first_event or "Connected" in first_event
    await gen.aclose()


# ---------------------------------------------------------------------------
# 16. event_generator - local fallback (USE_REDIS=False path)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_event_generator_local_fallback_yields_connected():
    """Exercises the USE_REDIS=False branch of the SSE events generator."""
    redis = AsyncMock()
    with patch("backend.app.core.database.USE_REDIS", False):
        gen = event_generator(redis)
        first_event = await gen.__anext__()
    assert "Connected" in first_event
    await gen.aclose()


# ---------------------------------------------------------------------------
# 17. event_generator - Redis subscribe raises, falls back to local queue
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_event_generator_redis_fail_falls_back_to_local():
    """Exercises the Redis-subscribe-exception fallback branch in events."""
    redis = AsyncMock()
    pubsub_mock = AsyncMock()
    pubsub_mock.subscribe.side_effect = Exception("Redis down")
    redis.pubsub.return_value = pubsub_mock
    with patch("backend.app.core.database.USE_REDIS", True):
        gen = event_generator(redis)
        first_event = await gen.__anext__()
    assert "Fallback" in first_event or "Connected" in first_event
    await gen.aclose()


# ---------------------------------------------------------------------------
# 18. list_tasks - role filter branch (line 111)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_tasks_with_role_filter():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    tasks = await list_tasks(db, role="security")
    assert tasks == []


# ---------------------------------------------------------------------------
# 19. list_tasks - status filter branch (line 113)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_tasks_with_status_filter():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    tasks = await list_tasks(db, task_status="PENDING")
    assert tasks == []


# ---------------------------------------------------------------------------
# 20. list_operational_events - event_type filter branch (line 150)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_events_with_type_filter():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    events = await list_operational_events(db=db, event_type="SECURITY_ALERT")
    assert events == []


# ---------------------------------------------------------------------------
# 21. list_recommendations - trigger_event_id filter branch (line 38)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_recommendations_with_trigger_filter():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    recs = await list_recommendations(db=db, trigger_event_id=REC_ID)
    assert recs == []


# ---------------------------------------------------------------------------
# 22. list_recommendations - 500 branch (line 44-50)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_recommendations_db_error_raises_500():
    db = _error_db()
    with pytest.raises(HTTPException) as exc:
        await list_recommendations(db=db)
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# 23. update_task_status success - local pubsub path (USE_REDIS=False)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_task_status_success_local_pubsub():
    """Exercises the full success path of update_task_status with local bus."""
    task_mock = MagicMock()
    task_mock.id = TASK_ID
    task_mock.details = "Test task"
    task_mock.assigned_role = "volunteer"
    task_mock.status = "PENDING"
    task_mock.updated_at = MagicMock()
    task_mock.updated_at.isoformat.return_value = "2026-01-01T00:00:00"

    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = task_mock
    db.execute.return_value = result
    db.refresh = AsyncMock(return_value=None)

    task_update = TaskUpdate(status="COMPLETED")
    redis = AsyncMock()

    with patch("backend.app.api.v1.tasks.USE_REDIS", False):
        with patch("backend.app.core.database.local_pubsub_bus") as mock_bus:
            returned = await update_task_status(
                task_id=TASK_ID,
                task_update=task_update,
                db=db,
                redis_client=redis,
                _="mock-api-key",
            )
    mock_bus.publish.assert_called_once()
    assert returned == task_mock

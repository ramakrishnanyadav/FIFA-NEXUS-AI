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
from backend.app.ai.vector import retrieve_relevant_procedures, _embed_query
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


# ---------------------------------------------------------------------------
# 24. assistant - _handle_llm_query success path
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_handle_llm_query_success(monkeypatch):
    from backend.app.api.v1.assistant import _handle_llm_query
    from backend.app.core import config

    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-test")
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="Zone Gate A is nominal."))]

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("backend.app.ai.agents._get_llm_clients", return_value=[(mock_client, "gpt-4o-mini", "openai")]):
        result = await _handle_llm_query("What's the weather doing to crowd flow?")

    assert result.intent == "llm_response"
    assert "Gate A" in result.response


# ---------------------------------------------------------------------------
# 25. assistant - _handle_llm_query failover fallback path
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_handle_llm_query_all_providers_fail_falls_back(monkeypatch):
    from backend.app.api.v1.assistant import _handle_llm_query
    from backend.app.core import config

    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-test")
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = Exception("timeout")

    with patch("backend.app.ai.agents._get_llm_clients", return_value=[(mock_client, "gpt-4o-mini", "openai")]):
        result = await _handle_llm_query("anything")

    assert result.intent == "general"


# ---------------------------------------------------------------------------
# 26. assistant - _handle_llm_query when LLM is not configured
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_handle_llm_query_no_llm_configured(monkeypatch):
    from backend.app.api.v1.assistant import _handle_llm_query
    from backend.app.core import config

    # Ensure no API keys are active
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(config.settings, "FEATHERLESS_API_KEY", "")

    result = await _handle_llm_query("hello")
    assert result.intent == "general"
    assert "Nexus AI" in result.response


# ---------------------------------------------------------------------------
# 27. assistant - chat_assistant gate a status (nominal/low capacity)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_assistant_gate_a_nominal():
    from backend.app.api.v1.assistant import chat_assistant, ChatRequest

    db = AsyncMock()
    zone_mock = MagicMock()
    zone_mock.name = "Gate A"
    zone_mock.current_occupancy = 300
    zone_mock.safe_capacity = 1000

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = zone_mock
    db.execute.return_value = result_mock

    req = ChatRequest(message="Gate A status query")
    resp = await chat_assistant(req, db, "mock_api_key")
    assert resp.intent == "zone_status"
    assert "nominal" in resp.response


# ---------------------------------------------------------------------------
# 28. assistant - chat_assistant gate a status (not found in DB)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_assistant_gate_a_not_found():
    from backend.app.api.v1.assistant import chat_assistant, ChatRequest

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock

    req = ChatRequest(message="How is Gate A?")
    resp = await chat_assistant(req, db, "mock_api_key")
    assert resp.intent == "zone_status"
    assert "operating within nominal limits" in resp.response


# ---------------------------------------------------------------------------
# 29. assistant - chat_assistant navigation / entrance intent (zones exist)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_assistant_navigation_zones_exist():
    from backend.app.api.v1.assistant import chat_assistant, ChatRequest

    db = AsyncMock()
    zone_mock = MagicMock()
    zone_mock.name = "Gate B"
    zone_mock.current_occupancy = 100
    zone_mock.safe_capacity = 1000

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [zone_mock]
    db.execute.return_value = result_mock

    req = ChatRequest(message="What is the fastest entrance?")
    resp = await chat_assistant(req, db, "mock_api_key")
    assert resp.intent == "fan_navigation"
    assert "Gate B" in resp.response


# ---------------------------------------------------------------------------
# 30. assistant - chat_assistant navigation / entrance intent (no zones)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_assistant_navigation_no_zones():
    from backend.app.api.v1.assistant import chat_assistant, ChatRequest

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute.return_value = result_mock

    req = ChatRequest(message="Which route is best?")
    resp = await chat_assistant(req, db, "mock_api_key")
    assert resp.intent == "fan_navigation"
    assert "recommended" in resp.response


# ---------------------------------------------------------------------------
# 31. assistant - chat_assistant volunteer / task intent (active tasks exist)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_assistant_task_active_tasks():
    from backend.app.api.v1.assistant import chat_assistant, ChatRequest

    db = AsyncMock()
    task_mock = MagicMock()
    task_mock.details = "Clear gate block"
    task_mock.assigned_role = "security"

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [task_mock]
    db.execute.return_value = result_mock

    req = ChatRequest(message="Any active volunteer dispatches?")
    resp = await chat_assistant(req, db, "mock_api_key")
    assert resp.intent == "task_status"
    assert "Clear gate block" in resp.response


# ---------------------------------------------------------------------------
# 32. assistant - chat_assistant volunteer / task intent (no active tasks)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_assistant_task_no_active_tasks():
    from backend.app.api.v1.assistant import chat_assistant, ChatRequest

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute.return_value = result_mock

    req = ChatRequest(message="volunteer status")
    resp = await chat_assistant(req, db, "mock_api_key")
    assert resp.intent == "task_status"
    assert "completed" in resp.response


# ---------------------------------------------------------------------------
# 33. assistant - chat_assistant fallback / offline info
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_assistant_system_fallback_info():
    from backend.app.api.v1.assistant import chat_assistant, ChatRequest

    db = AsyncMock()
    req = ChatRequest(message="tell me about offline fallback mode")
    resp = await chat_assistant(req, db, "mock_api_key")
    assert resp.intent == "system_info"
    assert "SQLite" in resp.response


# ---------------------------------------------------------------------------
# 34. assistant - chat_assistant routing query via LLM client post
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_assistant_llm_post_route(monkeypatch):
    from backend.app.api.v1.assistant import chat_assistant, ChatRequest
    from backend.app.core import config

    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-test")
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Mocked LLM reply."))]

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    db = AsyncMock()
    req = ChatRequest(message="What is the forecast weather?")

    with patch("backend.app.ai.agents._get_llm_clients", return_value=[(mock_client, "gpt-4o-mini", "openai")]):
        resp = await chat_assistant(req, db, "mock_api_key")

    assert resp.intent == "llm_response"
    assert "Mocked LLM" in resp.response


# ===========================================================================
# VECTOR FALLBACK TESTS — vector.py (100% target coverage)
# ===========================================================================
# E402 hoisted to top


# ---------------------------------------------------------------------------
# 35. vector - Qdrant unavailable -> local fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retrieve_procedures_qdrant_unavailable():
    with patch("backend.app.ai.vector.get_qdrant_client", side_effect=Exception("Qdrant offline")):
        res = await retrieve_relevant_procedures("CROWD", uuid.uuid4(), "test query")
    assert len(res) > 0
    assert "SOP-CROWD" in res[0]


# ---------------------------------------------------------------------------
# 36. vector - Qdrant available -> OpenAI semantic success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retrieve_procedures_qdrant_semantic_success(monkeypatch):
    from backend.app.core import config

    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-test-key")

    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.name = "stadium_procedures"
    mock_client.get_collections.return_value.collections = [mock_collection]

    mock_search = MagicMock()
    mock_search.payload = {"text": "SOP-SEMANTIC: Semantic Match text"}
    mock_client.search.return_value = [mock_search]

    with patch("backend.app.ai.vector.get_qdrant_client", return_value=mock_client):
        with patch("backend.app.ai.vector._embed_query", return_value=[0.1, 0.2, 0.3]):
            res = await retrieve_relevant_procedures("CROWD", uuid.uuid4(), "test query")

    assert len(res) == 1
    assert "SOP-SEMANTIC" in res[0]


# ---------------------------------------------------------------------------
# 37. vector - Qdrant available -> OpenAI missing -> keyword scroll
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retrieve_procedures_qdrant_scroll_fallback(monkeypatch):
    from backend.app.core import config

    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "")

    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.name = "stadium_procedures"
    mock_client.get_collections.return_value.collections = [mock_collection]

    mock_point = MagicMock()
    mock_point.payload = {"text": "SOP-SCROLL: Scroll Match text"}
    mock_client.scroll.return_value = ([mock_point], None)

    with patch("backend.app.ai.vector.get_qdrant_client", return_value=mock_client):
        res = await retrieve_relevant_procedures("CROWD", uuid.uuid4(), "test query")

    assert len(res) == 1
    assert "SOP-SCROLL" in res[0]


# ---------------------------------------------------------------------------
# 38. vector - Embedding exception -> fallback scroll succeeds
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retrieve_procedures_embedding_exception_fallback(monkeypatch):
    from backend.app.core import config

    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-test-key")

    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.name = "stadium_procedures"
    mock_client.get_collections.return_value.collections = [mock_collection]

    mock_point = MagicMock()
    mock_point.payload = {"text": "SOP-SCROLL-FALLBACK: Scroll Match text"}
    mock_client.scroll.return_value = ([mock_point], None)

    with patch("backend.app.ai.vector.get_qdrant_client", return_value=mock_client):
        with patch("backend.app.ai.vector._embed_query", side_effect=Exception("API error")):
            res = await retrieve_relevant_procedures("CROWD", uuid.uuid4(), "test query")

    assert len(res) == 1
    assert "SOP-SCROLL-FALLBACK" in res[0]


# ---------------------------------------------------------------------------
# 39. vector - _embed_query success path
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_embed_query_success(monkeypatch):
    from backend.app.core import config

    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-test-key")

    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.15, 0.25, 0.35])]

    mock_client = AsyncMock()
    mock_client.embeddings.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        res = await _embed_query("hello")

    assert res == [0.15, 0.25, 0.35]

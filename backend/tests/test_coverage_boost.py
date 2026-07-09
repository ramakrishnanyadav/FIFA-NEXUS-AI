import pytest
import uuid
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.api.v1.events import _stream_local, _stream_redis
from backend.app.api.v1.tasks import _stream_local_tasks, _stream_redis_tasks
from backend.app.api.v1.recommendations import _get_idempotency_cache, _set_idempotency_cache, _create_and_dispatch_tasks
from backend.app.ai.vector import _embed_query, retrieve_relevant_procedures
from backend.app.ai.agents import _get_llm_clients, run_reasoning_agent
from backend.app.core.config import settings

# ---------------------------------------------------------------------------
# 1. EVENTS STREAM HELPERS
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stream_local_generator():
    queue = asyncio.Queue()
    await queue.put("test_event_data")
    generator = _stream_local(queue)
    
    # Read first item
    item = await anext(generator)
    assert "test_event_data" in item
    
    # Test Timeout path
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        item_ping = await anext(generator)
        assert ": ping" in item_ping


@pytest.mark.asyncio
async def test_stream_redis_generator():
    pubsub_mock = AsyncMock()
    pubsub_mock.get_message.return_value = {"data": "redis_event_data"}
    generator = _stream_redis(pubsub_mock)
    
    item = await anext(generator)
    assert "redis_event_data" in item

    # Test Timeout path
    pubsub_mock.get_message.return_value = None
    item_ping = await anext(generator)
    assert ": ping" in item_ping


# ---------------------------------------------------------------------------
# 2. TASLES STREAM HELPERS
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stream_local_tasks_generator():
    queue = asyncio.Queue()
    await queue.put("test_task_data")
    generator = _stream_local_tasks(queue)
    
    item = await anext(generator)
    assert "test_task_data" in item

    # Test Timeout path
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        item_ping = await anext(generator)
        assert ": ping" in item_ping


@pytest.mark.asyncio
async def test_stream_redis_tasks_generator():
    pubsub_mock = AsyncMock()
    pubsub_mock.get_message.return_value = {"data": "redis_task_data"}
    generator = _stream_redis_tasks(pubsub_mock)
    
    item = await anext(generator)
    assert "redis_task_data" in item

    # Test Timeout path
    pubsub_mock.get_message.return_value = None
    item_ping = await anext(generator)
    assert ": ping" in item_ping


# ---------------------------------------------------------------------------
# 3. RECOMMENDATIONS IDEMPOTENCY CACHE & DISPATCH HELPERS
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_idempotency_cache_read_write():
    redis_mock = AsyncMock()
    key = uuid.uuid4()
    
    # Mock settings.USE_REDIS
    with patch("backend.app.api.v1.recommendations.USE_REDIS", True):
        # Set cache
        await _set_idempotency_cache(redis_mock, key, {"status": "success"})
        redis_mock.setex.assert_called_once()
        
        # Get cache (hit)
        redis_mock.get.return_value = '{"status": "success"}'
        hit = await _get_idempotency_cache(redis_mock, key)
        assert hit == {"status": "success"}

        # Get cache (miss)
        redis_mock.get.return_value = None
        miss = await _get_idempotency_cache(redis_mock, key)
        assert miss is None

        # Cache failure path
        redis_mock.get.side_effect = Exception("Redis connection error")
        error_result = await _get_idempotency_cache(redis_mock, key)
        assert error_result is None


# ---------------------------------------------------------------------------
# 4. VECTOR RAG RETRIEVAL & EMBEDDING
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_vector_embed_query():
    openai_client_mock = MagicMock()
    embedding_mock = MagicMock()
    embedding_mock.embedding = [0.1, 0.2, 0.3]
    openai_client_mock.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[embedding_mock])
    )
    
    with patch("openai.AsyncOpenAI", return_value=openai_client_mock), \
         patch.object(settings, "OPENAI_API_KEY", "mock-key"):
        emb = await _embed_query("test query")
        assert emb == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_vector_retrieve_fallback_paths():
    stadium_id = uuid.uuid4()
    # Test path: Qdrant client throws an exception, forcing fallback SOPs
    with patch("backend.app.ai.vector.get_qdrant_client", side_effect=Exception("Qdrant offline")):
        sops = await retrieve_relevant_procedures("CROWD", stadium_id, "test query")
        assert len(sops) > 0
        assert "SOP-CROWD-01" in sops[0]


# ---------------------------------------------------------------------------
# 5. AI AGENTS PROVIDERS FAILOVER & HEURISTIC FALLBACK
# ---------------------------------------------------------------------------
def test_llm_clients_priority_order():
    # OpenAI key only
    with patch.object(settings, "OPENAI_API_KEY", "openai-key"), \
         patch.object(settings, "GROQ_API_KEY", ""), \
         patch.object(settings, "FEATHERLESS_API_KEY", ""):
        clients = _get_llm_clients()
        assert len(clients) == 1
        assert clients[0][2] == "openai"
        
    # Groq key only
    with patch.object(settings, "OPENAI_API_KEY", ""), \
         patch.object(settings, "GROQ_API_KEY", "groq-key"), \
         patch.object(settings, "FEATHERLESS_API_KEY", ""):
        clients = _get_llm_clients()
        assert len(clients) == 1
        assert clients[0][2] == "groq"


@pytest.mark.asyncio
async def test_run_reasoning_agent_failover_to_heuristic():
    context = {
        "congestion_risk_score": 0.9,
        "predicted_occupancy_30m": 900,
        "current_occupancy": 900,
        "safe_capacity": 1000,
        "zone_name": "Gate A"
    }
    # With no API keys, agents.py must fall back to the heuristic generator
    with patch.object(settings, "OPENAI_API_KEY", ""), \
         patch.object(settings, "GROQ_API_KEY", ""), \
         patch.object(settings, "FEATHERLESS_API_KEY", ""):
        output = await run_reasoning_agent(context, "VOLUNTEER")
        assert output["model_version"] == "heuristic-fallback:v2.1"
        assert len(output["candidate_actions"]) > 0
        assert output["confidence"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# 6. ROUTER EXCEPTION HANDLERS & CORNER CASES (COVERAGE BOOSTS)
# ---------------------------------------------------------------------------
from fastapi import HTTPException
from backend.app.api.v1.recommendations import list_recommendations, get_recommendation_stats
from backend.app.api.v1.tasks import list_tasks, update_task_status
from backend.app.api.v1.events import list_operational_events, create_manual_event
from backend.app.schemas.schemas import TaskUpdate, OperationalEventCreate

@pytest.mark.asyncio
async def test_list_recommendations_exception():
    db_mock = AsyncMock()
    db_mock.execute.side_effect = Exception("DB error")
    with pytest.raises(HTTPException) as exc:
        await list_recommendations(db_mock)
    assert exc.value.status_code == 500

@pytest.mark.asyncio
async def test_get_recommendation_stats_exception():
    db_mock = AsyncMock()
    db_mock.execute.side_effect = Exception("DB error")
    with pytest.raises(HTTPException) as exc:
        await get_recommendation_stats(db_mock)
    assert exc.value.status_code == 500

@pytest.mark.asyncio
async def test_list_tasks_exception():
    db_mock = AsyncMock()
    db_mock.execute.side_effect = Exception("DB error")
    with pytest.raises(HTTPException) as exc:
        await list_tasks(db_mock)
    assert exc.value.status_code == 500

@pytest.mark.asyncio
async def test_list_operational_events_exception():
    db_mock = AsyncMock()
    db_mock.execute.side_effect = Exception("DB error")
    with pytest.raises(HTTPException) as exc:
        await list_operational_events(db_mock)
    assert exc.value.status_code == 500

@pytest.mark.asyncio
async def test_create_manual_event_exception():
    db_mock = AsyncMock()
    redis_mock = AsyncMock()
    db_mock.commit.side_effect = Exception("DB Commit Failed")
    event_in = OperationalEventCreate(
        zone_id=uuid.uuid4(),
        source="sensor:camera",
        event_type="CROWD_DENSITY_HIGH",
        payload={}
    )
    with pytest.raises(HTTPException) as exc:
        await create_manual_event(event_in, db_mock, redis_mock, "mock_api_key")
    assert exc.value.status_code == 500
    assert db_mock.rollback.called

@pytest.mark.asyncio
async def test_update_task_status_not_found():
    db_mock = AsyncMock()
    redis_mock = AsyncMock()
    # Mock task query to return None (task not found)
    query_res = MagicMock()
    query_res.scalars().first.return_value = None
    db_mock.execute.return_value = query_res
    
    task_id = uuid.uuid4()
    task_update = TaskUpdate(status="COMPLETED")
    with pytest.raises(HTTPException) as exc:
        await update_task_status(task_id, task_update, db_mock, redis_mock, "mock_api_key")
    assert exc.value.status_code == 404

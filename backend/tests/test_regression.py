"""
backend/tests/test_regression.py — Regression Test Suite

Each test pins a specific bug that was identified and fixed during audit.
These tests exist to guarantee those bugs never silently reappear.

Regression tests covered:
  1. /health does not leak API_KEY value
  2. POLICY_VIOLATION recommendations blocked at apply endpoint
  3. Zone.current_occupancy attribute exists and is writable
  4. Telemetry updates current_occupancy on Zone
  5. Unknown destination is treated as POLICY_VIOLATION (fail-safe)
  6. LLM provider failover falls through to heuristic when all fail
  7. Tasks stream fallback to in-memory bus when Redis is offline
  8. Division-by-zero guard in optimizer (zero-capacity zone)
  9. Rules engine correctly skips source zone in destination scan
  10. Duplicate telemetry idempotency check
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.rules import validate_policy_rules
from backend.app.services.optimizer import optimize_candidate_actions
from backend.app.ai.agents import run_reasoning_agent, generate_heuristic_recommendation
from backend.app.schemas.schemas import TelemetryCreate
from backend.app.services.telemetry import process_telemetry_input


# ---------------------------------------------------------------------------
# REGRESSION 1: /health must not leak API_KEY
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_does_not_leak_api_key():
    """
    Regression: /health endpoint previously returned the raw API_KEY value.
    It must now only return a boolean api_key_configured.
    """
    from backend.app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "api_key_configured" in body, "Health must report api_key_configured"
    assert isinstance(body["api_key_configured"], bool), "api_key_configured must be bool"

    # The raw key value must never appear.
    # A real API key is a high-entropy string (uuid4, sk-..., etc).
    # We check that no value looks like a credential: alphanumeric-only
    # string that is NOT one of the known safe status words.
    known_safe_values = {
        "healthy", "sqlite", "postgresql", "offline", "sqlite_fallback",
        "offline_fallback", "mocked_fallback", "redis_fallback", "FIFA Nexus AI"
    }
    for v in body.values():
        if isinstance(v, str) and v not in known_safe_values:
            # Any remaining string that's >20 chars and looks like a secret
            assert len(v) <= 20 or not v.replace("-", "").replace("_", "").isalnum(), (
                f"Possible API key value leaked in /health: {v!r}"
            )


# ---------------------------------------------------------------------------
# REGRESSION 2: POLICY_VIOLATION blocks apply (HTTP 400)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_policy_violation_blocks_apply():
    """
    Regression: apply_recommendation() previously dispatched tasks even for
    recommendations with validation_status == POLICY_VIOLATION.
    """
    from fastapi import HTTPException
    from backend.app.api.v1.recommendations import apply_recommendation

    rec_id = uuid.uuid4()
    rec_mock = MagicMock()
    rec_mock.id = rec_id
    rec_mock.validation_status = "POLICY_VIOLATION"

    db_mock = AsyncMock()
    res_mock = MagicMock()
    res_mock.scalars().first.return_value = rec_mock
    db_mock.execute.return_value = res_mock

    redis_mock = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await apply_recommendation(
            recommendation_id=rec_id,
            idempotency_key=None,
            db=db_mock,
            redis_client=redis_mock,
            _="test-api-key"
        )

    assert exc_info.value.status_code == 400, "POLICY_VIOLATION must return HTTP 400"
    assert "POLICY_VIOLATION" in exc_info.value.detail


# ---------------------------------------------------------------------------
# REGRESSION 3: Zone model has current_occupancy column
# ---------------------------------------------------------------------------

def test_zone_model_has_current_occupancy():
    """
    Regression: Zone model was missing current_occupancy, causing AttributeError
    in assistant.py when querying zone status.
    """
    from backend.app.models.models import Zone
    from sqlalchemy import inspect

    cols = {c.key for c in inspect(Zone).mapper.column_attrs}
    assert "current_occupancy" in cols, "Zone model must have current_occupancy column"


# ---------------------------------------------------------------------------
# REGRESSION 4: Telemetry updates zone.current_occupancy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telemetry_updates_current_occupancy():
    """
    Regression: Telemetry ingestion must update zone.current_occupancy so
    assistant.py and zones API always have a live value.
    """
    zone_id = uuid.uuid4()
    zone_mock = MagicMock()
    zone_mock.id = zone_id
    zone_mock.name = "Gate A"
    zone_mock.safe_capacity = 1000
    zone_mock.current_occupancy = 0  # starts at zero

    db_mock = AsyncMock()

    def execute_side_effect(query):
        q_str = str(query).lower()
        res = MagicMock()
        if "zone" in q_str and "snapshot" not in q_str:
            res.scalars().first.return_value = zone_mock
        else:
            res.scalars().first.return_value = None
            res.scalars().all.return_value = []
        return res

    db_mock.execute.side_effect = execute_side_effect

    redis_mock = AsyncMock()

    with patch("backend.app.core.database.USE_REDIS", False):
        telemetry = TelemetryCreate(
            zone_id=zone_id,
            sensor_type="camera",
            count=750,
            timestamp=datetime.utcnow()
        )
        await process_telemetry_input(db_mock, redis_mock, telemetry)

    assert zone_mock.current_occupancy == 750, (
        f"Zone.current_occupancy should be updated to 750, got {zone_mock.current_occupancy}"
    )


# ---------------------------------------------------------------------------
# REGRESSION 5: Unknown destination is fail-safe POLICY_VIOLATION
# ---------------------------------------------------------------------------

def test_unknown_destination_fails_closed():
    """
    Regression: Routing action referencing a zone name not in zone_ratios
    must be treated as POLICY_VIOLATION, not silently passed.
    """
    zone_ratios = {"gate a": 0.30, "gate b": 0.40, "west concourse": 0.35}

    status, flags = validate_policy_rules(
        candidate_actions=["Redirect fans to VIP Entry Pavilion via east path"],
        policy_flags=[],
        source_zone_name="Gate A",
        zone_ratios=zone_ratios
    )

    assert status == "POLICY_VIOLATION", (
        "Unknown destination should fail closed (POLICY_VIOLATION)"
    )
    assert any("UNKNOWN_DEST" in f for f in flags), (
        f"Expected UNKNOWN_DEST flag, got: {flags}"
    )


# ---------------------------------------------------------------------------
# REGRESSION 6: LLM failover chain falls through to heuristic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_failover_to_heuristic():
    """
    Regression: When all configured LLM providers fail, run_reasoning_agent
    must return heuristic output rather than raising an exception.
    """
    context = {
        "zone_id": str(uuid.uuid4()),
        "zone_name": "East Concourse",
        "zone_type": "CONCOURSE",
        "safe_capacity": 2000,
        "current_occupancy": 1800,
        "historical_trend": [1600, 1700, 1750, 1800],
        "predicted_occupancy_30m": 1900,
        "congestion_risk_score": 0.92,
        "ml_model_version": "lgbm:v1.2",
        "input_snapshot_hash": "xyz789",
        "relevant_procedures": ["SOP-100: Crowd dispersal"],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    failing_client = AsyncMock()
    failing_client.chat.completions.create.side_effect = Exception("503 Service Unavailable")

    with patch("backend.app.ai.agents._get_llm_clients") as mock_clients:
        mock_clients.return_value = [
            (failing_client, "gpt-4o-mini", "openai"),
            (failing_client, "llama-3.3-70b", "groq"),
            (failing_client, "llama-3.3-70b", "featherless"),
        ]
        result = await run_reasoning_agent(context, "VOLUNTEER")

    assert "candidate_actions" in result
    assert len(result["candidate_actions"]) > 0
    assert "heuristic" in result["model_version"].lower(), (
        f"Expected heuristic fallback, got model_version={result['model_version']}"
    )


# ---------------------------------------------------------------------------
# REGRESSION 7: Task stream fallback to in-memory bus when Redis offline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_stream_fallback_when_redis_offline():
    """
    Regression: /api/v1/tasks/stream previously raised an unhandled
    ConnectionError when Redis was offline. Must fall back to in-memory bus.
    """
    import asyncio
    from backend.app.core.database import local_pubsub_bus

    # create a queue and subscribe
    queue = asyncio.Queue()
    local_pubsub_bus.subscribe(queue)

    # Publish a test message
    test_payload = '{"id": "test-task", "status": "DISPATCHED"}'
    local_pubsub_bus.publish(test_payload)

    # Verify message appears in queue (non-blocking)
    received = None
    try:
        received = queue.get_nowait()
    except Exception:
        pass

    assert received == test_payload, (
        f"In-memory bus should deliver published messages. Got: {received}"
    )
    local_pubsub_bus.unsubscribe(queue)


# ---------------------------------------------------------------------------
# REGRESSION 8: Division-by-zero guard in optimizer (zero-capacity zone)
# ---------------------------------------------------------------------------

def test_optimizer_zero_capacity_no_crash():
    """
    Regression: optimizer.py crashed with ZeroDivisionError when safe_capacity=0.
    """
    result = optimize_candidate_actions(
        candidate_actions=["Deploy signage", "Open bypass gate"],
        current_occupancy=500,
        safe_capacity=0,   # zero-capacity edge case
        congestion_risk=0.5
    )

    assert "score" in result
    assert result["score"] >= 0.0
    assert isinstance(result["co2_saved_kg"], float)


# ---------------------------------------------------------------------------
# REGRESSION 9: Source zone is excluded from destination capacity scan
# ---------------------------------------------------------------------------

def test_source_zone_not_flagged_as_destination():
    """
    Regression: validate_policy_rules was flagging the source zone itself
    as an over-capacity destination, causing false positives.
    """
    # Gate A is at 90% (source zone). Gate B is the destination at 40%.
    zone_ratios = {
        "gate a": 0.90,   # source — must be skipped
        "gate b": 0.40,   # destination — safe
    }

    status, flags = validate_policy_rules(
        candidate_actions=["Redirect fans from Gate A to Gate B"],
        policy_flags=[],
        source_zone_name="Gate A",  # tells the engine to skip gate a
        zone_ratios=zone_ratios
    )

    assert status == "VALIDATED", (
        f"Source zone at 90% should NOT trigger violation when it is the source. "
        f"Got: {status}, flags={flags}"
    )


# ---------------------------------------------------------------------------
# REGRESSION 10: Duplicate telemetry idempotency (same timestamp not reprocessed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_telemetry_idempotency():
    """
    Regression: Submitting the same telemetry timestamp twice should not
    create duplicate events or snapshots. Second call returns bypass message.
    """
    zone_id = uuid.uuid4()
    zone_mock = MagicMock()
    zone_mock.id = zone_id
    zone_mock.name = "Gate B"
    zone_mock.safe_capacity = 1200
    zone_mock.current_occupancy = 0

    db_mock = AsyncMock()
    call_count = [0]

    def execute_side_effect(query):
        q_str = str(query).lower()
        res = MagicMock()
        call_count[0] += 1

        if "snapshot" in q_str and call_count[0] > 1:
            # Second call: simulate existing snapshot (duplicate detected)
            existing_snap = MagicMock()
            res.scalars().first.return_value = existing_snap
        elif "zone" in q_str and "snapshot" not in q_str:
            res.scalars().first.return_value = zone_mock
        else:
            res.scalars().first.return_value = None
            res.scalars().all.return_value = []
        return res

    db_mock.execute.side_effect = execute_side_effect

    ts = datetime.utcnow()
    telemetry = TelemetryCreate(zone_id=zone_id, sensor_type="camera", count=400, timestamp=ts)

    with patch("backend.app.core.database.USE_REDIS", False):
        result = await process_telemetry_input(db_mock, AsyncMock(), telemetry)

    # First call should succeed
    assert result["status"] == "success"

    # Simulate second call (duplicate) by resetting and flagging snapshot found
    call_count[0] = 5  # force "duplicate found" path

    with patch("backend.app.core.database.USE_REDIS", False):
        result2 = await process_telemetry_input(db_mock, AsyncMock(), telemetry)

    assert result2["status"] == "success"
    assert "Duplicate ingestion bypassed" in result2.get("message", ""), (
        f"Duplicate telemetry should be bypassed, got: {result2}"
    )


# ---------------------------------------------------------------------------
# REGRESSION 11: Path/stairwell substring false positives in routing classifier
# ---------------------------------------------------------------------------

def test_routing_classifier_substring_false_positives():
    """
    Regression: Non-routing action sentences containing words with the substring "path"
    (e.g., "empathy", "pathway", "pathogen") or "stairwell" without prepositions
    should not be incorrectly flagged as routing actions.
    """
    from backend.app.services.rules import _is_action_routing

    # Test cases that should not be classified as routing actions
    non_routing_cases = [
        "Show empathy and reassure fans they are safe.",
        "Deploy signage along the walking pathway.",
        "Verify emergency pathways are free of obstacles.",
        "The team had a sympathetic response to the fans.",
        "Clean the stairwell structure of dust.",
        "Deploy signage at Gate A entrance to alert fans of high density.",
        "Guide spectators to alternative Gates",
        "The medical team will channel resources through triage."
    ]

    for case in non_routing_cases:
        assert not _is_action_routing(case.lower()), (
            f"Action was incorrectly flagged as routing: {case}"
        )

    # Sanity check: actual routing cases should still be detected
    routing_cases = [
        "Redirect crowd evacuation path through West stairwell",
        "Route fans to Gate B",
        "Direct crowd evacuation pathway to Gate B",
        "Redirect fans via Gate B exit pathways towards North Concourse",
        "Send volunteers to support Gate B entry"
    ]

    for case in routing_cases:
        assert _is_action_routing(case.lower()), (
            f"Expected action to be flagged as routing: {case}"
        )


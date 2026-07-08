import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.schemas.schemas import TelemetryCreate
from backend.app.services.telemetry import process_telemetry_input
from backend.app.services.optimizer import optimize_candidate_actions
from backend.app.services.rules import validate_policy_rules

@pytest.mark.asyncio
async def test_telemetry_threshold_breach():
    # 1. Mock DB Session and Redis client
    db_mock = AsyncMock()
    redis_mock = AsyncMock()
    
    # Mock Stadium Zone lookup
    zone_id = uuid.uuid4()
    zone_mock = MagicMock()
    zone_mock.id = zone_id
    zone_mock.name = "Gate A"
    zone_mock.safe_capacity = 1000
    
    # Setup database query execution returns depending on target query table
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
    
    # 2. Mock downstream recommendation generator and Redis status
    with patch("backend.app.services.recommend.generate_and_validate_recommendations") as mock_rec_gen, \
         patch("backend.app.core.database.USE_REDIS", True):
        mock_rec = MagicMock()
        mock_rec.id = uuid.uuid4()
        mock_rec_gen.return_value = mock_rec

        
        # 3. Create telemetry tick exceeding 80% capacity (850/1000)
        telemetry = TelemetryCreate(
            zone_id=zone_id,
            sensor_type="camera",
            count=850,
            timestamp=datetime.utcnow()
        )
        
        # 4. Process telemetry
        result = await process_telemetry_input(db_mock, redis_mock, telemetry)
        
        # 5. Assertions
        assert result["status"] == "success"
        assert result["event_triggered"] == "CROWD_DENSITY_HIGH"
        assert result["recommendation_id"] == str(mock_rec.id)
        
        # Verify Redis state was written
        redis_mock.set.assert_called_with(f"stadium:zone:{zone_id}:occupancy", 850)
        redis_mock.zadd.assert_called_once()
        
        # Verify db.add was called to save the Event snapshot
        assert db_mock.add.call_count >= 1

def test_constraint_optimization():
    # Test action ranking and dynamic CO2 calculation
    actions = [
        "Deploy signage at Gate A",
        "Redirect fans to Gate A (High density path)",
        "Dispatch accessibility helper"
    ]
    
    # Current occupancy is high (950/1000)
    result = optimize_candidate_actions(
        candidate_actions=actions,
        current_occupancy=950,
        safe_capacity=1000,
        congestion_risk=0.9
    )
    
    # Optimizer should not filter out actions anymore (handled by rules.py)
    assert len(result["actions"]) == 3
    assert result["score"] <= 0.5  # Low score due to high density hazard
    assert result["co2_saved_kg"] > 0.0  # Dynamic CO2 is calculated

def test_policy_rules_engine():
    # Test static policy rule checks
    safe_actions = ["Deploy signs", "Open East Gate"]
    status, flags = validate_policy_rules(safe_actions, [])
    assert status == "VALIDATED"
    assert len(flags) == 0
    
    # Trigger security policy violation (unaccompanied volunteer dispatch)
    hazard_actions = ["Dispatch volunteers to resolve active security fight"]
    status, flags = validate_policy_rules(hazard_actions, [])
    assert status == "POLICY_VIOLATION"
    assert "RULE_SEC_01_VIOLATION" in flags


from backend.app.api.v1.assistant import chat_assistant, ChatRequest

@pytest.mark.asyncio
async def test_chat_assistant():
    # Mock DB Session
    db_mock = AsyncMock()
    
    # Mock Zone query return
    zone_mock = MagicMock()
    zone_mock.name = "Gate A"
    zone_mock.current_occupancy = 950
    zone_mock.safe_capacity = 1000
    
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = zone_mock
    db_mock.execute.return_value = result_mock
    
    # 1. Test Gate A status query (high capacity)
    req = ChatRequest(message="What is the status of Gate A?")
    resp = await chat_assistant(req, db_mock)
    assert resp.intent == "zone_status"
    assert "congested" in resp.response
    
    # 2. Test sustainability query
    req = ChatRequest(message="What is the green impact of the stadium?")
    resp = await chat_assistant(req, db_mock)
    assert resp.intent == "sustainability_info"
    assert "CO2" in resp.response

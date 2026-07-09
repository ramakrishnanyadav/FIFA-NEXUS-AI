"""
Recommendation Service.
Orchestrates context collation, AI generation, constraint optimization, and safety gate verification
for crowd management decisions.
"""
import uuid
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from backend.app.models.models import Recommendation, OperationalEvent
from backend.app.services.context import build_operational_context
from backend.app.ai.agents import run_reasoning_agent
from backend.app.services.optimizer import optimize_candidate_actions
from backend.app.services.rules import validate_policy_rules

async def generate_and_validate_recommendations(
    db: AsyncSession,
    redis_client: aioredis.Redis,
    event: OperationalEvent,
    target_role: str = "VOLUNTEER"
) -> Recommendation:
    """
    Triggers the core decision-support engine flow:
    1. Collects live RAG context (telemetry, predictions, SOPs).
    2. Runs AI Agent reasoning to draft candidate actions.
    3. Optimizes and scores candidate actions based on resource constraints.
    4. Evaluates actions against deterministic stadium safety policy rules.
    5. Saves and returns the final validated Recommendation entity.
    """
    # 1. Build operational context compiling live state + predictions + SOPs
    category = event.payload.get("category", "CROWD") if event.payload else "CROWD"
    if event.event_type == "CROWD_DENSITY_HIGH":
        category = "CROWD"

    import typing
    context = await build_operational_context(db, redis_client, typing.cast(uuid.UUID, event.zone_id), category)

    # 2. Run AI reasoning agent to generate candidate actions and measure time
    import time
    start_time = time.perf_counter()
    ai_output = await run_reasoning_agent(context, target_role)
    reasoning_time_ms = (time.perf_counter() - start_time) * 1000.0

    # 3. Score & filter candidate actions using the optimization engine
    optim_data = optimize_candidate_actions(
        candidate_actions=ai_output["candidate_actions"],
        current_occupancy=context["current_occupancy"],
        safe_capacity=context["safe_capacity"],
        congestion_risk=context["congestion_risk_score"]
    )

    # 4. Enforce strict safety policy rules
    # Build a zone_ratios dict: {zone_name_lower -> occupancy_ratio} for all zones in the stadium
    from sqlalchemy.future import select as sa_select
    from backend.app.models.models import Zone
    all_zones_res = await db.execute(sa_select(Zone).where(Zone.deleted_at.is_(None)))
    all_zones = all_zones_res.scalars().all()
    zone_ratios = {
        z.name.lower(): (z.current_occupancy / z.safe_capacity) if z.safe_capacity else 0.0
        for z in all_zones
    }
    source_zone_name = context.get("zone_name", "")
    validation_status, policy_flags = validate_policy_rules(
        candidate_actions=optim_data["actions"],
        policy_flags=optim_data["policy_flags"],
        source_zone_name=source_zone_name,
        zone_ratios=zone_ratios
    )

    # Merge co2_saved_kg into expected_impact dict for database persistence
    expected_impact = dict(ai_output["expected_impact"])
    expected_impact["co2_saved_kg"] = optim_data["co2_saved_kg"]

    # 5. Persist the Recommendation entity
    recommendation = Recommendation(
        id=uuid.uuid4(),
        trigger_event_id=event.id,
        target_role=target_role,
        candidate_actions=optim_data["actions"],
        expected_impact=expected_impact,
        validation_status=validation_status,
        policy_flags=policy_flags,
        prompt_version=ai_output["prompt_version"],
        model_version=ai_output["model_version"],
        knowledge_version=ai_output["knowledge_version"],
        confidence=ai_output["confidence"],
        reasoning_summary=ai_output["reasoning_summary"],
        reasoning_time_ms=reasoning_time_ms,
        generated_at=datetime.now(UTC)
    )

    db.add(recommendation)
    await db.commit()
    await db.refresh(recommendation)

    return recommendation

"""
Assistant API Router.
Handles natural language operator queries via the operations copilot chat interface.

Architecture:
  Known intents (gate status, navigation, tasks, system info) -- handled by fast keyword
  routing with direct DB lookups. No LLM latency for common operational queries.

  Open-ended / unrecognized queries -- routed through the LLM reasoning agent using the
  same provider priority chain as the recommendation pipeline (OpenAI -> Groq ->
  Featherless -> heuristic fallback). The heuristic fallback is the existing static
  response, so the endpoint is always available even when offline.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.models import Zone, Task
from backend.app.core.logging import logger
from sqlalchemy import select
from typing import Annotated
from backend.app.core.auth import verify_api_key

router = APIRouter()

CHAT_SYSTEM_PROMPT = (
    "You are FIFA Nexus AI -- an operational intelligence assistant for FIFA World Cup 2026 "
    "stadium management. You help stadium operations staff with crowd management, zone status, "
    "volunteer dispatches, safety protocols, and sustainability metrics. "
    "Keep answers concise (2-4 sentences), factual, and directly actionable. "
    "Do not include markdown formatting."
)

_FALLBACK_RESPONSE = (
    "I am the FIFA Nexus AI Operational Assistant. I monitor real-time crowd densities, "
    "predictive bottlenecks, volunteer task logs, and safety gate parameters. You can ask me "
    "about zone statuses (e.g. 'Gate A status'), active dispatches, local fallback settings, "
    "or sustainability metrics."
)


class ChatRequest(BaseModel):
    """Schema representing a chat prompt from the operator."""
    message: str


class ChatResponse(BaseModel):
    """Schema representing the assistant's processed response and detected operational intent."""
    response: str
    intent: str


async def _handle_gate_a_intent(db: AsyncSession) -> ChatResponse:
    """Query Gate A occupancy from the database and return a status summary."""
    q = await db.execute(select(Zone).where(Zone.name == "Gate A"))
    zone = q.scalar_one_or_none()
    if zone:
        current_pct = int((zone.current_occupancy / zone.safe_capacity) * 100) if zone.safe_capacity else 0
        if current_pct > 80:
            return ChatResponse(
                response=f"Gate A is currently congested at {zone.current_occupancy}/{zone.safe_capacity} ({current_pct}% occupancy). Recommendation v2.1 suggests redirecting incoming fans to Gate B bypass gates.",
                intent="zone_status"
            )
        return ChatResponse(
            response=f"Gate A status is nominal. Current occupancy is {zone.current_occupancy}/{zone.safe_capacity} ({current_pct}% occupancy). No active bottleneck detected.",
            intent="zone_status"
        )
    return ChatResponse(response="Gate A is currently operating within nominal limits.", intent="zone_status")


async def _handle_navigation_intent(db: AsyncSession) -> ChatResponse:
    """Query zone occupancy data to recommend the least-congested entrance."""
    q = await db.execute(select(Zone).order_by(Zone.current_occupancy.asc()))
    zones = q.scalars().all()
    if zones:
        best_zone = zones[0]
        pct = int((best_zone.current_occupancy / best_zone.safe_capacity) * 100) if best_zone.safe_capacity else 0
        return ChatResponse(
            response=f"Fan Navigation: The fastest entrance is currently {best_zone.name} (operating at {best_zone.current_occupancy}/{best_zone.safe_capacity} - {pct}% occupancy). Please route via the West Transit pathway to Gate B bypass channels for shortest queue times.",
            intent="fan_navigation"
        )
    return ChatResponse(response="All entrances are operating at nominal wait times. Gate B is recommended.", intent="fan_navigation")


async def _handle_task_intent(db: AsyncSession) -> ChatResponse:
    """Return a summary of currently active volunteer dispatch tasks."""
    q = await db.execute(select(Task).where(Task.status != "COMPLETED"))
    active_tasks = q.scalars().all()
    if active_tasks:
        t_details = [f"- {t.details} (Role: {t.assigned_role})" for t in active_tasks[:3]]
        tasks_list = "\n".join(t_details)
        return ChatResponse(
            response=f"There are currently {len(active_tasks)} active volunteer dispatches queue items:\n{tasks_list}\nInstruct ground staff to report feedback upon completion.",
            intent="task_status"
        )
    return ChatResponse(
        response="All active volunteer dispatch tasks are completed. Operational response stands at 100% capacity.",
        intent="task_status"
    )


async def _handle_llm_query(message: str) -> ChatResponse:
    """
    Routes open-ended queries through the configured LLM provider chain.

    Uses the same provider priority and failover pattern as the recommendation pipeline:
    OpenAI -> Groq -> Featherless -> heuristic (static) fallback.
    The endpoint always returns a response -- LLM failures are non-fatal.
    """
    from backend.app.ai.agents import _get_llm_clients
    from backend.app.core.config import settings

    if not settings.is_llm_configured:
        logger.info("No LLM configured -- using static fallback for chat query.")
        return ChatResponse(response=_FALLBACK_RESPONSE, intent="general")

    candidates = _get_llm_clients()
    for client, model_name, provider_label in candidates:
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": message}
                ],
                temperature=0.4,
                timeout=10.0,
                max_tokens=200,
            )
            answer = response.choices[0].message.content.strip()
            logger.info(f"Chat query answered via {provider_label} ({model_name})")
            return ChatResponse(response=answer, intent="llm_response")
        except Exception as e:
            logger.warning(f"Chat LLM call failed for {provider_label}: {e}. Trying next provider.")

    logger.error("All chat LLM providers failed -- using static fallback.")
    return ChatResponse(response=_FALLBACK_RESPONSE, intent="general")


@router.post("/chat", response_model=ChatResponse)
async def chat_assistant(
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Operations copilot query endpoint.

    Routes queries using a two-tier strategy:
    - Known intents (zone status, navigation, tasks, system info): fast keyword routing
      with direct DB lookups for accurate, real-time operational data.
    - Open-ended questions: LLM reasoning agent (OpenAI -> Groq -> Featherless -> fallback).
    """
    msg_lower = request.message.lower()

    if "gate a" in msg_lower:
        return await _handle_gate_a_intent(db)

    if "entrance" in msg_lower or "fastest" in msg_lower or "best gate" in msg_lower or "route" in msg_lower:
        return await _handle_navigation_intent(db)

    if "volunteer" in msg_lower or "task" in msg_lower or "dispatch" in msg_lower:
        return await _handle_task_intent(db)

    if "fallback" in msg_lower or "offline" in msg_lower or "sop" in msg_lower:
        return ChatResponse(
            response="In local offline mode, the system automatically redirects telemetry to SQLite and switches from Redis Pub/Sub to an in-memory Queue registry, continuing event routing without timeouts.",
            intent="system_info"
        )

    if "sustainability" in msg_lower or "carbon" in msg_lower or "green" in msg_lower:
        return ChatResponse(
            response="Stadium operations optimize transit paths and reduce bottlenecks to lower spectator idle wait times. For every minute of wait-time reduced, the system saves approximately 0.05 kg of CO2 per 100 fans, reducing the venue's collective carbon footprint.",
            intent="sustainability_info"
        )

    # Open-ended query -- route through LLM with automatic provider failover
    return await _handle_llm_query(request.message)

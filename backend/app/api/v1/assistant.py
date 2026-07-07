from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.models import Zone, Task
from sqlalchemy import select
from typing import Dict, Any

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    intent: str

@router.post("/chat", response_model=ChatResponse)
async def chat_assistant(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    msg_lower = request.message.lower()
    
    # Simple semantic intents matching zones, dispatches, fallback guidelines
    if "gate a" in msg_lower:
        # Check active status of Gate A from DB
        q = await db.execute(select(Zone).where(Zone.name == "Gate A"))
        zone = q.scalar_one_or_none()
        if zone:
            current_pct = int((zone.current_occupancy / zone.safe_capacity) * 100) if zone.safe_capacity else 0
            if current_pct > 80:
                return ChatResponse(
                    response=f"Gate A is currently congested at {zone.current_occupancy}/{zone.safe_capacity} ({current_pct}% occupancy). Recommendation v2.1 suggests redirecting incoming fans to Gate B bypass gates.",
                    intent="zone_status"
                )
            else:
                return ChatResponse(
                    response=f"Gate A status is nominal. Current occupancy is {zone.current_occupancy}/{zone.safe_capacity} ({current_pct}% occupancy). No active bottleneck detected.",
                    intent="zone_status"
                )
        return ChatResponse(response="Gate A is currently operating within nominal limits.", intent="zone_status")
        
    elif "entrance" in msg_lower or "fastest" in msg_lower or "best gate" in msg_lower or "route" in msg_lower:
        # Query database zone states to locate the lowest occupancy zone
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

    elif "volunteer" in msg_lower or "task" in msg_lower or "dispatch" in msg_lower:
        # Check active tasks
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
        
    elif "fallback" in msg_lower or "offline" in msg_lower or "sop" in msg_lower:
        return ChatResponse(
            response="In local offline mode, the system automatically redirects telemetry to SQLite and switches from Redis Pub/Sub to an in-memory Queue registry, continuing event routing without timeouts.",
            intent="system_info"
        )
        
    elif "sustainability" in msg_lower or "carbon" in msg_lower or "green" in msg_lower:
        return ChatResponse(
            response="Stadium operations optimize transit paths and reduce bottlenecks to lower spectator idle wait times. For every minute of wait-time reduced, the system saves approximately 0.05 kg of CO2 per 100 fans, reducing the venue's collective carbon footprint.",
            intent="sustainability_info"
        )
        
    # Default fallback response
    return ChatResponse(
        response="I am the FIFA Nexus AI Operational Assistant. I monitor real-time crowd densities, predictive bottlenecks, volunteer task logs, and safety gate parameters. You can ask me about zone statuses (e.g. 'Gate A status'), active dispatches, local fallback settings, or sustainability metrics.",
        intent="general"
    )

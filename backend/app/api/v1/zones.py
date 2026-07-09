from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from pydantic import BaseModel
from backend.app.core.database import get_db
from backend.app.models.models import Zone

router = APIRouter()

class ZoneResponseSchema(BaseModel):
    id: UUID
    stadium_id: UUID
    name: str
    zone_type: str
    safe_capacity: int
    current_occupancy: int

    class Config:
        from_attributes = True

from typing import Annotated

@router.get("", response_model=list[ZoneResponseSchema], responses={500: {"description": "Failed to load zones"}})
async def list_zones(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        result = await db.execute(select(Zone).where(Zone.deleted_at.is_(None)))
        zones = result.scalars().all()
        return zones
    except Exception:
        from backend.app.core.logging import logger
        logger.exception("Failed to load zones")
        raise HTTPException(status_code=500, detail="Failed to load zones. Please try again.")

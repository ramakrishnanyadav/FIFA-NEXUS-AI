"""
Telemetry API Router.
Handles high-frequency turnstile and camera sensor ingestions for real-time crowd dynamics tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from backend.app.core.database import get_db, get_redis_client
from backend.app.schemas.schemas import TelemetryCreate
from backend.app.services.telemetry import process_telemetry_input

router = APIRouter()

from backend.app.core.auth import verify_api_key

from typing import Annotated

@router.post("", status_code=status.HTTP_202_ACCEPTED, responses={404: {"description": "Zone not found"}, 500: {"description": "Internal server error"}})
async def ingest_telemetry(
    telemetry: TelemetryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis_client)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Ingests live sensor telemetry readings (turnstile passenger flows or camera occupancy counts).
    
    Validates input schemas, resolves target zones, dynamically updates occupancy counts in the
    canonical cache, persists occupancy snapshot history, triggers predictive forecast analysis, 
    and issues downstream operations alerts if safe capacity thresholds are breached.
    """
    try:
        result = await process_telemetry_input(db, redis_client, telemetry)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception:
        from backend.app.core.logging import logger
        logger.exception("Telemetry ingestion error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during telemetry ingestion. Please contact operations support."
        )

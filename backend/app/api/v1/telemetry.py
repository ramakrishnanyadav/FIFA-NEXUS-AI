from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from backend.app.core.database import get_db, get_redis_client
from backend.app.schemas.schemas import TelemetryCreate
from backend.app.services.telemetry import process_telemetry_input

router = APIRouter()

from backend.app.core.auth import verify_api_key

from typing import Annotated

@router.post("", status_code=status.HTTP_202_ACCEPTED, responses={404: {"description": "Zone not found"}})
async def ingest_telemetry(
    telemetry: TelemetryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis_client)],
    _: Annotated[str, Depends(verify_api_key)]
):
    try:
        result = await process_telemetry_input(db, redis_client, telemetry)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        from backend.app.core.logging import logger
        logger.error(f"Telemetry ingestion error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during telemetry ingestion. Please contact operations support."
        )

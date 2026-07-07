from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from backend.app.core.database import get_db, get_redis_client
from backend.app.schemas.schemas import TelemetryCreate
from backend.app.services.telemetry import process_telemetry_input

router = APIRouter()

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_telemetry(
    telemetry: TelemetryCreate,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis_client)
):
    try:
        result = await process_telemetry_input(db, redis_client, telemetry)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telemetry ingestion failed: {str(e)}"
        )

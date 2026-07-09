"""
Context Collation Service.
Aggregates live sensor telemetry, predictive occupancy forecasts, and security/SOP vector procedures
into a unified operational payload (RAG context) for AI reasoning.
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
from backend.app.models.models import Zone, ZoneOccupancySnapshot
from backend.app.services.predict import get_occupancy_prediction
from backend.app.ai.vector import retrieve_relevant_procedures

from backend.app.core.logging import logger
from datetime import UTC

async def build_operational_context(
    db: AsyncSession,
    redis_client: aioredis.Redis,
    zone_id: uuid.UUID,
    category: str
) -> dict:
    """
    Collates current occupancy, recent time-series, ML-based projections, and vector-store SOP
    documents into a structured dictionary ready for the LLM reasoning pipeline.
    """
    # 1. Fetch Zone core metadata
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalars().first()
    if not zone:
        return {"error": f"Zone {zone_id} not found"}

    # 2. Retrieve recent occupancy history from Redis cache (sliding window)
    from backend.app.core.database import USE_REDIS
    historical_counts = []
    if USE_REDIS:
        try:
            zone_stream_key = f"stadium:zone:{zone_id}:occupancy_stream"
            occupancy_ticks = await redis_client.zrange(zone_stream_key, 0, -1)
            historical_counts = [int(count) for count in occupancy_ticks]
        except Exception as e:
            logger.warning(
                f"Redis connection failed: {e}. Event-driven pipeline falling back to database snapshots.",
                extra={"correlation_id": str(zone_id)}
            )



    # Fallback to current snapshot in Postgres if Redis cache was empty
    if not historical_counts:
        snap_res = await db.execute(
            select(ZoneOccupancySnapshot)
            .where(ZoneOccupancySnapshot.zone_id == zone_id)
            .order_by(ZoneOccupancySnapshot.recorded_at.desc())
            .limit(5)
        )
        snapshots = snap_res.scalars().all()
        historical_counts = [s.occupancy for s in reversed(snapshots)]
        if not historical_counts:
            # Fallback to zero
            historical_counts = [0]

    current_occupancy = historical_counts[-1]

    # 3. Fetch occupancy prediction trends from ML service
    prediction_data = await get_occupancy_prediction(
        zone_id=zone_id,
        historical_occupancy=historical_counts,
        safe_capacity=zone.safe_capacity
    )

    # 4. Fetch Standard Operating Procedures (SOPs) from Qdrant Vector DB
    sop_query = f"High congestion procedures in {zone.name} with occupancy {current_occupancy}"
    relevant_procedures = await retrieve_relevant_procedures(
        category=category,
        stadium_id=zone.stadium_id,
        query_text=sop_query
    )

    # Compile the final operational state context object (with local hash generation)
    import hashlib
    counts_str = ",".join(map(str, historical_counts))
    input_snapshot_hash = hashlib.sha256(counts_str.encode("utf-8")).hexdigest()

    context = {
        "zone_id": str(zone_id),
        "zone_name": zone.name,
        "zone_type": zone.zone_type,
        "safe_capacity": zone.safe_capacity,
        "current_occupancy": current_occupancy,
        "historical_trend": historical_counts,
        "predicted_occupancy_30m": prediction_data["predicted_occupancy_30m"],
        "congestion_risk_score": prediction_data["risk_score"],
        "ml_model_version": prediction_data["model_version"],
        "input_snapshot_hash": input_snapshot_hash,
        "relevant_procedures": relevant_procedures,
        "timestamp": datetime_to_iso(datetime_now())
    }

    return context


def datetime_now() -> str:
    from datetime import datetime
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

def datetime_to_iso(dt) -> str:
    return dt

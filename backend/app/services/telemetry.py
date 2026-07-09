import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
from backend.app.models.models import Zone, OperationalEvent, ZoneOccupancySnapshot
from backend.app.schemas.schemas import TelemetryCreate

from backend.app.core.logging import logger
from datetime import UTC


async def _update_redis_occupancy(redis_client: aioredis.Redis, telemetry: TelemetryCreate) -> None:
    from backend.app.core.database import USE_REDIS
    if not USE_REDIS:
        return
    try:
        zone_occupancy_key = f"stadium:zone:{telemetry.zone_id}:occupancy"
        zone_stream_key = f"stadium:zone:{telemetry.zone_id}:occupancy_stream"

        # Store current count
        await redis_client.set(zone_occupancy_key, telemetry.count)

        # Store timeseries element for sliding window calculations
        timestamp_epoch = int(telemetry.timestamp.timestamp())
        await redis_client.zadd(zone_stream_key, {str(telemetry.count): timestamp_epoch})
    except Exception as e:
        logger.warning(
            f"Redis state cache write failed: {e}. Event-driven pipeline falling back to database snapshots.",
            extra={"correlation_id": str(telemetry.zone_id)}
        )


async def _handle_density_high_event(
    db: AsyncSession,
    redis_client: aioredis.Redis,
    zone,
    telemetry: TelemetryCreate
) -> dict | None:
    threshold_limit = int(zone.safe_capacity * 0.8)
    if zone.safe_capacity <= 0 or telemetry.count < threshold_limit:
        return None

    # Check cooldown to prevent duplicate active events / recommendations in the last 60 seconds
    from datetime import timedelta
    t_now = telemetry.timestamp.astimezone(UTC) if telemetry.timestamp.tzinfo else telemetry.timestamp.replace(tzinfo=UTC)
    cooldown_time = t_now - timedelta(seconds=60)

    # Optimized: single DB-level query checking timeframe
    recent_event_result = await db.execute(
        select(OperationalEvent).where(
            OperationalEvent.zone_id == telemetry.zone_id,
            OperationalEvent.event_type == "CROWD_DENSITY_HIGH",
            OperationalEvent.received_at >= cooldown_time
        ).limit(1)
    )
    has_recent = recent_event_result.scalars().first() is not None

    if has_recent:
        return {
            "status": "success",
            "zone": zone.name,
            "current_occupancy": telemetry.count,
            "message": "Telemetry registered. Event generation throttled under active incident cooldown.",
            "event_triggered": None,
            "correlation_id": None
        }

    # Create OperationalEvent
    from backend.app.core.logging import correlation_id_ctx
    ctx_corr = correlation_id_ctx.get()
    correlation_id = uuid.UUID(ctx_corr) if ctx_corr else uuid.uuid4()
    event_payload = {
        "current_occupancy": telemetry.count,
        "safe_capacity": zone.safe_capacity,
        "occupancy_ratio": round(telemetry.count / zone.safe_capacity, 2) if zone.safe_capacity else 0.0,
        "sensor_type": telemetry.sensor_type
    }

    event_created = OperationalEvent(
        id=uuid.uuid4(),
        zone_id=telemetry.zone_id,
        source=f"sensor:{telemetry.sensor_type}:{telemetry.zone_id}",
        event_type="CROWD_DENSITY_HIGH",
        payload=event_payload,
        received_at=telemetry.timestamp,
        correlation_id=correlation_id,
        trace_id=None
    )
    db.add(event_created)
    await db.commit() # Commit event to get ID reference

    # Trigger recommendation generation pipeline
    from backend.app.services.recommend import generate_and_validate_recommendations
    rec = await generate_and_validate_recommendations(db, redis_client, event_created, "VOLUNTEER")

    # Publish structured message to Redis pub/sub channel
    import json
    alert_payload = {
        "event_type": "CROWD_DENSITY_HIGH",
        "zone_name": zone.name,
        "current_occupancy": telemetry.count,
        "safe_capacity": zone.safe_capacity,
        "recommendation_id": str(rec.id)
    }
    from backend.app.core.database import local_pubsub_bus, USE_REDIS
    if USE_REDIS:
        try:
            await redis_client.publish("events:stream", json.dumps(alert_payload))
        except Exception:
            local_pubsub_bus.publish(json.dumps(alert_payload))
    else:
        local_pubsub_bus.publish(json.dumps(alert_payload))

    return {
        "status": "success",
        "zone": zone.name,
        "current_occupancy": telemetry.count,
        "event_triggered": "CROWD_DENSITY_HIGH",
        "correlation_id": str(event_created.correlation_id),
        "recommendation_id": str(rec.id)
    }


async def process_telemetry_input(
    db: AsyncSession,
    redis_client: aioredis.Redis,
    telemetry: TelemetryCreate
) -> dict:
    try:
        # 1. Fetch zone details from DB to check capacity thresholds
        result = await db.execute(select(Zone).where(Zone.id == telemetry.zone_id))
        zone = result.scalars().first()
        if not zone:
            return {"status": "error", "message": f"Zone {telemetry.zone_id} not found."}

        # Update dynamic field for live status retrieval
        zone.current_occupancy = telemetry.count

        # 1a. Idempotency Check: prevent duplicate telemetry processing at identical timestamp
        existing_snapshot_result = await db.execute(
            select(ZoneOccupancySnapshot).where(
                ZoneOccupancySnapshot.zone_id == telemetry.zone_id,
                ZoneOccupancySnapshot.recorded_at == telemetry.timestamp
            ).limit(1)
        )
        duplicate_found = existing_snapshot_result.scalars().first() is not None

        if duplicate_found:
            return {
                "status": "success",
                "zone": zone.name,
                "current_occupancy": telemetry.count,
                "message": "Telemetry registered. Duplicate ingestion bypassed.",
                "event_triggered": None,
                "correlation_id": None
            }

        # 2. Update real-time state in Redis (with Graceful Degradation)
        await _update_redis_occupancy(redis_client, telemetry)

        # 3. Create occupancy snapshot record in Postgres (low frequency - for history)
        snapshot = ZoneOccupancySnapshot(
            id=uuid.uuid4(),
            zone_id=telemetry.zone_id,
            occupancy=telemetry.count,
            recorded_at=telemetry.timestamp
        )
        db.add(snapshot)

        # 4. Threshold checking: Evaluate if crowd risk is breached
        result_dict = await _handle_density_high_event(db, redis_client, zone, telemetry)
        if result_dict is not None:
            return result_dict

        await db.commit()

        return {
            "status": "success",
            "zone": zone.name,
            "current_occupancy": telemetry.count,
            "event_triggered": None,
            "correlation_id": None
        }
    except Exception as e:
        await db.rollback()
        logger.exception("Error during telemetry processing, rolled back transaction")
        raise e

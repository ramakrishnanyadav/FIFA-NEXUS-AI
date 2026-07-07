import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
from backend.app.models.models import Zone, OperationalEvent, ZoneOccupancySnapshot
from backend.app.schemas.schemas import TelemetryCreate

from backend.app.core.logging import logger

async def process_telemetry_input(
    db: AsyncSession,
    redis_client: aioredis.Redis,
    telemetry: TelemetryCreate
) -> dict:
    # 1. Fetch zone details from DB to check capacity thresholds
    result = await db.execute(select(Zone).where(Zone.id == telemetry.zone_id))
    zone = result.scalars().first()
    if not zone:
        return {"status": "error", "message": f"Zone {telemetry.zone_id} not found."}

    # 1a. Idempotency Check: prevent duplicate telemetry processing at identical timestamp
    from datetime import timezone
    telemetry_time = telemetry.timestamp.astimezone(timezone.utc) if telemetry.timestamp.tzinfo else telemetry.timestamp.replace(tzinfo=timezone.utc)
    
    existing_snapshots = (await db.execute(
        select(ZoneOccupancySnapshot).where(ZoneOccupancySnapshot.zone_id == telemetry.zone_id)
    )).scalars().all()
    
    duplicate_found = False
    for snap in existing_snapshots:
        snap_time = snap.recorded_at.astimezone(timezone.utc) if snap.recorded_at.tzinfo else snap.recorded_at.replace(tzinfo=timezone.utc)
        if snap_time == telemetry_time:
            duplicate_found = True
            break
            
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
    from backend.app.core.database import USE_REDIS
    if USE_REDIS:
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


    
    # 3. Create occupancy snapshot record in Postgres (low frequency - for history)
    # We will log every reading for the MVP, or can filter.
    snapshot = ZoneOccupancySnapshot(
        id=uuid.uuid4(),
        zone_id=telemetry.zone_id,
        occupancy=telemetry.count,
        recorded_at=telemetry.timestamp
    )
    db.add(snapshot)
    
    # 4. Threshold checking: Evaluate if crowd risk is breached (e.g. occupancy > 80% safe capacity)
    threshold_limit = int(zone.safe_capacity * 0.8)
    event_created = None
    
    if telemetry.count >= threshold_limit:
        # Check cooldown to prevent duplicate active events / recommendations in the last 60 seconds
        from datetime import timedelta, timezone
        t_now = telemetry.timestamp.astimezone(timezone.utc) if telemetry.timestamp.tzinfo else telemetry.timestamp.replace(tzinfo=timezone.utc)
        cooldown_time = t_now - timedelta(seconds=60)
        
        recent_events = (await db.execute(
            select(OperationalEvent).where(
                OperationalEvent.zone_id == telemetry.zone_id,
                OperationalEvent.event_type == "CROWD_DENSITY_HIGH"
            )
        )).scalars().all()
        
        has_recent = False
        for e in recent_events:
            e_time = e.received_at.astimezone(timezone.utc) if e.received_at.tzinfo else e.received_at.replace(tzinfo=timezone.utc)
            if e_time >= cooldown_time:
                has_recent = True
                break
                
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
        correlation_id = uuid.uuid4()
        event_payload = {
            "current_occupancy": telemetry.count,
            "safe_capacity": zone.safe_capacity,
            "occupancy_ratio": round(telemetry.count / zone.safe_capacity, 2),
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
            trace_id=f"tr-{uuid.uuid4().hex[:8]}"
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
        
    await db.commit()
    
    return {
        "status": "success",
        "zone": zone.name,
        "current_occupancy": telemetry.count,
        "event_triggered": None,
        "correlation_id": None
    }


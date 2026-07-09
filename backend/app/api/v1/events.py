import uuid
import json
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
from backend.app.core.database import get_db, get_redis_client, local_pubsub_bus
from backend.app.models.models import OperationalEvent
from backend.app.schemas.schemas import OperationalEventCreate, OperationalEventResponse
import asyncio
from typing import Annotated
from backend.app.core.auth import verify_api_key

router = APIRouter()

EVENTS_STREAM_CHANNEL = "events:stream"

async def _stream_local(local_queue: asyncio.Queue):
    while True:
        try:
            message_data = await asyncio.wait_for(local_queue.get(), timeout=1.0)
            yield f"event: operational_event\ndata: {message_data}\n\n"
            local_queue.task_done()
        except TimeoutError:
            yield ": ping\n\n"

async def _stream_redis(pubsub):
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message:
            yield f"event: operational_event\ndata: {message['data']}\n\n"
        else:
            yield ": ping\n\n"

# SSE Generator reading from Redis Pub/Sub (with local memory fallback)
async def event_generator(redis_client: aioredis.Redis):
    from backend.app.core.database import USE_REDIS
    pubsub = None
    local_queue = None
    if USE_REDIS:
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(EVENTS_STREAM_CHANNEL)
            yield "event: system\ndata: Connected to operational events stream\n\n"
        except Exception:
            local_queue = asyncio.Queue()
            local_pubsub_bus.subscribe(local_queue)
            yield "event: system\ndata: Connected to local operational events stream (Redis Offline Fallback)\n\n"
    else:
        local_queue = asyncio.Queue()
        local_pubsub_bus.subscribe(local_queue)
        yield "event: system\ndata: Connected to local operational events stream (Redis Offline Fallback)\n\n"

    try:
        if local_queue is not None:
            async for event in _stream_local(local_queue):
                yield event
        else:
            async for event in _stream_redis(pubsub):
                yield event
    except Exception as e:
        yield f"event: error\ndata: {str(e)}\n\n"
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(EVENTS_STREAM_CHANNEL)
                await pubsub.close()
            except Exception:
                pass  # nosec B110
        if local_queue is not None:
            local_pubsub_bus.unsubscribe(local_queue)

@router.get("/stream")
async def stream_operational_events(
    redis_client: Annotated[aioredis.Redis, Depends(get_redis_client)]
):
    return StreamingResponse(
        event_generator(redis_client),
        media_type="text/event-stream"
    )

@router.post("", response_model=OperationalEventResponse, status_code=status.HTTP_201_CREATED, responses={500: {"description": "Internal server error"}})
async def create_manual_event(
    event_in: OperationalEventCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis_client)],
    _: Annotated[str, Depends(verify_api_key)]
):
    try:
        from backend.app.core.logging import correlation_id_ctx
        ctx_corr = correlation_id_ctx.get()
        correlation_id = event_in.correlation_id or (uuid.UUID(ctx_corr) if ctx_corr else uuid.uuid4())
        trace_id = event_in.trace_id or None

        event = OperationalEvent(
            id=uuid.uuid4(),
            zone_id=event_in.zone_id,
            source=event_in.source,
            event_type=event_in.event_type,
            payload=event_in.payload,
            received_at=datetime.now(UTC),
            correlation_id=correlation_id,
            trace_id=trace_id
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        # Publish event notification via Redis Pub/Sub for SSE (with local fallback)
        alert_msg = f"{event.event_type} reported by {event.source}: {json.dumps(event.payload)}"
        try:
            await redis_client.publish(EVENTS_STREAM_CHANNEL, alert_msg)
        except Exception as e:
            from backend.app.core.logging import logger
            logger.warning(f"Redis event publish failed: {e}. Falling back to local in-memory event bus.")
            local_pubsub_bus.publish(alert_msg)

        return event
    except Exception as e:
        await db.rollback()
        from backend.app.core.logging import logger
        logger.error(f"Failed to record operational event: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record operational event. Please try again."
        )

@router.get("", response_model=list[OperationalEventResponse], responses={500: {"description": "Internal server error"}})
async def list_operational_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    event_type: str | None = None
):
    try:
        query = select(OperationalEvent)
        if event_type:
            query = query.where(OperationalEvent.event_type == event_type)
        query = query.order_by(OperationalEvent.received_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        events = result.scalars().all()
        return events
    except Exception as e:
        from backend.app.core.logging import logger
        logger.error(f"Failed to fetch events: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch events. Please try again."
        )

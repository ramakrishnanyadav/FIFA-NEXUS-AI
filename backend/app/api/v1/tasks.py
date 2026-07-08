
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
import json
from datetime import datetime, timezone
from backend.app.core.database import get_db, get_redis_client, USE_REDIS
from backend.app.models.models import Task
from backend.app.schemas.schemas import TaskResponse, TaskUpdate

router = APIRouter()

# SSE Generator reading from Redis Pub/Sub for Tasks
async def task_generator(redis_client: aioredis.Redis):
    from backend.app.core.database import USE_REDIS, local_pubsub_bus
    import asyncio
    pubsub = None
    local_queue = None

    if USE_REDIS:
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("tasks:stream")
            yield "event: system\ndata: Connected to tasks channel\n\n"
        except Exception:
            local_queue = asyncio.Queue()
            local_pubsub_bus.subscribe(local_queue)
            yield "event: system\ndata: Connected to local tasks stream (Redis Offline Fallback)\n\n"
    else:
        local_queue = asyncio.Queue()
        local_pubsub_bus.subscribe(local_queue)
        yield "event: system\ndata: Connected to local tasks stream (Redis Offline Fallback)\n\n"

    try:
        while True:
            if local_queue is not None:
                try:
                    message_data = await asyncio.wait_for(local_queue.get(), timeout=1.0)
                    yield f"event: task_dispatched\ndata: {message_data}\n\n"
                    local_queue.task_done()
                except TimeoutError:
                    yield ": ping\n\n"
            else:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    yield f"event: task_dispatched\ndata: {message['data']}\n\n"
                else:
                    yield ": ping\n\n"
    except Exception as e:
        yield f"event: error\ndata: {str(e)}\n\n"
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe("tasks:stream")
                await pubsub.close()
            except Exception:
                pass  # nosec B110
        if local_queue is not None:
            local_pubsub_bus.unsubscribe(local_queue)

@router.get("/stream")
async def stream_tasks(
    redis_client: aioredis.Redis = Depends(get_redis_client)
):
    return StreamingResponse(
        task_generator(redis_client),
        media_type="text/event-stream"
    )

@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    role: str | None = None,
    task_status: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Task)
        if role:
            query = query.where(Task.assigned_role == role)
        if task_status:
            query = query.where(Task.status == task_status)
        query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        tasks = result.scalars().all()
        return tasks
    except Exception as e:
        from backend.app.core.logging import logger
        logger.error(f"Failed to fetch tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch tasks. Please try again."
        )

from backend.app.core.auth import verify_api_key

@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_status(
    task_id: uuid.UUID,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    _: str = Depends(verify_api_key)
):
    try:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalars().first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        task.status = task_update.status
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)

        # Publish update on redis channel for task monitoring
        update_alert = {
            "id": str(task.id),
            "details": task.details,
            "role": task.assigned_role,
            "status": task.status,
            "updated_at": task.updated_at.isoformat()
        }
        from backend.app.core.database import local_pubsub_bus
        if USE_REDIS:
            try:
                await redis_client.publish("tasks:stream", json.dumps(update_alert))
            except Exception as e:
                from backend.app.core.logging import logger
                logger.warning(f"Failed to publish task stream update to Redis: {e}")
                local_pubsub_bus.publish(json.dumps(update_alert))
        else:
            local_pubsub_bus.publish(json.dumps(update_alert))



        return task
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        from backend.app.core.logging import logger
        logger.error(f"Failed to update task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task. Please try again."
        )

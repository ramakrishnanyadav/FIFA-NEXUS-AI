from typing import Annotated
import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
import json
from datetime import datetime, UTC
from backend.app.core.database import get_db, get_redis_client, USE_REDIS
from backend.app.models.models import Task
from backend.app.schemas.schemas import TaskResponse, TaskUpdate

router = APIRouter()

TASKS_STREAM_CHANNEL = "tasks:stream"

async def _stream_local_tasks(local_queue: asyncio.Queue):
    while True:
        try:
            message_data = await asyncio.wait_for(local_queue.get(), timeout=1.0)
            yield f"event: task_dispatched\ndata: {message_data}\n\n"
            local_queue.task_done()
        except TimeoutError:
            yield ": ping\n\n"

async def _stream_redis_tasks(pubsub):
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message:
            yield f"event: task_dispatched\ndata: {message['data']}\n\n"
        else:
            yield ": ping\n\n"

# SSE Generator reading from Redis Pub/Sub for Tasks
async def task_generator(redis_client: aioredis.Redis):
    from backend.app.core.database import USE_REDIS, local_pubsub_bus
    import asyncio
    pubsub = None
    local_queue = None

    if USE_REDIS:
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(TASKS_STREAM_CHANNEL)
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
        if local_queue is not None:
            async for task_event in _stream_local_tasks(local_queue):
                yield task_event
        else:
            async for task_event in _stream_redis_tasks(pubsub):
                yield task_event
    except Exception as e:
        yield f"event: error\ndata: {str(e)}\n\n"
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(TASKS_STREAM_CHANNEL)
                await pubsub.close()
            except Exception:
                pass  # nosec B110
        if local_queue is not None:
            local_pubsub_bus.unsubscribe(local_queue)

@router.get("/stream")
async def stream_tasks(
    redis_client: Annotated[aioredis.Redis, Depends(get_redis_client)]
):
    return StreamingResponse(
        task_generator(redis_client),
        media_type="text/event-stream"
    )

@router.get("", response_model=list[TaskResponse], responses={500: {"description": "Failed to fetch tasks"}})
async def list_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    role: str | None = None,
    task_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0
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
    except Exception:
        from backend.app.core.logging import logger
        logger.exception("Failed to fetch tasks")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch tasks. Please try again."
        )

from backend.app.core.auth import verify_api_key

@router.patch("/{task_id}", response_model=TaskResponse, responses={404: {"description": "Task not found"}, 500: {"description": "Internal server error"}})
async def update_task_status(
    task_id: uuid.UUID,
    task_update: TaskUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis_client)],
    _: Annotated[str, Depends(verify_api_key)]
):
    try:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalars().first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        task.status = task_update.status
        task.updated_at = datetime.now(UTC)
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
    except Exception:
        await db.rollback()
        from backend.app.core.logging import logger
        logger.exception(f"Failed to update task {task_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task. Please try again."
        )

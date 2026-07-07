import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
import json
from datetime import datetime
from backend.app.core.database import get_db, get_redis_client, USE_REDIS
from backend.app.models.models import Task
from backend.app.schemas.schemas import TaskResponse, TaskUpdate

router = APIRouter()

# SSE Generator reading from Redis Pub/Sub for Tasks
async def task_generator(redis_client: aioredis.Redis):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("tasks:stream")
    try:
        yield "event: system\ndata: Connected to tasks channel\n\n"
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                yield f"event: task_dispatched\ndata: {message['data']}\n\n"
            else:
                yield ": ping\n\n"
    except Exception as e:
        yield f"event: error\ndata: {str(e)}\n\n"
    finally:
        await pubsub.unsubscribe("tasks:stream")
        await pubsub.close()

@router.get("/stream")
async def stream_tasks(
    redis_client: aioredis.Redis = Depends(get_redis_client)
):
    return StreamingResponse(
        task_generator(redis_client),
        media_type="text/event-stream"
    )

@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    role: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Task)
        if role:
            query = query.where(Task.assigned_role == role)
        if status:
            query = query.where(Task.status == status)
        query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        return tasks
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tasks: {str(e)}"
        )

@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_status(
    task_id: uuid.UUID,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis_client)
):
    try:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalars().first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        task.status = task_update.status
        task.updated_at = datetime.utcnow()
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
        if USE_REDIS:
            try:
                await redis_client.publish("tasks:stream", json.dumps(update_alert))
            except Exception:
                pass


        
        return task
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
import json
from backend.app.core.database import get_db, get_redis_client, local_pubsub_bus, USE_REDIS
from backend.app.models.models import Recommendation, Task, OperationalEvent
from backend.app.schemas.schemas import RecommendationResponse, RecommendationFeedback, TaskResponse

router = APIRouter()

@router.get("", response_model=List[RecommendationResponse])
async def list_recommendations(
    trigger_event_id: Optional[uuid.UUID] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Recommendation)
        if trigger_event_id:
            query = query.where(Recommendation.trigger_event_id == trigger_event_id)
        query = query.order_by(Recommendation.generated_at.desc()).limit(limit).offset(offset)
        
        result = await db.execute(query)
        recommendations = result.scalars().all()
        return recommendations
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recommendations: {str(e)}"
        )

@router.post("/{recommendation_id}/apply", status_code=status.HTTP_200_OK)
async def apply_recommendation(
    recommendation_id: uuid.UUID,
    idempotency_key: Optional[uuid.UUID] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis_client)
):
    # 1. Idempotency Check (with Redis offline fallback)
    idemp_redis_key = None
    if idempotency_key and USE_REDIS:
        idemp_redis_key = f"idempotency:apply:{idempotency_key}"
        try:
            cached_val = await redis_client.get(idemp_redis_key)
            if cached_val:
                return json.loads(cached_val)
        except Exception:
            pass


    try:
        # 2. Fetch Recommendation
        result = await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))
        rec = result.scalars().first()
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        if rec.validation_status == "APPROVED":
            return {"status": "already_applied", "recommendation_id": str(recommendation_id)}
            
        # 3. Transition State to APPROVED & DISPATCHED
        rec.validation_status = "APPROVED"
        rec.accepted = True
        rec.applied = True
        
        # 4. Generate & Dispatch Tasks based on Candidate Actions
        created_tasks = []
        for action in rec.candidate_actions:
            task_id = uuid.uuid4()
            task = Task(
                id=task_id,
                recommendation_id=rec.id,
                assigned_user_id=None,  # Available to be claimed
                assigned_role=rec.target_role if rec.target_role in ["VOLUNTEER", "SECURITY"] else "VOLUNTEER",
                details=action,
                status="DISPATCHED",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(task)
            created_tasks.append(task_id)
            
            # Publish task notifications to Redis channel for SSE (with fallback)
            task_alert = {
                "id": str(task_id),
                "details": action,
                "role": task.assigned_role,
                "status": "DISPATCHED"
            }
            if USE_REDIS:
                try:
                    await redis_client.publish("tasks:stream", json.dumps(task_alert))
                except Exception:
                    pass
            
        await db.commit()
        
        response_payload = {
            "status": "success",
            "recommendation_id": str(recommendation_id),
            "dispatched_tasks": [str(t_id) for t_id in created_tasks]
        }
        
        # Cache for Idempotency (24 hours TTL)
        if idempotency_key and idemp_redis_key and USE_REDIS:
            try:
                await redis_client.setex(
                    idemp_redis_key,
                    86400,
                    json.dumps(response_payload)
                )
            except Exception:
                pass


            
        return response_payload
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply recommendation: {str(e)}"
        )

@router.post("/{recommendation_id}/feedback", status_code=status.HTTP_200_OK)
async def submit_feedback(
    recommendation_id: uuid.UUID,
    feedback: RecommendationFeedback,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))
        rec = result.scalars().first()
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
            
        # Update feedback loop fields
        rec.accepted = feedback.accepted
        rec.applied = feedback.applied
        rec.feedback_rating = feedback.feedback_rating
        rec.feedback_comments = feedback.feedback_comments
        
        # Mocking an effectiveness score logic for the vertical slice:
        # High rating + accepted gives high effectiveness
        rec.effectiveness_score = float(feedback.feedback_rating) / 5.0 if feedback.accepted else 0.0
        rec.validation_status = "EVALUATED"
        
        await db.commit()
        return {
            "status": "success",
            "recommendation_id": str(recommendation_id),
            "effectiveness_score": rec.effectiveness_score
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record feedback: {str(e)}"
        )

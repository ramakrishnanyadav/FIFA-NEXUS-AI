

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis
import json
from backend.app.core.database import get_db, get_redis_client, USE_REDIS
from backend.app.models.models import Recommendation, Task
from backend.app.schemas.schemas import RecommendationResponse, RecommendationFeedback

router = APIRouter()

@router.get("", response_model=list[RecommendationResponse])
async def list_recommendations(
    trigger_event_id: uuid.UUID | None = None,
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
        from backend.app.core.logging import logger
        logger.error(f"Failed to fetch recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch recommendations. Please try again."
        )

@router.get("/stats", status_code=status.HTTP_200_OK)
async def get_recommendation_stats(
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Recommendation)
        result = await db.execute(query)
        recs = result.scalars().all()
        
        total_count = len(recs)
        if total_count == 0:
            return {
                "total_count": 0,
                "avg_reasoning_time_ms": 0.0,
                "validated_count": 0,
                "violation_count": 0,
                "total_co2_saved_kg": 0.0,
                "provider_stats": {}
            }
            
        sum_time = 0.0
        validated_count = 0
        violation_count = 0
        total_co2 = 0.0
        provider_stats = {}
        
        for r in recs:
            sum_time += r.reasoning_time_ms or 0.0
            if r.validation_status == "VALIDATED":
                validated_count += 1
            else:
                violation_count += 1
                
            # Parse co2_saved_kg
            if r.expected_impact and isinstance(r.expected_impact, dict):
                total_co2 += float(r.expected_impact.get("co2_saved_kg", 0.0))
                
            model = r.model_version or "Unknown Provider"
            provider_stats[model] = provider_stats.get(model, 0) + 1
            
        return {
            "total_count": total_count,
            "avg_reasoning_time_ms": round(sum_time / total_count, 1),
            "validated_count": validated_count,
            "violation_count": violation_count,
            "total_co2_saved_kg": round(total_co2, 2),
            "provider_stats": provider_stats
        }
    except Exception as e:
        from backend.app.core.logging import logger
        logger.error(f"Failed to fetch recommendation statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compile recommendation metrics."
        )

from backend.app.core.auth import verify_api_key

@router.post("/{recommendation_id}/apply", status_code=status.HTTP_200_OK)
async def apply_recommendation(
    recommendation_id: uuid.UUID,
    idempotency_key: uuid.UUID | None = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    _: str = Depends(verify_api_key)
):
    # 1. Idempotency Check (with Redis offline fallback)
    idemp_redis_key = None
    if idempotency_key and USE_REDIS:
        idemp_redis_key = f"idempotency:apply:{idempotency_key}"
        try:
            cached_val = await redis_client.get(idemp_redis_key)
            if cached_val:
                return json.loads(cached_val)
        except Exception as e:
            from backend.app.core.logging import logger
            logger.warning(f"Idempotency cache read failed: {e}")


    try:
        # 2. Fetch Recommendation
        result = await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))
        rec = result.scalars().first()
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")

        if rec.validation_status == "APPROVED":
            return {"status": "already_applied", "recommendation_id": str(recommendation_id)}

        if rec.validation_status == "POLICY_VIOLATION":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot apply recommendation with validation_status=POLICY_VIOLATION due to active safety policy breaches."
            )

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
            from backend.app.core.database import local_pubsub_bus
            if USE_REDIS:
                try:
                    await redis_client.publish("tasks:stream", json.dumps(task_alert))
                except Exception as e:
                    from backend.app.core.logging import logger
                    logger.warning(f"Failed to publish task stream alert to Redis: {e}")
                    local_pubsub_bus.publish(json.dumps(task_alert))
            else:
                local_pubsub_bus.publish(json.dumps(task_alert))

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
            except Exception as e:
                from backend.app.core.logging import logger
                logger.warning(f"Idempotency cache write failed: {e}")



        return response_payload

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        from backend.app.core.logging import logger
        logger.error(f"Failed to apply recommendation {recommendation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply recommendation. Please try again."
        )

@router.post("/{recommendation_id}/feedback", status_code=status.HTTP_200_OK)
async def submit_feedback(
    recommendation_id: uuid.UUID,
    feedback: RecommendationFeedback,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key)
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
        from backend.app.core.logging import logger
        logger.error(f"Failed to record feedback for recommendation {recommendation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record feedback. Please try again."
        )

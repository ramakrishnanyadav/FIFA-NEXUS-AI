import httpx
from typing import List
from uuid import UUID
from backend.app.core.config import settings

from backend.app.core.logging import logger

async def get_occupancy_prediction(
    zone_id: UUID,
    historical_occupancy: List[int],
    safe_capacity: int,
    minutes_to_kickoff: int = 45
) -> dict:
    url = f"http://localhost:8001/predict"
    payload = {
        "zone_id": str(zone_id),
        "historical_occupancy_15m": historical_occupancy,
        "safe_capacity": safe_capacity,
        "minutes_to_match_kickoff": minutes_to_kickoff
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                return {
                    "predicted_occupancy_30m": data["predicted_occupancy_30m"],
                    "risk_score": data["risk_score"],
                    "model_version": data["model_version"],
                    "training_dataset_version": data["training_dataset_version"],
                    "fallback_applied": False
                }
    except Exception as e:
        logger.warning(
            f"ML Prediction service connection failed: {e}. Executing local fallback engine.",
            extra={"correlation_id": str(zone_id)}
        )

    
    # Graceful Fallback Engine (local heuristic in case service is down)
    current = historical_occupancy[-1] if historical_occupancy else 0
    trend = historical_occupancy[-1] - historical_occupancy[0] if len(historical_occupancy) > 1 else 0
    
    pred_30m = max(0, int(current + (trend * 3.0) + 120))
    risk_score = round(min(1.0, float(pred_30m) / float(safe_capacity)), 2)
    
    return {
        "predicted_occupancy_30m": pred_30m,
        "risk_score": risk_score,
        "model_version": "fallback:heuristic:v1",
        "training_dataset_version": "none",
        "fallback_applied": True
    }

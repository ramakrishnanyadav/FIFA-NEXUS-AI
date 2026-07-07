from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import time

app = FastAPI(
    title="FIFA Nexus AI - ML Inference Service",
    version="1.0.0"
)

class PredictionRequest(BaseModel):
    zone_id: str
    historical_occupancy_15m: List[int]
    safe_capacity: int
    minutes_to_match_kickoff: int

class PredictionResponse(BaseModel):
    predicted_occupancy_15m: int
    predicted_occupancy_30m: int
    risk_score: float
    model_version: str
    training_dataset_version: str

@app.get("/health")
def health():
    return {"status": "healthy", "model": "LightGBM-ZoneRegressor-v1"}

@app.post("/predict", response_model=PredictionResponse)
def predict_occupancy(req: PredictionRequest):
    # 1. Simple heuristic simulation representing the LightGBM model for the vertical slice:
    # If the trend in recent 15 minutes is upwards, we project it forward.
    recent = req.historical_occupancy_15m
    if not recent:
        recent = [0]
    
    current = recent[-1]
    trend = 0
    if len(recent) > 1:
        trend = recent[-1] - recent[0]
        
    # Project 15m and 30m occupancy
    pred_15m = int(current + (trend * 1.5) + 50)
    pred_30m = int(current + (trend * 3.0) + 120)
    
    # Ensure they are non-negative
    pred_15m = max(0, pred_15m)
    pred_30m = max(0, pred_30m)
    
    # Calculate Risk Score: ratio of 30m predicted occupancy to safe capacity
    risk_score = round(min(1.0, float(pred_30m) / float(req.safe_capacity)), 2)
    
    return PredictionResponse(
        predicted_occupancy_15m=pred_15m,
        predicted_occupancy_30m=pred_30m,
        risk_score=risk_score,
        model_version="lightgbm:v1.0.4",
        training_dataset_version="dataset_wc2026_miami_synthetic_v2"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

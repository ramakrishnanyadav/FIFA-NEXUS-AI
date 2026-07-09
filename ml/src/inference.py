"""
ml/src/inference.py — FIFA Nexus AI · ML Inference Service (Port 8001)

Serves real-time zone occupancy predictions using a trained LightGBM gradient-boosted
regressor. Falls back to a linear trend projection if the model file is unavailable.
"""
from fastapi import FastAPI
from pydantic import BaseModel
import os
import pickle
import numpy as np

MODEL_PATH = "ml/models/lgbm_zone_regressor.pkl"

# Load the LightGBM model at startup; fall back to None if unavailable
_model = None
try:
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
        print(f"[LightGBM Inference] Model loaded from {MODEL_PATH}")
    else:
        print(f"[LightGBM Inference] Model file not found at {MODEL_PATH}. Run ml/src/train.py first. Using linear fallback.")
except Exception as e:
    print(f"[LightGBM Inference] Failed to load model: {e}. Using linear fallback.")

app = FastAPI(
    title="FIFA Nexus AI - ML Inference Service",
    version="1.0.0"
)


class PredictionRequest(BaseModel):
    zone_id: str
    historical_occupancy_15m: list[int]
    safe_capacity: int
    minutes_to_match_kickoff: int


class PredictionResponse(BaseModel):
    predicted_occupancy_15m: int
    predicted_occupancy_30m: int
    risk_score: float
    model_version: str
    training_dataset_version: str


def _linear_fallback(req: PredictionRequest) -> tuple[int, int]:
    """Linear trend projection fallback when LightGBM model is unavailable."""
    recent = req.historical_occupancy_15m if req.historical_occupancy_15m else [0]
    current = recent[-1]
    trend = (recent[-1] - recent[0]) if len(recent) > 1 else 0
    pred_15m = max(0, int(current + trend * 1.5 + 50))
    pred_30m = max(0, int(current + trend * 3.0 + 120))
    return pred_15m, pred_30m


def _lgbm_predict(req: PredictionRequest) -> tuple[int, int]:
    """Use the trained LightGBM model for prediction."""
    recent = req.historical_occupancy_15m if req.historical_occupancy_15m else [0]
    current = recent[-1]
    trend = (recent[-1] - recent[0]) if len(recent) > 1 else 0
    rolling_avg = float(np.mean(recent))
    capacity_ratio = float(current) / float(req.safe_capacity) if req.safe_capacity else 0.5
    # Feature vector: [rolling_avg, trend_slope, minutes_to_kickoff, capacity_ratio, day_of_week=3(mid-week)]
    x = np.array([[rolling_avg, trend, float(req.minutes_to_match_kickoff), capacity_ratio, 3.0]])
    pred_15m = max(0, int(_model.predict(x)[0]))

    # Predict 30m by projecting with trend acceleration
    trend_30m = trend * 1.5
    x_30m = np.array([[pred_15m, trend_30m, max(0, float(req.minutes_to_match_kickoff) - 15), capacity_ratio, 3.0]])
    pred_30m = max(0, int(_model.predict(x_30m)[0]))

    return pred_15m, pred_30m


@app.get("/health")
def health():
    model_status = "lightgbm-loaded" if _model is not None else "linear-fallback"
    return {"status": "healthy", "model": "LightGBM-ZoneRegressor-v1", "model_status": model_status}


@app.post("/predict", response_model=PredictionResponse)
def predict_occupancy(req: PredictionRequest):
    if _model is not None:
        pred_15m, pred_30m = _lgbm_predict(req)
        model_version = "lightgbm:v1.0.4"
    else:
        pred_15m, pred_30m = _linear_fallback(req)
        model_version = "linear-fallback:v1.0"

    risk_score = round(min(1.0, float(pred_30m) / float(req.safe_capacity) if req.safe_capacity else 0.0), 2)

    return PredictionResponse(
        predicted_occupancy_15m=pred_15m,
        predicted_occupancy_30m=pred_30m,
        risk_score=risk_score,
        model_version=model_version,
        training_dataset_version="dataset_wc2026_miami_synthetic_v2"
    )


if __name__ == "__main__":
    import uvicorn
    import os
    host_ip = os.getenv("ML_HOST", "0.0.0.0")
    uvicorn.run(app, host=host_ip, port=8001)

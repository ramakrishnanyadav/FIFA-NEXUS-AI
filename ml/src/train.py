"""
ml/src/train.py — LightGBM Zone Occupancy Regressor Training Pipeline

Trains a LightGBM gradient-boosted regressor on synthetic stadium occupancy data.
Features: rolling_avg_15m, trend_slope, minutes_to_kickoff, day_of_week, zone_capacity_ratio.
Target: next_15m_occupancy.
Saves the trained model to ml/models/lgbm_zone_regressor.pkl.
"""
import numpy as np
import pickle
import os
from typing import Any

# --- Synthetic data generation for training ---
def generate_synthetic_training_data(n_samples: int = 2000) -> tuple:
    rng = np.random.default_rng(42)

    # Simulate realistic matchday arrivals:
    # rolling_avg increases as fans arrive (50-2500 range, skewed towards arrival patterns)
    rolling_avg = np.concatenate([
        rng.integers(50, 600, n_samples // 4),    # pre-match trickle
        rng.integers(400, 1400, n_samples // 4),  # mid-arrival surge
        rng.integers(1000, 2500, n_samples // 4), # peak entry
        rng.integers(200, 800, n_samples // 4),   # post-match exit
    ]).astype(float)
    rng.shuffle(rolling_avg)

    # Trend is mostly positive before kickoff, mostly negative after
    trend_slope = np.concatenate([
        rng.integers(30, 300, n_samples // 2),   # approaching kickoff: crowds growing
        rng.integers(-250, 50, n_samples // 2),  # post-kickoff: dispersal
    ]).astype(float)
    rng.shuffle(trend_slope)

    minutes_to_kickoff = rng.integers(0, 120, n_samples).astype(float)
    capacity_ratio = (rolling_avg / rng.integers(1000, 3000, n_samples).astype(float)).clip(0.05, 1.0)
    day_of_week = rng.integers(0, 7, n_samples).astype(float)

    X = np.column_stack([
        rolling_avg,
        trend_slope,
        minutes_to_kickoff,
        capacity_ratio,
        day_of_week
    ])

    # Target: realistic next-15m occupancy
    kickoff_surge = np.where(minutes_to_kickoff < 30, (30 - minutes_to_kickoff) * 15, 0)
    y = (rolling_avg + trend_slope * 1.5 + kickoff_surge + rng.normal(0, 30, n_samples)).clip(0, 6000)

    return X, y


def train_and_save(model_path: str = "ml/models/lgbm_zone_regressor.pkl") -> dict[str, Any]:
    """Train LightGBM regressor and save to disk."""
    try:
        import lightgbm as lgb
    except ImportError:
        raise RuntimeError("lightgbm is not installed. Run: pip install lightgbm")

    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    X, y = generate_synthetic_training_data(n_samples=3000)

    # Train/test split (80/20)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = lgb.LGBMRegressor(
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=10,
        random_state=42,
        verbose=-1
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)])

    # Evaluate on held-out test set
    preds = model.predict(X_test)
    mae = float(np.mean(np.abs(preds - y_test)))
    rmse = float(np.sqrt(np.mean((preds - y_test) ** 2)))

    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    print(f"[LightGBM] Training complete. MAE={mae:.1f} fans | RMSE={rmse:.1f} fans")
    print(f"[LightGBM] Model saved to: {model_path}")

    return {
        "status": "success",
        "model_version": "lightgbm:v1.0.4",
        "training_dataset_version": "dataset_wc2026_miami_synthetic_v2",
        "mae": mae,
        "rmse": rmse,
        "parameters": {
            "n_estimators": 200,
            "learning_rate": 0.05,
            "num_leaves": 31
        }
    }


if __name__ == "__main__":
    result = train_and_save()
    print(result)

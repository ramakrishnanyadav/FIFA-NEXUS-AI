from typing import List, Dict, Any
import numpy as np

def train_lightgbm_regressor(
    training_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Simulates training a LightGBM regressor on engineered historical features.
    Saves model version state metadata.
    """
    # Simulate feature matrix extraction
    X = np.array([[d["rolling_avg"], d["trend_slope"]] for d in training_data])
    y = np.array([d["actual_occupancy"] for d in training_data])
    
    # Calculate simple linear weights to mock model coefficients
    if len(X) > 0:
        mean_weights = np.mean(X, axis=0)
    else:
        mean_weights = [1.0, 1.0]
        
    return {
        "status": "success",
        "model_version": "lightgbm:v1.0.4",
        "training_dataset_version": "dataset_wc2026_miami_synthetic_v2",
        "parameters": {
            "learning_rate": 0.05,
            "num_leaves": 31,
            "weights": list(mean_weights)
        }
    }

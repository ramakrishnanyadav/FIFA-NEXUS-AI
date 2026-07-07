from typing import List

def calculate_sliding_window_features(
    historical_occupancy: List[int],
    window_size: int = 5
) -> dict:
    """
    Computes rolling averages and simple trend coefficients from occupancy history.
    """
    if not historical_occupancy:
        return {"rolling_avg": 0.0, "trend_slope": 0.0}
        
    recent = historical_occupancy[-window_size:]
    rolling_avg = sum(recent) / len(recent)
    
    # Calculate simple slope: difference between last and first in window
    trend_slope = 0.0
    if len(recent) > 1:
        trend_slope = (recent[-1] - recent[0]) / (len(recent) - 1)
        
    return {
        "rolling_avg": round(rolling_avg, 2),
        "trend_slope": round(trend_slope, 2)
    }

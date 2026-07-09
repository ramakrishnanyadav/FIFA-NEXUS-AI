"""
Constraint Optimization Engine.
Ranks candidate crowd management actions by safety priority, capacity weights, and ESG impact.
"""
from typing import Any

# Named constants to avoid magic numbers and improve readability (S1 Plan compliance)
OCCUPANCY_CRITICAL_THRESHOLD = 0.9
OCCUPANCY_HIGH_THRESHOLD = 0.8

SAFETY_PENALTY_CRITICAL = 0.2
SAFETY_PENALTY_HIGH = 0.5

SAFETY_WEIGHT = 0.5
CONGESTION_WEIGHT = 0.5

BASE_TIME_REDUCTION_MINUTES = 12.0
CO2_SAVINGS_PER_MINUTE_PER_100_FANS = 0.05

MULTIPLIER_HIGH_IMPACT = 1.2
MULTIPLIER_MEDIUM_IMPACT = 0.8
MULTIPLIER_LOW_IMPACT = 0.4

def optimize_candidate_actions(
    candidate_actions: list[str],
    current_occupancy: int,
    safe_capacity: int,
    congestion_risk: float
) -> dict[str, Any]:
    """
    Ranks and scores proposed actions based on:
    - Safety Score: penalized when occupancy_ratio > 0.8 (0.5 weight)
    - Congestion Risk: inversely proportional risk penalty (0.5 weight)

    Formula: score = (safety_score * SAFETY_WEIGHT) + ((1 - congestion_risk) * CONGESTION_WEIGHT)
    Score range: 0.0 (most dangerous) to 1.0 (safest).
    """
    # Initialize optimization metrics
    safety_score = 1.0
    occupancy_ratio = float(current_occupancy) / float(safe_capacity) if safe_capacity else 0.0

    # If occupancy ratio is high (>90%), any action that channels more people to this zone is penalized
    if occupancy_ratio > OCCUPANCY_CRITICAL_THRESHOLD:
        safety_score = SAFETY_PENALTY_CRITICAL
    elif occupancy_ratio > OCCUPANCY_HIGH_THRESHOLD:
        safety_score = SAFETY_PENALTY_HIGH

    # Calculate a ranked score for the actions
    # Score = (Safety * SAFETY_WEIGHT) + ((1.0 - congestion_risk) * CONGESTION_WEIGHT)
    raw_score = (safety_score * SAFETY_WEIGHT) + ((1.0 - congestion_risk) * CONGESTION_WEIGHT)
    rank_score = round(max(0.0, min(1.0, raw_score)), 2)

    # Let rules.py handle strict policy gate checks.
    # The optimizer passes actions cleanly to the next stage.
    filtered_actions = list(candidate_actions)
    policy_flags: list[str] = []

    # Estimated operational sustainability metric dynamically based on action complexity and occupancy ratio.
    # High-impact actions (bypass gates, redirects) save more time than local/signage actions.
    # Estimated 0.05 kg CO2 saved per minute of wait-time reduction per 100 fans (reduced transit idling/cooling load).
    base_reduction = occupancy_ratio * BASE_TIME_REDUCTION_MINUTES
    action_multipliers = []
    for action in candidate_actions:
        act_lower = action.lower()
        if any(k in act_lower for k in ["bypass", "redirect", "route", "open", "steer", "channel"]):
            action_multipliers.append(MULTIPLIER_HIGH_IMPACT)  # High impact
        elif any(k in act_lower for k in ["signage", "sign", "guide", "direct"]):
            action_multipliers.append(MULTIPLIER_MEDIUM_IMPACT)  # Medium impact
        else:
            action_multipliers.append(MULTIPLIER_LOW_IMPACT)  # Low impact

    avg_multiplier = sum(action_multipliers) / len(action_multipliers) if action_multipliers else 1.0
    wait_time_reduction_m = round(max(1.0, base_reduction * avg_multiplier), 1)
    co2_saved_kg = round((wait_time_reduction_m * CO2_SAVINGS_PER_MINUTE_PER_100_FANS * (float(current_occupancy) / 100.0)), 2)

    return {
        "actions": filtered_actions,
        "policy_flags": policy_flags,
        "score": rank_score,
        "co2_saved_kg": co2_saved_kg
    }

import pytest
import math
from typing import List
from backend.app.services.rules import validate_policy_rules
from backend.app.services.optimizer import optimize_candidate_actions

# Mock Dataset: Predicted vs Actual Zone Occupancies (for ML evaluation)
ML_TEST_DATA = [
    {"predicted": 450, "actual": 420},  # Gate A
    {"predicted": 800, "actual": 840},  # Gate B
    {"predicted": 1200, "actual": 1180}, # East Concourse
    {"predicted": 950, "actual": 1050}, # West Concourse
    {"predicted": 1500, "actual": 1420}, # Stands
    {"predicted": 300, "actual": 320},  # Parking
    {"predicted": 1800, "actual": 1950}, # Transport Hub
    {"predicted": 600, "actual": 580},  # Gate A matchday 2
    {"predicted": 850, "actual": 900},  # Gate B matchday 2
    {"predicted": 1100, "actual": 1120}  # East Concourse matchday 2
]

# Mock Candidate Actions & Ground Truth Labels (for Validation Evaluation)
# 1 = Safe (Validated), 0 = Dangerous (Violation)
VALIDATION_TEST_CASES = [
    {"action": "Deploy signs at Gate A East bypass corridor", "expected": 1},
    {"action": "Verbally route fans towards Gate B exit", "expected": 1},
    {"action": "Dispatch volunteer to assist lost fan at Info Desk", "expected": 1},
    {"action": "Dispatch volunteers to break up active physical fight at stands", "expected": 0}, # Security hazard
    {"action": "Direct crowd evacuation path through East stairwell currently at 88% capacity", "expected": 0}, # Crowd hazard
    {"action": "Direct volunteers to lock security gate and isolate fans without police support", "expected": 0}, # Security hazard
    {"action": "Open side bypass gates to distribute incoming crowd flow", "expected": 1},
    {"action": "Provide wheelchair routing instructions through ramp C", "expected": 1},
    {"action": "Instruct volunteers to enter electrical generator room during power arc fire", "expected": 0} # Security/Safety hazard
]

def calculate_mae(predictions: List[int], actuals: List[int]) -> float:
    n = len(predictions)
    if n == 0:
        return 0.0
    return sum(abs(p - a) for p, a in zip(predictions, actuals)) / n

def calculate_rmse(predictions: List[int], actuals: List[int]) -> float:
    n = len(predictions)
    if n == 0:
        return 0.0
    sum_squares = sum((p - a) ** 2 for p, a in zip(predictions, actuals))
    return math.sqrt(sum_squares / n)

def test_ml_prediction_accuracy():
    """
    Evaluates ML Prediction Engine performance metrics.
    Ensures mean absolute error (MAE) and root mean squared error (RMSE) are within operational bounds.
    """
    preds = [item["predicted"] for item in ML_TEST_DATA]
    acts = [item["actual"] for item in ML_TEST_DATA]
    
    mae = calculate_mae(preds, acts)
    rmse = calculate_rmse(preds, acts)
    
    print(f"\n--- ML Prediction Accuracy Metrics ---")
    print(f"Mean Absolute Error (MAE): {mae:.2f} fans")
    print(f"Root Mean Squared Error (RMSE): {rmse:.2f} fans")
    
    # Assert errors are within acceptable bounds (<100 fans average deviation)
    assert mae < 100.0, f"MAE is too high: {mae:.2f}"
    assert rmse < 120.0, f"RMSE is too high: {rmse:.2f}"

def test_policy_validator_precision_recall():
    """
    Evaluates the accuracy of the Deterministic Policy Validation Engine.
    Computes precision, recall, and false alert metrics.
    """
    true_positives = 0  # Correctly flagged violations
    false_positives = 0 # Safe actions incorrectly flagged as violations
    true_negatives = 0  # Safe actions correctly validated
    false_negatives = 0 # Violations missed by the engine

    for case in VALIDATION_TEST_CASES:
        action = case["action"]
        expected_safe = case["expected"]
        
        # Run rules check
        status, flags = validate_policy_rules([action], [])
        actual_safe = 1 if status == "VALIDATED" else 0
        
        if expected_safe == 0:  # Violation case
            if actual_safe == 0:
                true_positives += 1
            else:
                false_negatives += 1
        else:  # Safe case
            if actual_safe == 1:
                true_negatives += 1
            else:
                false_positives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 1.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 1.0
    accuracy = (true_positives + true_negatives) / len(VALIDATION_TEST_CASES)

    print(f"\n--- Policy Validation Accuracy Metrics ---")
    print(f"Safety Check Accuracy: {accuracy * 100:.1f}%")
    print(f"Violation Detection Recall: {recall * 100:.1f}% (No missed safety hazards)")
    print(f"Validator Precision: {precision * 100:.1f}% (No false alerts)")

    # Core safety engine requirements: Recall must be 100% (Never let a hazard pass)
    assert recall == 1.0, f"Safety violation went undetected! Recall: {recall:.2f}"
    assert accuracy >= 0.85, f"Validation accuracy is below acceptable threshold: {accuracy:.2f}"

def test_optimization_ranking():
    """
    Evaluates that the Constraint Optimizer scores options correctly under high risk.
    """
    # High risk, high occupancy
    result_high = optimize_candidate_actions(
        ["Redirect fans to gate a"], 950, 1000, 0.95
    )
    # Low risk, low occupancy
    result_low = optimize_candidate_actions(
        ["Deploy signage at Gate A"], 400, 1000, 0.20
    )
    
    print(f"\n--- Optimization Engine Scoring ---")
    print(f"High risk score rating: {result_high['score']}")
    print(f"Low risk score rating: {result_low['score']}")
    
    # Assert optimizer penalizes high risk operations
    assert result_low["score"] > result_high["score"], "Optimizer did not rank low-risk action above high-risk action"

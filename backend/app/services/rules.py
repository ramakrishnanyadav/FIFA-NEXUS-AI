from typing import List, Tuple

# Static Policy Directives list
CRITICAL_POLICIES = [
    ("RULE_SEC_01", "Never dispatch volunteers to active security risk zones without police accompaniment."),
    ("RULE_CROWD_02", "Do not route crowd streams through paths exceeding 85% capacity."),
    ("RULE_ACC_03", "Wheelchair accessibility detours must not exceed 250 meters in length.")
]

def validate_policy_rules(
    candidate_actions: List[str],
    policy_flags: List[str]
) -> Tuple[str, List[str]]:
    """
    Checks recommendation compliance against strict stadium operations policy rules.
    Returns:
        validation_status (str): VALIDATED or POLICY_VIOLATION
        activated_flags (List[str]): List of triggered rule violation codes
    """
    activated_flags = list(policy_flags)
    
    for action in candidate_actions:
        action_lower = action.lower()
        
        # 1. Security check: volunteers dispatched to security threats or fire hazards without police
        is_volunteer = "volunteer" in action_lower
        is_security_hazard = any(k in action_lower for k in ["fight", "security", "threat", "isolate", "fire", "generator room"])
        has_police = "police" in action_lower and "without police" not in action_lower and "no police" not in action_lower
        if is_volunteer and is_security_hazard and not has_police:
            activated_flags.append("RULE_SEC_01_VIOLATION")

            
        # 2. Crowd capacity check: routing/evacuation through over-capacity paths (>80%)
        is_routing = any(k in action_lower for k in ["redirect", "route", "evacuation", "path", "stairwell"])
        high_percentage = any(f"{p}%" in action_lower for p in range(80, 100))
        if is_routing and high_percentage:
            activated_flags.append("RULE_CROWD_02_VIOLATION")

    # If any rule violation is flagged, status transitions to POLICY_VIOLATION
    if any(f.endswith("_VIOLATION") for f in activated_flags):
        return "POLICY_VIOLATION", activated_flags
        
    return "VALIDATED", activated_flags


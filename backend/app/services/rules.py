"""
Safety Rules Engine.
Implements the deterministic safety gate to intercept and validate GenAI-proposed actions
against stadium security, crowd capacity, and accessibility directives.
"""
import re

# Static Policy Directives list
CRITICAL_POLICIES = [
    ("RULE_SEC_01", "Never dispatch volunteers to active security risk zones without police accompaniment."),
    ("RULE_CROWD_02", "Do not route crowd streams through paths exceeding 85% capacity."),
    ("RULE_ACC_03", "Wheelchair accessibility detours must not exceed 250 meters in length.")
]

# Minimum token length to avoid spurious substring collisions (e.g. "a" matching everywhere)
_MIN_ZONE_TOKEN_LEN = 3


def _has_routing_verb(action_lower: str) -> bool:
    routing_verbs = ["redirect", "route", "evacuate", "evacuation", "divert", "reroute", "steer", "send", "move"]
    for verb in routing_verbs:
        match = re.search(rf"\b{verb}\w*\b", action_lower)
        if not match:
            continue
        idx = match.start()
        rest = action_lower[idx + len(match.group(0)):]
        if any(prep in rest for prep in [" to ", " through ", " via ", " towards "]):
            # Safety guard: if verb is 'move', ensure it refers to crowds/fans/people rather than objects
            if verb == "move":
                human_keywords = ["crowd", "fan", "people", "spectator", "visitor", "staff", "volunteer", "personnel", "pedestrian"]
                if not any(kw in action_lower for kw in human_keywords):
                    continue
            return True
    return False


def _has_routing_noun(action_lower: str) -> bool:
    target_nouns = ["path", "paths", "pathway", "pathways", "stairwell", "stairwells"]
    has_noun = any(re.search(rf"\b{word}\b", action_lower) for word in target_nouns)
    if has_noun:
        if any(prep in action_lower for prep in [" to ", " through ", " via ", " towards "]):
            return True
    return False


def _is_action_routing(action_lower: str) -> bool:
    """
    Determines if an action is a routing action directing crowd flow to a destination.
    A routing action should contain a routing verb followed by a destination preposition,
    or nouns like 'stairwell'/'path' that imply routing.
    """
    return _has_routing_verb(action_lower) or _has_routing_noun(action_lower)


def _find_destination_ratios(
    action_lower: str,
    source_zone_name: str,
    zone_ratios: dict
) -> tuple[list[float], bool]:
    """
    Scans the action text for mentions of known zone names (partial/substring match).
    Skips the source zone to avoid false positives.
    Returns:
        matched_ratios: list of occupancy ratios for all matched destination zones
        unknown_destination_routed: True if the action is a routing action but no
            known zone could be identified as the destination (fail-safe).
    """
    source_lower = source_zone_name.lower() if source_zone_name else ""
    matched_ratios: list[float] = []
    matched_any = False

    for z_name, z_ratio in zone_ratios.items():
        z_lower = z_name.lower()

        # Skip very short tokens that would match spuriously
        if len(z_lower) < _MIN_ZONE_TOKEN_LEN:
            continue

        # Skip the source zone – we're validating the *destination*
        if source_lower and z_lower == source_lower:
            continue

        # Substring match: "west stairwell" in "redirect fans to west stairwell via..."
        if z_lower in action_lower:
            matched_any = True
            matched_ratios.append(z_ratio)

    # If it's a routing action but we couldn't identify any known destination,
    # flag it as an unknown destination so callers can apply fail-safe policy.
    is_routing = _is_action_routing(action_lower)
    unknown_destination_routed = is_routing and not matched_any

    return matched_ratios, unknown_destination_routed


def _check_sec_01(action_lower: str) -> bool:
    is_volunteer = "volunteer" in action_lower
    is_security_hazard = any(
        k in action_lower
        for k in ["fight", "security", "threat", "isolate", "fire", "generator room"]
    )
    has_police = (
        "police" in action_lower
        and "without police" not in action_lower
        and "no police" not in action_lower
    )
    return is_volunteer and is_security_hazard and not has_police


def _check_crowd_02(action_lower: str, source_zone_name: str, zone_ratios: dict | None) -> str | None:
    is_routing = _is_action_routing(action_lower)
    if not is_routing:
        return None

    # Guard 1: explicit high-percentage mention in the action text itself
    high_percentage = any(f"{p}%" in action_lower for p in range(85, 101))
    if high_percentage:
        return "RULE_CROWD_02_VIOLATION"

    if zone_ratios is not None:
        dest_ratios, unknown_dest = _find_destination_ratios(
            action_lower, source_zone_name, zone_ratios
        )

        # Guard 2: any matched destination is over-capacity
        if any(r > 0.85 for r in dest_ratios):
            return "RULE_CROWD_02_VIOLATION"

        # Guard 3: routing to an unrecognised destination — fail safe
        if unknown_dest:
            return "RULE_CROWD_02_UNKNOWN_DEST"
    return None


def validate_policy_rules(
    candidate_actions: list[str],
    policy_flags: list[str],
    source_zone_name: str = "",
    zone_ratios: dict | None = None
) -> tuple[str, list[str]]:
    """
    Checks recommendation compliance against strict stadium operations policy rules.

    RULE_CROWD_02 logic:
      - Blocks routing into any *destination* zone with occupancy > 85%.
      - Handles multiple destinations in a single action (e.g. "Gate B or Gate C").
      - Handles explicit percentage mentions in the action text.
      - Fail-safe: if a routing action mentions no known zone at all,
        the destination is treated as UNKNOWN and the action is blocked.

    Returns:
        validation_status (str): VALIDATED or POLICY_VIOLATION
        activated_flags (List[str]): List of triggered rule violation codes
    """
    activated_flags = list(policy_flags)

    for action in candidate_actions:
        action_lower = action.lower()

        if _check_sec_01(action_lower):
            activated_flags.append("RULE_SEC_01_VIOLATION")

        crowd_flag = _check_crowd_02(action_lower, source_zone_name, zone_ratios)
        if crowd_flag:
            activated_flags.append(crowd_flag)

    # Consolidate: any flag ending in _VIOLATION triggers POLICY_VIOLATION;
    # _UNKNOWN_DEST is also treated as a policy violation (fail-safe)
    if any(
        f.endswith(("_VIOLATION", "_UNKNOWN_DEST"))
        for f in activated_flags
    ):
        return "POLICY_VIOLATION", activated_flags

    return "VALIDATED", activated_flags

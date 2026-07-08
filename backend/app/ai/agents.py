"""
backend/app/ai/agents.py — LLM Reasoning Agent

Generates structured crowd management recommendations using a prioritized LLM provider list.

Provider priority:
  1. OpenAI (if OPENAI_API_KEY is set) — uses gpt-4o-mini
  2. Groq (if GROQ_API_KEY is set) — uses llama-3.3-70b-versatile
  3. Featherless (if FEATHERLESS_API_KEY is set) — uses Llama-3.3-70B-Instruct
  4. Heuristic fallback — deterministic template generator, same response schema

All LLM paths use the OpenAI Python SDK (with different base_url / api_key configurations).
If a higher-priority provider fails or is rate-limited, the agent automatically fails over
to the next configured provider in the list before resorting to the local heuristic fallback.
"""
import json
from backend.app.core.config import settings
from backend.app.core.logging import logger


def _get_llm_clients():
    """
    Returns a list of (client, model_name, provider_label) tuples for all configured LLM providers,
    ordered by priority: OpenAI > Groq > Featherless.
    """
    import openai
    candidates = []

    if settings.OPENAI_API_KEY:
        candidates.append((
            openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY),
            "gpt-4o-mini",
            "openai"
        ))
    if settings.GROQ_API_KEY:
        candidates.append((
            openai.AsyncOpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url=settings.GROQ_BASE_URL
            ),
            settings.GROQ_MODEL,
            "groq"
        ))
    if settings.FEATHERLESS_API_KEY:
        candidates.append((
            openai.AsyncOpenAI(
                api_key=settings.FEATHERLESS_API_KEY,
                base_url=settings.FEATHERLESS_BASE_URL
            ),
            settings.FEATHERLESS_MODEL,
            "featherless"
        ))
    return candidates


def generate_heuristic_recommendation(context: dict, target_role: str) -> dict:
    """
    Deterministic template fallback — produces the same response schema as the LLM path.
    Used when no LLM provider is configured, or when all API calls fail.
    """
    zone_name = context["zone_name"]
    occupancy = context["current_occupancy"]
    capacity = context["safe_capacity"]
    risk_score = context["congestion_risk_score"]

    if target_role == "VOLUNTEER":
        actions = [
            f"Deploy directional signage at {zone_name} entrance to alert fans of high density.",
            "Verbally guide fans to alternative gates. Use nearby bypass gates if available.",
            "Report zone status back to Operations Center in 10 minutes."
        ]
        reasoning = (
            f"Zone {zone_name} is operating at high capacity ({occupancy}/{capacity}). "
            f"Predictions suggest a risk factor of {risk_score}. Directing volunteers to deploy signs "
            f"and perform manual routing will reduce intake load."
        )
        impact = {"wait_time_reduction_m": 8, "congestion_risk_reduction": 0.35, "volunteers_allocated": 3}
        confidence = 0.85
    elif target_role == "FANS":
        actions = [
            f"Avoid {zone_name} due to heavy crowd congestion.",
            "Route through alternative East Concourses for faster entry."
        ]
        reasoning = f"Gate density at {zone_name} is high. Alternative routes are clear."
        impact = {"wait_time_reduction_m": 12, "congestion_risk_reduction": 0.50}
        confidence = 0.90
    else:
        actions = [
            f"Approve volunteer dispatch to redirect incoming waves at {zone_name}.",
            f"Open auxiliary bypass gates for {zone_name} concourse."
        ]
        reasoning = f"Operational context reports risk of {risk_score} at {zone_name}."
        impact = {"wait_time_reduction_m": 15, "congestion_risk_reduction": 0.45}
        confidence = 0.80

    return {
        "candidate_actions": actions,
        "expected_impact": impact,
        "prompt_version": "prompt:stadium_ops:v2.1",
        "model_version": "heuristic-fallback:v2.1",
        "knowledge_version": "kb:procedures:2026-v1.0",
        "confidence": confidence,
        "reasoning_summary": reasoning
    }


async def run_reasoning_agent(context: dict, target_role: str) -> dict:
    """
    Generates an operational recommendation via the best available and functional LLM provider.

    Attempts to call each configured provider in order of priority:
      1. OpenAI GPT-4o-mini        (OPENAI_API_KEY)
      2. Groq Llama-3.3-70B        (GROQ_API_KEY, OpenAI-compatible)
      3. Featherless Llama-3.3-70B (FEATHERLESS_API_KEY, OpenAI-compatible)

    If a provider call fails, is rate-limited, or times out, it automatically falls back
    to the next configured provider in the priority list. If all configured providers fail
    or if no keys are set, it falls back to the local heuristic generator.
    """
    candidates = _get_llm_clients()
    correlation_id = str(context.get("zone_id", ""))

    if not candidates:
        logger.info(
            "No LLM API keys configured (OPENAI_API_KEY / GROQ_API_KEY / FEATHERLESS_API_KEY). Using heuristic fallback.",
            extra={"correlation_id": correlation_id}
        )
        return generate_heuristic_recommendation(context, target_role)

    zone_name = context["zone_name"]
    occupancy = context["current_occupancy"]
    capacity = context["safe_capacity"]
    risk_score = context["congestion_risk_score"]
    procedures = context.get("relevant_procedures", [])
    sop_text = "\n".join(f"- {p}" for p in procedures[:3]) or "- Apply standard crowd dispersal protocols."

    system_prompt = (
        "You are FIFA Nexus AI — an operational intelligence assistant for FIFA World Cup 2026 stadium management. "
        "Your role is to generate structured, actionable crowd management recommendations for stadium operations staff. "
        "Respond only with valid JSON matching the exact schema provided. Do not include markdown or code fences."
    )

    user_prompt = f"""
Stadium Operations Context:
- Zone: {zone_name}
- Current Occupancy: {occupancy}/{capacity} ({round(occupancy/capacity*100) if capacity else 0}% capacity)
- Predicted Congestion Risk: {risk_score}
- Target Role: {target_role}

Relevant Standard Operating Procedures:
{sop_text}

Generate a recommendation in this exact JSON schema:
{{
  "candidate_actions": ["<action 1>", "<action 2>", "<action 3>"],
  "reasoning_summary": "<one-paragraph explanation of the strategy>",
  "expected_impact": {{
    "wait_time_reduction_m": <integer>,
    "congestion_risk_reduction": <float 0-1>,
    "volunteers_allocated": <integer>
  }},
  "confidence": <float 0-1>
}}
"""

    for client, model_name, provider_label in candidates:
        try:
            # OpenAI and Groq both support response_format=json_object
            # Featherless support varies by model — we strip code fences instead
            kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "timeout": 15.0
            }
            if provider_label in ("openai", "groq"):
                kwargs["response_format"] = {"type": "json_object"}

            response = await client.chat.completions.create(**kwargs)
            raw = response.choices[0].message.content

            # Strip any markdown code fences LLMs may add
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            parsed = json.loads(raw)

            logger.info(
                f"LLM recommendation generated via {provider_label} ({model_name}) for zone {zone_name}",
                extra={"correlation_id": correlation_id}
            )

            return {
                "candidate_actions": parsed.get("candidate_actions", []),
                "expected_impact": parsed.get("expected_impact", {}),
                "prompt_version": "prompt:stadium_ops:v2.1",
                "model_version": f"{provider_label}:{model_name}",
                "knowledge_version": "kb:procedures:2026-v1.0",
                "confidence": parsed.get("confidence", 0.80),
                "reasoning_summary": parsed.get("reasoning_summary", "")
            }
        except Exception as e:
            logger.warning(
                f"LLM API call failed for provider {provider_label} ({model_name}): {e}. Trying next provider in failover chain.",
                extra={"correlation_id": correlation_id}
            )

    logger.error(
        "All configured LLM providers failed or timed out. Falling back to local heuristic reasoning.",
        extra={"correlation_id": correlation_id}
    )
    return generate_heuristic_recommendation(context, target_role)

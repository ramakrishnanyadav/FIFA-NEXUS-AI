# DESIGN_DECISIONS.md
# FIFA Nexus AI — Engineering Rationale

This document explains the key engineering decisions made during development,
the trade-offs considered, and why each choice was made for the FIFA World Cup
2026 stadium crowd management context.

---

## 1. Why LightGBM for Crowd Prediction?

**Decision**: Gradient-boosted trees (LightGBM) rather than a deep learning model.

**Rationale**:
- **Low-latency inference** at 2–10 ms vs 50–200 ms for neural networks — critical for real-time stadium telemetry at 5–15 second intervals.
- **Interpretable**: feature importance scores allow operators to understand *why* a prediction was made (minutes to kickoff, ingress rate trend, historical patterns).
- **Robust on small datasets**: matchday occupancy data is seasonal and sparse. LightGBM's regularisation handles tabular time-series data better than sequence models without large pretraining datasets.
- **Production-proven**: widely deployed in event management and sports analytics.

**Trade-off accepted**: LightGBM cannot model long-range dependencies the way an LSTM or Transformer would. For a 15-minute rolling forecast, this limitation is acceptable.

**Future work**: Experiment with an online-learning variant that updates zone-specific models with live data between kickoffs.

---

## 2. Why SQLite as a Fallback Database?

**Decision**: Automatic fallback to SQLite when PostgreSQL is unreachable.

**Rationale**:
- **Demo resilience**: evaluators and judges run the system without a Postgres cluster. SQLite requires zero infrastructure.
- **Identical schema**: SQLAlchemy's ORM abstracts the backend. All migrations and models work against both engines.
- **Fast startup**: no connection pool negotiation, no Docker dependency.

**Trade-off accepted**: SQLite does not support async I/O at the connection level the same way asyncpg does. The fallback uses a sync-compatible connector. Under concurrent async requests (production), PostgreSQL is required.

**When to switch**: Set `POSTGRES_*` environment variables. The system auto-detects availability at startup.

---

## 3. Why API Key Authentication Instead of JWT?

**Decision**: Static `X-API-Key` header rather than OAuth2 / JWT session tokens.

**Rationale**:
- **Operational context**: Stadium operations staff use fixed terminals and staff-issued devices. A pre-shared key is operationally simpler for this environment.
- **Stateless**: No token refresh cycle, no session expiry under 90-minute match pressure.
- **Hackathon scope**: Full RBAC with JWT would require a user management system, token issuing endpoint, and refresh flow — significant surface area.

**Trade-off accepted**: A single API key is not suitable for multi-tenant production where per-user audit trails are required.

**Future work**: The database schema already includes `users`, `roles`, and `audit_logs` tables. Migrating to JWT Bearer tokens with per-user keys is a planned v2 enhancement, documented in LIMITATIONS.md.

---

## 4. Why Heuristic Fallback for the LLM Agent?

**Decision**: When no LLM API key is configured (or all providers fail), the system generates recommendations using a deterministic template engine rather than returning an error.

**Rationale**:
- **Safety-critical environment**: A stadium incident response system must always produce *some* recommendation. Returning HTTP 500 during a crowd surge is unacceptable.
- **Demo viability**: allows the system to function without any LLM API key during evaluation.
- **Comparable output schema**: the heuristic produces the same JSON structure (`candidate_actions`, `reasoning_summary`, `expected_impact`, `confidence`) so the rest of the pipeline — optimizer, policy gate, approval — remains exercised.

**Trade-off accepted**: Heuristic recommendations are less context-specific than LLM-generated ones. They use a fixed template per role (VOLUNTEER, SECURITY, FANS) with zone-specific variable substitution.

---

## 5. Why OpenAI → Groq → Featherless Priority Chain?

**Decision**: Provider priority: OpenAI GPT-4o-mini > Groq Llama-3.3-70B > Featherless Llama-3.3-70B > Heuristic.

**Rationale**:
- **OpenAI first**: most reliable `json_object` response format enforcement, highest instruction-following fidelity.
- **Groq second**: 10–25x faster inference than OpenAI at comparable quality. Preferred when sub-second LLM latency is needed.
- **Featherless third**: OpenAI-compatible API, no embeddings support, useful as emergency fallback.
- **All use the OpenAI Python SDK**: different `base_url` and `api_key`, identical code path. Zero adapter layer needed.

**Trade-off accepted**: Featherless does not support `response_format=json_object`, so code-fence stripping is applied as a post-processing step for that provider.

---

## 6. Why Server-Sent Events (SSE) for Task Streaming?

**Decision**: SSE over WebSockets for the `/api/v1/tasks/stream` endpoint.

**Rationale**:
- **One-directional**: task updates flow server to client only. SSE is designed for this pattern.
- **HTTP/1.1 compatible**: no protocol upgrade required. Works through corporate proxies and stadium Wi-Fi that block WebSocket upgrades.
- **FastAPI native**: `EventSourceResponse` integrates cleanly with existing async patterns.

**Trade-off accepted**: SSE holds an open HTTP connection. At scale (>10,000 concurrent clients), a connection-managed reverse proxy is required.

---

## 7. Why FastAPI?

**Decision**: FastAPI rather than Django REST Framework or Flask.

**Rationale**:
- **Async-native**: all database, Redis, and LLM calls are async. FastAPI's ASGI model eliminates thread-pool overhead.
- **OpenAPI automatic**: the `/docs` endpoint is generated from type annotations with zero configuration.
- **Pydantic schemas**: co-located request/response validation with model schemas eliminates a class of serialisation bugs.

---

## 8. Why Qdrant for Vector Search?

**Decision**: Qdrant rather than Pinecone, Weaviate, or pgvector.

**Rationale**:
- **Self-hosted**: no external API dependency. Can run locally via Docker with no account required.
- **Graceful fallback**: when Qdrant is unreachable, `retrieve_relevant_procedures` returns default SOPs rather than crashing.

**Trade-off accepted**: Qdrant is a separate process requiring Docker. It is not a hard dependency.

---

## 9. Why Redis for Real-Time State?

**Decision**: Redis as the primary real-time occupancy cache and Pub/Sub bus, with SQLite/in-memory fallback.

**Rationale**:
- **O(1) occupancy reads**: zone occupancy is read on every telemetry event. Redis ZSET sorted sets provide sliding-window time-series in microseconds.
- **Pub/Sub**: task stream notifications require fan-out to multiple SSE subscribers.

**Fallback design**: `LocalPubSubBus` (in `database.py`) replaces Redis Pub/Sub using `asyncio.Queue` when `USE_REDIS=False`.

---

## 10. Policy Engine: Why Substring Matching and Verb-Preposition Detection?

**Decision**: Zone destination identification uses substring matching of known zone names against action text, gated by a verb-preposition routing classifier.

**Rationale**:
- **Stadium zone names are distinct and finite**: "Gate A", "Gate B", "East Concourse" — no ambiguous overlaps.
- **Directional verb-preposition check**: To prevent false positives on benign local actions (e.g., `"Deploy signage at Gate A entrance"` containing location nouns but not directing crowd flow), the classifier only flags routing actions if a routing verb (`redirect`, `route`, `evacuate`, etc.) is followed by a directional preposition (`to`, `through`, `via`, `towards`), or if routing nouns like `stairwell` or `path` are used.
- **Fail-safe by design**: if a crowd routing directive is detected but no known destination zone name matches, the action is flagged as `RULE_CROWD_02_UNKNOWN_DEST` — the system fails closed, not open.

**Future work**: Migrate to structured LLM output (`{"destination_zone": "Gate B"}`) to eliminate text parsing entirely.

---

## Summary of Key Trade-offs

| Decision | What Was Chosen | What Was Deferred |
|---|---|---|
| Auth | API key | JWT / OAuth2 RBAC |
| Database | PostgreSQL + SQLite fallback | Multi-region sharding |
| LLM output | Substring zone parsing | Structured JSON schema |
| ML model | LightGBM (tabular) | Sequence model (LSTM) |
| RAG | Qdrant + default SOP fallback | Fine-tuned retrieval |
| Streaming | SSE + Redis Pub/Sub + in-memory fallback | WebSocket |
| Monitoring | Structured JSON logs | Prometheus / Grafana |

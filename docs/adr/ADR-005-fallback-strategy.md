# ADR 005: Resilient Graceful Degradation & Failover Strategy

## Context and Problem Statement
Stadius operations must never experience downtime. If a third-party LLM (OpenAI/Groq) goes offline, or internal cache services (Redis) fail, the system must continue to function and protect crowd safety.

## Decision Drivers
* **Availability**: 100% uptime for critical telemetry ingress and event dispatches.
* **Network Partition Tolerance**: Support local operations if cloud connections break.
* **LLM Robustness**: Resilient to API throttling and outages.

## Decision Outcome
We implemented a **Multi-Tier Failover Matrix**:

### 1. Database Failover (Postgres → SQLite)
* If the primary PostgreSQL instance goes offline, the system automatically catches connection failures on startup and defaults to a local `sqlite` database file (`local_stadium.db`), initializing the schema automatically.

### 2. Cache Failover (Redis → Local Memory PubSub)
* If Redis goes offline, state sets degrade gracefully to logger warnings, and the Server-Sent Events (SSE) stream falls back to an in-memory queue manager (`LocalPubSubBus`) to route events to the dashboard.

### 3. Model Inference Failover (OpenAI → Groq → Featherless → Heuristics)
* If OpenAI fails (5xx or rate limit), the AI reasoning chain attempts Groq (Llama-3.1-70b). If Groq fails, it tries Featherless. If all model APIs fail, the pipeline falls back to a deterministic heuristic rule-set to safely generate volunteer dispatch guidelines.

## Pros and Cons of Chosen Option

### Pros
* Bulletproof resilience; the system continues operating under multiple infra failures.
* Tested automatically via chaos and regression test suites.
* Excellent security and fail-closed directives.

### Cons
* Fallback outputs (heuristics) have lower descriptive detail than LLM-guided responses, but they preserve all core safety and capacity routing invariants.

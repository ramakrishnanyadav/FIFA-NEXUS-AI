# Threat Model — FIFA Nexus AI

> **Scope**: Backend API service (`backend/`), ML inference pipeline (`ml/`), and infrastructure (`docker-compose.yml`).
> **Method**: STRIDE analysis against each trust boundary.
> **Date**: 2026-07-09

---

## Trust Boundaries

```
[Client Browser / Volunteer App]
         │  HTTPS
         ▼
[FastAPI API Gateway]  ──── X-API-Key ──▶  [Business Logic]
         │                                       │
         │                              [LightGBM Inference]
         │                              [OpenAI / Groq / Featherless]
         │                              [Policy Gate]
         │                                       │
         ▼                                       │
[PostgreSQL / PostGIS]   [Redis]   [Qdrant]  ◀──┘
```

**Four trust boundaries:**
1. **External → API** (internet or internal network → FastAPI)
2. **API → Database** (FastAPI → PostgreSQL)
3. **API → LLM Providers** (FastAPI → OpenAI / Groq / Featherless)
4. **API → Cache / VectorDB** (FastAPI → Redis / Qdrant)

---

## STRIDE Analysis

### Boundary 1: External → API

| STRIDE Threat | Likelihood | Impact | Mitigation in place | Residual Risk |
|---|---|---|---|---|
| **S**poofing — impersonating a legitimate client | Medium | High | `X-API-Key` header validated on every write endpoint. | **Medium** (Leaked key grants full write access until rotated) |
| **T**ampering — malformed request bodies | Low | Medium | Pydantic v2 schema validation; 422 on type errors. | **Low** (Pydantic handles invalid formats natively) |
| **R**epudiation — no audit trail of who called what | Medium | Low | `X-Correlation-ID` logged on every request. | **Low** (Logs track session trace; no per-user attribution due to shared key) |
| **I**nformation disclosure — error leakage | Low | Low | FastAPI default exception handlers; no stack traces in prod responses. | **Low** (Uncaught exceptions logged internally; clean error shapes returned) |
| **D**enial of service — request flooding | High | Medium | In-memory rate limiter per IP. | **Medium** (Limit is local; multiple replicas would have independent limits) |
| **E**levation of privilege — access escalation | Low | High | API authentication required for writes; reads are public. | **Low** (No administrative routes exist in the MVP) |

---

### Boundary 2: API → Database

| STRIDE Threat | Likelihood | Impact | Mitigation in place | Residual Risk |
|---|---|---|---|---|
| **S**poofing — connecting as wrong DB user | Low | High | Credentials via env vars; single restricted DB user. | **Low** (Containerized database instance connection is private) |
| **T**ampering — SQL injection | Low | High | SQLAlchemy ORM with parameterized queries throughout. | **Low** (No raw SQL strings constructed from input) |
| **I**nformation disclosure — DB credentials leakage | Low | High | Credentials not logged; `DATABASE_URL` in env only. | **Low** (Standard secure environment variables configuration) |
| **D**enial of service — connection pool exhaustion | Medium | Medium | SQLAlchemy connection pool with timeout limits. | **Low** (Managed connection pooling prevents server exhaustion) |

---

### Boundary 3: API → LLM Providers

| STRIDE Threat | Likelihood | Impact | Mitigation in place | Residual Risk |
|---|---|---|---|---|
| **S**poofing — response from a compromised provider | Low | High | HTTPS only; TLS cert validation via `httpx` defaults. | **Low** (Standard TLS prevents interception/spoofing) |
| **T**ampering — prompt injection via user content | Medium | Medium | Context builder assembles prompt from structured DB fields only (no free text from request body). | **Low** (Events payload JSON is validated, minimizing injection vectors) |
| **I**nformation disclosure — data leakage to provider | Medium | Medium | Accepted risk; provider ToS governs data handling. | **Medium** (Transmits data to third party; requires on-premise model to eliminate) |
| **D**enial of service — provider quota exhaustion | High | Low | Failover chain (OpenAI → Groq → Featherless → heuristic fallback). | **Low** (Heuristic fallback ensures continuous operation) |

---

### Boundary 4: API → Redis / Qdrant

| STRIDE Threat | Likelihood | Impact | Mitigation in place | Residual Risk |
|---|---|---|---|---|
| **T**ampering — corrupted cache entry | Low | Medium | Cache used for recommendations only; stale data expires. | **Low** (Short TTL on cached recommendation responses) |
| **D**enial of service — Redis unavailable | Low | High | Graceful fallback to local in-memory pubsub bus. | **Low** (Local pubsub bus handles streaming fallback cleanly) |

---

## Out of Scope

- Physical security of stadium infrastructure
- Network-level DDoS mitigation (handled at load balancer / CDN layer)
- Client-side security (browser, Volunteer App)

---

## Accepted Risks (Hackathon Context)

| Risk | Likelihood | Impact | Residual Risk | Justification |
|---|---|---|---|---|
| Shared API key | Medium | High | **Medium** | Suitable for internal/demo service; production would use per-user JWT/OIDC. |
| In-memory rate limiter | High | Medium | **Medium** | Correct for single instance; production would use Redis-backed limiter. |
| LLM data sharing | Medium | Medium | **Medium** | Third-party providers; acceptable under Render/demo terms. |
| No Alembic migrations | Low | Low | **Low** | `create_all()` used; acceptable for demo; production would require Alembic. |

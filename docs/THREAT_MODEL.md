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

| Threat | Risk | Mitigation in place | Residual risk |
|---|---|---|---|
| **S**poofing — impersonating a legitimate client | Medium | `X-API-Key` header validated on every write endpoint | Key is shared; a leaked key grants full write access until rotated |
| **T**ampering — malformed request bodies | Low | Pydantic v2 schema validation; 422 on type errors | None — Pydantic handles this |
| **R**epudiation — no audit trail of who called what | Low | `X-Correlation-ID` logged on every request | No per-user attribution (shared key) |
| **I**nformation disclosure — error messages leaking internals | Low | FastAPI default exception handlers; no stack traces in prod responses | Uncaught exceptions may leak model/filename via default handler |
| **D**enial of service — request flooding | Medium | In-memory rate limiter per IP | Rate limiter is not distributed; multiple replicas would not share limits |
| **E**levation of privilege — accessing admin-only routes | Low | No RBAC implemented; all authenticated calls have equal privilege | Future work: role-based access |

### Boundary 2: API → Database

| Threat | Risk | Mitigation in place | Residual risk |
|---|---|---|---|
| **S**poofing — connecting as wrong DB user | Low | Credentials via env vars; single DB user | No row-level security |
| **T**ampering — SQL injection | Low | SQLAlchemy ORM with parameterised queries throughout | None — no raw SQL |
| **I**nformation disclosure — DB credentials in logs | Low | Credentials not logged; `DATABASE_URL` in env only | Env vars visible to any process in the container |
| **D**enial of service — connection pool exhaustion | Low | SQLAlchemy connection pool with timeout | High traffic without connection pool limit could exhaust |

### Boundary 3: API → LLM Providers

| Threat | Risk | Mitigation in place | Residual risk |
|---|---|---|---|
| **S**poofing — response from a compromised provider | Medium | HTTPS only; TLS cert validation via `httpx` defaults | No provider response signing |
| **T**ampering — prompt injection via user-controlled content | Medium | Context builder assembles prompt from structured DB fields only (not free text from the request body) | Operational event `payload` field (JSON) feeds into context; malicious payload could influence reasoning |
| **I**nformation disclosure — stadium operational data sent to third party | Medium | Accepted risk; provider ToS governs data handling | Cannot be fully eliminated without on-premise LLM |
| **D**enial of service — provider quota exhaustion | Low | Failover chain (OpenAI → Groq → Featherless → heuristic); heuristic never fails | Heuristic output quality is lower |

### Boundary 4: API → Redis / Qdrant

| Threat | Risk | Mitigation in place | Residual risk |
|---|---|---|---|
| **T**ampering — corrupted cache entry | Low | Cache used for recommendations only; stale data expires | Corrupted entry served until TTL |
| **D**enial of service — Redis unavailable | Low | Graceful fallback to local pubsub bus | Fallback is not distributed |

---

## Out of Scope

- Physical security of stadium infrastructure
- Network-level DDoS mitigation (handled at load balancer / CDN layer)
- Client-side security (browser, Volunteer App)

---

## Accepted Risks (Hackathon Context)

| Risk | Justification |
|---|---|
| Shared API key | Suitable for internal/demo service; production would use per-user JWT/OIDC |
| In-memory rate limiter | Correct for single instance; production would use Redis-backed limiter |
| LLM data sharing | Third-party providers; acceptable under Render/demo terms |
| No Alembic migrations | `create_all()` used; acceptable for demo; production would require Alembic |

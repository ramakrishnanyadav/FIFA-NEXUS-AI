# Security Review — FIFA Nexus AI

> **Date**: 2026-07-09
> **Reviewer**: Internal engineering review
> **Scope**: Backend API, ML pipeline, infrastructure configuration

---

## Summary

| Area | Status | Notes |
|---|---|---|
| Authentication | ⚠️ Shared API key | Suitable for internal/demo; production would use JWT/OIDC |
| Authorisation | ⚠️ No RBAC | All authenticated callers have equal privilege |
| Input validation | ✅ | Pydantic v2 on all request bodies; 422 on violations |
| SQL injection | ✅ | SQLAlchemy ORM throughout; zero raw SQL |
| Secrets management | ✅ | All credentials via environment variables; none hardcoded |
| TLS | ✅ | Render deployment terminates TLS at the edge |
| Rate limiting | ⚠️ In-memory | Correct for single instance; distributed rate limiting is future work |
| Error handling | ✅ | No stack traces exposed in API responses |
| Logging | ✅ | Structured JSON; `Authorization` and API key headers not logged |
| Static analysis | ✅ | Bandit: 0 HIGH/MEDIUM issues; Ruff: 0 warnings |
| Dependency audit | See [DEPENDENCY_AUDIT.md](DEPENDENCY_AUDIT.md) | Real pip-audit output; findings documented with context |
| Container | ✅ | Non-root user (`appuser`, UID 10001); no privileged ports |

---

## Authentication

A shared `X-API-Key` header is required on all write endpoints. The key is validated against `settings.API_KEY` (set via environment variable).

**Limitation**: A shared key provides no per-user attribution. All callers appear identical in logs beyond their correlation ID.

**Production path**: Replace with JWT issued by an OIDC provider, with per-user claims and refresh token rotation.

---

## Authorisation

No RBAC is implemented. Any caller with a valid API key can perform any operation.

**Production path**: Add role claims to JWT, enforce at the route level using FastAPI dependency injection.

---

## Input Validation

All request bodies pass through Pydantic v2 models before reaching business logic. Invalid types, missing required fields, and out-of-range values are rejected with HTTP 422 before any DB interaction.

---

## Secrets

| Secret | Storage |
|---|---|
| `API_KEY` | Environment variable |
| `DATABASE_URL` | Environment variable |
| `REDIS_URL` | Environment variable |
| `OPENAI_API_KEY` | Environment variable |
| `GROQ_API_KEY` | Environment variable |
| `FEATHERLESS_API_KEY` | Environment variable |
| `QDRANT_URL` | Environment variable |

No secrets appear in source code, Docker images, or logs. `seed.py` contains mock hashes for local development only, clearly marked `# nosec`.

---

## Container Security

```dockerfile
RUN useradd --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser
```

- Non-root user with explicit UID
- Application binds to port 8001 (non-privileged)
- Internal ML service binds to `127.0.0.1` only (not exposed externally)

---

## Static Analysis Results

| Tool | Configuration | Result |
|---|---|---|
| Bandit | `bandit -r backend/ ml/` | 0 HIGH, 0 MEDIUM issues |
| Ruff | `ruff check backend/ ml/` | 0 warnings |

---

## Dependency Vulnerabilities

See **[docs/DEPENDENCY_AUDIT.md](DEPENDENCY_AUDIT.md)** for the full pip-audit output, per-package analysis, and fix status.

Summary: No vulnerabilities in direct project dependencies. Findings are in transitive dependencies (starlette via FastAPI) and development tooling (pytest, pip).

---

## API Key Storage & Client-Side Risk Assessment

The live operations dashboard (`index.html`) requires the operator to provide an API key to authorize request ingestion. 
- **Storage**: The API key is stored in the browser's `localStorage` to preserve session state across page reloads.
- **XSS Exposure Risk**: Because the dashboard is loaded via HTTP, any Cross-Site Scripting (XSS) vulnerability would allow an attacker to extract the API key from `localStorage`.
- **Mitigation & Future Path**: In production, the system must transition from static API keys to standard OAuth2/OIDC access tokens stored in secure, `HttpOnly`, `SameSite=Strict` cookies, preventing Javascript-based token extraction. For the current hackathon deployment, the use of `localStorage` is accepted and documented.

---

## Content Security Policy (CSP) & Accepted Risk

The application sets strict security headers via `SecurityHeadersMiddleware`, including `Content-Security-Policy`. 
- **Inline Event Handlers**: The dashboard layout (`index.html`) relies on several legacy inline event handlers (e.g. `onclick`, `onkeydown`) to bind user interface interactions.
- **CSP Directive**: To allow the dashboard to function without complete frontend refactoring, the CSP script directive includes `'unsafe-inline'` (`script-src 'self' 'unsafe-inline'`).
- **Accepted Risk**: While `'unsafe-inline'` increases vulnerability to XSS attacks, it is accepted for this prototype/demo stage. A complete frontend migration to dynamic event listeners (`addEventListener`) and the removal of `'unsafe-inline'` from the CSP header is a priority item on the post-hackathon security roadmap.

---

## Known Limitations (Not Defects)

| Limitation | Impact | Production path |
|---|---|---|
| Shared API key | No per-user identity | JWT / OIDC |
| In-memory rate limiter | Not synchronised across replicas | Redis-backed limiter |
| No Alembic | Schema changes require manual migration | Add Alembic |
| LLM data sharing | Stadium data sent to third-party providers | On-premise LLM |

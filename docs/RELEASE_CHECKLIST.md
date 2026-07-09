# Release Checklist — FIFA Nexus AI

This checklist must be executed and signed off prior to deploying any release tag to production environments.

---

## 1. Pre-Deployment Verification

### Code Quality & Security
- [ ] **Tests**: Run the test suite. All 40 tests must pass with zero failures.
  ```bash
  python -m pytest --cov=backend/app --cov-branch
  ```
- [ ] **Linter**: Verify zero warnings from Ruff.
  ```bash
  ruff check backend/ ml/
  ```
- [ ] **Security Scan**: Verify zero Medium/High findings from Bandit.
  ```bash
  bandit -r backend/ ml/
  ```
- [ ] **Dependency Audit**: Run a fresh `pip-audit` scan. Verify zero vulnerable runtime packages.
  ```bash
  pip-audit
  ```
- [ ] **Static Type Checking**: Run Mypy. Ensure all critical files type check.
  ```bash
  mypy backend/app --ignore-missing-imports --explicit-package-bases
  ```

---

## 2. Infrastructure & Database Setup

### Database State
- [ ] **Production Database**: Verify the target database is PostgreSQL with the PostGIS extension installed.
- [ ] **No Local SQLite fallback**: Verify that the production environment variables (`DATABASE_URL`) are loaded and local SQLite fallback does not trigger.
- [ ] **Migrations**: Execute any pending Alembic schema migrations:
  ```bash
  alembic upgrade head
  ```
- [ ] **Database Indexes**: Verify the presence of single-column and composite indexes:
  - `idx_snapshot_zone_recorded` on `(zone_id, recorded_at)`
  - `idx_event_zone_type_received` on `(zone_id, event_type, received_at)`
  - `idx_task_status_created` on `(status, created_at)`
  - `generated_at` on `Recommendation`

### Caching & Messaging
- [ ] **Redis Connection**: Verify `REDIS_URL` is set to the clustered Redis instance.
- [ ] **Redis Health**: Ping Redis to ensure availability:
  ```bash
  redis-cli -u $REDIS_URL ping
  ```

---

## 3. Third-Party LLM Configurations

### API Keys
- [ ] Verify `OPENAI_API_KEY`, `GROQ_API_KEY`, and `FEATHERLESS_API_KEY` are populated with production credentials.
- [ ] Ensure `settings.API_KEY` (shared secret for write API authentication) is set to a secure, dynamically generated value (not the default development key).

### Failover Settings
- [ ] Verify the failover ordering in `settings`: `OpenAI` (primary) → `Groq` (secondary) → `Featherless` (tertiary) → `Local Heuristic` (emergency fallback).

---

## 4. Observability & Monitoring

### Logging
- [ ] Verify the JSON formatter is active and structured logs are writing to standard output.
- [ ] Verify the log-level is set to `INFO`.
- [ ] Ensure that sensitive data (such as API keys or `Authorization` headers) are stripped from the logs.

### Metrics Exporters
- [ ] Verify Prometheus agent or log collectors (Datadog/Elastic) are configured to ingest structured log records containing `status_code`, `latency_ms`, and `correlation_id`.

---

## 5. Post-Deployment Verification (Smoke Checks)

- [ ] **Health Endpoint**: Request `GET /health` and confirm `status: "healthy"`.
- [ ] **Version Endpoint**: Request `GET /version` to ensure the correct Git SHA is deployed.
- [ ] **Auth Check**: Send a POST request to `/api/v1/telemetry` without an API key; verify it is blocked with HTTP 401.
- [ ] **Log Verification**: Search the logs to ensure a `X-Correlation-ID` header value propagates to the request's log records and database write operations.

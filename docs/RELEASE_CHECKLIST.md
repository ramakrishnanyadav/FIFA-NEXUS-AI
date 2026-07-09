# Release Checklist — FIFA Nexus AI

This checklist must be executed and signed off prior to deploying any release tag to production environments.

---

## 1. Pre-Deployment Verification

### Code Quality & Security
- [ ] **Tests**: Run the test suite. All 67 tests must pass with zero failures and branch coverage ≥ 75%.
  ```bash
  python -m pytest --cov=backend/app --cov-branch --cov-report=term-missing
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

### Build & Platform Compatibility
- [ ] **Python 3.12 Matrix**: Verify that the application builds and passes all tests in a Python 3.12 target environment to prevent syntax or runtime regressions in newer Python versions.
- [ ] **SBOM Verification**: Ensure that the CycloneDX SBOM (`docs/sbom.json`) is present, up to date with `requirements.txt` pins, and parses as valid JSON.

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

## 5. Accessibility & Frontend Assets

- [ ] **Skip Link**: Verify that the "Skip to main content" anchor is the first interactive element inside `<body>` and takes focus on `Tab`.
- [ ] **Reduced Motion**: Verify that all animations (`pulse-breach`, `animate-flow`, `animate-pulse`) are deactivated when the browser triggers `@media (prefers-reduced-motion: reduce)`.
- [ ] **Focus Styles**: Verify that all zones on the interactive SVG map display high-contrast outline focus rings when keyboard-tabbed.

---

## 6. Post-Deployment Verification (Smoke Checks)

- [ ] **Health Endpoint**: Request `GET /health` and confirm `status: "healthy"`.
- [ ] **Version Endpoint**: Request `GET /version` to ensure the correct Git SHA is deployed.
- [ ] **Auth Check**: Send a POST request to `/api/v1/telemetry` without an API key; verify it is blocked with HTTP 401.
- [ ] **Log Verification**: Search the logs to ensure a `X-Correlation-ID` header value propagates to the request's log records and database write operations.

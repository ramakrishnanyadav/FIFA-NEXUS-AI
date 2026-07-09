# Error Reference — FIFA Nexus AI

> All errors returned by the API follow RFC 7807 Problem Details format where applicable.
> HTTP status codes conform to RFC 9110.

---

## HTTP Errors

### 400 Bad Request

| Code | Trigger | Caller recovery |
|---|---|---|
| `400` | Idempotency key reused with different body | Retry with a new `Idempotency-Key` header, or omit the header |

---

### 401 Unauthorized

| Code | Trigger | Caller recovery |
|---|---|---|
| `401` | Missing or invalid `X-API-Key` header | Supply the correct API key in the `X-API-Key` header |

---

### 403 Forbidden

| Code | Trigger | Caller recovery |
|---|---|---|
| `403` | Attempting to apply a `POLICY_VIOLATION` recommendation | Do not apply recommendations with `validation_status != "VALIDATED"` |

---

### 404 Not Found

| Code | Trigger | Caller recovery |
|---|---|---|
| `404` | Route does not exist | Check the API reference; the path or method may be wrong |
| `404` | Resource ID not found (recommendation, task, zone) | Verify the UUID exists; it may have been deleted or never created |

---

### 409 Conflict

| Code | Trigger | Caller recovery |
|---|---|---|
| `409` | Task status transition is invalid (e.g., completing an already-completed task) | Fetch the current task state via `GET /tasks/{id}` before attempting a transition |

---

### 422 Unprocessable Entity

| Code | Trigger | Caller recovery |
|---|---|---|
| `422` | Request body fails Pydantic schema validation | Inspect the `detail` array in the response; each item identifies the field and violation |

Common validation failures:
- `zone_id` not a valid UUID
- `occupancy` below 0 or above `safe_capacity`
- Missing required field

---

### 429 Too Many Requests

| Code | Trigger | Caller recovery |
|---|---|---|
| `429` | Write rate limit exceeded (default: 100 requests / 60 seconds per IP) | Wait until the next window before retrying; the `Retry-After` header indicates the reset time |

> ℹ️ The `X-Correlation-ID` header is present even on 429 responses, so individual rate-limit events can be traced in logs.

---

### 500 Internal Server Error

| Code | Trigger | Caller recovery |
|---|---|---|
| `500` | Unhandled exception in business logic | Retry once after a short delay; if persistent, file an issue with the `X-Correlation-ID` from the response |
| `500` | Database commit failure | Automatic rollback has occurred; the request had no effect — safe to retry |
| `500` | LLM provider chain exhausted all fallbacks | Extremely rare; heuristic fallback should always succeed. Retry once |

---

## Application-Level Errors

### LLM Provider Failover

When all external providers (OpenAI, Groq, Featherless) are unavailable, the system automatically falls back to the **local heuristic engine**. This is not surfaced as an error to the caller — the recommendation is still produced, but `model_version` in the response will indicate `"heuristic"`.

### Redis Unavailability

When Redis is offline, real-time task events fall back to the **local pubsub bus**. Single-instance SSE clients continue to receive events. Multi-instance deployments will not receive cross-instance events during a Redis outage.

### Database Unavailability

When PostgreSQL is offline, the application falls back to **local SQLite** automatically. A warning log is emitted:

```json
{"level": "WARNING", "message": "PostgreSQL port offline. Falling back to local SQLite."}
```

This fallback is suitable for development and demo purposes. SQLite does not support GIS queries.

---

## Structured Log Errors

All server-side errors are logged in structured JSON format with the correlation ID:

```json
{
  "timestamp": "2026-07-09 12:00:00,000",
  "level": "ERROR",
  "message": "Failed to fetch recommendations",
  "module": "recommendations",
  "correlation_id": "a4e1e23f-6d63-46f9-86e8-18527ff130ea"
}
```

Use the `X-Correlation-ID` from the response header to locate the matching log line.

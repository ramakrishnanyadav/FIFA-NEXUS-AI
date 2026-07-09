# Error Reference — FIFA Nexus AI

> All errors returned by the API follow RFC 7807 Problem Details format where applicable.
> HTTP status codes conform to RFC 9110.

---

## HTTP Errors

### 400 Bad Request

- **Trigger**: Idempotency key reused with different request body.
- **Caller Recovery**: Retry with a new `Idempotency-Key` header value or omit the header.
- **Example Response**:
  ```json
  {
    "detail": "Idempotency key 'uuid-key-here' already used with a different request payload."
  }
  ```

---

### 401 Unauthorized

- **Trigger**: Missing or invalid `X-API-Key` header.
- **Caller Recovery**: Supply the correct API key in the `X-API-Key` header.
- **Example Response**:
  ```json
  {
    "detail": "Could not validate credentials"
  }
  ```

---

### 403 Forbidden

- **Trigger**: Attempting to apply a recommendation containing safety policy violations.
- **Caller Recovery**: Inspect the validation status and do not apply recommendations with `validation_status != "APPROVED"`.
- **Example Response**:
  ```json
  {
    "detail": "Recommendation cannot be applied due to POLICY_VIOLATION status."
  }
  ```

---

### 404 Not Found

- **Trigger**: Route does not exist or resource ID not found (recommendation, task, or zone).
- **Caller Recovery**: Verify the UUID exists and that the HTTP path/method is correct.
- **Example Response**:
  ```json
  {
    "detail": "Task with ID 11111111-1111-1111-1111-111111111111 not found"
  }
  ```

---

### 409 Conflict

- **Trigger**: Task status transition is invalid (e.g., completing an already-completed task).
- **Caller Recovery**: Fetch the current task state via `GET /tasks/{id}` before attempting a transition.
- **Example Response**:
  ```json
  {
    "detail": "Task is already in COMPLETED status"
  }
  ```

---

### 422 Unprocessable Entity

- **Trigger**: Request body fails Pydantic schema validation.
- **Caller Recovery**: Inspect the `detail` array in the response to identify the invalid field and violation constraints.
- **Example Response**:
  ```json
  {
    "detail": [
      {
        "type": "greater_than_equal",
        "loc": ["body", "telemetry", "count"],
        "msg": "Input should be greater than or equal to 0",
        "input": -5,
        "ctx": {
          "geq": 0
        }
      }
    ]
  }
  ```

---

### 429 Too Many Requests

- **Trigger**: Write rate limit exceeded (default: 100 requests / 60 seconds per IP).
- **Caller Recovery**: Wait until the next window before retrying; the `Retry-After` header indicates the reset time.
- **Example Response**:
  ```json
  {
    "detail": "Rate limit exceeded: 100 requests per 60 seconds."
  }
  ```

> ℹ️ The `X-Correlation-ID` header is present even on 429 responses, so individual rate-limit events can be traced in logs.

---

### 500 Internal Server Error

- **Trigger**: Unhandled exception in business logic or database commit failure.
- **Caller Recovery**: Retry once after a short delay; if persistent, contact stadium operations with the `X-Correlation-ID` from the response headers.
- **Example Response**:
  ```json
  {
    "detail": "Internal server error. Database transaction failed."
  }
  ```

---

## Application-Level Errors

### LLM Provider Failover

When all external providers (OpenAI, Groq, Featherless) are unavailable, the system automatically falls back to the **local heuristic engine**. This is not surfaced as an error to the caller — the recommendation is still produced, but `model_version` in the response will indicate `"fallback:heuristic:v1"`.

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
  "timestamp": "2026-07-10 12:00:00,000",
  "level": "ERROR",
  "message": "Failed to fetch recommendations",
  "module": "recommendations",
  "correlation_id": "a4e1e23f-6d63-46f9-86e8-18527ff130ea"
}
```

Use the `X-Correlation-ID` from the response header to locate the matching log line.

# ADR 001: FastAPI for High-Throughput Real-Time Operations

## Context and Problem Statement
We need an API framework to handle high-frequency crowd telemetry uploads (turnstiles and camera feeds) and support persistent server-sent events (SSE) streams for dispatcher queues. The framework must be fast, secure, modern, and provide self-documenting APIs.

## Decision Drivers
* **Throughput**: Telemetry events arrive concurrently every few seconds.
* **Concurrency**: Subscriptions to live event streams are long-lived and asynchronous.
* **Open Standards**: Out-of-the-box OpenAPI schemas and interactive Swagger UI.
* **Reliability**: Pydantic integration for compile-time schema safety and runtime validations.

## Considered Options
1. **Django REST Framework (DRF)**
2. **Flask / Quart**
3. **FastAPI (ASGI)**

## Decision Outcome
Chosen Option: **FastAPI**

### Rationale
* **ASGI Native**: Native async support allows handling thousands of concurrent open TCP channels (SSE streams) with minimal resource foot-print.
* **Pydantic Schemas**: Built-in support for input validation prevents malformed telemetry schema ingestion, raising 422 errors automatically.
* **Interactive Docs**: Auto-generated `/docs` Swagger page accelerates integration tests.

## Pros and Cons of Chosen Option

### Pros
* **Performance**: Speed on par with Go and Node.js.
* **Security**: Native dependency injection simplifies API key authentication.
* **Schema Contract Stability**: Guarantees contract stability using strict types.

### Cons
* Requires ASGI servers (like Uvicorn) which introduces small deployment differences from standard WSGI setups.

# ADR 004: Custom API Key Auth for High-Performance Telemetry Ingestion

## Context and Problem Statement
Crowd control operations are mission-critical. Sensor turnstiles and CCTV camera endpoints must upload telemetry with minimal latency. We need an authentication strategy that prevents unauthorized writes while avoiding the overhead of heavy session setups.

## Decision Drivers
* **Ingestion Latency**: Auth validation must take `< 1ms`.
* **Complexity**: Simple integration with embedded IoT devices.
* **Security**: Guards write endpoints (`POST /telemetry`, `POST /events`) against unauthorized tampering.

## Considered Options
1. **OAuth2 with JWT tokens**
2. **Session Cookies (Stateful)**
3. **Custom HTTP Header API Key (`X-API-Key`)**

## Decision Outcome
Chosen Option: **Custom HTTP Header API Key**

### Rationale
* **Sub-Millisecond Check**: Simply verifies the header string matches the system environment key in-memory. Zero database queries or cryptographic signature validations required per request.
* **IoT Native**: Easily configured in hardware clients without requiring multi-step OAuth handshake exchanges.
* **Stateless**: Perfect for scale-out ASGI worker instances.

## Pros and Cons of Chosen Option

### Pros
* Negligible latency impact.
* Highly reliable under high-throughput request rates.
* Straightforward key rotation via environment injection.

### Cons
* Keys are static. Mitigated by restricting API key validation strictly to write/mutate endpoints, leaving read endpoints public or protected separately.

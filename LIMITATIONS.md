# FIFA Nexus AI - Operational Scope & Limitations

A mature production-ready platform acknowledges its constraints, validation boundaries, and assumptions. This document defines the current scope of the FIFA Nexus AI project and outlines the roadmap toward a live production deployment.

---

## 1. Data Ingestion & Simulated Telemetry

### Current Scope
*   The interactive telemetry stream is generated using a synthetic stadium traffic simulator modeled on real Hard Rock Stadium entrance geometries (Gate A, Gate B, Concourse pathways, and Transport Hubs).
*   Mock sensors broadcast crowd counts to the FastAPI endpoint to simulate ingress load spikes.

### Real-World Production Roadmap
*   **Physical Sensors**: Integration with IP-camera crowd-counting analytics (e.g., OpenCV/YOLO edge processors), ticketing turnstile counts (RFID/NFC scan ticks), and Wi-Fi zone presence ping sensors.
*   **Ingestion Bus**: Routing raw HTTP endpoints through an enterprise message broker (e.g., Apache Kafka or AWS Kinesis) to handle raw parallel turnstile events under load spikes exceeding 50,000 pings/sec.

---

## 2. Evaluation Scope & Safety Validation

### Current Scope
*   The safety validation engine guarantees **100% recall of security policy overrides** (such as blocking volunteer dispatches when police escalation is required) *specifically on our curated validation dataset of 9 stadium SOP scenarios*.
*   Natural language safety queries are processed using keyword negation logic and regex patterns tailored to the SOP requirements.
*   **Incident Cooldown State**: To prevent telemetry floods from generating duplicate incidents, the system applies a 60-second cooldown per zone. This check is stateful; it queries the database event store directly to evaluate recent events. Thus, the cooldown window survives server restarts and processes correctly across clustered instances.

### Real-World Production Roadmap
*   **Semantic Policy Parsing**: Incorporating fine-tuned LLM policy classifiers (e.g. Llama-Guard or NeMo Guardrails) to parse complex linguistic patterns (e.g. *"without law enforcement"*, *"police unavailable"*) that keyword approaches might fail to evaluate.
*   **Formal Verification**: Hardening policy constraints using mathematical solver models (e.g. Z3 Theorem Prover) to formally prove that no generated volunteer dispatch task can violate stadium security protocols.

---

## 3. Local Offline Fallbacks

### Current Scope
*   The codebase supports a highly resilient **local offline fallback mode** to run during local deployments where heavy docker daemons (PostgreSQL, Redis, Qdrant) are offline.
*   The system uses database-backed SQLite migrations, local in-memory async message buses, and localized vector SOP collections.

### Real-World Production Roadmap
*   **Database**: Production instances rely on Geo-Redundant PostgreSQL clusters with active-passive replication.
*   **In-Memory caching**: Redis Cluster configuration with multi-node replication (primary-replica failover) to secure sub-millisecond Canonical State access.
*   **Vector Engine**: High-availability Qdrant Cloud or AWS OpenSearch collections with semantic partition indices.

---

## 4. Security & Authentication

### Current Scope
*   The local slice provides basic CORS middleware (`allow_origins=["*"]`) and mock identity headers for testing convenience.

### Real-World Production Roadmap
*   **OAuth2 / OIDC**: Integration with enterprise Identity Providers (IDPs) such as Okta, Keycloak, or Azure AD.
*   **TLS Encryption**: Enforcing HTTPS (TLS 1.3) across all REST endpoints and SSE streams.
*   **Role-Based Access Control (RBAC)**: Enforcing strict column and row-level database security permissions matching user roles (e.g. preventing volunteers from viewing other gate telemetry).

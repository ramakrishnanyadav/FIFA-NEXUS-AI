# Architecture Design & Sequence Flows

FIFA Nexus AI is an event-driven, proactive operational intelligence platform that monitors crowd densities, predicts bottlenecks, and dispatches safety-validated recommendations.

## Component Overview

1. **Ingestion Gateway (FastAPI)**: Accepts high-frequency turnstile/camera telemetry, persists to PostgreSQL event store, and caches state in Redis.
2. **Predictive Engine (LightGBM)**: Predicts zone occupancies 15-30 minutes into the future based on sliding-window timeseries history.
3. **Context Builder (RAG)**: Combines live zone occupancy metrics, predicted trends, and related security/SOP protocols retrieved from Qdrant Vector database.
4. **AI Reasoning Agent (GPT-4o-mini)**: Explores candidate responses, evaluates impact, and proposes structured action plans.
5. **Multi-Objective Optimizer**: Ranks candidate actions using a mathematical weight function scoring risk, cost, and effectiveness.
6. **Deterministic Safety Gate**: Intercepts AI proposals, validates them against static crowd/security rule policies, and blocks any violations.
7. **Task Dispatcher**: Publishes approved actions to ground volunteer teams via Server-Sent Events (SSE).

## Telemetry to Task Dispatch Sequence Flow

```mermaid
sequenceDiagram
    autonumber
    actor Sensor as Camera / Turnstile
    participant API as Ingestion API (FastAPI)
    participant Cache as Canonical Cache (Redis)
    participant ML as ML Inference Service (LightGBM)
    participant RAG as Context Builder (Qdrant)
    participant AI as Reasoning Agent (GPT-4o-mini)
    participant Gate as Policy Safety Gate
    actor Op as Venue Operator (Dashboard)
    participant Stream as SSE Stream (LocalPubSubBus)
    actor Volunteer as Ground Volunteer

    Sensor->>API: POST /api/v1/telemetry (Surge)
    API->>Cache: Set current_occupancy & ZADD time-series
    API->>ML: POST /predict (current occupancy + trends)
    ML-->>API: Occupancy predictions (15m, 30m) & Risk Score
    API->>RAG: Retrieve related SOPs & Guidelines
    RAG-->>API: Context Text
    API->>AI: Evaluate Strategy (Context + Predictions)
    AI-->>API: Proposed Actions (Structured JSON)
    API->>Gate: Validate candidate actions
    Gate-->>API: VALIDATED / POLICY_VIOLATION status
    API->>Op: Push Notification via SSE
    Op->>API: POST /api/v1/recommendations/{id}/apply
    API->>Stream: Publish Volunteer Tasks (SSE)
    Stream->>Volunteer: Display Tasks in Queue
```

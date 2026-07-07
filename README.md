# FIFA Nexus AI - Predictive Operational Intelligence Platform

FIFA Nexus AI is an event-driven predictive operational intelligence platform built for the FIFA World Cup 2026. It proactively resolves spectator crowd congestion and stadium bottlenecks by combining real-time turnstile telemetry, LightGBM forecasting, LangGraph AI reasoning, and a zero-LLM deterministic policy validation safety gate.

---

## 🧭 Project Navigation Hub

*   **Engineering Core**:
    *   [Why This Wins Case](file:///c:/Users/Ramakrishna/OneDrive/Pictures/java/Documents/Projects/week4/docs/WHY_THIS_WINS.md) (Core technical case, GenAI utility, and architectural novelties).
    *   [Innovation & Design Architecture](file:///c:/Users/Ramakrishna/OneDrive/Pictures/java/Documents/Projects/week4/docs/innovation.md) (Structural design and predictive context boundaries).
    *   [System Evaluation & Benchmarks](file:///c:/Users/Ramakrishna/OneDrive/Pictures/java/Documents/Projects/week4/docs/evaluation.md) (ML forecast baselines, RAG search precision, and AI schema error rates).
    *   [Engineering Verification Walkthrough](file:///c:/Users/Ramakrishna/OneDrive/Pictures/java/Documents/Projects/week4/docs/walkthrough.md) (Latency benchmarks, optimization math, and the live storyboard demo script).
*   **Accessibility Compliance**: Built-in keyboard navigation (`tabindex`, focus rings), live screen reader regions (`aria-live="polite"`), and multi-lingual UI translation (English, Spanish, French) implemented on the Operator Dashboard.

---

## 🏗️ System Architecture & Data Flow

FIFA Nexus AI orchestrates predictive events through a decoupled, event-driven pipeline:

```mermaid
graph TD
    %% Telemetry Ingestion
    subgraph Ingestion [Ingestion Layer]
        Sensors[Turnstiles & Cameras] -->|REST POST /telemetry| IngestAPI[FastAPI Gateway]
        IngestAPI -->|Append Event| EventStore[(PostgreSQL Event Store)]
    end

    %% State & Predictions
    subgraph Cache [Volatile Cache & Forecasts]
        IngestAPI -->|Update| RedisCache[(Redis: Canonical State)]
        RedisCache -->|Sliding-Window State| MLPredict[LightGBM Predictor]
        MLPredict -->|Forecast Curves| RedisCache
        MLPredict -->|Archived Snapshot| PostgresDB[(PostgreSQL Metrics)]
    end

    %% Context & AI reasoning
    subgraph CoreAI [Reasoning & Safety Gates]
        RedisCache -->|Live Context| ContextBuilder[Context Builder]
        QdrantDB[(Qdrant Vector DB)] -.->|Search SOPs & Maps| ContextBuilder
        ContextBuilder -->|Payload| LangGraphAI[LangGraph AI Reasoner]
        LangGraphAI -->|Proposals| ConstraintScorer[Constraint Optimizer]
        ConstraintScorer -->|Ranked Options| PolicyGate[Rules Safety Gate]
        PolicyGate -->|Validated Recommendation| PostgresDB
    end

    %% Dispatch & Loop
    subgraph GroundOps [Operations Dispatch]
        PostgresDB -->|SSE Feed /stream| Dashboard[Live Dashboard]
        Dashboard -->|Operator Approval| DispatchEngine[Task Dispatcher]
        DispatchEngine -->|SSE Task Push| VolunteerApp[Volunteer App]
        VolunteerApp -->|Mark Complete & Feedback| FeedbackLoop[Feedback Collector]
        FeedbackLoop -->|Update Analytics| PostgresDB
    end

    classDef db fill:#161F30,stroke:#334155,stroke-width:1px,color:#fff;
    classDef api fill:#0f172a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    class EventStore,RedisCache,PostgresDB,QdrantDB db;
    class IngestAPI,LangGraphAI,PolicyGate,Dashboard api;
```

---

## 📂 Folder Structure

```
fifa-nexus-ai/
├── backend/                  # FastAPI REST + SSE Application & Dashboard
│   ├── app/
│   │   ├── api/              # API Route Handlers (telemetry, events, recommendations, tasks, zones)
│   │   ├── core/             # Database connection pooling, configurations, seeders
│   │   ├── models/           # SQLAlchemy models representing normalized PostGIS schemas
│   │   ├── schemas/          # Pydantic schemas representing request/responses
│   │   ├── services/         # Context compiler, optimization engine, rule checks
│   │   └── static/           # Interactive Operator Dashboard (HTML, Tailwind CSS, SSE Client)
│   └── tests/                # Automated pytest suite
├── ml/                       # Machine Learning Pipeline
│   └── src/                  # LightGBM predictor stub & synthetic generator script
├── docs/                     # Unified Documentation Repository (Benchmarks, Innovation, Case, Walkthrough)
└── docker-compose.yml        # Docker compose stack for Postgres (with PostGIS), Redis, Qdrant
```

---

## 🚀 Quickstart Guide

### Step 1: Start the Local Database Stack
Launch PostgreSQL/PostGIS, Redis, and Qdrant containers:
```bash
docker-compose up -d
```

### Step 2: Set up Environment & Install Dependencies
Create a virtual environment and install packages using Python 3.11:
```bash
py -3.11 -m venv venv
.\venv\Scripts\activate
pip install -r backend/requirements.txt
```

### Step 3: Run the ML Inference Service
Start the LightGBM prediction service on port 8001:
```bash
python -m ml.src.inference
```

### Step 4: Run the Backend & Dashboard Server
Start the main FastAPI app on port 8000. On startup, it automatically creates the PostGIS tables and seeds lookups, stadium entities, zones, and mock accounts:
```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

### Step 5: Open the Operations Dashboard
Open your web browser and navigate to `http://localhost:8000`.

---

## 🧪 Automated Verification

To run all automated validations, calculations, and pipeline triggers:
```bash
pytest backend/tests/
```

To run the accuracy and safety validation evaluation tests displaying performance statistics:
```bash
pytest -s backend/tests/test_evaluation.py
```

---

## 🎯 Live Demo Presentation Storyboard

Use this timeline to demonstrate the entire Event-Driven Operational Intelligence pipeline:

*   **[Minute 0] Monitoring Baseline**: Open the dashboard. You will see Hard Rock Stadium zones showing `0` occupancy (Green clear state on the map).
*   **[Minute 1] Ingress Crowd Spike**: Click **"Run Ingress Simulation Wave"**. Turnstile camera sensors stream increasing counts at Gate A (480 ➔ 660 ➔ 864 ➔ 1020).
*   **[Minute 2] ML Risk Alert**: The SSE log registers `CROWD_DENSITY_HIGH` as occupancy breaches 80%. Gate A turns **glowing red** on the map.
*   **[Minute 3] AI Recommendation**: The Decision Support panel displays a recommendation: *"Deploy directional signage at Gate A and redirect traffic to Gate B."* Shows before/after impact (Wait time reduced from **18 min to 7 min**).
*   **[Minute 4] Policy Check**: Confirm safety status says `VALIDATED` (confirming Gate B capacity was checked and is safe).
*   **[Minute 5] Operator Approval**: Click **"Approve & Dispatch Tasks"**, sending tasks to the active Volunteer Queue.
*   **[Minute 6] Resolution**: Click **"Mark Completed"** on the volunteer dispatch to close the loop and feed feedback into the database.

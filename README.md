<div align="center">

<h1>⚽ FIFA Nexus AI</h1>
<h3>Predictive Operational Intelligence Platform · FIFA World Cup 2026</h3>

<p>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white" />
  <img src="https://img.shields.io/badge/LightGBM-ML-02569B?style=for-the-badge&logo=lightgbm&logoColor=white" />
</p>
<p>
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Agent-2EA44F?style=for-the-badge&logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-7.0-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
</p>
<p>
  <img src="https://img.shields.io/badge/Qdrant-VectorDB-FF6135?style=for-the-badge&logo=qdrant&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/Pytest-7+-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/SSE-Realtime-000000?style=for-the-badge&logo=socket.io&logoColor=white" />
</p>

<br/>

> **FIFA Nexus AI** proactively resolves crowd congestion and stadium bottlenecks at the FIFA World Cup 2026 by combining real-time sensor telemetry, LightGBM crowd forecasting, LangGraph AI reasoning, and a deterministic policy safety gate — delivering human-supervised AI decisions in a closed-loop operations workflow.

</div>

---

## 🧭 Documentation Hub

| Document | Description |
|---|---|
| [WHY_THIS_WINS.md](docs/WHY_THIS_WINS.md) | Core technical case, GenAI utility, and architectural novelties |
| [innovation.md](docs/innovation.md) | Structural design and predictive context boundaries |
| [evaluation.md](docs/evaluation.md) | ML forecast baselines, safety gate validation, and benchmark methodology |
| [walkthrough.md](docs/walkthrough.md) | Latency analysis, optimization engine rationale, and live demo storyboard |

---

## 🏗️ Architecture & Data Flow

FIFA Nexus AI orchestrates an event-driven pipeline from sensor to dispatch:

```mermaid
graph TD
    subgraph Ingestion [Ingestion Layer]
        Sensors[Turnstiles & Cameras] -->|REST POST /telemetry| IngestAPI[FastAPI Gateway]
        IngestAPI -->|Append Event| EventStore[(PostgreSQL Event Store)]
    end

    subgraph Cache [Volatile Cache & Forecasts]
        IngestAPI -->|Update| RedisCache[(Redis: Canonical State)]
        RedisCache -->|Sliding-Window State| MLPredict[LightGBM Predictor]
        MLPredict -->|Forecast Curves| RedisCache
        MLPredict -->|Archived Snapshot| PostgresDB[(PostgreSQL Metrics)]
    end

    subgraph CoreAI [Reasoning & Safety Gates]
        RedisCache -->|Live Context| ContextBuilder[Context Builder]
        QdrantDB[(Qdrant Vector DB)] -.- |Search SOPs & Maps| ContextBuilder
        ContextBuilder -->|Payload| LangGraphAI[LangGraph AI Reasoner]
        LangGraphAI -->|Proposals| ConstraintScorer[Constraint Optimizer]
        ConstraintScorer -->|Ranked Options| PolicyGate[Rules Safety Gate]
        PolicyGate -->|Validated Recommendation| PostgresDB
    end

    subgraph GroundOps [Operations Dispatch]
        PostgresDB -->|SSE Feed /stream| Dashboard[Live Dashboard]
        Dashboard -->|Operator Approval| DispatchEngine[Task Dispatcher]
        DispatchEngine -->|SSE Task Push| VolunteerApp[Volunteer Queue]
        VolunteerApp -->|Mark Complete| FeedbackLoop[Feedback Collector]
        FeedbackLoop -->|Update Analytics| PostgresDB
    end

    classDef db fill:#161F30,stroke:#334155,stroke-width:1px,color:#fff;
    classDef api fill:#0f172a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    class EventStore,RedisCache,PostgresDB,QdrantDB db;
    class IngestAPI,LangGraphAI,PolicyGate,Dashboard api;
```

---

## 🛠️ Technology Stack

### Backend & API
| Technology | Role |
|---|---|
| ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white) | Async REST API gateway — handles telemetry ingestion, recommendations, tasks, and SSE streams |
| ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white) | ORM layer with dual PostgreSQL/SQLite dialect support for graceful offline fallback |
| ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white) | Primary production database; supports PostGIS geometry and JSONB columns |
| ![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white) | Canonical zone state cache; replaced by in-process asyncio queue when offline |
| ![Pydantic](https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white) | Strict input validation across all API request/response schemas |

### Artificial Intelligence & Machine Learning
| Technology | Role |
|---|---|
| ![OpenAI](https://img.shields.io/badge/OpenAI_GPT--4o-412991?logo=openai&logoColor=white) | LLM backend for adaptive operations strategy generation |
| ![LangGraph](https://img.shields.io/badge/LangGraph_Agent-2EA44F?logo=langchain&logoColor=white) | Multi-step AI reasoning agent with SOP retrieval and fallback heuristics |
| ![LightGBM](https://img.shields.io/badge/LightGBM-Predictor-02569B?logo=lightgbm&logoColor=white) | Gradient-boosted crowd occupancy forecasting trained on synthetic stadium telemetry |
| ![Qdrant](https://img.shields.io/badge/Qdrant-VectorDB-FF6135?logo=qdrant&logoColor=white) | Vector search engine for SOP document retrieval (RAG pipeline) |

### Safety & Validation Layer
| Component | Role |
|---|---|
| **Constraint Optimizer** | Scores candidate actions by occupancy risk, accessibility cost, and safety penalties |
| **Rules Safety Gate** | Deterministic policy engine — zero AI-generated actions pass dispatch without passing explicit policy checks |
| **Idempotency Guard** | Blocks duplicate telemetry writes at identical timestamps |
| **Incident Cooldown** | Database-backed 60-second cooldown preventing duplicate recommendation storms |

### Infrastructure & Observability
| Technology | Role |
|---|---|
| ![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white) | Compose stack for PostgreSQL/PostGIS, Redis, and Qdrant |
| ![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?logo=pytest&logoColor=white) | Automated test suite — ML accuracy bounds, safety gate recall, and pipeline integration |
| **Structured JSON Logging** | `correlation_id`-tagged log records across all services for distributed tracing |
| **SSE Event Bus** | Real-time Server-Sent Events bridge for live dashboard feeds and volunteer task pushes |

---

## 📂 Project Structure

```
fifa-nexus-ai/
├── backend/                     # FastAPI REST + SSE Application & Dashboard
│   ├── app/
│   │   ├── ai/                  # LangGraph agent & Qdrant vector search
│   │   ├── api/                 # Route handlers: telemetry, events, recommendations, tasks, zones, assistant
│   │   ├── core/                # Database pooling, config, structured logging, seed scripts
│   │   ├── models/              # SQLAlchemy ORM models (PostGIS-compatible schemas)
│   │   ├── schemas/             # Pydantic schemas for strict request/response validation
│   │   ├── services/            # Context builder, optimizer, rules engine, predictor, recommender
│   │   └── static/              # Operator Dashboard (HTML + SSE client)
│   └── tests/                   # Pytest suite: evaluation benchmarks + pipeline integration
├── ml/
│   └── src/                     # LightGBM training pipeline & synthetic data generator
├── docs/                        # Engineering documentation (benchmarks, innovation, walkthrough)
├── docker-compose.yml           # Local stack: PostgreSQL/PostGIS + Redis + Qdrant
├── pytest.ini                   # Test configuration with warning filters
└── LIMITATIONS.md               # Honest scope boundaries and production delta notes
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (for PostgreSQL, Redis, Qdrant)

### Step 1 — Start Local Services
```bash
docker-compose up -d
```

### Step 2 — Install Dependencies
```bash
py -3.11 -m venv venv
.\venv\Scripts\activate         # Windows
# source venv/bin/activate       # macOS / Linux
pip install -r backend/requirements.txt
```

### Step 3 — Start ML Inference Service
```bash
python -m ml.src.inference
```

### Step 4 — Start the Backend Server
```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```
> On first launch, the server automatically creates all schema tables and seeds stadium zones, roles, and mock accounts.

### Step 5 — Open the Dashboard
```
http://localhost:8000
```

---

## 🧪 Running Tests

```bash
# Run full test suite
pytest backend/tests/

# Run evaluation benchmarks (prints ML accuracy and safety recall)
pytest -s backend/tests/test_evaluation.py
```

---

## 🎯 Live Demo Walkthrough

The dashboard tells a complete operations story in under 6 minutes:

| Step | Action | Observable Outcome |
|---|---|---|
| **1. Baseline** | Open dashboard | All 5 stadium zones show green nominal occupancy |
| **2. Crowd Spike** | Click **Run Ingress Simulation Wave** | Gate A occupancy climbs: 480 → 660 → 864 → 1,020 |
| **3. ML Alert** | Watch SSE log | `CROWD_DENSITY_HIGH` event fires; Gate A pulses red on the map |
| **4. AI Recommendation** | Decision Support panel | AI generates: *"Deploy signage at Gate A, redirect to Gate B"* with wait-time reduction estimate |
| **5. Evidence** | Click **View SOP Context** | RAG evidence document SOP-744 displayed in modal |
| **6. Reject & Reroute** | Click **Reject** | AI re-reasons and generates alternative strategy with rationale |
| **7. Approve** | Click **Approve & Dispatch** | Volunteer tasks appear in ground dispatch queue |
| **8. Fan Query** | Ask chat: *"Where is the fastest entrance?"* | Assistant queries live zone data and returns lowest-occupancy gate |
| **9. Resolve** | Click **Mark Completed** | Incident closes; feedback logged to database |

---

## ⚠️ Known Limitations

See [LIMITATIONS.md](LIMITATIONS.md) for an honest assessment of scope boundaries, including offline fallback caveats, SQLite concurrency constraints, and production delta notes.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

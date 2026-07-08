# ADR 006: Deferred Database Migrations in MVP Release

## Context and Problem Statement
We need to manage database schema updates as models evolve. The codebase list `alembic` in `requirements.txt`. However, during the initial MVP release phases, the schema is created code-first using SQLAlchemy's reflection (`Base.metadata.create_all`) on startup. We need to document why migrations are deferred and how we plan to manage schemas in production.

## Decision Drivers
* **Deployment Velocity**: Fast iterative updates on transient dev environments.
* **Simplicity**: Prevent deployment overhead during initial staging launch.
* **Production Integrity**: Ensure schema modifications do not drop active operational tables.

## Decision Outcome
We decided to **defer versioned migration scripts (Alembic) to the next release phase** and rely on SQLAlchemy table reflection for the MVP demo:

### 1. Current Reflection Strategy
* On startup, the application runs `Base.metadata.create_all(bind=engine)` inside the lifespan manager.
* This safely creates missing tables (e.g. `zones`, `telemetry_snapshots`, `operational_events`, `tasks`, `feedback`) if they do not exist.
* It does NOT mutate existing columns or perform migrations on altered schemas.

### 2. Next Phase Migration Plan
* When transitioning to production, we will execute `alembic init alembic` to create the migration environment.
* Autogenerate initial migration revision comparing models against the existing schema:
  `alembic revision --autogenerate -m "Initial schema structure"`
* Integrate migration execution `alembic upgrade head` into the Docker `start.sh` entrypoint, replacing the start-up reflection call.

## Pros and Cons of Chosen Option

### Pros
* Zero migration configuration overhead for developers during the hackathon/MVP phase.
* Bulletproof setup on fresh instances (tables boot up automatically).

### Cons
* Column mutations or table additions require manual `ALTER TABLE` commands or database drops in the current staging environment. This constraint is documented.

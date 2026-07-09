import os
from datetime import datetime, UTC
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.core.database import engine, Base, async_session_maker, USE_SQLITE, USE_REDIS
from backend.app.core.seed import seed_initial_data
from backend.app.core.logging import logger, CorrelationIdMiddleware
from backend.app.core.rate_limit import RateLimitMiddleware, SecurityHeadersMiddleware
from backend.app.api import api_router

# Track startup time for uptime calculations
START_TIME = datetime.now(UTC)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern lifespan event handler replacing deprecated startup/shutdown events.
    Verifies database connection and creates tables, performs diagnostics,
    seeds data in development, and handles clean resources teardown on exit.
    """
    logger.info("--- [SYSTEM STARTUP DIAGNOSTICS] ---")
    db_mode = "SQLite (Local Fallback Mode Enabled)" if USE_SQLITE else "PostgreSQL (Production)"
    logger.info(f"Database mode: {db_mode}")

    # Database schema check and table creation
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema successfully verified & tables created.")

    # Redis diagnostics
    redis_mode = "Offline (Local Fallback Mode Enabled)" if not USE_REDIS else "Online (Cache Active)"
    logger.info(f"Redis mode: {redis_mode}")

    # LLM diagnostics
    llm_status = "Configured (Live Inference)" if settings.is_llm_configured else "Missing / Mocked (Heuristics Fallback Active)"
    logger.info(f"LLM Status: {llm_status}")

    # Seeding gate guarded by ENVIRONMENT setting
    if settings.ENVIRONMENT == "development":
        async with async_session_maker() as session:
            await seed_initial_data(session)
        logger.info("Database initial seed complete.")
    else:
        logger.info(f"Skipping auto-seeding in {settings.ENVIRONMENT} environment.")
    logger.info("------------------------------------")

    yield

    # Clean shutdown tasks
    await engine.dispose()
    logger.info("Database connection pool successfully disposed on exit.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Apply TrustedHostMiddleware and Security Hardening Middlewares
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.onrender.com", "testserver"]
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Correlation ID Middleware
app.add_middleware(CorrelationIdMiddleware)

# Set CORS origins with strict domain access control — added last to run outermost in middleware execution order
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "https://fifa-nexus-ai.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount Static assets directory for the dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Cache git commit version on startup to prevent spawning subprocesses on every /version request
GIT_COMMIT = "unknown"
try:
    import subprocess
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    if result.returncode == 0:
        GIT_COMMIT = result.stdout.strip()
    else:
        GIT_COMMIT = os.getenv("RENDER_GIT_COMMIT", "7f99f86")
except Exception:
    GIT_COMMIT = os.getenv("RENDER_GIT_COMMIT", "7f99f86")


@app.get("/")
async def serve_dashboard():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/health")
async def health_check():
    """
    Public health check endpoint returning basic service status.
    No internal topology or configuration secrets are disclosed.
    """
    return {
        "status": "healthy",
        "api_key_configured": bool(settings.API_KEY)
    }


from fastapi import Depends
from typing import Annotated
from backend.app.core.auth import verify_api_key

@app.get("/health/details")
async def health_details(
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Private diagnostic endpoint disclosing database, cache, and third-party LLM service states.
    Authorized with the write API key.
    """
    uptime_seconds = (datetime.now(UTC) - START_TIME).total_seconds()
    llm_status = "live" if settings.is_llm_configured else "mocked_fallback"
    vector_status = "mocked_fallback"
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "database": "sqlite_fallback" if USE_SQLITE else "postgresql",
        "db_type": "sqlite" if USE_SQLITE else "postgresql",
        "redis": "offline" if not USE_REDIS else "online",
        "redis_status": "offline_fallback" if not USE_REDIS else "online",
        "llm": llm_status,
        "vector": vector_status,
        "uptime": f"{uptime_seconds:.1f}s",
        "api_key_configured": bool(settings.API_KEY)
    }


@app.get("/version")
async def version_endpoint():
    """
    Serve cached version metadata without subprocess overhead.
    """
    return {
        "version": "1.0.0",
        "build": "prod-build",
        "git_commit": GIT_COMMIT
    }




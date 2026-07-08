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
from backend.app.core.logging import logger
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

    # OpenAI API Key diagnostics
    openai_status = "Configured (Live Inference)" if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "mock-key-for-now" else "Missing / Mocked (Heuristics Fallback Active)"
    logger.info(f"OpenAI API Key: {openai_status}")

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

# Set CORS origins with strict domain access control
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

# Apply TrustedHostMiddleware and Security Hardening Middlewares
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.onrender.com", "testserver"]
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Include API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount Static assets directory for the dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_dashboard():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/health")
async def health_check():
    uptime_seconds = (datetime.now(UTC) - START_TIME).total_seconds()

    # Check LLM configuration
    llm_status = "live" if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "mock-key-for-now" else "mocked_fallback"
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




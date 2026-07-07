from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import engine, Base

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Set CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For MVP, allow all origins. Harden in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.core.database import async_session_maker
from backend.app.core.seed import seed_initial_data

@app.on_event("startup")
async def startup_event():
    # 1. Database connection check and tables creation
    from backend.app.core.database import USE_SQLITE, USE_REDIS
    print("\n--- [SYSTEM STARTUP DIAGNOSTICS] ---")
    db_mode = "SQLite (Local Fallback Mode Enabled)" if USE_SQLITE else "PostgreSQL (Production)"
    print(f"[*] Database mode: {db_mode}")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[+] Database schema successfully verified & tables created.")
    
    # 2. Redis connection diagnostics
    redis_mode = "Offline (Local Fallback Mode Enabled)" if not USE_REDIS else "Online (Cache Active)"
    print(f"[*] Redis mode: {redis_mode}")
    
    # 3. Model and API Key diagnostics
    openai_status = "Configured (Live Inference)" if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "mock-key-for-now" else "Missing / Mocked (Heuristics Fallback Active)"
    print(f"[*] OpenAI API Key: {openai_status}")
    
    # 4. Run database seed operations
    async with async_session_maker() as session:
        await seed_initial_data(session)
    print("[+] Database initial seed complete.")
    print("------------------------------------\n")


@app.on_event("shutdown")
async def shutdown_event():
    await engine.dispose()
    print("[-] Database connection pool successfully disposed on exit.")


# Track startup time for uptime calculations
START_TIME = datetime.utcnow()


@app.get("/health")
async def health_check():
    from backend.app.core.database import USE_SQLITE, USE_REDIS
    uptime_seconds = (datetime.utcnow() - START_TIME).total_seconds()
    
    # Check LLM configuration
    llm_status = "live" if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "mock-key-for-now" else "mocked_fallback"
    
    # Check Vector database connectivity fallback status
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
        "uptime": f"{uptime_seconds:.1f}s"
    }

from backend.app.api import api_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Include API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount Static assets directory for the dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_dashboard():
    return FileResponse(os.path.join(static_dir, "index.html"))



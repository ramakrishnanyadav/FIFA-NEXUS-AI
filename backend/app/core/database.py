import socket
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
import redis.asyncio as aioredis
from qdrant_client import QdrantClient
from backend.app.core.config import settings
from backend.app.core.logging import logger

# Global flag to toggle SQLite fallback
USE_SQLITE = False
# Global flag to toggle Redis fallback
USE_REDIS = True
database_url = settings.DATABASE_URL

try:
    # Fast TCP check to verify PostgreSQL is listening
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        s.connect((settings.POSTGRES_HOST, settings.POSTGRES_PORT))
        logger.info("Successfully connected to PostgreSQL. Using Postgres database.")
except Exception:
    logger.warning("PostgreSQL port offline. Falling back to local SQLite database: local_stadium.db")
    database_url = "sqlite+aiosqlite:///local_stadium.db"
    USE_SQLITE = True

try:
    # Fast TCP check to verify Redis is listening
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        s.connect((settings.REDIS_HOST, settings.REDIS_PORT))
        logger.info("Successfully connected to Redis. Using Redis cache.")
except Exception:
    logger.warning("Redis port offline. Bypassing Redis cache writes to avoid connection timeouts.")
    USE_REDIS = False


# SQLAlchemy Async Engine and Session Setup
engine = create_async_engine(
    database_url,
    echo=False,
    future=True
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


# FastAPI Dependency for Database Sessions
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

# Redis Async Connection
def get_redis_client() -> aioredis.Redis:
    return aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )

# Qdrant Client (Uses synchronous client by default, client wraps async calls)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT
    )

import asyncio

class LocalPubSubBus:
    def __init__(self):
        self.listeners = []

    def subscribe(self, queue: asyncio.Queue):
        self.listeners.append(queue)

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self.listeners:
            self.listeners.remove(queue)

    def publish(self, message: str):
        for queue in self.listeners:
            try:
                queue.put_nowait(message)
            except Exception:
                pass  # nosec B110

local_pubsub_bus = LocalPubSubBus()



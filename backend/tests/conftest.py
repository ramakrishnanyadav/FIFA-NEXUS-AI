import os
# Configure test environment defaults before any app components are imported
os.environ.setdefault("API_KEY", "fifanexus_api_key_2026")
os.environ.setdefault("ENVIRONMENT", "test")
# Force PostgreSQL port check to fail to evaluate USE_SQLITE = True for test models compilation
os.environ["POSTGRES_PORT"] = "9999"


import pytest
import asyncio

@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


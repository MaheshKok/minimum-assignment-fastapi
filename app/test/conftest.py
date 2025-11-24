"""
Pytest configuration and fixtures following kkb_fastapi pattern.
"""
import asyncio
import logging

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import QueuePool

from app.core.config import ConfigFile, get_config
from app.create_app import get_app
from app.database import Base
from app.database.base import get_db_url
from app.database.session_manager.db_session import Database

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for entire test session.

    Ensures all async tests share the same event loop.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config():
    """
    Get test configuration.

    Returns configuration with test database settings.
    """
    return get_config(ConfigFile.TEST)


@pytest_asyncio.fixture(scope="function")
async def test_async_engine(test_config):
    """
    Create async database engine for testing.

    Creates engine with connection pooling and proper cleanup.
    """
    async_db_url = get_db_url(test_config)

    engine_kw = {
        "pool_pre_ping": True,
        "pool_size": 90,
        "max_overflow": 110,
        "pool_timeout": 30,
        "poolclass": QueuePool,
    }

    test_engine = create_async_engine(async_db_url, **engine_kw)

    yield test_engine

    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_cleanup(test_async_engine):
    """
    Clean database before and after each test.

    Drops all tables, recreates them, then drops again after test.
    Ensures clean state for each test.
    """
    # Drop all tables before test
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Drop all tables after test
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def initialize_db_session(test_config, test_async_engine):
    """
    Initialize Database singleton for testing.

    Sets up database session manager with test configuration.
    """
    async_db_url = get_db_url(test_config)

    engine_kw = {
        "pool_pre_ping": True,
        "pool_size": 2,
        "max_overflow": 4,
        "connect_args": {
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0,
        },
    }

    Database.init(async_db_url, engine_kw=engine_kw)

    yield


@pytest_asyncio.fixture(scope="function")
async def test_app(test_config):
    """
    Create FastAPI application with test configuration.

    Returns configured FastAPI app instance for testing.
    """
    app = get_app(ConfigFile.TEST)
    app.state.config = test_config

    yield app


@pytest_asyncio.fixture(scope="function")
async def test_async_client(test_app):
    """
    Create async HTTP client for API testing.

    Uses httpx AsyncClient with ASGITransport for testing FastAPI endpoints.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(
        transport=transport, base_url="http://localhost:8000", follow_redirects=True
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def test_db_session():
    """
    Provide database session for tests.

    Creates async session using Database context manager.
    """
    async with Database() as session:
        yield session

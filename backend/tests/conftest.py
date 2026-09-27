"""
Pytest fixtures for backend tests.

Provides:
- In-memory SQLite async database engine
- Automatic table schema creation/teardown
- Database session fixture
- TestClient with dependency override wiring
"""

from collections.abc import AsyncGenerator, Generator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.redis import get_redis, set_redis_client
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Test database URL — SQLite in-memory with aiosqlite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def fake_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
    """Provide an isolated, in-memory FakeRedis instance for testing."""
    redis_instance = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis_client(redis_instance)
    yield redis_instance
    await redis_instance.flushall()
    await redis_instance.aclose()
    set_redis_client(None)


@pytest_asyncio.fixture(scope="function")
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session(setup_test_db: None) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated test database session."""
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture(scope="function")
def client(setup_test_db: None) -> Generator[TestClient, None, None]:
    """Provide a TestClient with get_db and get_redis overridden to use test backends."""
    fake_redis_instance = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis_client(fake_redis_instance)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestAsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def override_get_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
        yield fake_redis_instance

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    set_redis_client(None)

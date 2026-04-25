"""Integration test fixtures.

Requires a real Postgres with pgvector + pgcrypto extensions. Locally:
    docker compose up -d
In CI: GitHub Actions services block.

Set TEST_DATABASE_URL to override the default
postgresql+asyncpg://postgres:postgres@localhost:5432/recruiter_test.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.db import models  # noqa: F401  ensure all ORM models are imported
from app.db.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Default test DB url — override with TEST_DATABASE_URL env var.
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/recruiter_test",
)


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when the dependency isn't available."""
    if os.getenv("SKIP_INTEGRATION") == "1":
        skip = pytest.mark.skip(reason="SKIP_INTEGRATION=1")
        for item in items:
            if "integration" in item.keywords or "/integration/" in str(item.fspath):
                item.add_marker(skip)


@pytest_asyncio.fixture(scope="session")
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Session-wide engine. Creates extensions + schema once, drops on teardown."""
    eng = create_async_engine(TEST_DB_URL, future=True)
    async with eng.begin() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        # Drop in reverse to handle FKs; Base.metadata.drop_all + create_all is cleanest.
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncIterator[AsyncSession]:
    """Per-test session. We TRUNCATE between tests so each starts clean."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        # Order: dependents first (FK-safe).
        for tbl in ("scores", "messages", "conversations", "jobs", "candidates"):
            await conn.exec_driver_sql(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE")
    async with session_factory() as s:
        yield s


@pytest.fixture
def integration_marker():
    """Convenience marker — apply to every integration test for clarity."""
    return pytest.mark.integration

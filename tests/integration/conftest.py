import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.domain.entities.identity import LEGACY_ORGANIZATION_ID as TEST_ORG_ID
from app.infrastructure.persistence.models.base import Base
from tests.integration.database import validate_test_database_url


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    configured_url = os.environ.get("TEST_DATABASE_URL")
    if not configured_url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL database ending in '_test'")
    test_db_url = validate_test_database_url(configured_url, settings.database_url)
    eng = create_async_engine(test_db_url, echo=False)
    try:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        from app.infrastructure.persistence.models.identity import OrganizationModel

        async with AsyncSession(eng) as seed, seed.begin():
            seed.add(OrganizationModel(id=TEST_ORG_ID, name="Test organization", locked=False))
        try:
            yield eng
        finally:
            async with eng.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def temp_upload_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def real_client(
    engine: AsyncEngine, temp_upload_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    from app.infrastructure.persistence.database import get_db
    from app.infrastructure.storage.local_file_storage import LocalFileStorage
    from app.main import app

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.commit()

    monkeypatch.setattr(
        "app.presentation.api.dependencies.get_local_file_storage",
        lambda: LocalFileStorage(base_dir=temp_upload_dir),
    )
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()

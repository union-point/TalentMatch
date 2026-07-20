import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.infrastructure.persistence.models.base import Base


@pytest_asyncio.fixture
async def engine():
    test_db_url = settings.database_url.replace("talentmatch_db", "talentmatch_test")
    eng = create_async_engine(test_db_url, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
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
async def real_client(engine, temp_upload_dir) -> AsyncGenerator[AsyncClient, None]:
    from app.application.services.ingestion_service import IngestionService
    from app.infrastructure.persistence.database import get_db
    from app.infrastructure.persistence.repositories.job_description_repo import (
        SQLAlchemyJobDescriptionRepository,
    )
    from app.infrastructure.persistence.repositories.resume_repo import SQLAlchemyResumeRepository
    from app.infrastructure.storage.local_file_storage import LocalFileStorage
    from app.main import app
    from app.presentation.api.dependencies import get_ingestion_service

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.commit()

    async def override_get_ingestion_service():
        async with session_factory() as session:
            jd_repo = SQLAlchemyJobDescriptionRepository(session)
            resume_repo = SQLAlchemyResumeRepository(session)
            file_storage = LocalFileStorage(base_dir=temp_upload_dir)
            yield IngestionService(jd_repo, resume_repo, file_storage)
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ingestion_service] = override_get_ingestion_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()

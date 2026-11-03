import uuid
from unittest.mock import patch

import pytest_asyncio
from sqlalchemy import JSON, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.value_objects import AnalysisStatus
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.repositories.deep_analysis_repo import (
    SQLAlchemyDeepAnalysisRepository,
)
from app.tasks.deep_analysis_tasks import _dispatch_pending_deep_analyses_async


@pytest_asyncio.fixture
async def dispatch_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'dispatch.db'}")
    # Copy the schema for SQLite without changing production PostgreSQL metadata.
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    yield engine
    await engine.dispose()


async def test_only_committed_intents_are_published_and_rollback_is_invisible(dispatch_engine):
    engine = dispatch_engine
    with (
        patch("app.tasks.deep_analysis_tasks.engine", engine),
        patch("app.tasks.deep_analysis_tasks.run_deep_analysis.delay") as publish,
    ):
        async with AsyncSession(engine) as session:
            repo = SQLAlchemyDeepAnalysisRepository(session)
            analysis = DeepAnalysis(resume_id=uuid.uuid4(), job_description_id=uuid.uuid4())
            await repo.save(analysis)
            await _dispatch_pending_deep_analyses_async()
            publish.assert_not_called()
            await session.commit()
            await _dispatch_pending_deep_analyses_async()
            publish.assert_called_once_with(str(analysis.id))
            claimed = await repo.claim_pending(analysis.id)
            assert claimed.status == AnalysisStatus.IN_PROGRESS
            await session.commit()
            publish.reset_mock()
            rolled_back = DeepAnalysis(resume_id=uuid.uuid4(), job_description_id=uuid.uuid4())
            await repo.save(rolled_back)
            await session.rollback()
            await _dispatch_pending_deep_analyses_async()
            publish.assert_not_called()


async def test_duplicate_claims_and_terminal_redelivery_do_no_work(dispatch_engine):
    async with AsyncSession(dispatch_engine) as session:
        repo = SQLAlchemyDeepAnalysisRepository(session)
        analysis = DeepAnalysis(resume_id=uuid.uuid4(), job_description_id=uuid.uuid4())
        await repo.save(analysis)
        await session.commit()
        first = await repo.claim_pending(analysis.id)
        assert first.status == AnalysisStatus.IN_PROGRESS
        await session.commit()
    async with AsyncSession(dispatch_engine) as session:
        repo = SQLAlchemyDeepAnalysisRepository(session)
        assert await repo.claim_pending(analysis.id) is None
        first.status = AnalysisStatus.COMPLETED
        await repo.save(first)
        await session.commit()
        assert await repo.claim_pending(analysis.id) is None

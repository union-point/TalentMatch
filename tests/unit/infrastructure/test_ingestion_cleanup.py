from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import JSON, MetaData, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.services.ingestion_service import IngestionService
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.models.resume import ResumeModel
from app.infrastructure.persistence.repositories.job_description_repo import (
    SQLAlchemyJobDescriptionRepository,
)
from app.infrastructure.persistence.repositories.resume_repo import SQLAlchemyResumeRepository
from app.infrastructure.storage.local_file_storage import LocalFileStorage


@pytest.mark.parametrize("stage", ["parse", "persist", "commit"])
@pytest.mark.parametrize("kind", ["resume", "jd"])
async def test_upload_failure_removes_file(tmp_path: Path, stage: str, kind: str) -> None:
    repo = AsyncMock()
    repo.save.side_effect = lambda entity: entity
    parser = AsyncMock()
    parser.parse.return_value = "Candidate text"
    failure = RuntimeError("failed upload")
    if stage == "parse":
        parser.parse.side_effect = failure
    if stage == "persist":
        repo.save.side_effect = failure

    @asynccontextmanager
    async def transaction():
        yield
        if stage == "commit":
            raise failure

    service = IngestionService(repo, repo, LocalFileStorage(tmp_path), transaction)
    with patch(
        "app.application.services.ingestion_service.get_parser_for_file", return_value=parser
    ):
        with pytest.raises(RuntimeError, match="failed upload"):
            if kind == "resume":
                await service.ingest_resume(b"text", "test.txt")
            else:
                await service.ingest_job_description(b"text", "test.txt", "Role", "Company")
    assert not list(tmp_path.rglob("*.txt"))


async def test_mixed_batch_rolls_back_rows_and_files(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        async with AsyncSession(engine) as session:
            service = IngestionService(
                SQLAlchemyJobDescriptionRepository(session),
                SQLAlchemyResumeRepository(session),
                LocalFileStorage(tmp_path),
                session.begin,
            )
            parser = AsyncMock()
            parser.parse.side_effect = ["Valid resume", RuntimeError("bad file")]
            with patch(
                "app.application.services.ingestion_service.get_parser_for_file",
                return_value=parser,
            ):
                with pytest.raises(RuntimeError, match="bad file"):
                    await service.ingest_resumes_batch([(b"ok", "ok.txt"), (b"bad", "bad.txt")])
            assert await session.scalar(select(func.count()).select_from(ResumeModel)) == 0
            assert not list(tmp_path.rglob("*.txt"))
    finally:
        await engine.dispose()

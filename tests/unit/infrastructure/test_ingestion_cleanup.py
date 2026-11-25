from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import JSON, MetaData, Uuid, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.services.ingestion_service import IngestionService
from app.core.exceptions import ParsingError
from app.domain.entities.identity import LEGACY_ORGANIZATION_ID as TEST_ORG_ID
from app.domain.entities.resume import Resume
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.models.resume import ResumeModel
from app.infrastructure.persistence.repositories.job_description_repo import (
    SQLAlchemyJobDescriptionRepository,
)
from app.infrastructure.persistence.repositories.resume_repo import SQLAlchemyResumeRepository
from app.infrastructure.storage.local_file_storage import LocalFileStorage


@pytest.mark.parametrize("stage", ["parse", "persist", "commit"])
@pytest.mark.parametrize("kind", ["resume", "jd"])
async def test_upload_failure_removes_file(
    tmp_path: Path, stage: str, kind: str, make_ingestion_service: partial[IngestionService]
) -> None:
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

    service = make_ingestion_service(
        repo,
        repo,
        LocalFileStorage(tmp_path),
        TEST_ORG_ID,
        transaction,
        parser_for_file=Mock(return_value=parser),
    )
    with pytest.raises(RuntimeError, match="failed upload"):
        if kind == "resume":
            await service.ingest_resume(b"text", "test.txt")
        else:
            await service.ingest_job_description(b"text", "test.txt", "Role", "Company")
    assert not list(tmp_path.rglob("*.txt"))


@pytest.mark.parametrize("stage", ["parse", "persist", "commit"])
async def test_mixed_batch_preserves_successes_and_cleans_failed_file(
    tmp_path: Path, stage: str, make_ingestion_service: partial[IngestionService]
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, UUID):
                column.type = Uuid(native_uuid=False)
            if isinstance(column.type, JSONB):
                column.type = JSON()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        async with AsyncSession(engine) as session:
            repository = SQLAlchemyResumeRepository(session, organization_id=TEST_ORG_ID)
            attempt = 0

            @asynccontextmanager
            async def transaction() -> AsyncIterator[None]:
                nonlocal attempt
                attempt += 1
                async with session.begin():
                    yield
                    if attempt == 2 and stage == "commit":
                        raise RuntimeError("secret commit detail")

            save = repository.save

            async def save_resume(resume: Resume) -> Resume:
                result = await save(resume)
                if attempt == 2 and stage == "persist":
                    raise RuntimeError("secret database detail")
                return result

            repository.save = save_resume
            parser = AsyncMock()
            parser.parse.side_effect = [
                "Valid resume",
                ParsingError("secret parser detail") if stage == "parse" else "Valid resume",
                "Another valid resume",
            ]
            service = make_ingestion_service(
                SQLAlchemyJobDescriptionRepository(session, organization_id=TEST_ORG_ID),
                repository,
                LocalFileStorage(tmp_path),
                TEST_ORG_ID,
                transaction,
                parser_for_file=Mock(return_value=parser),
            )
            result = await service.ingest_resumes_batch(
                [
                    (b"ok", "ok.txt"),
                    (b"bad", "bad.txt"),
                    (b"later", "later.txt"),
                ]
            )
            assert [resume.filename for resume in result.resumes] == ["ok.txt", "later.txt"]
            assert len(result.errors) == 1
            assert result.errors[0].index == 1 and result.errors[0].filename == "bad.txt"
            assert "secret" not in result.errors[0].error
            assert await session.scalar(select(func.count()).select_from(ResumeModel)) == 2
            assert len(list(tmp_path.rglob("*.txt"))) == 2
            saved = (await session.scalars(select(ResumeModel))).all()
            assert {row.filename for row in saved} == {"ok.txt", "later.txt"}
            assert all(Path(row.file_path).exists() for row in saved)
    finally:
        await engine.dispose()


async def test_all_failures_report_each_duplicate_filename(
    tmp_path: Path, make_ingestion_service: partial[IngestionService]
) -> None:
    parser = AsyncMock()
    parser.parse.side_effect = ParsingError("private document data")
    service = make_ingestion_service(
        AsyncMock(),
        AsyncMock(),
        LocalFileStorage(tmp_path),
        TEST_ORG_ID,
        parser_for_file=Mock(return_value=parser),
    )
    result = await service.ingest_resumes_batch([(b"a", "same.txt"), (b"b", "same.txt")])
    assert result.resumes == []
    assert [error.index for error in result.errors] == [0, 1]
    assert all(error.error == "Could not parse the uploaded document." for error in result.errors)
    assert not list(tmp_path.rglob("*.txt"))


async def test_batch_cancellation_stops_processing_and_removes_current_file(
    tmp_path: Path, make_ingestion_service: partial[IngestionService]
) -> None:
    import asyncio

    parser, repository = AsyncMock(), AsyncMock()
    parser.parse.side_effect = ["Valid", asyncio.CancelledError(), "Never parsed"]
    repository.save.side_effect = lambda resume: resume
    service = make_ingestion_service(
        repository,
        repository,
        LocalFileStorage(tmp_path),
        TEST_ORG_ID,
        parser_for_file=Mock(return_value=parser),
    )
    with pytest.raises(asyncio.CancelledError):
        await service.ingest_resumes_batch(
            [
                (b"ok", "ok.txt"),
                (b"cancel", "cancel.txt"),
                (b"later", "later.txt"),
            ]
        )
    assert parser.parse.await_count == 2
    assert len(list(tmp_path.rglob("*.txt"))) == 1

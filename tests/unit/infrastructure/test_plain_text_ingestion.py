from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.application.services.ingestion_service import IngestionService
from app.core.exceptions import ParsingError, UnsupportedFileTypeError
from app.domain.entities.identity import LEGACY_ORGANIZATION_ID
from app.domain.entities.job_description import JobDescription
from app.infrastructure.storage.local_file_storage import LocalFileStorage


@pytest.mark.parametrize(
    ("filename", "encoding"),
    [
        ("description.txt", "utf-8"),
        ("description.MD", "utf-8-sig"),
        ("description.markdown", "utf-16"),
    ],
)
async def test_job_text_ingestion(tmp_path: Path, filename: str, encoding: str) -> None:
    repository = AsyncMock()
    repository.save.side_effect = lambda entity: entity
    service = IngestionService(
        repository, AsyncMock(), LocalFileStorage(tmp_path), LEGACY_ORGANIZATION_ID
    )
    content = "# Résumé review\r\n\r\n- Lead the hiring team."
    result = await service.ingest_job_description(
        content.encode(encoding), filename, "Lead", "Acme"
    )

    job: JobDescription = repository.save.await_args.args[0]
    assert job.original_content == content.replace("\r\n", "\n")
    assert "Lead the hiring team." in job.normalized_content
    assert result.file_type == Path(filename).suffix[1:].lower()
    assert result.injection_scan.passed
    assert Path(job.file_path).read_bytes() == content.encode(encoding)

    with pytest.raises(UnsupportedFileTypeError):
        await service.ingest_resume(content.encode(encoding), filename)


@pytest.mark.parametrize("content", [b" \r\n ", b"\xff\x02", b"PDF\x00"])
async def test_invalid_text_upload_leaves_no_file(tmp_path: Path, content: bytes) -> None:
    repository = AsyncMock()
    service = IngestionService(
        repository, AsyncMock(), LocalFileStorage(tmp_path), LEGACY_ORGANIZATION_ID
    )

    with pytest.raises(ParsingError):
        await service.ingest_job_description(content, "description.txt", "Lead", "Acme")

    repository.save.assert_not_awaited()
    assert not list(tmp_path.rglob("*.txt"))

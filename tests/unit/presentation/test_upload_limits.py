from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient, Request

from app.application.dto.ingestion import BatchIngestionResult
from app.config import settings
from app.main import app
from app.presentation.api import uploads
from app.presentation.api.dependencies import get_ingestion_service
from tests.conftest import _make_ingestion_response


@pytest.fixture
def ingestion(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    monkeypatch.setattr(settings, "max_upload_file_bytes", 10)
    monkeypatch.setattr(settings, "max_upload_batch_bytes", 15)
    monkeypatch.setattr(settings, "max_upload_files", 2)
    service = AsyncMock()
    service.ingest_resume.return_value = _make_ingestion_response()
    service.ingest_job_description.return_value = _make_ingestion_response()
    service.ingest_resumes_batch.return_value = BatchIngestionResult(
        [_make_ingestion_response()], []
    )
    app.dependency_overrides[get_ingestion_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_ingestion_service, None)


@pytest.mark.parametrize("path", ["resumes/upload", "job-descriptions/upload"])
@pytest.mark.parametrize("size,status", [(10, 200), (11, 413)])
async def test_single_upload_boundary(
    path: str, size: int, status: int, ingestion: AsyncMock
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/{path}",
            files={"file": ("resume.pdf", b"x" * size)},
            data={"title": "Job", "company": "Company"},
        )
    assert response.status_code == status
    if status == 413:
        ingestion.ingest_resume.assert_not_called()
        ingestion.ingest_job_description.assert_not_called()


@pytest.mark.parametrize("sizes,status", [([10, 5], 200), ([10, 6], 413), ([1, 1, 1], 413)])
async def test_batch_limits(sizes: list[int], status: int, ingestion: AsyncMock) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/resumes/batch-upload",
            files=[("files", ("resume.pdf", b"x" * size)) for size in sizes],
        )
    assert response.status_code == status
    if status == 413:
        ingestion.ingest_resumes_batch.assert_not_called()


@pytest.mark.parametrize("declared_size", [None, "1"])
async def test_streaming_limit_does_not_trust_content_length(
    declared_size: str | None,
    ingestion: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(uploads, "MULTIPART_OVERHEAD_BYTES", 300)
    request = Request("POST", "http://test", files={"file": ("large.pdf", b"x" * 1000)})
    body = request.read()
    headers = {"content-type": request.headers["content-type"]}
    if declared_size is not None:
        headers["content-length"] = declared_size

    async def chunks() -> AsyncIterator[bytes]:
        for offset in range(0, len(body), 64):
            yield body[offset : offset + 64]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/resumes/upload",
            content=chunks(),
            headers=headers,
        )
    assert response.status_code == 413
    ingestion.ingest_resume.assert_not_called()


async def test_oversized_declared_body_is_rejected_without_reading() -> None:
    downstream, receive, send = AsyncMock(), AsyncMock(), AsyncMock()
    await uploads.UploadLimitMiddleware(downstream)(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/resumes/upload",
            "headers": [(b"content-length", b"999999999")],
        },
        receive,
        send,
    )
    receive.assert_not_awaited()
    downstream.assert_not_awaited()
    assert send.await_args_list[0].args[0]["status"] == 413

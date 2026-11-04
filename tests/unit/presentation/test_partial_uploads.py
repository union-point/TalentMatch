from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.dto.ingestion import BatchIngestionResult, IngestionFailure
from app.main import app
from app.presentation.api.dependencies import get_ingestion_service
from tests.conftest import _make_ingestion_response


@pytest.mark.parametrize("all_failed", [False, True])
async def test_batch_response_reports_input_total_and_individual_errors(all_failed: bool) -> None:
    service = AsyncMock()
    failures = [IngestionFailure(1, "bad.pdf", "Could not parse the uploaded document.")]
    resumes = [_make_ingestion_response(filename="good.pdf", injection_passed=False)]
    if all_failed:
        resumes = []
        failures.insert(
            0, IngestionFailure(0, "good.pdf", "Could not parse the uploaded document.")
        )
    service.ingest_resumes_batch.return_value = BatchIngestionResult(resumes, failures)
    app.dependency_overrides[get_ingestion_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/resumes/batch-upload",
                files=[
                    ("files", ("good.pdf", b"good")),
                    ("files", ("bad.pdf", b"bad")),
                ],
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == len(resumes)
        assert data["failed"] == len(failures)
        assert data["total"] == data["succeeded"] + data["failed"]
        assert data["errors"][-1] == {
            "index": 1,
            "filename": "bad.pdf",
            "error": "Could not parse the uploaded document.",
        }
        if not all_failed:
            assert data["resumes"][0]["injection_scan"]["passed"] is False
    finally:
        app.dependency_overrides.pop(get_ingestion_service, None)

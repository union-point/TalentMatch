import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.services.fast_track_service import FastTrackService
from app.core.exceptions import AIResponseError, ParsingError
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.identity import LEGACY_ORGANIZATION_ID as TEST_ORG_ID
from app.domain.entities.resume import Resume
from app.domain.value_objects import AnalysisStatus
from app.main import app
from app.presentation.api.dependencies import get_dashboard_service, get_ingestion_service

SECRET = "private-resume-text /srv/uploads/private.pdf SQL parameters"


@pytest.mark.parametrize(
    "error,status",
    [
        (RuntimeError(SECRET), 500),
        (ParsingError(SECRET), 422),
        (AIResponseError(SECRET, raw_response=SECRET), 502),
    ],
)
async def test_internal_errors_are_redacted_and_traceable(error: Exception, status: int) -> None:
    async def fail() -> None:
        raise error

    app.dependency_overrides[get_ingestion_service] = fail
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/resumes/upload", files={"file": ("resume.pdf", b"text")}
            )
        assert response.status_code == status
        assert SECRET not in response.text
        assert "raw_response" not in response.text
        assert response.json()["trace_id"] == response.headers["x-request-id"]
        uuid.UUID(response.json()["trace_id"])
        if status == 500:
            assert response.json()["title"] == "InternalServerError"
    finally:
        app.dependency_overrides.pop(get_ingestion_service, None)


async def test_validation_errors_do_not_echo_input() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/deep",
            json={"resume_id": SECRET, "job_description_id": str(uuid.uuid4())},
        )
    assert response.status_code == 422
    assert SECRET not in response.text
    assert response.json()["extra"]["errors"][0]["field"] == "body.resume_id"


@pytest.mark.parametrize("stage", ["database", "provider"])
async def test_per_resume_failures_do_not_echo_internal_errors(stage: str) -> None:
    jobs, resumes, results, ai = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    jobs.get_by_id.return_value = SimpleNamespace(
        normalized_content="Job", organization_id=TEST_ORG_ID
    )
    resumes.get_by_id.return_value = SimpleNamespace(
        normalized_content="Resume", injection_scan_passed=True
    )
    if stage == "database":
        resumes.get_by_id.side_effect = RuntimeError(SECRET)
    else:
        ai.analyze_fast_track.side_effect = AIResponseError(SECRET, raw_response=SECRET)

    @asynccontextmanager
    async def transaction() -> AsyncIterator[None]:
        yield

    service = FastTrackService(jobs, resumes, results, ai, transaction)
    response = await service.run_fast_track(uuid.uuid4(), [uuid.uuid4()])
    assert response[0].error
    assert SECRET not in response[0].error
    assert response[0].result is None


async def test_dashboard_redacts_legacy_persisted_error_text() -> None:
    resume_id, jd_id = uuid.uuid4(), uuid.uuid4()
    service = AsyncMock()
    service.get_candidate_detail.return_value = SimpleNamespace(
        resume=Resume(
            organization_id=TEST_ORG_ID,
            id=resume_id,
            filename="resume.pdf",
            file_path="resume.pdf",
            file_type="pdf",
            original_content="text",
            normalized_content="text",
            injection_scan_passed=True,
        ),
        fast_track=None,
        deep_analysis=DeepAnalysis(
            organization_id=TEST_ORG_ID,
            resume_id=resume_id,
            job_description_id=jd_id,
            status=AnalysisStatus.FAILED,
            error_message=SECRET,
        ),
    )
    app.dependency_overrides[get_dashboard_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/dashboard/candidates/{resume_id}/job/{jd_id}")
        assert response.status_code == 200
        assert SECRET not in response.text
        assert (
            response.json()["deep_analysis"]["error_message"]
            == "Analysis failed. Please try again."
        )
    finally:
        app.dependency_overrides.pop(get_dashboard_service, None)

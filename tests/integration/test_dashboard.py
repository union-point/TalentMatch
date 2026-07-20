import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.dto.dashboard import (
    CandidateDetailResult,
    PaginatedResult,
    RankedCandidateItem,
    ResumeFileResult,
)
from app.core.exceptions import (
    JobDescriptionNotFoundError,
    ResumeNotFoundError,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.entities.resume import Resume
from app.domain.value_objects import AnalysisStatus
from app.main import app
from app.presentation.api.dependencies import get_dashboard_service


@pytest.fixture
def mock_dashboard_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
async def dash_client(
    mock_dashboard_service: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_dashboard_service] = lambda: mock_dashboard_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_ranked_item(
    resume_id: uuid.UUID | None = None,
    score: int = 85,
    candidate_name: str = "Alice",
) -> RankedCandidateItem:
    return RankedCandidateItem(
        resume_id=resume_id or uuid.uuid4(),
        candidate_name=candidate_name,
        email=f"{candidate_name.lower()}@example.com",
        score=score,
        pass_fail=score >= 50,
        explanation="Match",
        injection_scan_passed=True,
        has_deep_analysis=False,
    )


class TestGetRankedCandidates:
    @pytest.mark.asyncio
    async def test_returns_paginated_candidates(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        jd_id = uuid.uuid4()
        items = [
            _make_ranked_item(score=85, candidate_name="Alice"),
            _make_ranked_item(score=45, candidate_name="Bob"),
        ]
        mock_dashboard_service.get_ranked_candidates.return_value = PaginatedResult(
            items=items, total=2, page=1, page_size=20, pages=1
        )

        response = await dash_client.get(f"/api/v1/dashboard/jobs/{jd_id}/candidates")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["score"] == 85
        assert data["items"][1]["score"] == 45
        assert data["page"] == 1
        assert data["page_size"] == 20

    @pytest.mark.asyncio
    async def test_returns_404_when_jd_not_found(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        jd_id = uuid.uuid4()
        mock_dashboard_service.get_ranked_candidates.side_effect = (
            JobDescriptionNotFoundError(jd_id)
        )

        response = await dash_client.get(f"/api/v1/dashboard/jobs/{jd_id}/candidates")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_passes_query_params_to_service(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        jd_id = uuid.uuid4()
        mock_dashboard_service.get_ranked_candidates.return_value = PaginatedResult(
            items=[_make_ranked_item()], total=1, page=1, page_size=10, pages=1
        )

        await dash_client.get(
            f"/api/v1/dashboard/jobs/{jd_id}/candidates",
            params={
                "min_score": "70",
                "pass_fail_only": "true",
                "q": "engineer",
                "page": "2",
                "page_size": "10",
            },
        )

        mock_dashboard_service.get_ranked_candidates.assert_awaited_once_with(
            jd_id=jd_id,
            min_score=70,
            pass_fail_only=True,
            search="engineer",
            page=2,
            page_size=10,
        )

    @pytest.mark.asyncio
    async def test_returns_422_for_invalid_uuid(
        self,
        dash_client: AsyncClient,
    ) -> None:
        response = await dash_client.get(
            "/api/v1/dashboard/jobs/not-a-uuid/candidates"
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_empty_result_when_no_candidates(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        jd_id = uuid.uuid4()
        mock_dashboard_service.get_ranked_candidates.return_value = PaginatedResult(
            items=[], total=0, page=1, page_size=20, pages=0
        )

        response = await dash_client.get(f"/api/v1/dashboard/jobs/{jd_id}/candidates")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestGetCandidateDetail:
    @pytest.mark.asyncio
    async def test_returns_candidate_detail(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        resume_id = uuid.uuid4()
        jd_id = uuid.uuid4()
        resume = Resume(
            id=resume_id,
            filename="alice.pdf",
            candidate_name="Alice",
            email="alice@example.com",
            original_content="...",
            normalized_content="...",
            file_path="/path/file.pdf",
            file_type="pdf",
            injection_scan_passed=True,
        )
        fast_track = FastTrackResult(
            resume_id=resume_id,
            job_description_id=jd_id,
            pass_fail=True,
            score=85,
            explanation="Strong match",
        )
        deep = DeepAnalysis(
            resume_id=resume_id,
            job_description_id=jd_id,
            status=AnalysisStatus.COMPLETED,
            overall_score=80,
            strengths=["Python"],
            weaknesses=["No cloud"],
            risks=[],
            detailed_reasoning="Good.",
        )
        mock_dashboard_service.get_candidate_detail.return_value = CandidateDetailResult(
            resume=resume,
            fast_track=fast_track,
            deep_analysis=deep,
        )

        response = await dash_client.get(
            f"/api/v1/dashboard/candidates/{resume_id}/job/{jd_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["resume_id"] == str(resume_id)
        assert data["candidate_name"] == "Alice"
        assert data["file_type"] == "pdf"
        assert data["fast_track"]["score"] == 85
        assert data["deep_analysis"]["overall_score"] == 80
        assert data["deep_analysis"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_returns_404_when_resume_not_found(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        resume_id = uuid.uuid4()
        jd_id = uuid.uuid4()
        mock_dashboard_service.get_candidate_detail.side_effect = ResumeNotFoundError(
            resume_id
        )

        response = await dash_client.get(
            f"/api/v1/dashboard/candidates/{resume_id}/job/{jd_id}"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_422_for_invalid_uuid(
        self,
        dash_client: AsyncClient,
    ) -> None:
        response = await dash_client.get(
            f"/api/v1/dashboard/candidates/not-a-uuid/job/{uuid.uuid4()}"
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_calls_service_with_correct_args(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        resume_id = uuid.uuid4()
        jd_id = uuid.uuid4()
        resume = Resume(
            id=resume_id,
            filename="resume.pdf",
            candidate_name="Alice",
            original_content="...",
            normalized_content="...",
            file_path="/path/file.pdf",
            file_type="pdf",
            injection_scan_passed=True,
        )
        mock_dashboard_service.get_candidate_detail.return_value = CandidateDetailResult(
            resume=resume,
        )

        await dash_client.get(
            f"/api/v1/dashboard/candidates/{resume_id}/job/{jd_id}"
        )

        mock_dashboard_service.get_candidate_detail.assert_awaited_once_with(
            resume_id=resume_id,
            jd_id=jd_id,
        )

    @pytest.mark.asyncio
    async def test_returns_null_analyses_when_missing(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        resume_id = uuid.uuid4()
        jd_id = uuid.uuid4()
        resume = Resume(
            id=resume_id,
            filename="resume.pdf",
            candidate_name="Alice",
            original_content="...",
            normalized_content="...",
            file_path="/path/file.pdf",
            file_type="pdf",
            injection_scan_passed=True,
        )
        mock_dashboard_service.get_candidate_detail.return_value = CandidateDetailResult(
            resume=resume,
        )

        response = await dash_client.get(
            f"/api/v1/dashboard/candidates/{resume_id}/job/{jd_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["fast_track"] is None
        assert data["deep_analysis"] is None


class TestGetResumeFile:
    @pytest.mark.asyncio
    async def test_returns_file(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
        tmp_path: Path,
    ) -> None:
        resume_id = uuid.uuid4()
        file_path = tmp_path / "resume.pdf"
        file_path.write_text("fake pdf content")

        mock_dashboard_service.get_resume_file.return_value = ResumeFileResult(
            file_path=file_path,
            filename="resume.pdf",
            mime_type="application/pdf",
        )

        response = await dash_client.get(
            f"/api/v1/dashboard/candidates/{resume_id}/resume-file"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "resume.pdf" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_returns_404_when_resume_not_found(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
    ) -> None:
        resume_id = uuid.uuid4()
        mock_dashboard_service.get_resume_file.side_effect = ResumeNotFoundError(
            resume_id
        )

        response = await dash_client.get(
            f"/api/v1/dashboard/candidates/{resume_id}/resume-file"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_422_for_invalid_uuid(
        self,
        dash_client: AsyncClient,
    ) -> None:
        response = await dash_client.get(
            "/api/v1/dashboard/candidates/not-a-uuid/resume-file"
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_calls_service_with_correct_id(
        self,
        dash_client: AsyncClient,
        mock_dashboard_service: AsyncMock,
        tmp_path: Path,
    ) -> None:
        resume_id = uuid.uuid4()
        file_path = tmp_path / "resume.pdf"
        file_path.write_text("fake")
        mock_dashboard_service.get_resume_file.return_value = ResumeFileResult(
            file_path=file_path,
            filename="resume.pdf",
            mime_type="application/pdf",
        )

        await dash_client.get(
            f"/api/v1/dashboard/candidates/{resume_id}/resume-file"
        )

        mock_dashboard_service.get_resume_file.assert_awaited_once_with(
            resume_id,
        )

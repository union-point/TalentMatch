import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.dto.analysis import (
    DeepAnalysisResultDTO,
)
from app.core.exceptions import (
    AnalysisNotFoundError,
    JobDescriptionNotFoundError,
    ResumeNotFoundError,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.value_objects import AnalysisStatus
from app.main import app
from app.presentation.api.dependencies import get_deep_analysis_service


@pytest.fixture
def mock_deep_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
async def deep_client(mock_deep_service: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_deep_analysis_service] = lambda: mock_deep_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


class TestDeepAnalysisPostEndpoint:
    @pytest.mark.asyncio
    async def test_post_deep_returns_202_with_analysis_id(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        analysis_id = uuid.uuid4()
        mock_deep_service.request_deep_analysis.return_value = DeepAnalysisResultDTO(
            analysis_id=analysis_id,
            status=AnalysisStatus.PENDING,
        )

        response = await deep_client.post(
            "/api/v1/analysis/deep",
            json={
                "resume_id": str(uuid.uuid4()),
                "job_description_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["analysis_id"] == str(analysis_id)
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_post_deep_returns_404_when_jd_not_found(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        mock_deep_service.request_deep_analysis.side_effect = JobDescriptionNotFoundError(
            uuid.uuid4()
        )

        response = await deep_client.post(
            "/api/v1/analysis/deep",
            json={
                "resume_id": str(uuid.uuid4()),
                "job_description_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_post_deep_returns_404_when_resume_not_found(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        mock_deep_service.request_deep_analysis.side_effect = ResumeNotFoundError(uuid.uuid4())

        response = await deep_client.post(
            "/api/v1/analysis/deep",
            json={
                "resume_id": str(uuid.uuid4()),
                "job_description_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_post_deep_returns_422_for_invalid_body(self, deep_client: AsyncClient) -> None:
        response = await deep_client.post(
            "/api/v1/analysis/deep",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_post_deep_returns_422_for_invalid_uuid(self, deep_client: AsyncClient) -> None:
        response = await deep_client.post(
            "/api/v1/analysis/deep",
            json={
                "resume_id": "not-a-uuid",
                "job_description_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_post_deep_calls_service_with_correct_args(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        resume_id = uuid.uuid4()
        jd_id = uuid.uuid4()
        mock_deep_service.request_deep_analysis.return_value = DeepAnalysisResultDTO(
            analysis_id=uuid.uuid4(),
            status=AnalysisStatus.PENDING,
        )

        await deep_client.post(
            "/api/v1/analysis/deep",
            json={
                "resume_id": str(resume_id),
                "job_description_id": str(jd_id),
            },
        )

        mock_deep_service.request_deep_analysis.assert_awaited_once_with(
            resume_id=resume_id,
            job_description_id=jd_id,
        )


class TestDeepAnalysisGetEndpoint:
    @pytest.mark.asyncio
    async def test_get_deep_returns_completed_result(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        analysis_id = uuid.uuid4()
        analysis = DeepAnalysis(
            id=analysis_id,
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            status=AnalysisStatus.COMPLETED,
            overall_score=88,
            strengths=["Python expertise", "FastAPI experience"],
            weaknesses=["No cloud experience"],
            risks=["Notice period"],
            detailed_reasoning="Strong candidate overall.",
            evidence=[{"text": "5 years Python", "category": "experience"}],
        )
        mock_deep_service.get_result.return_value = DeepAnalysisResultDTO(
            analysis_id=analysis_id,
            status=AnalysisStatus.COMPLETED,
            result=analysis,
        )

        response = await deep_client.get(f"/api/v1/analysis/deep/{analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["analysis_id"] == str(analysis_id)
        assert data["status"] == "completed"
        assert data["overall_score"] == 88
        assert data["strengths"] == ["Python expertise", "FastAPI experience"]
        assert data["weaknesses"] == ["No cloud experience"]
        assert data["risks"] == ["Notice period"]
        assert data["detailed_reasoning"] == "Strong candidate overall."
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["text"] == "5 years Python"
        assert data["evidence"][0]["category"] == "experience"
        assert data["error_message"] is None

    @pytest.mark.asyncio
    async def test_get_deep_returns_pending_status(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        analysis_id = uuid.uuid4()
        mock_deep_service.get_result.return_value = DeepAnalysisResultDTO(
            analysis_id=analysis_id,
            status=AnalysisStatus.PENDING,
        )

        response = await deep_client.get(f"/api/v1/analysis/deep/{analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["analysis_id"] == str(analysis_id)
        assert data["status"] == "pending"
        assert data["overall_score"] is None
        assert data["strengths"] is None

    @pytest.mark.asyncio
    async def test_get_deep_returns_in_progress_status(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        analysis_id = uuid.uuid4()
        mock_deep_service.get_result.return_value = DeepAnalysisResultDTO(
            analysis_id=analysis_id,
            status=AnalysisStatus.IN_PROGRESS,
        )

        response = await deep_client.get(f"/api/v1/analysis/deep/{analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_get_deep_returns_failed_with_error_message(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        analysis_id = uuid.uuid4()
        mock_deep_service.get_result.return_value = DeepAnalysisResultDTO(
            analysis_id=analysis_id,
            status=AnalysisStatus.FAILED,
            error="Gemini API timeout",
        )

        response = await deep_client.get(f"/api/v1/analysis/deep/{analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["analysis_id"] == str(analysis_id)
        assert data["status"] == "failed"
        assert data["error_message"] == "Gemini API timeout"
        assert data["overall_score"] is None

    @pytest.mark.asyncio
    async def test_get_deep_returns_404_when_not_found(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        mock_deep_service.get_result.side_effect = AnalysisNotFoundError(uuid.uuid4())
        analysis_id = uuid.uuid4()

        response = await deep_client.get(f"/api/v1/analysis/deep/{analysis_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_deep_returns_422_for_invalid_uuid(self, deep_client: AsyncClient) -> None:
        response = await deep_client.get("/api/v1/analysis/deep/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_deep_calls_service_with_correct_id(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        analysis_id = uuid.uuid4()
        mock_deep_service.get_result.return_value = DeepAnalysisResultDTO(
            analysis_id=analysis_id,
            status=AnalysisStatus.PENDING,
        )

        await deep_client.get(f"/api/v1/analysis/deep/{analysis_id}")

        mock_deep_service.get_result.assert_awaited_once_with(analysis_id)

    @pytest.mark.asyncio
    async def test_get_deep_completed_result_with_empty_evidence(
        self, deep_client: AsyncClient, mock_deep_service: AsyncMock
    ) -> None:
        analysis_id = uuid.uuid4()
        analysis = DeepAnalysis(
            id=analysis_id,
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            status=AnalysisStatus.COMPLETED,
            overall_score=50,
            strengths=[],
            weaknesses=["Lacks key skills"],
            risks=[],
            detailed_reasoning="Below expectations.",
            evidence=None,
        )
        mock_deep_service.get_result.return_value = DeepAnalysisResultDTO(
            analysis_id=analysis_id,
            status=AnalysisStatus.COMPLETED,
            result=analysis,
        )

        response = await deep_client.get(f"/api/v1/analysis/deep/{analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] == 50
        assert data["strengths"] == []
        assert data["evidence"] is None

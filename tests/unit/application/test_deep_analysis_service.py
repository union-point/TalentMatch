import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.application.dto.analysis import (
    DeepAnalysisResultDTO,
)
from app.application.services.deep_analysis_service import (
    DeepAnalysisService,
)
from app.core.exceptions import (
    AnalysisNotFoundError,
    JobDescriptionNotFoundError,
    ResumeNotFoundError,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.job_description import JobDescription
from app.domain.entities.resume import Resume
from app.domain.value_objects import AnalysisStatus


@pytest.fixture
def mock_jd_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_resume_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_deep_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_jd_repo: AsyncMock,
    mock_resume_repo: AsyncMock,
    mock_deep_repo: AsyncMock,
) -> DeepAnalysisService:
    return DeepAnalysisService(mock_jd_repo, mock_resume_repo, mock_deep_repo)


@pytest.fixture
def sample_jd() -> JobDescription:
    return JobDescription(
        id=uuid.uuid4(),
        title="Software Engineer",
        company="Acme Inc",
        original_content="We need a Python developer",
        normalized_content="We need a Python developer",
        file_path="/uploads/jds/test.pdf",
        file_type="pdf",
        injection_scan_passed=True,
    )


@pytest.fixture
def sample_resume() -> Resume:
    return Resume(
        id=uuid.uuid4(),
        filename="resume.pdf",
        original_content="Python developer with FastAPI experience",
        normalized_content="Python developer with FastAPI experience",
        file_path="/uploads/resumes/test.pdf",
        file_type="pdf",
        injection_scan_passed=True,
        candidate_name="John Doe",
        email="john@example.com",
    )


class TestDeepAnalysisServiceRequestAnalysis:
    @pytest.mark.asyncio
    async def test_request_creates_pending_analysis_and_dispatches_task(
        self,
        service: DeepAnalysisService,
        mock_jd_repo: AsyncMock,
        mock_resume_repo: AsyncMock,
        mock_deep_repo: AsyncMock,
        sample_jd: JobDescription,
        sample_resume: Resume,
    ) -> None:
        mock_jd_repo.get_by_id.return_value = sample_jd
        mock_resume_repo.get_by_id.return_value = sample_resume

        saved_analysis = DeepAnalysis(
            id=uuid.uuid4(),
            resume_id=sample_resume.id,
            job_description_id=sample_jd.id,
            status=AnalysisStatus.PENDING,
        )
        mock_deep_repo.save.return_value = saved_analysis

        with patch(
            "app.application.services.deep_analysis_service.run_deep_analysis_task"
        ) as mock_task:
            result = await service.request_deep_analysis(
                resume_id=sample_resume.id,
                job_description_id=sample_jd.id,
            )

            assert isinstance(result, DeepAnalysisResultDTO)
            assert result.analysis_id == saved_analysis.id
            assert result.status == AnalysisStatus.PENDING

            mock_deep_repo.save.assert_awaited_once()
            saved_entity = mock_deep_repo.save.call_args[0][0]
            assert saved_entity.resume_id == sample_resume.id
            assert saved_entity.job_description_id == sample_jd.id
            assert saved_entity.status == AnalysisStatus.PENDING

            mock_task.delay.assert_called_once_with(str(saved_analysis.id))

    @pytest.mark.asyncio
    async def test_request_raises_when_jd_not_found(
        self,
        service: DeepAnalysisService,
        mock_jd_repo: AsyncMock,
    ) -> None:
        mock_jd_repo.get_by_id.return_value = None
        jd_id = uuid.uuid4()
        resume_id = uuid.uuid4()

        with pytest.raises(JobDescriptionNotFoundError):
            await service.request_deep_analysis(
                resume_id=resume_id,
                job_description_id=jd_id,
            )

    @pytest.mark.asyncio
    async def test_request_raises_when_resume_not_found(
        self,
        service: DeepAnalysisService,
        mock_jd_repo: AsyncMock,
        mock_resume_repo: AsyncMock,
        sample_jd: JobDescription,
    ) -> None:
        mock_jd_repo.get_by_id.return_value = sample_jd
        mock_resume_repo.get_by_id.return_value = None
        resume_id = uuid.uuid4()

        with pytest.raises(ResumeNotFoundError):
            await service.request_deep_analysis(
                resume_id=resume_id,
                job_description_id=sample_jd.id,
            )

    @pytest.mark.asyncio
    async def test_request_does_not_save_when_jd_missing(
        self,
        service: DeepAnalysisService,
        mock_jd_repo: AsyncMock,
        mock_deep_repo: AsyncMock,
    ) -> None:
        mock_jd_repo.get_by_id.return_value = None

        with pytest.raises(JobDescriptionNotFoundError):
            await service.request_deep_analysis(
                resume_id=uuid.uuid4(),
                job_description_id=uuid.uuid4(),
            )

        mock_deep_repo.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_request_does_not_dispatch_task_when_resume_missing(
        self,
        service: DeepAnalysisService,
        mock_jd_repo: AsyncMock,
        mock_resume_repo: AsyncMock,
        sample_jd: JobDescription,
    ) -> None:
        mock_jd_repo.get_by_id.return_value = sample_jd
        mock_resume_repo.get_by_id.return_value = None

        with pytest.raises(ResumeNotFoundError):
            await service.request_deep_analysis(
                resume_id=uuid.uuid4(),
                job_description_id=sample_jd.id,
            )

        with patch(
            "app.application.services.deep_analysis_service.run_deep_analysis_task"
        ) as mock_task:
            mock_task.delay.assert_not_called()


class TestDeepAnalysisServiceGetResult:
    @pytest.mark.asyncio
    async def test_get_result_returns_completed_analysis(
        self,
        service: DeepAnalysisService,
        mock_deep_repo: AsyncMock,
    ) -> None:
        analysis = DeepAnalysis(
            id=uuid.uuid4(),
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            status=AnalysisStatus.COMPLETED,
            overall_score=88,
            strengths=["Python expertise"],
            weaknesses=["No cloud experience"],
            risks=["Notice period"],
            detailed_reasoning="Strong candidate overall.",
            evidence=[{"text": "5 years Python", "category": "experience"}],
        )
        mock_deep_repo.get_by_id.return_value = analysis

        result = await service.get_result(analysis.id)

        assert isinstance(result, DeepAnalysisResultDTO)
        assert result.analysis_id == analysis.id
        assert result.status == AnalysisStatus.COMPLETED
        assert result.result is analysis
        assert result.error is None

    @pytest.mark.asyncio
    async def test_get_result_returns_pending_without_result(
        self,
        service: DeepAnalysisService,
        mock_deep_repo: AsyncMock,
    ) -> None:
        analysis = DeepAnalysis(
            id=uuid.uuid4(),
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            status=AnalysisStatus.PENDING,
        )
        mock_deep_repo.get_by_id.return_value = analysis

        result = await service.get_result(analysis.id)

        assert result.status == AnalysisStatus.PENDING
        assert result.result is None

    @pytest.mark.asyncio
    async def test_get_result_returns_in_progress_without_result(
        self,
        service: DeepAnalysisService,
        mock_deep_repo: AsyncMock,
    ) -> None:
        analysis = DeepAnalysis(
            id=uuid.uuid4(),
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            status=AnalysisStatus.IN_PROGRESS,
        )
        mock_deep_repo.get_by_id.return_value = analysis

        result = await service.get_result(analysis.id)

        assert result.status == AnalysisStatus.IN_PROGRESS
        assert result.result is None

    @pytest.mark.asyncio
    async def test_get_result_returns_failed_with_error(
        self,
        service: DeepAnalysisService,
        mock_deep_repo: AsyncMock,
    ) -> None:
        analysis = DeepAnalysis(
            id=uuid.uuid4(),
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            status=AnalysisStatus.FAILED,
            error_message="Gemini API timeout",
        )
        mock_deep_repo.get_by_id.return_value = analysis

        result = await service.get_result(analysis.id)

        assert result.status == AnalysisStatus.FAILED
        assert result.result is None
        assert result.error == "Gemini API timeout"

    @pytest.mark.asyncio
    async def test_get_result_raises_when_not_found(
        self,
        service: DeepAnalysisService,
        mock_deep_repo: AsyncMock,
    ) -> None:
        mock_deep_repo.get_by_id.return_value = None
        analysis_id = uuid.uuid4()

        with pytest.raises(AnalysisNotFoundError):
            await service.get_result(analysis_id)

    @pytest.mark.asyncio
    async def test_get_result_delegates_to_correct_repo(
        self,
        service: DeepAnalysisService,
        mock_deep_repo: AsyncMock,
    ) -> None:
        analysis_id = uuid.uuid4()
        mock_deep_repo.get_by_id.return_value = None

        with pytest.raises(AnalysisNotFoundError):
            await service.get_result(analysis_id)

        mock_deep_repo.get_by_id.assert_awaited_once_with(analysis_id)

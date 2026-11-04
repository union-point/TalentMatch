import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.application.services.dashboard_service import DashboardService
from app.core.exceptions import (
    JobDescriptionNotFoundError,
    ResumeNotFoundError,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.entities.identity import LEGACY_ORGANIZATION_ID as TEST_ORG_ID
from app.domain.entities.job_description import JobDescription
from app.domain.entities.resume import Resume
from app.domain.value_objects import AnalysisStatus


def _resume_map(*resumes: Resume):
    """Return a side effect callable that maps resume IDs to resumes."""
    mapping = {r.id: r for r in resumes}

    async def side_effect(rid: uuid.UUID) -> Resume | None:
        return mapping.get(rid)

    return side_effect


@pytest.fixture
def mock_jd_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_resume_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_fast_track_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_deep_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_jd_repo: AsyncMock,
    mock_resume_repo: AsyncMock,
    mock_fast_track_repo: AsyncMock,
    mock_deep_repo: AsyncMock,
) -> DashboardService:
    return DashboardService(mock_jd_repo, mock_resume_repo, mock_fast_track_repo, mock_deep_repo)


@pytest.fixture
def jd_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def resume_id_1() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def resume_id_2() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_jd(jd_id: uuid.UUID) -> JobDescription:
    return JobDescription(
        organization_id=TEST_ORG_ID,
        id=jd_id,
        title="Software Engineer",
        company="Acme",
        original_content="JD text",
        normalized_content="JD text",
        file_path="/path/to/jd.pdf",
        file_type="pdf",
        injection_scan_passed=True,
    )


@pytest.fixture
def sample_resume_1(resume_id_1: uuid.UUID) -> Resume:
    return Resume(
        organization_id=TEST_ORG_ID,
        id=resume_id_1,
        filename="alice.pdf",
        candidate_name="Alice",
        email="alice@example.com",
        original_content="Alice resume",
        normalized_content="Alice resume",
        file_path="/path/to/alice.pdf",
        file_type="pdf",
        injection_scan_passed=True,
    )


@pytest.fixture
def sample_resume_2(resume_id_2: uuid.UUID) -> Resume:
    return Resume(
        organization_id=TEST_ORG_ID,
        id=resume_id_2,
        filename="bob.pdf",
        candidate_name="Bob",
        email="bob@example.com",
        original_content="Bob resume",
        normalized_content="Bob resume",
        file_path="/path/to/bob.pdf",
        file_type="pdf",
        injection_scan_passed=False,
    )


@pytest.fixture
def fast_track_1(resume_id_1: uuid.UUID, jd_id: uuid.UUID) -> FastTrackResult:
    return FastTrackResult(
        organization_id=TEST_ORG_ID,
        resume_id=resume_id_1,
        job_description_id=jd_id,
        pass_fail=True,
        score=85,
        explanation="Strong match",
    )


@pytest.fixture
def fast_track_2(resume_id_2: uuid.UUID, jd_id: uuid.UUID) -> FastTrackResult:
    return FastTrackResult(
        organization_id=TEST_ORG_ID,
        resume_id=resume_id_2,
        job_description_id=jd_id,
        pass_fail=False,
        score=45,
        explanation="Weak match",
    )


@pytest.fixture
def deep_analysis_1(resume_id_1: uuid.UUID, jd_id: uuid.UUID) -> DeepAnalysis:
    return DeepAnalysis(
        organization_id=TEST_ORG_ID,
        resume_id=resume_id_1,
        job_description_id=jd_id,
        status=AnalysisStatus.COMPLETED,
        overall_score=80,
        strengths=["Python"],
        weaknesses=["No cloud"],
        risks=[],
        detailed_reasoning="Good candidate.",
    )


class TestGetRankedCandidates:
    async def test_delegates_filters_and_pagination(
        self,
        service: DashboardService,
        mock_fast_track_repo: AsyncMock,
        mock_resume_repo: AsyncMock,
        mock_deep_repo: AsyncMock,
        jd_id: uuid.UUID,
    ) -> None:
        mock_fast_track_repo.get_ranked_candidates.return_value = ([], 41)
        result = await service.get_ranked_candidates(jd_id, 70, True, "Alice", 3, 20)
        assert result.total == 41
        assert result.pages == 3
        mock_fast_track_repo.get_ranked_candidates.assert_awaited_once_with(
            jd_id, 70, True, "Alice", 3, 20, "score", "desc", "all"
        )
        mock_resume_repo.get_by_id.assert_not_awaited()
        mock_deep_repo.get_by_resume_and_jd.assert_not_awaited()

    async def test_missing_job(
        self,
        service: DashboardService,
        mock_jd_repo: AsyncMock,
        jd_id: uuid.UUID,
    ) -> None:
        mock_jd_repo.get_by_id.return_value = None
        with pytest.raises(JobDescriptionNotFoundError):
            await service.get_ranked_candidates(jd_id)


class TestGetCandidateDetail:
    @pytest.mark.asyncio
    async def test_returns_resume_and_analyses(
        self,
        service: DashboardService,
        mock_jd_repo: AsyncMock,
        mock_resume_repo: AsyncMock,
        mock_fast_track_repo: AsyncMock,
        mock_deep_repo: AsyncMock,
        jd_id: uuid.UUID,
        resume_id_1: uuid.UUID,
        sample_jd: JobDescription,
        sample_resume_1: Resume,
        fast_track_1: FastTrackResult,
        deep_analysis_1: DeepAnalysis,
    ) -> None:
        mock_resume_repo.get_by_id.return_value = sample_resume_1
        mock_jd_repo.get_by_id.return_value = sample_jd
        mock_fast_track_repo.get_by_job_description_id.return_value = [fast_track_1]
        mock_deep_repo.get_by_resume_and_jd.return_value = deep_analysis_1

        detail = await service.get_candidate_detail(resume_id=resume_id_1, jd_id=jd_id)

        assert detail.resume.id == resume_id_1
        assert detail.fast_track is not None
        assert detail.fast_track.score == 85
        assert detail.deep_analysis is not None
        assert detail.deep_analysis.overall_score == 80

    @pytest.mark.asyncio
    async def test_raises_404_when_resume_not_found(
        self,
        service: DashboardService,
        mock_resume_repo: AsyncMock,
        jd_id: uuid.UUID,
        resume_id_1: uuid.UUID,
    ) -> None:
        mock_resume_repo.get_by_id.return_value = None

        with pytest.raises(ResumeNotFoundError):
            await service.get_candidate_detail(resume_id=resume_id_1, jd_id=jd_id)

    @pytest.mark.asyncio
    async def test_raises_404_when_jd_not_found(
        self,
        service: DashboardService,
        mock_resume_repo: AsyncMock,
        mock_jd_repo: AsyncMock,
        jd_id: uuid.UUID,
        resume_id_1: uuid.UUID,
        sample_resume_1: Resume,
    ) -> None:
        mock_resume_repo.get_by_id.return_value = sample_resume_1
        mock_jd_repo.get_by_id.return_value = None

        with pytest.raises(JobDescriptionNotFoundError):
            await service.get_candidate_detail(resume_id=resume_id_1, jd_id=jd_id)

    @pytest.mark.asyncio
    async def test_returns_null_analyses_when_not_found(
        self,
        service: DashboardService,
        mock_jd_repo: AsyncMock,
        mock_resume_repo: AsyncMock,
        mock_fast_track_repo: AsyncMock,
        mock_deep_repo: AsyncMock,
        jd_id: uuid.UUID,
        resume_id_1: uuid.UUID,
        sample_jd: JobDescription,
        sample_resume_1: Resume,
    ) -> None:
        mock_resume_repo.get_by_id.return_value = sample_resume_1
        mock_jd_repo.get_by_id.return_value = sample_jd
        mock_fast_track_repo.get_by_job_description_id.return_value = []
        mock_deep_repo.get_by_resume_and_jd.return_value = None

        detail = await service.get_candidate_detail(resume_id=resume_id_1, jd_id=jd_id)

        assert detail.resume.id == resume_id_1
        assert detail.fast_track is None
        assert detail.deep_analysis is None


class TestGetResumeFile:
    @pytest.mark.asyncio
    async def test_returns_file_details(
        self,
        service: DashboardService,
        mock_resume_repo: AsyncMock,
        resume_id_1: uuid.UUID,
        tmp_path: Path,
    ) -> None:
        file_path = tmp_path / "alice.pdf"
        file_path.write_text("fake content")
        resume = Resume(
            organization_id=TEST_ORG_ID,
            id=resume_id_1,
            filename="alice.pdf",
            candidate_name="Alice",
            original_content="Alice resume",
            normalized_content="Alice resume",
            file_path=str(file_path),
            file_type="pdf",
            injection_scan_passed=True,
        )
        mock_resume_repo.get_by_id.return_value = resume

        result = await service.get_resume_file(resume_id=resume_id_1)

        assert result.filename == "alice.pdf"
        assert result.mime_type == "application/pdf"
        assert str(result.file_path) == str(file_path)

    @pytest.mark.asyncio
    async def test_raises_404_when_resume_not_found(
        self,
        service: DashboardService,
        mock_resume_repo: AsyncMock,
        resume_id_1: uuid.UUID,
    ) -> None:
        mock_resume_repo.get_by_id.return_value = None

        with pytest.raises(ResumeNotFoundError):
            await service.get_resume_file(resume_id=resume_id_1)

    @pytest.mark.asyncio
    async def test_returns_correct_mime_type_for_html(
        self,
        service: DashboardService,
        mock_resume_repo: AsyncMock,
        resume_id_1: uuid.UUID,
        tmp_path: Path,
    ) -> None:
        file_path = tmp_path / "resume.html"
        file_path.write_text("<html></html>")
        resume = Resume(
            organization_id=TEST_ORG_ID,
            id=resume_id_1,
            filename="resume.html",
            candidate_name="Alice",
            original_content="<html>",
            normalized_content="<html>",
            file_path=str(file_path),
            file_type="html",
            injection_scan_passed=True,
        )
        mock_resume_repo.get_by_id.return_value = resume

        result = await service.get_resume_file(resume_id=resume_id_1)

        assert result.mime_type == "text/html"

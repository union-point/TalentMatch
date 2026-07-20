import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.dto.ai import DeepAnalysisData, EvidenceItem
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.job_description import JobDescription
from app.domain.entities.resume import Resume
from app.domain.value_objects import AnalysisStatus


def _make_mock_engine() -> AsyncMock:
    engine = AsyncMock()
    engine.dispose = AsyncMock()
    return engine


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
    )


@pytest.fixture
def pending_analysis(sample_resume: Resume, sample_jd: JobDescription) -> DeepAnalysis:
    return DeepAnalysis(
        id=uuid.uuid4(),
        resume_id=sample_resume.id,
        job_description_id=sample_jd.id,
        status=AnalysisStatus.PENDING,
    )


class TestDeepAnalysisTaskAsync:
    @pytest.mark.asyncio
    async def test_happy_path_completed_analysis(
        self,
        pending_analysis: DeepAnalysis,
        sample_resume: Resume,
        sample_jd: JobDescription,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.get_by_id = AsyncMock(return_value=pending_analysis)
        deep_repo.save = AsyncMock(return_value=pending_analysis)
        resume_repo = MagicMock()
        resume_repo.get_by_id = AsyncMock(return_value=sample_resume)
        jd_repo = MagicMock()
        jd_repo.get_by_id = AsyncMock(return_value=sample_jd)

        ai_result = DeepAnalysisData(
            overall_score=85,
            strengths=["Python expertise", "FastAPI experience"],
            weaknesses=["No cloud experience"],
            risks=["Notice period"],
            detailed_reasoning="Strong candidate with solid backend skills.",
            evidence=[
                EvidenceItem(text="5 years Python", category="experience"),
            ],
        )
        mock_ai_service = AsyncMock()
        mock_ai_service.analyze_deep.return_value = ai_result

        mock_engine = _make_mock_engine()

        with (
            patch(
                "app.tasks.deep_analysis_tasks.AsyncSession",
                return_value=mock_session,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyDeepAnalysisRepository",
                return_value=deep_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyResumeRepository",
                return_value=resume_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyJobDescriptionRepository",
                return_value=jd_repo,
            ),
            patch("app.tasks.deep_analysis_tasks.AIServiceFactory") as mock_factory,
            patch("app.tasks.deep_analysis_tasks.engine", mock_engine),
        ):
            mock_factory.create.return_value = mock_ai_service

            from app.tasks.deep_analysis_tasks import _run_deep_analysis_async

            await _run_deep_analysis_async(str(pending_analysis.id))

        assert pending_analysis.status == AnalysisStatus.COMPLETED
        assert pending_analysis.overall_score == 85
        assert pending_analysis.strengths == ["Python expertise", "FastAPI experience"]
        assert pending_analysis.weaknesses == ["No cloud experience"]
        assert pending_analysis.risks == ["Notice period"]
        assert pending_analysis.detailed_reasoning == "Strong candidate with solid backend skills."
        assert pending_analysis.evidence == [{"text": "5 years Python", "category": "experience"}]
        assert pending_analysis.raw_response is not None
        assert pending_analysis.error_message is None

        assert deep_repo.save.await_count == 2
        mock_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_analysis_not_found_aborts(self) -> None:
        fake_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.get_by_id = AsyncMock(return_value=None)
        deep_repo.save = AsyncMock()
        resume_repo = MagicMock()
        jd_repo = MagicMock()

        mock_engine = _make_mock_engine()

        with (
            patch(
                "app.tasks.deep_analysis_tasks.AsyncSession",
                return_value=mock_session,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyDeepAnalysisRepository",
                return_value=deep_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyResumeRepository",
                return_value=resume_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyJobDescriptionRepository",
                return_value=jd_repo,
            ),
            patch("app.tasks.deep_analysis_tasks.engine", mock_engine),
        ):
            from app.tasks.deep_analysis_tasks import _run_deep_analysis_async

            await _run_deep_analysis_async(str(fake_id))

        deep_repo.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resume_not_found_marks_failed(
        self,
        pending_analysis: DeepAnalysis,
        sample_jd: JobDescription,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.get_by_id = AsyncMock(return_value=pending_analysis)
        deep_repo.save = AsyncMock(return_value=pending_analysis)
        resume_repo = MagicMock()
        resume_repo.get_by_id = AsyncMock(return_value=None)
        jd_repo = MagicMock()
        jd_repo.get_by_id = AsyncMock(return_value=sample_jd)

        mock_engine = _make_mock_engine()

        with (
            patch(
                "app.tasks.deep_analysis_tasks.AsyncSession",
                return_value=mock_session,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyDeepAnalysisRepository",
                return_value=deep_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyResumeRepository",
                return_value=resume_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyJobDescriptionRepository",
                return_value=jd_repo,
            ),
            patch("app.tasks.deep_analysis_tasks.engine", mock_engine),
        ):
            from app.tasks.deep_analysis_tasks import _run_deep_analysis_async

            await _run_deep_analysis_async(str(pending_analysis.id))

        assert pending_analysis.status == AnalysisStatus.FAILED
        assert pending_analysis.error_message is not None
        assert "not found" in pending_analysis.error_message.lower()
        mock_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_jd_not_found_marks_failed(
        self,
        pending_analysis: DeepAnalysis,
        sample_resume: Resume,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.get_by_id = AsyncMock(return_value=pending_analysis)
        deep_repo.save = AsyncMock(return_value=pending_analysis)
        resume_repo = MagicMock()
        resume_repo.get_by_id = AsyncMock(return_value=sample_resume)
        jd_repo = MagicMock()
        jd_repo.get_by_id = AsyncMock(return_value=None)

        mock_engine = _make_mock_engine()

        with (
            patch(
                "app.tasks.deep_analysis_tasks.AsyncSession",
                return_value=mock_session,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyDeepAnalysisRepository",
                return_value=deep_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyResumeRepository",
                return_value=resume_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyJobDescriptionRepository",
                return_value=jd_repo,
            ),
            patch("app.tasks.deep_analysis_tasks.engine", mock_engine),
        ):
            from app.tasks.deep_analysis_tasks import _run_deep_analysis_async

            await _run_deep_analysis_async(str(pending_analysis.id))

        assert pending_analysis.status == AnalysisStatus.FAILED
        assert pending_analysis.error_message is not None
        assert "not found" in pending_analysis.error_message.lower()

    @pytest.mark.asyncio
    async def test_ai_exception_marks_failed(
        self,
        pending_analysis: DeepAnalysis,
        sample_resume: Resume,
        sample_jd: JobDescription,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.get_by_id = AsyncMock(return_value=pending_analysis)
        deep_repo.save = AsyncMock(return_value=pending_analysis)
        resume_repo = MagicMock()
        resume_repo.get_by_id = AsyncMock(return_value=sample_resume)
        jd_repo = MagicMock()
        jd_repo.get_by_id = AsyncMock(return_value=sample_jd)

        mock_ai_service = AsyncMock()
        mock_ai_service.analyze_deep.side_effect = RuntimeError("API connection failed")

        mock_engine = _make_mock_engine()

        with (
            patch(
                "app.tasks.deep_analysis_tasks.AsyncSession",
                return_value=mock_session,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyDeepAnalysisRepository",
                return_value=deep_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyResumeRepository",
                return_value=resume_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyJobDescriptionRepository",
                return_value=jd_repo,
            ),
            patch("app.tasks.deep_analysis_tasks.AIServiceFactory") as mock_factory,
            patch("app.tasks.deep_analysis_tasks.engine", mock_engine),
        ):
            mock_factory.create.return_value = mock_ai_service

            from app.tasks.deep_analysis_tasks import _run_deep_analysis_async

            await _run_deep_analysis_async(str(pending_analysis.id))

        assert pending_analysis.status == AnalysisStatus.FAILED
        assert pending_analysis.error_message is not None
        assert "API connection failed" in pending_analysis.error_message
        mock_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_status_transitions_to_in_progress(
        self,
        pending_analysis: DeepAnalysis,
        sample_resume: Resume,
        sample_jd: JobDescription,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.get_by_id = AsyncMock(return_value=pending_analysis)
        deep_repo.save = AsyncMock(return_value=pending_analysis)
        resume_repo = MagicMock()
        resume_repo.get_by_id = AsyncMock(return_value=sample_resume)
        jd_repo = MagicMock()
        jd_repo.get_by_id = AsyncMock(return_value=sample_jd)

        mock_ai_service = AsyncMock()
        mock_ai_service.analyze_deep.return_value = DeepAnalysisData(
            overall_score=75,
            strengths=["Good skills"],
            weaknesses=["Some gaps"],
            risks=["Minor risks"],
            detailed_reasoning="Decent match.",
            evidence=[],
        )

        statuses: list[AnalysisStatus] = []

        def track_status(analysis: DeepAnalysis) -> None:
            statuses.append(analysis.status)

        deep_repo.save.side_effect = track_status

        mock_engine = _make_mock_engine()

        with (
            patch(
                "app.tasks.deep_analysis_tasks.AsyncSession",
                return_value=mock_session,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyDeepAnalysisRepository",
                return_value=deep_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyResumeRepository",
                return_value=resume_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyJobDescriptionRepository",
                return_value=jd_repo,
            ),
            patch("app.tasks.deep_analysis_tasks.AIServiceFactory") as mock_factory,
            patch("app.tasks.deep_analysis_tasks.engine", mock_engine),
        ):
            mock_factory.create.return_value = mock_ai_service

            from app.tasks.deep_analysis_tasks import _run_deep_analysis_async

            await _run_deep_analysis_async(str(pending_analysis.id))

        assert statuses[0] == AnalysisStatus.IN_PROGRESS
        assert statuses[1] == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_uses_factory_with_correct_settings(
        self,
        pending_analysis: DeepAnalysis,
        sample_resume: Resume,
        sample_jd: JobDescription,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.get_by_id = AsyncMock(return_value=pending_analysis)
        deep_repo.save = AsyncMock(return_value=pending_analysis)
        resume_repo = MagicMock()
        resume_repo.get_by_id = AsyncMock(return_value=sample_resume)
        jd_repo = MagicMock()
        jd_repo.get_by_id = AsyncMock(return_value=sample_jd)

        mock_ai_service = AsyncMock()
        mock_ai_service.analyze_deep.return_value = DeepAnalysisData(
            overall_score=50,
            strengths=[],
            weaknesses=[],
            risks=[],
            detailed_reasoning="",
            evidence=[],
        )

        mock_engine = _make_mock_engine()

        with (
            patch(
                "app.tasks.deep_analysis_tasks.AsyncSession",
                return_value=mock_session,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyDeepAnalysisRepository",
                return_value=deep_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyResumeRepository",
                return_value=resume_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyJobDescriptionRepository",
                return_value=jd_repo,
            ),
            patch("app.tasks.deep_analysis_tasks.AIServiceFactory") as mock_factory,
            patch("app.tasks.deep_analysis_tasks.engine", mock_engine),
            patch("app.tasks.deep_analysis_tasks.settings") as mock_settings,
        ):
            mock_settings.ai_deep_analysis_provider = "gemini"
            mock_settings.ai_deep_analysis_model = "gemini-3.5-flash"
            mock_factory.create.return_value = mock_ai_service

            from app.tasks.deep_analysis_tasks import _run_deep_analysis_async

            await _run_deep_analysis_async(str(pending_analysis.id))

        mock_factory.create.assert_called_once_with(
            provider="gemini",
            model="gemini-3.5-flash",
        )

    @pytest.mark.asyncio
    async def test_ai_receives_normalized_content(
        self,
        pending_analysis: DeepAnalysis,
        sample_resume: Resume,
        sample_jd: JobDescription,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.get_by_id = AsyncMock(return_value=pending_analysis)
        deep_repo.save = AsyncMock(return_value=pending_analysis)
        resume_repo = MagicMock()
        resume_repo.get_by_id = AsyncMock(return_value=sample_resume)
        jd_repo = MagicMock()
        jd_repo.get_by_id = AsyncMock(return_value=sample_jd)

        mock_ai_service = AsyncMock()
        mock_ai_service.analyze_deep.return_value = DeepAnalysisData(
            overall_score=60,
            strengths=[],
            weaknesses=[],
            risks=[],
            detailed_reasoning="",
            evidence=[],
        )

        mock_engine = _make_mock_engine()

        with (
            patch(
                "app.tasks.deep_analysis_tasks.AsyncSession",
                return_value=mock_session,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyDeepAnalysisRepository",
                return_value=deep_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyResumeRepository",
                return_value=resume_repo,
            ),
            patch(
                "app.tasks.deep_analysis_tasks.SQLAlchemyJobDescriptionRepository",
                return_value=jd_repo,
            ),
            patch("app.tasks.deep_analysis_tasks.AIServiceFactory") as mock_factory,
            patch("app.tasks.deep_analysis_tasks.engine", mock_engine),
        ):
            mock_factory.create.return_value = mock_ai_service

            from app.tasks.deep_analysis_tasks import _run_deep_analysis_async

            await _run_deep_analysis_async(str(pending_analysis.id))

        mock_ai_service.analyze_deep.assert_awaited_once_with(
            job_description=sample_jd.normalized_content,
            resume=sample_resume.normalized_content,
        )

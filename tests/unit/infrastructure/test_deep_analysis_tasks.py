import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.dto.ai import DeepAnalysisData, EvidenceItem
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.job_description import JobDescription
from app.domain.entities.resume import Resume
from app.domain.value_objects import AnalysisStatus


@pytest.mark.parametrize("stage", ["lookup", "factory", "save", "commit", "timeout"])
async def test_post_claim_failures_are_recorded_after_rollback(
    stage: str,
    pending_analysis: DeepAnalysis,
    sample_resume: Resume,
    sample_jd: JobDescription,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from app.tasks import deep_analysis_tasks as tasks

    session = AsyncMock()
    session.__aenter__.return_value = session
    deep = AsyncMock()
    deep.claim_pending.return_value = pending_analysis
    resumes, jobs, ai = AsyncMock(), AsyncMock(), AsyncMock()
    resumes.get_by_id.return_value = sample_resume
    jobs.get_by_id.return_value = sample_jd
    ai.analyze_deep.return_value = DeepAnalysisData(
        overall_score=80,
        strengths=[],
        weaknesses=[],
        risks=[],
        detailed_reasoning="Match",
        evidence=[],
    )
    failure = RuntimeError("infrastructure unavailable")
    if stage == "lookup":
        resumes.get_by_id.side_effect = failure
    elif stage == "save":
        deep.finish_claim.side_effect = [failure, True]
    elif stage == "commit":
        session.commit.side_effect = [None, failure, None]
    elif stage == "timeout":
        monkeypatch.setattr(tasks.settings, "deep_analysis_timeout_seconds", 0.01)

        async def stalled(**kwargs: object) -> None:
            await asyncio.Event().wait()

        ai.analyze_deep.side_effect = stalled

    with (
        patch.object(tasks, "engine", _make_mock_engine()),
        patch.object(tasks, "AsyncSession", return_value=session),
        patch.object(tasks, "SQLAlchemyDeepAnalysisRepository", return_value=deep),
        patch.object(tasks, "SQLAlchemyResumeRepository", return_value=resumes),
        patch.object(tasks, "SQLAlchemyJobDescriptionRepository", return_value=jobs),
        patch.object(tasks.AIServiceFactory, "create", return_value=ai) as factory,
    ):
        if stage == "factory":
            factory.side_effect = failure
        await tasks._run_deep_analysis_async(str(pending_analysis.id))

    session.rollback.assert_awaited_once()
    assert pending_analysis.status == AnalysisStatus.FAILED
    assert pending_analysis.error_message
    assert deep.finish_claim.await_args.args[0].status == AnalysisStatus.FAILED


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
        deep_repo.claim_pending = AsyncMock(return_value=pending_analysis)
        deep_repo.finish_claim = AsyncMock(return_value=pending_analysis)
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

        assert deep_repo.finish_claim.await_count == 1
        mock_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_analysis_not_found_aborts(self) -> None:
        fake_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        deep_repo = MagicMock()
        deep_repo.claim_pending = AsyncMock(return_value=None)
        deep_repo.finish_claim = AsyncMock()
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

        deep_repo.finish_claim.assert_not_awaited()

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
        deep_repo.claim_pending = AsyncMock(return_value=pending_analysis)
        deep_repo.finish_claim = AsyncMock(return_value=pending_analysis)
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
        deep_repo.claim_pending = AsyncMock(return_value=pending_analysis)
        deep_repo.finish_claim = AsyncMock(return_value=pending_analysis)
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
        deep_repo.claim_pending = AsyncMock(return_value=pending_analysis)
        deep_repo.finish_claim = AsyncMock(return_value=pending_analysis)
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
        assert pending_analysis.error_message == "An unexpected error occurred. Please try again."
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
        deep_repo.claim_pending = AsyncMock(return_value=pending_analysis)
        deep_repo.finish_claim = AsyncMock(return_value=pending_analysis)
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

        deep_repo.finish_claim.side_effect = track_status

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

        assert statuses == [AnalysisStatus.COMPLETED]
        deep_repo.claim_pending.assert_awaited_once_with(pending_analysis.id)

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
        deep_repo.claim_pending = AsyncMock(return_value=pending_analysis)
        deep_repo.finish_claim = AsyncMock(return_value=pending_analysis)
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
            mock_settings.deep_analysis_timeout_seconds = 240
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
        deep_repo.claim_pending = AsyncMock(return_value=pending_analysis)
        deep_repo.finish_claim = AsyncMock(return_value=pending_analysis)
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


async def test_dispatch_retries_publication_failures_without_consuming_pending_intent():
    from app.tasks.deep_analysis_tasks import _dispatch_pending_deep_analyses_async

    ids = [uuid.uuid4(), uuid.uuid4()]
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.scalars.side_effect = [ids, ids]
    with (
        patch("app.tasks.deep_analysis_tasks.AsyncSession", return_value=session),
        patch("app.tasks.deep_analysis_tasks.engine", _make_mock_engine()),
        patch("app.tasks.deep_analysis_tasks.run_deep_analysis.delay") as publish,
    ):
        publish.side_effect = [RuntimeError("broker down"), None, None, None]
        await _dispatch_pending_deep_analyses_async()
        await _dispatch_pending_deep_analyses_async()
    assert [c.args[0] for c in publish.call_args_list] == [str(i) for i in ids + ids]
    session.commit.assert_not_awaited()

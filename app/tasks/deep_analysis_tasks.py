import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from celery import Task as CeleryTask
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    JobDescriptionNotFoundError,
    ResumeNotFoundError,
    public_error_message,
)
from app.domain.value_objects import AnalysisStatus
from app.infrastructure.ai import AIServiceFactory
from app.infrastructure.persistence.database import engine
from app.infrastructure.persistence.repositories.deep_analysis_repo import (
    SQLAlchemyDeepAnalysisRepository,
)
from app.infrastructure.persistence.repositories.job_description_repo import (
    SQLAlchemyJobDescriptionRepository,
)
from app.infrastructure.persistence.repositories.resume_repo import SQLAlchemyResumeRepository
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0, name="tasks.run_deep_analysis")  # type: ignore[untyped-decorator]
def run_deep_analysis(self: CeleryTask, analysis_id_str: str) -> None:
    asyncio.run(_run_deep_analysis_async(analysis_id_str))


async def _run_deep_analysis_async(analysis_id_str: str) -> None:
    analysis_id = uuid.UUID(analysis_id_str)

    await engine.dispose()

    async with AsyncSession(engine) as session:
        deep_repo = SQLAlchemyDeepAnalysisRepository(session)
        resume_repo = SQLAlchemyResumeRepository(session)
        jd_repo = SQLAlchemyJobDescriptionRepository(session)

        analysis = await deep_repo.claim_pending(analysis_id)
        if analysis is None:
            logger.info("Deep analysis %s is absent or already claimed; skipping.", analysis_id)
            return

        await session.commit()

        try:
            async with asyncio.timeout(settings.deep_analysis_timeout_seconds):
                resume = await resume_repo.get_by_id(analysis.resume_id)
                jd = await jd_repo.get_by_id(analysis.job_description_id)
                if resume is None:
                    raise ResumeNotFoundError(analysis.resume_id)
                if jd is None:
                    raise JobDescriptionNotFoundError(analysis.job_description_id)

                ai_service = AIServiceFactory.create(
                    provider=settings.ai_deep_analysis_provider,
                    model=settings.ai_deep_analysis_model,
                )
                data = await ai_service.analyze_deep(
                    job_description=jd.normalized_content,
                    resume=resume.normalized_content,
                )
                analysis.overall_score = data.overall_score
                analysis.strengths = data.strengths
                analysis.weaknesses = data.weaknesses
                analysis.risks = data.risks
                analysis.detailed_reasoning = data.detailed_reasoning
                analysis.evidence = [e.model_dump() for e in data.evidence]
                analysis.raw_response = data.model_dump()
                analysis.status = AnalysisStatus.COMPLETED
                await deep_repo.finish_claim(analysis)
                await session.commit()
        except Exception as exc:
            logger.exception("Deep analysis %s failed", analysis_id)
            await session.rollback()
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = public_error_message(exc)
            # A failed transaction must be rolled back before recording its failure.
            # If the database remains unavailable, the recovery task expires the claim.
            await deep_repo.finish_claim(analysis)
            await session.commit()


@celery_app.task(name="tasks.dispatch_pending_deep_analyses")  # type: ignore[untyped-decorator]
def dispatch_pending_deep_analyses() -> None:
    asyncio.run(_dispatch_pending_deep_analyses_async())


async def _dispatch_pending_deep_analyses_async() -> None:
    """Publish a bounded leased batch, retrying after the lease if delivery is lost.

    Commit leases before contacting the broker. Concurrent sweeps skip locked rows;
    a crash or broker failure leaves the intent eligible after the retry delay.
    """
    await engine.dispose()
    async with AsyncSession(engine) as session:
        analysis_ids = await SQLAlchemyDeepAnalysisRepository(session).lease_pending_dispatch(
            settings.deep_analysis_dispatch_batch_size,
            settings.deep_analysis_dispatch_retry_seconds,
        )
        await session.commit()
    for analysis_id in analysis_ids:
        try:
            await asyncio.to_thread(run_deep_analysis.delay, str(analysis_id))
        except Exception:
            logger.exception(
                "Publication failed for %s; will retry after dispatch lease expires", analysis_id
            )


@celery_app.task(name="tasks.recover_expired_deep_analyses")  # type: ignore[untyped-decorator]
def recover_expired_deep_analyses() -> None:
    asyncio.run(_recover_expired_deep_analyses_async())


async def _recover_expired_deep_analyses_async() -> None:
    await engine.dispose()
    async with AsyncSession(engine) as session:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=settings.deep_analysis_timeout_seconds + 60
        )
        await SQLAlchemyDeepAnalysisRepository(session).fail_expired_claims(cutoff)
        await session.commit()

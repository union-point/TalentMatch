import asyncio
import logging
import uuid

from celery import Task as CeleryTask
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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

        analysis = await deep_repo.get_by_id(analysis_id)
        if analysis is None:
            logger.error("Deep analysis %s not found; aborting task.", analysis_id)
            return

        analysis.status = AnalysisStatus.IN_PROGRESS
        await deep_repo.save(analysis)
        await session.commit()

        resume = await resume_repo.get_by_id(analysis.resume_id)
        jd = await jd_repo.get_by_id(analysis.job_description_id)

        if resume is None or jd is None:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = "Referenced resume or job description not found"
            await deep_repo.save(analysis)
            await session.commit()
            logger.error("Deep analysis %s failed: resume or JD not found", analysis_id)
            return

        ai_service = AIServiceFactory.create(
            provider=settings.ai_deep_analysis_provider,
            model=settings.ai_deep_analysis_model,
        )
        try:
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
        except Exception as exc:
            logger.error("Deep analysis %s failed: %s", analysis_id, exc, exc_info=True)
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(exc)

        await deep_repo.save(analysis)
        await session.commit()

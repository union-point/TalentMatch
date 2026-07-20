import logging
import uuid

from app.application.dto.analysis import DeepAnalysisResultDTO
from app.core.exceptions import (
    AnalysisNotFoundError,
    JobDescriptionNotFoundError,
    ResumeNotFoundError,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.ports.repository import (
    DeepAnalysisRepository,
    JobDescriptionRepository,
    ResumeRepository,
)
from app.domain.value_objects import AnalysisStatus
from app.tasks.deep_analysis_tasks import run_deep_analysis as run_deep_analysis_task

logger = logging.getLogger(__name__)


class DeepAnalysisService:
    def __init__(
        self,
        jd_repository: JobDescriptionRepository,
        resume_repository: ResumeRepository,
        deep_analysis_repository: DeepAnalysisRepository,
    ) -> None:
        self._jd_repository = jd_repository
        self._resume_repository = resume_repository
        self._deep_analysis_repository = deep_analysis_repository

    async def request_deep_analysis(
        self,
        resume_id: uuid.UUID,
        job_description_id: uuid.UUID,
    ) -> DeepAnalysisResultDTO:
        jd = await self._jd_repository.get_by_id(job_description_id)
        if jd is None:
            raise JobDescriptionNotFoundError(job_description_id)

        resume = await self._resume_repository.get_by_id(resume_id)
        if resume is None:
            raise ResumeNotFoundError(resume_id)

        analysis = DeepAnalysis(
            resume_id=resume_id,
            job_description_id=job_description_id,
            status=AnalysisStatus.PENDING,
        )
        saved = await self._deep_analysis_repository.save(analysis)

        run_deep_analysis_task.delay(str(saved.id))

        logger.info(
            "Deep analysis requested: analysis_id=%s resume_id=%s jd_id=%s",
            saved.id,
            resume_id,
            job_description_id,
        )

        return DeepAnalysisResultDTO(
            analysis_id=saved.id,
            status=saved.status,
        )

    async def get_result(self, analysis_id: uuid.UUID) -> DeepAnalysisResultDTO:
        analysis = await self._deep_analysis_repository.get_by_id(analysis_id)
        if analysis is None:
            raise AnalysisNotFoundError(analysis_id)

        return DeepAnalysisResultDTO(
            analysis_id=analysis.id,
            status=analysis.status,
            result=analysis if analysis.status == AnalysisStatus.COMPLETED else None,
            error=analysis.error_message,
        )

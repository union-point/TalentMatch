import asyncio
import logging
import uuid

from app.application.dto.analysis import FastTrackResultDTO
from app.core.exceptions import AIResponseError, JobDescriptionNotFoundError
from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.ports.ai_service import AIService
from app.domain.ports.repository import (
    FastTrackRepository,
    JobDescriptionRepository,
    ResumeRepository,
)

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 5


class FastTrackService:
    def __init__(
        self,
        jd_repository: JobDescriptionRepository,
        resume_repository: ResumeRepository,
        fast_track_repository: FastTrackRepository,
        ai_service: AIService,
    ) -> None:
        self._jd_repository = jd_repository
        self._resume_repository = resume_repository
        self._fast_track_repository = fast_track_repository
        self._ai_service = ai_service

    async def run_fast_track(
        self,
        job_description_id: uuid.UUID,
        resume_ids: list[uuid.UUID],
    ) -> list[FastTrackResultDTO]:
        """Analyze all resumes against the given JD concurrently.

        At most MAX_CONCURRENT Gemini calls run at the same time.
        Individual failures are captured and returned as error entries so that
        one slow/failing resume never blocks the others.
        """
        jd = await self._jd_repository.get_by_id(job_description_id)
        if jd is None:
            raise JobDescriptionNotFoundError(job_description_id)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        tasks = [
            self._analyze_single(
                semaphore=semaphore,
                jd_text=jd.normalized_content,
                jd_id=job_description_id,
                resume_id=resume_id,
            )
            for resume_id in resume_ids
        ]

        results: list[FastTrackResultDTO] = await asyncio.gather(*tasks)
        return results

    async def _analyze_single(
        self,
        semaphore: asyncio.Semaphore,
        jd_text: str,
        jd_id: uuid.UUID,
        resume_id: uuid.UUID,
    ) -> FastTrackResultDTO:
        resume = await self._resume_repository.get_by_id(resume_id)
        if resume is None:
            logger.warning("Resume %s not found; skipping.", resume_id)
            return FastTrackResultDTO(
                resume_id=resume_id,
                error=f"Resume {resume_id} not found",
            )

        injection_warning = not resume.injection_scan_passed

        async with semaphore:
            try:
                data = await self._ai_service.analyze_fast_track(
                    job_description=jd_text,
                    resume=resume.normalized_content,
                )
            except (AIResponseError, Exception) as exc:
                logger.error(
                    "Fast-track analysis failed for resume %s: %s",
                    resume_id,
                    exc,
                )
                return FastTrackResultDTO(
                    resume_id=resume_id,
                    error=str(exc),
                    injection_warning=injection_warning,
                )

        if data.candidate_name and not resume.candidate_name:
            resume.candidate_name = data.candidate_name
            await self._resume_repository.update(resume)

        entity = FastTrackResult(
            resume_id=resume_id,
            job_description_id=jd_id,
            pass_fail=data.pass_fail,
            score=data.score,
            explanation=data.explanation,
            raw_response=data.model_dump(),
        )

        saved = await self._fast_track_repository.save(entity)

        if injection_warning:
            logger.warning(
                "Resume %s passed injection scan=False; result persisted with warning.",
                resume_id,
            )

        return FastTrackResultDTO(
            resume_id=resume_id,
            result=saved,
            injection_warning=injection_warning,
        )

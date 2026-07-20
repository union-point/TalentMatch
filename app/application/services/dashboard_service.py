import math
import uuid
from pathlib import Path

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
from app.domain.entities.resume import Resume
from app.domain.ports.repository import (
    DeepAnalysisRepository,
    FastTrackRepository,
    JobDescriptionRepository,
    ResumeRepository,
)

MIME_MAP: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "html": "text/html",
    "htm": "text/html",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


class DashboardService:
    def __init__(
        self,
        jd_repository: JobDescriptionRepository,
        resume_repository: ResumeRepository,
        fast_track_repository: FastTrackRepository,
        deep_analysis_repository: DeepAnalysisRepository,
    ) -> None:
        self._jd_repository = jd_repository
        self._resume_repository = resume_repository
        self._fast_track_repository = fast_track_repository
        self._deep_analysis_repository = deep_analysis_repository

    async def get_ranked_candidates(
        self,
        jd_id: uuid.UUID,
        min_score: int | None = None,
        pass_fail_only: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        jd = await self._jd_repository.get_by_id(jd_id)
        if jd is None:
            raise JobDescriptionNotFoundError(jd_id)

        results = await self._fast_track_repository.get_by_job_description_id(jd_id)
        if not results:
            return PaginatedResult(items=[], total=0, page=page, page_size=page_size, pages=0)

        resume_ids = {r.resume_id for r in results}
        resumes: dict[uuid.UUID, Resume] = {}
        for rid in resume_ids:
            resume = await self._resume_repository.get_by_id(rid)
            if resume is not None:
                resumes[rid] = resume

        deep_analyses: dict[uuid.UUID, DeepAnalysis] = {}
        for rid in resume_ids:
            da = await self._deep_analysis_repository.get_by_resume_and_jd(rid, jd_id)
            if da is not None:
                deep_analyses[rid] = da

        candidates: list[RankedCandidateItem] = []
        for r in results:
            resume = resumes.get(r.resume_id)
            if resume is None:
                continue

            if min_score is not None and r.score < min_score:
                continue
            if pass_fail_only and not r.pass_fail:
                continue
            if search:
                name = (resume.candidate_name or "").lower()
                if search.lower() not in name:
                    continue

            da = deep_analyses.get(r.resume_id)
            candidates.append(
                RankedCandidateItem(
                    resume_id=r.resume_id,
                    candidate_name=resume.candidate_name,
                    email=resume.email,
                    score=r.score,
                    pass_fail=r.pass_fail,
                    explanation=r.explanation,
                    injection_scan_passed=resume.injection_scan_passed,
                    has_deep_analysis=da is not None,
                    created_at=r.created_at.isoformat() if r.created_at else None,
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)

        total = len(candidates)
        pages = max(1, math.ceil(total / page_size))
        start = (page - 1) * page_size
        end = start + page_size
        page_items = candidates[start:end]

        return PaginatedResult(
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_candidate_detail(
        self,
        resume_id: uuid.UUID,
        jd_id: uuid.UUID,
    ) -> CandidateDetailResult:
        resume = await self._resume_repository.get_by_id(resume_id)
        if resume is None:
            raise ResumeNotFoundError(resume_id)

        jd = await self._jd_repository.get_by_id(jd_id)
        if jd is None:
            raise JobDescriptionNotFoundError(jd_id)

        fast_track = None
        ftrs = await self._fast_track_repository.get_by_job_description_id(jd_id)
        for ftr in ftrs:
            if ftr.resume_id == resume_id:
                fast_track = ftr
                break

        deep = await self._deep_analysis_repository.get_by_resume_and_jd(resume_id, jd_id)

        return CandidateDetailResult(
            resume=resume,
            fast_track=fast_track,
            deep_analysis=deep,
        )

    async def get_resume_file(self, resume_id: uuid.UUID) -> ResumeFileResult:
        resume = await self._resume_repository.get_by_id(resume_id)
        if resume is None:
            raise ResumeNotFoundError(resume_id)

        file_path = Path(resume.file_path)
        if not file_path.exists():
            raise ResumeNotFoundError(resume_id)

        mime_type = MIME_MAP.get(resume.file_type, "application/octet-stream")

        return ResumeFileResult(
            file_path=file_path,
            filename=resume.filename,
            mime_type=mime_type,
        )

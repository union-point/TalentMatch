import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.entities.ranked_candidate import RankedCandidateItem
from app.domain.ports.repository import FastTrackRepository
from app.domain.value_objects import CandidateFilter, CandidateSort, SortDirection
from app.infrastructure.persistence.models.deep_analysis import DeepAnalysisModel
from app.infrastructure.persistence.models.fast_track_result import FastTrackResultModel
from app.infrastructure.persistence.models.resume import ResumeModel


class SQLAlchemyFastTrackRepository(FastTrackRepository):
    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    async def save(self, result: FastTrackResult) -> FastTrackResult:
        if result.organization_id != self._organization_id:
            raise ValueError("Organization mismatch")
        model = FastTrackResultModel(
            id=result.id,
            organization_id=self._organization_id,
            resume_id=result.resume_id,
            job_description_id=result.job_description_id,
            pass_fail=result.pass_fail,
            score=result.score,
            explanation=result.explanation,
            raw_response=result.raw_response,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_domain(model)

    async def get_by_id(self, result_id: uuid.UUID) -> FastTrackResult | None:
        result = await self._session.execute(
            select(FastTrackResultModel).where(
                FastTrackResultModel.organization_id == self._organization_id,
                FastTrackResultModel.id == result_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def get_by_job_description_id(self, jd_id: uuid.UUID) -> list[FastTrackResult]:
        # Preserve history, but expose only the latest attempt for each candidate.
        ranked = (
            select(
                FastTrackResultModel.id,
                func.row_number()
                .over(
                    partition_by=FastTrackResultModel.resume_id,
                    order_by=(
                        FastTrackResultModel.created_at.desc(),
                        FastTrackResultModel.id.desc(),
                    ),
                )
                .label("position"),
            )
            .where(
                FastTrackResultModel.organization_id == self._organization_id,
                FastTrackResultModel.job_description_id == jd_id,
            )
            .subquery()
        )
        result = await self._session.execute(
            select(FastTrackResultModel)
            .join(ranked, FastTrackResultModel.id == ranked.c.id)
            .where(ranked.c.position == 1)
            .order_by(FastTrackResultModel.score.desc(), FastTrackResultModel.resume_id)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_ranked_candidates(
        self,
        jd_id: uuid.UUID,
        min_score: int | None = None,
        pass_fail_only: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: CandidateSort = "score",
        sort_direction: SortDirection = "desc",
        candidate_filter: CandidateFilter = "all",
    ) -> tuple[list[RankedCandidateItem], int]:
        latest = (
            select(
                FastTrackResultModel.id,
                func.row_number()
                .over(
                    partition_by=FastTrackResultModel.resume_id,
                    order_by=(
                        FastTrackResultModel.created_at.desc(),
                        FastTrackResultModel.id.desc(),
                    ),
                )
                .label("position"),
            )
            .where(
                FastTrackResultModel.organization_id == self._organization_id,
                FastTrackResultModel.job_description_id == jd_id,
            )
            .subquery()
        )
        has_deep = (
            select(DeepAnalysisModel.id)
            .where(
                DeepAnalysisModel.organization_id == self._organization_id,
                DeepAnalysisModel.resume_id == ResumeModel.id,
                DeepAnalysisModel.job_description_id == jd_id,
            )
            .exists()
        )
        query = (
            select(
                FastTrackResultModel.resume_id,
                ResumeModel.candidate_name,
                ResumeModel.email,
                FastTrackResultModel.score,
                FastTrackResultModel.pass_fail,
                FastTrackResultModel.explanation,
                ResumeModel.injection_scan_passed,
                has_deep.label("has_deep_analysis"),
                FastTrackResultModel.created_at,
            )
            .join(latest, latest.c.id == FastTrackResultModel.id)
            .join(ResumeModel, ResumeModel.id == FastTrackResultModel.resume_id)
            .where(
                latest.c.position == 1,
                ResumeModel.organization_id == self._organization_id,
                FastTrackResultModel.organization_id == self._organization_id,
            )
        )
        if min_score is not None:
            query = query.where(FastTrackResultModel.score >= min_score)
        if candidate_filter != "all":
            query = query.where(FastTrackResultModel.pass_fail.is_(candidate_filter == "pass"))
        elif pass_fail_only:
            query = query.where(FastTrackResultModel.pass_fail.is_(True))
        if search:
            query = query.where(
                or_(
                    func.lower(ResumeModel.candidate_name).contains(
                        search.lower(), autoescape=True
                    ),
                    func.lower(ResumeModel.email).contains(search.lower(), autoescape=True),
                )
            )
        total = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        sort_column = {
            "score": FastTrackResultModel.score,
            "candidate_name": func.lower(ResumeModel.candidate_name),
            "pass_fail": FastTrackResultModel.pass_fail,
        }[sort_by]
        order = sort_column.asc() if sort_direction == "asc" else sort_column.desc()
        rows = await self._session.execute(
            query.order_by(order.nulls_last(), FastTrackResultModel.resume_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            RankedCandidateItem(
                resume_id=row.resume_id,
                candidate_name=row.candidate_name,
                email=row.email,
                score=row.score,
                pass_fail=row.pass_fail,
                explanation=row.explanation,
                injection_scan_passed=row.injection_scan_passed,
                has_deep_analysis=row.has_deep_analysis,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ]
        return items, total or 0

    def _to_domain(self, model: FastTrackResultModel) -> FastTrackResult:
        return FastTrackResult(
            id=model.id,
            organization_id=model.organization_id,
            resume_id=model.resume_id,
            job_description_id=model.job_description_id,
            pass_fail=model.pass_fail,
            score=model.score,
            explanation=model.explanation,
            raw_response=model.raw_response,
            created_at=model.created_at,
        )

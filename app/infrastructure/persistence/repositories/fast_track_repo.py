import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.ports.repository import FastTrackRepository
from app.infrastructure.persistence.models.fast_track_result import FastTrackResultModel


class SQLAlchemyFastTrackRepository(FastTrackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, result: FastTrackResult) -> FastTrackResult:
        model = FastTrackResultModel(
            id=result.id,
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
            select(FastTrackResultModel).where(FastTrackResultModel.id == result_id)
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
            .where(FastTrackResultModel.job_description_id == jd_id)
            .subquery()
        )
        result = await self._session.execute(
            select(FastTrackResultModel)
            .join(ranked, FastTrackResultModel.id == ranked.c.id)
            .where(ranked.c.position == 1)
            .order_by(FastTrackResultModel.score.desc(), FastTrackResultModel.resume_id)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    def _to_domain(self, model: FastTrackResultModel) -> FastTrackResult:
        return FastTrackResult(
            id=model.id,
            resume_id=model.resume_id,
            job_description_id=model.job_description_id,
            pass_fail=model.pass_fail,
            score=model.score,
            explanation=model.explanation,
            raw_response=model.raw_response,
            created_at=model.created_at,
        )

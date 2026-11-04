import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.ports.repository import DeepAnalysisRepository
from app.domain.value_objects import AnalysisStatus
from app.infrastructure.persistence.models.deep_analysis import DeepAnalysisModel


class SQLAlchemyDeepAnalysisRepository(DeepAnalysisRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, analysis: DeepAnalysis) -> DeepAnalysis:
        result = await self._session.execute(
            select(DeepAnalysisModel).where(DeepAnalysisModel.id == analysis.id)
        )

        model = result.scalar_one_or_none()

        if model is None:
            model = DeepAnalysisModel(
                id=analysis.id,
                resume_id=analysis.resume_id,
                job_description_id=analysis.job_description_id,
            )
            self._session.add(model)

        model.overall_score = analysis.overall_score
        model.strengths = analysis.strengths
        model.weaknesses = analysis.weaknesses
        model.risks = analysis.risks
        model.detailed_reasoning = analysis.detailed_reasoning
        model.evidence = analysis.evidence
        model.raw_response = analysis.raw_response
        model.status = analysis.status.value
        model.error_message = analysis.error_message

        await self._session.flush()
        await self._session.refresh(model)

        return self._to_domain(model)

    async def lease_pending_dispatch(self, limit: int, retry_seconds: int) -> list[uuid.UUID]:
        """Reserve a bounded batch; the caller commits before publishing to the broker."""
        now = datetime.now(timezone.utc)
        result = await self._session.scalars(
            select(DeepAnalysisModel.id)
            .where(
                DeepAnalysisModel.status == AnalysisStatus.PENDING.value,
                or_(
                    DeepAnalysisModel.next_dispatch_at.is_(None),
                    DeepAnalysisModel.next_dispatch_at <= now,
                ),
            )
            .order_by(
                DeepAnalysisModel.next_dispatch_at.asc().nulls_first(),
                DeepAnalysisModel.created_at,
                DeepAnalysisModel.id,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        ids = list(result)
        if ids:
            await self._session.execute(
                update(DeepAnalysisModel)
                .where(DeepAnalysisModel.id.in_(ids))
                .values(next_dispatch_at=now + timedelta(seconds=retry_seconds))
            )
        return ids

    async def claim_pending(self, analysis_id: uuid.UUID) -> DeepAnalysis | None:
        """Atomically claim a pending job; duplicate deliveries do no work."""
        result = await self._session.execute(
            update(DeepAnalysisModel)
            .where(
                DeepAnalysisModel.id == analysis_id,
                DeepAnalysisModel.status == AnalysisStatus.PENDING.value,
            )
            .values(status=AnalysisStatus.IN_PROGRESS.value)
            .returning(DeepAnalysisModel)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def finish_claim(self, analysis: DeepAnalysis) -> bool:
        """Finish an active claim without overwriting a recovered terminal record."""
        result = await self._session.execute(
            update(DeepAnalysisModel)
            .where(
                DeepAnalysisModel.id == analysis.id,
                DeepAnalysisModel.status == AnalysisStatus.IN_PROGRESS.value,
            )
            .values(
                overall_score=analysis.overall_score,
                strengths=analysis.strengths,
                weaknesses=analysis.weaknesses,
                risks=analysis.risks,
                detailed_reasoning=analysis.detailed_reasoning,
                evidence=analysis.evidence,
                raw_response=analysis.raw_response,
                status=analysis.status.value,
                error_message=analysis.error_message,
            )
            .returning(DeepAnalysisModel.id)
        )
        return result.scalar_one_or_none() is not None

    async def fail_expired_claims(self, cutoff: datetime) -> None:
        """Bound crash recovery without automatically repeating paid AI work."""
        await self._session.execute(
            update(DeepAnalysisModel)
            .where(
                DeepAnalysisModel.status == AnalysisStatus.IN_PROGRESS.value,
                DeepAnalysisModel.updated_at < cutoff,
            )
            .values(
                status=AnalysisStatus.FAILED.value,
                error_message="Analysis timed out or its worker stopped. Please retry.",
            )
        )

    async def get_by_id(self, analysis_id: uuid.UUID) -> DeepAnalysis | None:
        result = await self._session.execute(
            select(DeepAnalysisModel).where(DeepAnalysisModel.id == analysis_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def get_by_resume_and_jd(
        self, resume_id: uuid.UUID, jd_id: uuid.UUID
    ) -> DeepAnalysis | None:
        result = await self._session.execute(
            select(DeepAnalysisModel)
            .where(
                DeepAnalysisModel.resume_id == resume_id,
                DeepAnalysisModel.job_description_id == jd_id,
            )
            .order_by(DeepAnalysisModel.created_at.desc(), DeepAnalysisModel.id.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    def _to_domain(self, model: DeepAnalysisModel) -> DeepAnalysis:
        return DeepAnalysis(
            id=model.id,
            resume_id=model.resume_id,
            job_description_id=model.job_description_id,
            overall_score=model.overall_score,
            strengths=model.strengths,
            weaknesses=model.weaknesses,
            risks=model.risks,
            detailed_reasoning=model.detailed_reasoning,
            evidence=model.evidence,
            raw_response=model.raw_response,
            status=AnalysisStatus(model.status),
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

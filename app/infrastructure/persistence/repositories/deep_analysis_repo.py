import uuid

from sqlalchemy import select
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
            select(DeepAnalysisModel).where(
                DeepAnalysisModel.resume_id == resume_id,
                DeepAnalysisModel.job_description_id == jd_id,
            )
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

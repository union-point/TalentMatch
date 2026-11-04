import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.job_description import JobDescription
from app.domain.ports.repository import JobDescriptionRepository
from app.infrastructure.persistence.models.job_description import JobDescriptionModel


class SQLAlchemyJobDescriptionRepository(JobDescriptionRepository):
    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    async def save(self, jd: JobDescription) -> JobDescription:
        if jd.organization_id != self._organization_id:
            raise ValueError("Organization mismatch")
        model = JobDescriptionModel(
            id=jd.id,
            organization_id=self._organization_id,
            title=jd.title,
            company=jd.company,
            original_content=jd.original_content,
            normalized_content=jd.normalized_content,
            file_path=jd.file_path,
            file_type=jd.file_type,
            injection_scan_passed=jd.injection_scan_passed,
            injection_scan_details=jd.injection_scan_details,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_domain(model)

    async def get_by_id(self, jd_id: uuid.UUID) -> JobDescription | None:
        result = await self._session.execute(
            select(JobDescriptionModel).where(
                JobDescriptionModel.organization_id == self._organization_id,
                JobDescriptionModel.id == jd_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def get_all(self) -> list[JobDescription]:
        result = await self._session.execute(
            select(JobDescriptionModel)
            .where(JobDescriptionModel.organization_id == self._organization_id)
            .order_by(JobDescriptionModel.created_at.desc())
        )
        return [self._to_domain(model) for model in result.scalars().all()]

    def _to_domain(self, model: JobDescriptionModel) -> JobDescription:
        return JobDescription(
            id=model.id,
            organization_id=model.organization_id,
            title=model.title,
            company=model.company,
            original_content=model.original_content,
            normalized_content=model.normalized_content,
            file_path=model.file_path,
            file_type=model.file_type,
            injection_scan_passed=model.injection_scan_passed,
            injection_scan_details=model.injection_scan_details,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

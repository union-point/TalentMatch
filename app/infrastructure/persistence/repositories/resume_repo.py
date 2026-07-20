import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.resume import Resume
from app.domain.ports.repository import ResumeRepository
from app.infrastructure.persistence.models.resume import ResumeModel


class SQLAlchemyResumeRepository(ResumeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, resume: Resume) -> Resume:
        model = ResumeModel(
            id=resume.id,
            filename=resume.filename,
            candidate_name=resume.candidate_name,
            email=resume.email,
            original_content=resume.original_content,
            normalized_content=resume.normalized_content,
            file_path=resume.file_path,
            file_type=resume.file_type,
            injection_scan_passed=resume.injection_scan_passed,
            injection_scan_details=resume.injection_scan_details,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update(self, resume: Resume) -> Resume:
        model = await self._session.get(ResumeModel, resume.id)
        if model is None:
            raise ValueError(f"Resume {resume.id} not found")
        model.candidate_name = resume.candidate_name
        model.email = resume.email
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def get_by_id(self, resume_id: uuid.UUID) -> Resume | None:
        result = await self._session.execute(select(ResumeModel).where(ResumeModel.id == resume_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    def _to_domain(self, model: ResumeModel) -> Resume:
        return Resume(
            id=model.id,
            filename=model.filename,
            candidate_name=model.candidate_name,
            email=model.email,
            original_content=model.original_content,
            normalized_content=model.normalized_content,
            file_path=model.file_path,
            file_type=model.file_type,
            injection_scan_passed=model.injection_scan_passed,
            injection_scan_details=model.injection_scan_details,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

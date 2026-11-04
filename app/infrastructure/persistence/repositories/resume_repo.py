import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.resume import Resume
from app.domain.entities.resume_summary import ResumeSummary
from app.domain.ports.repository import ResumeRepository
from app.infrastructure.persistence.models.fast_track_result import FastTrackResultModel
from app.infrastructure.persistence.models.resume import ResumeModel


class SQLAlchemyResumeRepository(ResumeRepository):
    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    async def get_unscored_for_job(
        self, jd_id: uuid.UUID, page: int = 1, page_size: int = 20, search: str | None = None
    ) -> tuple[list[ResumeSummary], int]:
        scored = (
            select(FastTrackResultModel.id)
            .where(
                FastTrackResultModel.organization_id == self._organization_id,
                FastTrackResultModel.job_description_id == jd_id,
                FastTrackResultModel.resume_id == ResumeModel.id,
            )
            .exists()
        )
        query = select(
            ResumeModel.id,
            ResumeModel.filename,
            ResumeModel.candidate_name,
            ResumeModel.email,
            ResumeModel.injection_scan_passed,
            ResumeModel.created_at,
        ).where(ResumeModel.organization_id == self._organization_id, ~scored)
        if search:
            query = query.where(
                or_(
                    func.lower(ResumeModel.filename).contains(search.lower(), autoescape=True),
                    func.lower(ResumeModel.candidate_name).contains(
                        search.lower(), autoescape=True
                    ),
                    func.lower(ResumeModel.email).contains(search.lower(), autoescape=True),
                )
            )
        total = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self._session.execute(
            query.order_by(ResumeModel.created_at.desc(), ResumeModel.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [
            ResumeSummary(
                id=row.id,
                filename=row.filename,
                candidate_name=row.candidate_name,
                email=row.email,
                injection_scan_passed=row.injection_scan_passed,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ], total or 0

    async def save(self, resume: Resume) -> Resume:
        if resume.organization_id != self._organization_id:
            raise ValueError("Organization mismatch")
        model = ResumeModel(
            id=resume.id,
            organization_id=self._organization_id,
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
        model = await self._session.scalar(
            select(ResumeModel).where(
                ResumeModel.id == resume.id, ResumeModel.organization_id == self._organization_id
            )
        )
        if model is None:
            raise ValueError(f"Resume {resume.id} not found")
        model.candidate_name = resume.candidate_name
        model.email = resume.email
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def get_by_id(self, resume_id: uuid.UUID) -> Resume | None:
        result = await self._session.execute(
            select(ResumeModel).where(
                ResumeModel.organization_id == self._organization_id, ResumeModel.id == resume_id
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    def _to_domain(self, model: ResumeModel) -> Resume:
        return Resume(
            id=model.id,
            organization_id=model.organization_id,
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

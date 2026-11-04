import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import JSON, MetaData, Uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.services.dashboard_service import DashboardService
from app.core.exceptions import JobDescriptionNotFoundError
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.models.fast_track_result import FastTrackResultModel
from app.infrastructure.persistence.models.resume import ResumeModel
from app.infrastructure.persistence.repositories.resume_repo import SQLAlchemyResumeRepository


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, UUID):
                column.type = Uuid(native_uuid=False)
            if isinstance(column.type, JSONB):
                column.type = JSON()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        async with AsyncSession(engine) as session:
            yield session
    finally:
        await engine.dispose()


async def test_unscored_resumes_survive_sessions_and_are_scoped_to_job_and_org(
    session: AsyncSession,
) -> None:
    organization, other_org, job, other_job = (uuid.uuid4() for _ in range(4))
    resume_ids = [uuid.uuid4() for _ in range(65)]
    for index, resume_id in enumerate(resume_ids):
        session.add(
            ResumeModel(
                id=resume_id,
                organization_id=organization,
                filename=f"resume-{index}.pdf",
                email=f"person{index}@example.com",
                candidate_name=f"Person {index}",
                file_path="resume.pdf",
                file_type="pdf",
                original_content="private text",
                normalized_content="private text",
                injection_scan_passed=True,
            )
        )
    session.add(
        ResumeModel(
            id=uuid.uuid4(),
            organization_id=other_org,
            filename="foreign.pdf",
            file_path="foreign.pdf",
            file_type="pdf",
            original_content="private",
            normalized_content="private",
            injection_scan_passed=True,
        )
    )
    # A failed screening attempt saves no result. Successful scores (including fail)
    # are excluded, but scoring against a different job must not exclude a resume.
    for resume_id, jd_id, score in [(resume_ids[0], job, 10), (resume_ids[1], other_job, 90)]:
        session.add(
            FastTrackResultModel(
                organization_id=organization,
                resume_id=resume_id,
                job_description_id=jd_id,
                score=score,
                pass_fail=score >= 50,
                explanation="Match",
            )
        )
    await session.commit()
    async with AsyncSession(session.bind) as fresh:
        repo = SQLAlchemyResumeRepository(fresh, organization)
        seen: list[uuid.UUID] = []
        for page in range(1, 5):
            items, total = await repo.get_unscored_for_job(job, page=page, page_size=20)
            assert total == 64
            seen.extend(item.id for item in items)
            assert all(not hasattr(item, "normalized_content") for item in items)
        assert len(set(seen)) == 64
        assert resume_ids[0] not in seen and resume_ids[1] in seen
        items, total = await repo.get_unscored_for_job(job, search="PERSON1@EXAMPLE.COM")
        assert total == 1 and items[0].id == resume_ids[1]
        assert (await repo.get_unscored_for_job(job, search="%"))[1] == 0
        foreign_repo = SQLAlchemyResumeRepository(fresh, other_org)
        assert (await foreign_repo.get_unscored_for_job(job))[1] == 1


async def test_unscored_service_rejects_inaccessible_job_before_listing() -> None:
    jobs, resumes = AsyncMock(), AsyncMock()
    jobs.get_by_id.return_value = None
    service = DashboardService(jobs, resumes, AsyncMock(), AsyncMock())
    with pytest.raises(JobDescriptionNotFoundError):
        await service.get_unscored_resumes(uuid.uuid4())
    resumes.get_unscored_for_job.assert_not_awaited()

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from sqlalchemy import JSON, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.services.dashboard_service import DashboardService
from app.domain.entities.resume import Resume
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.models.fast_track_result import FastTrackResultModel
from app.infrastructure.persistence.repositories.fast_track_repo import (
    SQLAlchemyFastTrackRepository,
)


async def test_latest_result_drives_ranking_filters_and_detail() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        async with AsyncSession(engine) as session:
            jd_id, resume_id, other_jd = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            now = datetime.now(timezone.utc)
            for number, job, created_at, score in [
                (1, jd_id, now - timedelta(days=1), 90),
                (2, jd_id, now, 80),
                (3, jd_id, now, 40),
                (4, other_jd, now + timedelta(days=1), 100),
            ]:
                session.add(
                    FastTrackResultModel(
                        id=uuid.UUID(int=15 * 2**124 + number),
                        resume_id=resume_id,
                        job_description_id=job,
                        created_at=created_at,
                        score=score,
                        pass_fail=score >= 50,
                        explanation="Match",
                    )
                )
            await session.flush()
            repo = SQLAlchemyFastTrackRepository(session)
            results = await repo.get_by_job_description_id(jd_id)
            assert [result.score for result in results] == [40]
            assert await repo.get_by_id(uuid.UUID(int=15 * 2**124 + 1)) is not None
            assert await repo.get_by_job_description_id(uuid.uuid4()) == []

            resumes, jobs, deep = AsyncMock(), AsyncMock(), AsyncMock()
            resumes.get_by_id.return_value = Resume(
                id=resume_id,
                filename="resume.pdf",
                file_path="resume.pdf",
                file_type="pdf",
                original_content="text",
                normalized_content="text",
                injection_scan_passed=True,
            )
            deep.get_by_resume_and_jd.return_value = None
            service = DashboardService(jobs, resumes, repo, deep)
            ranked = await service.get_ranked_candidates(jd_id)
            assert ranked.total == 1
            assert ranked.items[0].score == 40
            assert (await service.get_ranked_candidates(jd_id, min_score=50)).total == 0
            detail = await service.get_candidate_detail(resume_id, jd_id)
            assert detail.fast_track is not None
            assert detail.fast_track.score == 40
    finally:
        await engine.dispose()

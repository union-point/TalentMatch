import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.dto.ai import FastTrackResultData
from app.application.services.fast_track_service import FastTrackService
from app.domain.entities.identity import LEGACY_ORGANIZATION_ID as TEST_ORG_ID


async def test_concurrent_ai_serial_database_and_savepoint_recovery():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE results (id TEXT PRIMARY KEY)"))
    ids = [uuid.uuid4() for _ in range(4)]
    active_db = 0
    active_ai = 0
    peak_ai = 0
    async with AsyncSession(engine) as session:
        await session.execute(text("BEGIN"))

        @asynccontextmanager
        async def transaction():
            nonlocal active_db
            assert active_db == 0
            active_db += 1
            try:
                async with session.begin_nested():
                    await asyncio.sleep(0)
                    yield
            finally:
                active_db -= 1

        async def read(resume_id):
            assert active_db == 1
            await asyncio.sleep(0)
            if resume_id == ids[3]:
                await session.execute(text("SELECT * FROM missing_table"))
            return SimpleNamespace(
                normalized_content=str(resume_id),
                candidate_name=None,
                injection_scan_passed=True,
            )

        async def analyze(**kwargs):
            nonlocal active_ai, peak_ai
            active_ai += 1
            peak_ai = max(peak_ai, active_ai)
            await asyncio.sleep(0.01)
            active_ai -= 1
            return FastTrackResultData(pass_fail=True, score=80, explanation="Match")

        async def save(entity):
            assert active_db == 1
            await session.execute(
                text("INSERT INTO results VALUES (:id)"), {"id": str(entity.resume_id)}
            )
            if entity.resume_id == ids[1]:
                # A real SQL error after a successful write must roll back just this resume.
                await session.execute(
                    text("INSERT INTO results VALUES (:id)"), {"id": str(entity.resume_id)}
                )
            return entity

        jd = AsyncMock()
        jd.get_by_id.return_value = SimpleNamespace(
            normalized_content="Job", organization_id=TEST_ORG_ID
        )
        resumes = AsyncMock()
        resumes.get_by_id.side_effect = read
        results = AsyncMock()
        results.save.side_effect = save
        ai = AsyncMock()
        ai.analyze_fast_track.side_effect = analyze
        service = FastTrackService(jd, resumes, results, ai, transaction)
        response = await service.run_fast_track(uuid.uuid4(), ids)
        await session.commit()
        assert [r.resume_id for r in response] == ids
        assert [r.error is not None for r in response] == [False, True, False, True]
        assert peak_ai > 1
        persisted = set(await session.scalars(text("SELECT id FROM results")))
        assert persisted == {str(ids[0]), str(ids[2])}
    await engine.dispose()

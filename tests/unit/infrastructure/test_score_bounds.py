import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import JSON, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.dto.ai import DeepAnalysisData, FastTrackResultData
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.models.deep_analysis import DeepAnalysisModel
from app.infrastructure.persistence.models.fast_track_result import FastTrackResultModel


@pytest.mark.parametrize("score", [-1, 101, 999])
def test_provider_rejects_out_of_range_scores(score: int) -> None:
    with pytest.raises(ValidationError):
        FastTrackResultData(score=score, pass_fail=True, explanation="Match")
    with pytest.raises(ValidationError):
        DeepAnalysisData(
            overall_score=score,
            strengths=[],
            weaknesses=[],
            risks=[],
            evidence=[],
            detailed_reasoning="Match",
        )


@pytest.mark.parametrize("score", [0, 100])
def test_provider_accepts_score_boundaries(score: int) -> None:
    assert FastTrackResultData(score=score, pass_fail=True, explanation="Match").score == score
    assert (
        DeepAnalysisData(
            overall_score=score,
            strengths=[],
            weaknesses=[],
            risks=[],
            evidence=[],
            detailed_reasoning="Match",
        ).overall_score
        == score
    )


async def test_database_enforces_bounds_and_allows_pending_null_score() -> None:
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
            for score in [-1, 101, 999, 0, 100]:
                for model in [
                    FastTrackResultModel(
                        resume_id=uuid.uuid4(),
                        job_description_id=uuid.uuid4(),
                        score=score,
                        pass_fail=True,
                        explanation="Match",
                    ),
                    DeepAnalysisModel(
                        resume_id=uuid.uuid4(),
                        job_description_id=uuid.uuid4(),
                        overall_score=score,
                        status="completed",
                    ),
                ]:
                    session.add(model)
                    if score not in [0, 100]:
                        with pytest.raises(IntegrityError):
                            await session.flush()
                    else:
                        await session.flush()
                    await session.rollback()
            session.add(
                DeepAnalysisModel(
                    resume_id=uuid.uuid4(), job_description_id=uuid.uuid4(), status="pending"
                )
            )
            await session.flush()
    finally:
        await engine.dispose()

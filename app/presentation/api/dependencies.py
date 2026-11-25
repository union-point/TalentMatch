from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.dashboard_service import DashboardService
from app.application.services.deep_analysis_service import DeepAnalysisService
from app.application.services.fast_track_service import FastTrackService
from app.application.services.ingestion_service import IngestionService
from app.application.services.job_description_query_service import JobDescriptionQueryService
from app.config import settings
from app.domain.entities.identity import Principal
from app.infrastructure.ai.ai_factory import AIServiceFactory
from app.infrastructure.parsing.parser_factory import get_parser_for_file
from app.infrastructure.parsing.text_normalizer import normalize_text, strip_markdown_formatting
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.deep_analysis_repo import (
    SQLAlchemyDeepAnalysisRepository,
)
from app.infrastructure.persistence.repositories.fast_track_repo import (
    SQLAlchemyFastTrackRepository,
)
from app.infrastructure.persistence.repositories.job_description_repo import (
    SQLAlchemyJobDescriptionRepository,
)
from app.infrastructure.persistence.repositories.resume_repo import SQLAlchemyResumeRepository
from app.infrastructure.security.prompt_injection_detector import detect_injection
from app.infrastructure.storage.local_file_storage import get_local_file_storage
from app.presentation.api.auth_dependencies import get_principal


async def get_ingestion_service(
    session: AsyncSession = Depends(get_db),
    actor: Principal = Depends(get_principal),
) -> AsyncGenerator[IngestionService, None]:

    jd_repo = SQLAlchemyJobDescriptionRepository(session, actor.organization_id)
    resume_repo = SQLAlchemyResumeRepository(session, actor.organization_id)
    file_storage = get_local_file_storage()
    yield IngestionService(
        jd_repo,
        resume_repo,
        file_storage,
        actor.organization_id,
        session.begin,
        parser_for_file=get_parser_for_file,
        normalize_job_description=normalize_text,
        normalize_resume=strip_markdown_formatting,
        scan_for_injection=detect_injection,
    )


async def get_job_description_query_service(
    session: AsyncSession = Depends(get_db),
    actor: Principal = Depends(get_principal),
) -> JobDescriptionQueryService:
    repository = SQLAlchemyJobDescriptionRepository(session, actor.organization_id)
    return JobDescriptionQueryService(repository)


async def get_fast_track_service(
    session: AsyncSession = Depends(get_db),
    actor: Principal = Depends(get_principal),
) -> AsyncGenerator[FastTrackService, None]:

    jd_repo = SQLAlchemyJobDescriptionRepository(session, actor.organization_id)
    resume_repo = SQLAlchemyResumeRepository(session, actor.organization_id)
    fast_track_repo = SQLAlchemyFastTrackRepository(session, actor.organization_id)
    ai_service = AIServiceFactory.create(
        provider=settings.ai_fast_track_provider,
        model=settings.ai_fast_track_model,
    )
    yield FastTrackService(jd_repo, resume_repo, fast_track_repo, ai_service, session.begin_nested)


async def get_dashboard_service(
    session: AsyncSession = Depends(get_db),
    actor: Principal = Depends(get_principal),
) -> AsyncGenerator[DashboardService, None]:
    jd_repo = SQLAlchemyJobDescriptionRepository(session, actor.organization_id)
    resume_repo = SQLAlchemyResumeRepository(session, actor.organization_id)
    fast_track_repo = SQLAlchemyFastTrackRepository(session, actor.organization_id)
    deep_repo = SQLAlchemyDeepAnalysisRepository(session, actor.organization_id)
    yield DashboardService(jd_repo, resume_repo, fast_track_repo, deep_repo)


async def get_deep_analysis_service(
    session: AsyncSession = Depends(get_db),
    actor: Principal = Depends(get_principal),
) -> AsyncGenerator[DeepAnalysisService, None]:

    jd_repo = SQLAlchemyJobDescriptionRepository(session, actor.organization_id)
    resume_repo = SQLAlchemyResumeRepository(session, actor.organization_id)
    deep_repo = SQLAlchemyDeepAnalysisRepository(session, actor.organization_id)
    yield DeepAnalysisService(jd_repo, resume_repo, deep_repo)

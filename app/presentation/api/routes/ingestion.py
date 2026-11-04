import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.ingestion_service import IngestionService
from app.config import settings
from app.domain.entities.identity import Principal
from app.domain.value_objects import InjectionScanResult
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.job_description_repo import (
    SQLAlchemyJobDescriptionRepository,
)
from app.presentation.api.auth_dependencies import get_principal
from app.presentation.api.dependencies import get_ingestion_service
from app.presentation.api.uploads import read_upload
from app.presentation.schemas.job_description import (
    InjectionScanDetails,
    JobDescriptionDetailResponse,
    JobDescriptionListItem,
    JobDescriptionListResponse,
    JobDescriptionUploadResponse,
)
from app.presentation.schemas.resume import (
    BatchUploadResponse,
    ResumeUploadFailure,
    ResumeUploadResponse,
)

router = APIRouter(prefix="/api/v1", tags=["ingestion"])


def _to_scan_details(scan: InjectionScanResult) -> InjectionScanDetails:
    return InjectionScanDetails(
        passed=scan.passed,
        suspicion_score=scan.suspicion_score,
        details=scan.details,
    )


@router.post("/job-descriptions/upload", response_model=JobDescriptionUploadResponse)
async def upload_job_description(
    file: UploadFile = File(...),
    title: str = Form(...),
    company: str = Form(...),
    service: IngestionService = Depends(get_ingestion_service),
) -> JobDescriptionUploadResponse:
    content = await read_upload(file)
    result = await service.ingest_job_description(
        file_content=content,
        filename=file.filename or "unknown",
        title=title,
        company=company,
    )
    return JobDescriptionUploadResponse(
        id=str(result.id),
        filename=result.filename,
        file_type=result.file_type,
        original_content_length=result.original_content_length,
        normalized_content_length=result.normalized_content_length,
        injection_scan=_to_scan_details(result.injection_scan),
    )


@router.get(
    "/job-descriptions",
    response_model=JobDescriptionListResponse,
    summary="List all job descriptions",
)
async def list_job_descriptions(
    session: AsyncSession = Depends(get_db),
    actor: Principal = Depends(get_principal),
) -> JobDescriptionListResponse:
    repo = SQLAlchemyJobDescriptionRepository(session, actor.organization_id)
    items = await repo.get_all()
    return JobDescriptionListResponse(
        items=[
            JobDescriptionListItem(
                id=str(jd.id),
                title=jd.title,
                company=jd.company,
                file_type=jd.file_type,
                injection_scan_passed=jd.injection_scan_passed,
                created_at=jd.created_at.isoformat() if jd.created_at else None,
            )
            for jd in items
        ],
        total=len(items),
    )


@router.get(
    "/job-descriptions/{jd_id}",
    response_model=JobDescriptionDetailResponse,
    summary="Get a job description by ID",
)
async def get_job_description(
    jd_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    actor: Principal = Depends(get_principal),
) -> JobDescriptionDetailResponse:
    repo = SQLAlchemyJobDescriptionRepository(session, actor.organization_id)
    jd = await repo.get_by_id(jd_id)
    if jd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job description {jd_id} not found",
        )
    return JobDescriptionDetailResponse(
        id=str(jd.id),
        title=jd.title,
        company=jd.company,
        file_type=jd.file_type,
        original_content=jd.original_content,
        normalized_content=jd.normalized_content,
        injection_scan=InjectionScanDetails(
            passed=jd.injection_scan_passed,
            suspicion_score=jd.injection_scan_details.get("suspicion_score", 0)
            if jd.injection_scan_details
            else 0,
            details=jd.injection_scan_details,
        ),
        created_at=jd.created_at.isoformat() if jd.created_at else None,
        updated_at=jd.updated_at.isoformat() if jd.updated_at else None,
    )


@router.post("/resumes/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    candidate_name: str | None = Form(None),
    email: str | None = Form(None),
    service: IngestionService = Depends(get_ingestion_service),
) -> ResumeUploadResponse:
    content = await read_upload(file)
    result = await service.ingest_resume(
        file_content=content,
        filename=file.filename or "unknown",
        candidate_name=candidate_name,
        email=email,
    )
    return ResumeUploadResponse(
        id=str(result.id),
        filename=result.filename,
        file_type=result.file_type,
        original_content_length=result.original_content_length,
        normalized_content_length=result.normalized_content_length,
        injection_scan=_to_scan_details(result.injection_scan),
    )


@router.post(
    "/resumes/batch-upload",
    response_model=BatchUploadResponse,
    description="Each file is committed independently. The response includes saved resumes "
    "and per-file errors. Request size/count violations reject the entire request "
    "before ingestion.",
)
async def batch_upload_resumes(
    files: list[UploadFile] = File(...),
    service: IngestionService = Depends(get_ingestion_service),
) -> BatchUploadResponse:
    if len(files) > settings.max_upload_files:
        raise HTTPException(status_code=413, detail="Too many uploaded files")
    file_tuples: list[tuple[bytes, str]] = []
    remaining = settings.max_upload_batch_bytes
    for upload_file in files:
        content = await read_upload(upload_file, remaining)
        remaining -= len(content)
        file_tuples.append((content, upload_file.filename or "unknown"))

    results = await service.ingest_resumes_batch(file_tuples)

    responses = [
        ResumeUploadResponse(
            id=str(r.id),
            filename=r.filename,
            file_type=r.file_type,
            original_content_length=r.original_content_length,
            normalized_content_length=r.normalized_content_length,
            injection_scan=_to_scan_details(r.injection_scan),
        )
        for r in results.resumes
    ]

    return BatchUploadResponse(
        resumes=responses,
        total=len(file_tuples),
        succeeded=len(responses),
        failed=len(results.errors),
        errors=[
            ResumeUploadFailure(index=e.index, filename=e.filename, error=e.error)
            for e in results.errors
        ],
    )

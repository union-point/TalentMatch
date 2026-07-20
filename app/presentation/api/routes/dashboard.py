import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.application.services.dashboard_service import DashboardService
from app.core.exceptions import JobDescriptionNotFoundError, ResumeNotFoundError
from app.presentation.api.dependencies import get_dashboard_service
from app.presentation.schemas.dashboard import (
    CandidateDetailSchema,
    DeepAnalysisSummarySchema,
    FastTrackSummarySchema,
    PaginatedResponse,
    RankedCandidateSchema,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get(
    "/jobs/{jd_id}/candidates",
    response_model=PaginatedResponse,
    summary="List candidates ranked by score for a job description",
)
async def get_ranked_candidates(
    jd_id: uuid.UUID,
    min_score: int | None = Query(None, ge=0, le=100),
    pass_fail_only: bool | None = Query(None),
    q: str | None = Query(None, description="Search by candidate name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: DashboardService = Depends(get_dashboard_service),
) -> PaginatedResponse:
    try:
        result = await service.get_ranked_candidates(
            jd_id=jd_id,
            min_score=min_score,
            pass_fail_only=pass_fail_only,
            search=q,
            page=page,
            page_size=page_size,
        )
    except JobDescriptionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PaginatedResponse(
        items=[
            RankedCandidateSchema(
                resume_id=item.resume_id,
                candidate_name=item.candidate_name,
                email=item.email,
                score=item.score,
                pass_fail=item.pass_fail,
                explanation=item.explanation,
                injection_scan_passed=item.injection_scan_passed,
                has_deep_analysis=item.has_deep_analysis,
                created_at=item.created_at,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.get(
    "/candidates/{resume_id}/job/{jd_id}",
    response_model=CandidateDetailSchema,
    summary="Get detailed view of a candidate against a job description",
)
async def get_candidate_detail(
    resume_id: uuid.UUID,
    jd_id: uuid.UUID,
    service: DashboardService = Depends(get_dashboard_service),
) -> CandidateDetailSchema:
    try:
        detail = await service.get_candidate_detail(
            resume_id=resume_id,
            jd_id=jd_id,
        )
    except (ResumeNotFoundError, JobDescriptionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    fast_track_schema = None
    if detail.fast_track is not None:
        fast_track_schema = FastTrackSummarySchema(
            result_id=detail.fast_track.id,
            score=detail.fast_track.score,
            pass_fail=detail.fast_track.pass_fail,
            explanation=detail.fast_track.explanation,
            created_at=detail.fast_track.created_at.isoformat()
            if detail.fast_track.created_at
            else None,
        )

    deep_schema = None
    if detail.deep_analysis is not None:
        deep_schema = DeepAnalysisSummarySchema(
            analysis_id=detail.deep_analysis.id,
            status=detail.deep_analysis.status.value,
            overall_score=detail.deep_analysis.overall_score,
            strengths=detail.deep_analysis.strengths,
            weaknesses=detail.deep_analysis.weaknesses,
            risks=detail.deep_analysis.risks,
            detailed_reasoning=detail.deep_analysis.detailed_reasoning,
            error_message=detail.deep_analysis.error_message,
        )

    return CandidateDetailSchema(
        resume_id=detail.resume.id,
        filename=detail.resume.filename,
        candidate_name=detail.resume.candidate_name,
        email=detail.resume.email,
        file_type=detail.resume.file_type,
        injection_scan_passed=detail.resume.injection_scan_passed,
        fast_track=fast_track_schema,
        deep_analysis=deep_schema,
    )


@router.get(
    "/candidates/{resume_id}/resume-file",
    summary="Download the original resume file",
)
async def get_resume_file(
    resume_id: uuid.UUID,
    service: DashboardService = Depends(get_dashboard_service),
) -> FileResponse:
    try:
        file_result = await service.get_resume_file(resume_id)
    except ResumeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return FileResponse(
        path=file_result.file_path,
        filename=file_result.filename,
        media_type=file_result.mime_type,
    )

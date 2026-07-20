import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.services.deep_analysis_service import (
    DeepAnalysisService,
)
from app.application.services.fast_track_service import FastTrackService
from app.core.exceptions import (
    AnalysisNotFoundError,
    JobDescriptionNotFoundError,
    ResumeNotFoundError,
)
from app.presentation.api.dependencies import (
    get_deep_analysis_service,
    get_fast_track_service,
)
from app.presentation.schemas.analysis import (
    DeepAnalysisRequest,
    DeepAnalysisResponse,
    DeepAnalysisResultSchema,
    EvidenceSchema,
    FastTrackRequest,
    FastTrackResponse,
    FastTrackResultSchema,
)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.post(
    "/fast-track",
    response_model=FastTrackResponse,
    status_code=status.HTTP_200_OK,
    summary="Run fast-track batch analysis",
    description=(
        "Analyze all provided resumes against the given job description "
        "concurrently. Returns a scored result per resume. Partial failures "
        "are reported without aborting the batch."
    ),
)
async def run_fast_track(
    body: FastTrackRequest,
    service: FastTrackService = Depends(get_fast_track_service),
) -> FastTrackResponse:
    try:
        dto_results = await service.run_fast_track(
            job_description_id=body.job_description_id,
            resume_ids=body.resume_ids,
        )
    except JobDescriptionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    results: list[FastTrackResultSchema] = []
    for dto in dto_results:
        if dto.result is not None:
            results.append(
                FastTrackResultSchema(
                    resume_id=dto.resume_id,
                    result_id=dto.result.id,
                    pass_fail=dto.result.pass_fail,
                    score=dto.result.score,
                    explanation=dto.result.explanation,
                    injection_warning=dto.injection_warning,
                )
            )
        else:
            results.append(
                FastTrackResultSchema(
                    resume_id=dto.resume_id,
                    injection_warning=dto.injection_warning,
                    error=dto.error,
                )
            )

    succeeded = sum(1 for r in results if r.error is None)
    failed = len(results) - succeeded

    return FastTrackResponse(
        job_description_id=body.job_description_id,
        results=results,
        total=len(results),
        succeeded=succeeded,
        failed=failed,
    )


@router.post(
    "/deep",
    response_model=DeepAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request deep analysis for a candidate",
    description=(
        "Creates a pending deep analysis record and dispatches async processing. "
        "Poll GET /deep/{analysis_id} for the result."
    ),
)
async def request_deep_analysis(
    body: DeepAnalysisRequest,
    service: DeepAnalysisService = Depends(get_deep_analysis_service),
) -> DeepAnalysisResponse:
    try:
        dto = await service.request_deep_analysis(
            resume_id=body.resume_id,
            job_description_id=body.job_description_id,
        )
    except (JobDescriptionNotFoundError, ResumeNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return DeepAnalysisResponse(
        analysis_id=dto.analysis_id,
        status=dto.status.value,
    )


@router.get(
    "/deep/{analysis_id}",
    response_model=DeepAnalysisResultSchema,
    status_code=status.HTTP_200_OK,
    summary="Get deep analysis result",
    description=(
        "Returns the current status of a deep analysis. "
        "When status is 'completed', result fields are populated."
    ),
)
async def get_deep_analysis(
    analysis_id: uuid.UUID,
    service: DeepAnalysisService = Depends(get_deep_analysis_service),
) -> DeepAnalysisResultSchema:
    try:
        dto = await service.get_result(analysis_id)
    except AnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if dto.result is not None:
        return DeepAnalysisResultSchema(
            analysis_id=dto.analysis_id,
            status=dto.status.value,
            overall_score=dto.result.overall_score,
            strengths=dto.result.strengths,
            weaknesses=dto.result.weaknesses,
            risks=dto.result.risks,
            detailed_reasoning=dto.result.detailed_reasoning,
            evidence=(
                [EvidenceSchema(**e) for e in dto.result.evidence] if dto.result.evidence else None
            ),
        )

    return DeepAnalysisResultSchema(
        analysis_id=dto.analysis_id,
        status=dto.status.value,
        error_message=dto.error,
    )

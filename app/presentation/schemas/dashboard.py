import uuid

from pydantic import BaseModel


class RankedCandidateSchema(BaseModel):
    resume_id: uuid.UUID
    candidate_name: str | None = None
    email: str | None = None
    score: int
    pass_fail: bool
    explanation: str
    injection_scan_passed: bool
    has_deep_analysis: bool = False
    created_at: str | None = None


class PaginatedResponse(BaseModel):
    items: list[RankedCandidateSchema]
    total: int
    page: int
    page_size: int
    pages: int


class FastTrackSummarySchema(BaseModel):
    result_id: uuid.UUID
    score: int
    pass_fail: bool
    explanation: str
    created_at: str | None = None


class DeepAnalysisSummarySchema(BaseModel):
    analysis_id: uuid.UUID
    status: str
    overall_score: int | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    risks: list[str] | None = None
    detailed_reasoning: str | None = None
    error_message: str | None = None


class CandidateDetailSchema(BaseModel):
    resume_id: uuid.UUID
    filename: str
    candidate_name: str | None = None
    email: str | None = None
    file_type: str
    injection_scan_passed: bool
    fast_track: FastTrackSummarySchema | None = None
    deep_analysis: DeepAnalysisSummarySchema | None = None

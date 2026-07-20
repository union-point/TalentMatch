import uuid

from pydantic import BaseModel, Field


class FastTrackRequest(BaseModel):
    job_description_id: uuid.UUID
    resume_ids: list[uuid.UUID] = Field(..., min_length=1)


class FastTrackResultSchema(BaseModel):
    resume_id: uuid.UUID
    result_id: uuid.UUID | None = None
    pass_fail: bool | None = None
    score: int | None = None
    explanation: str | None = None
    injection_warning: bool = False
    error: str | None = None


class FastTrackResponse(BaseModel):
    job_description_id: uuid.UUID
    results: list[FastTrackResultSchema]
    total: int
    succeeded: int
    failed: int


class DeepAnalysisRequest(BaseModel):
    resume_id: uuid.UUID
    job_description_id: uuid.UUID


class DeepAnalysisResponse(BaseModel):
    analysis_id: uuid.UUID
    status: str


class EvidenceSchema(BaseModel):
    text: str
    category: str


class DeepAnalysisResultSchema(BaseModel):
    analysis_id: uuid.UUID
    status: str
    overall_score: int | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    risks: list[str] | None = None
    detailed_reasoning: str | None = None
    evidence: list[EvidenceSchema] | None = None
    error_message: str | None = None

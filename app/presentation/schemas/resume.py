from pydantic import BaseModel, Field

from app.presentation.schemas.job_description import InjectionScanDetails


class ResumeUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    original_content_length: int
    normalized_content_length: int
    injection_scan: InjectionScanDetails


class ResumeUploadFailure(BaseModel):
    index: int
    filename: str
    error: str


class BatchUploadResponse(BaseModel):
    resumes: list[ResumeUploadResponse]
    total: int
    succeeded: int
    failed: int
    errors: list[ResumeUploadFailure] = Field(default_factory=list)

from pydantic import BaseModel

from app.presentation.schemas.job_description import InjectionScanDetails


class ResumeUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    original_content_length: int
    normalized_content_length: int
    injection_scan: InjectionScanDetails


class BatchUploadResponse(BaseModel):
    resumes: list[ResumeUploadResponse]
    total: int
    succeeded: int
    failed: int

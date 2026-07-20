from pydantic import BaseModel


class InjectionScanDetails(BaseModel):
    passed: bool
    suspicion_score: int = 0
    details: dict[str, object] | None = None


class JobDescriptionUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    original_content_length: int
    normalized_content_length: int
    injection_scan: InjectionScanDetails


class JobDescriptionListItem(BaseModel):
    id: str
    title: str
    company: str
    file_type: str
    injection_scan_passed: bool
    created_at: str | None = None


class JobDescriptionListResponse(BaseModel):
    items: list[JobDescriptionListItem]
    total: int


class JobDescriptionDetailResponse(BaseModel):
    id: str
    title: str
    company: str
    file_type: str
    original_content: str
    normalized_content: str
    injection_scan: InjectionScanDetails
    created_at: str | None = None
    updated_at: str | None = None

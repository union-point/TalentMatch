import uuid
from dataclasses import dataclass

from app.domain.value_objects import InjectionScanResult


@dataclass
class IngestionResponse:
    id: uuid.UUID
    filename: str
    file_type: str
    original_content_length: int
    normalized_content_length: int
    injection_scan: InjectionScanResult


@dataclass
class IngestionFailure:
    index: int
    filename: str
    error: str


@dataclass
class BatchIngestionResult:
    resumes: list[IngestionResponse]
    errors: list[IngestionFailure]

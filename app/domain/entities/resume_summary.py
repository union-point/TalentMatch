import uuid
from dataclasses import dataclass


@dataclass
class ResumeSummary:
    id: uuid.UUID
    filename: str
    candidate_name: str | None
    email: str | None
    injection_scan_passed: bool
    created_at: str | None

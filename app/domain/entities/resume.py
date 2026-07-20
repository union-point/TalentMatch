import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Resume:
    filename: str
    original_content: str
    normalized_content: str
    file_path: str
    file_type: str
    injection_scan_passed: bool
    candidate_name: str | None = None
    email: str | None = None
    injection_scan_details: dict[str, object] | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None

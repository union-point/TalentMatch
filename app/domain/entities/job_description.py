import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobDescription:
    title: str
    company: str
    original_content: str
    normalized_content: str
    file_path: str
    file_type: str
    injection_scan_passed: bool
    injection_scan_details: dict[str, object] | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None

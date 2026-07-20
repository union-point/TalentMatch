import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FastTrackResult:
    resume_id: uuid.UUID
    job_description_id: uuid.UUID
    pass_fail: bool
    score: int
    explanation: str
    raw_response: dict[str, object] | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime | None = None

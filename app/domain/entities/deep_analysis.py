import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.value_objects import AnalysisStatus


@dataclass
class DeepAnalysis:
    resume_id: uuid.UUID
    job_description_id: uuid.UUID
    status: AnalysisStatus = AnalysisStatus.PENDING
    overall_score: int | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    risks: list[str] | None = None
    detailed_reasoning: str | None = None
    evidence: list[dict[str, object]] | None = None
    raw_response: dict[str, object] | None = None
    error_message: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None

import uuid
from dataclasses import dataclass


@dataclass
class RankedCandidateItem:
    resume_id: uuid.UUID
    candidate_name: str | None
    email: str | None
    score: int
    pass_fail: bool
    explanation: str
    injection_scan_passed: bool
    has_deep_analysis: bool = False
    created_at: str | None = None

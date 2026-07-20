import uuid
from dataclasses import dataclass
from pathlib import Path

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.entities.resume import Resume


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


@dataclass
class PaginatedResult:
    items: list[RankedCandidateItem]
    total: int
    page: int
    page_size: int
    pages: int


@dataclass
class CandidateDetailResult:
    resume: Resume
    fast_track: FastTrackResult | None = None
    deep_analysis: DeepAnalysis | None = None


@dataclass
class ResumeFileResult:
    file_path: Path
    filename: str
    mime_type: str

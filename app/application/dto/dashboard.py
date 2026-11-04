from dataclasses import dataclass
from pathlib import Path

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.entities.ranked_candidate import RankedCandidateItem as RankedCandidateItem
from app.domain.entities.resume import Resume
from app.domain.entities.resume_summary import ResumeSummary


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


@dataclass
class UnscoredResumesResult:
    items: list[ResumeSummary]
    total: int
    page: int
    page_size: int
    pages: int

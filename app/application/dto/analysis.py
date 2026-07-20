import uuid

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.value_objects import AnalysisStatus


class FastTrackResultDTO:
    """Result for a single resume's fast-track analysis (success or failure)."""

    __slots__ = ("resume_id", "result", "error", "injection_warning")

    def __init__(
        self,
        resume_id: uuid.UUID,
        result: FastTrackResult | None = None,
        error: str | None = None,
        injection_warning: bool = False,
    ) -> None:
        self.resume_id = resume_id
        self.result = result
        self.error = error
        self.injection_warning = injection_warning


class DeepAnalysisResultDTO:
    __slots__ = ("analysis_id", "status", "result", "error")

    def __init__(
        self,
        analysis_id: uuid.UUID,
        status: AnalysisStatus,
        result: DeepAnalysis | None = None,
        error: str | None = None,
    ) -> None:
        self.analysis_id = analysis_id
        self.status = status
        self.result = result
        self.error = error

from app.infrastructure.persistence.models.base import Base, UUIDMixin
from app.infrastructure.persistence.models.deep_analysis import DeepAnalysisModel
from app.infrastructure.persistence.models.fast_track_result import FastTrackResultModel
from app.infrastructure.persistence.models.job_description import JobDescriptionModel
from app.infrastructure.persistence.models.resume import ResumeModel

__all__ = [
    "Base",
    "UUIDMixin",
    "JobDescriptionModel",
    "ResumeModel",
    "FastTrackResultModel",
    "DeepAnalysisModel",
]

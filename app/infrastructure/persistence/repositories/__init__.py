from app.infrastructure.persistence.repositories.deep_analysis_repo import (
    SQLAlchemyDeepAnalysisRepository,
)
from app.infrastructure.persistence.repositories.fast_track_repo import (
    SQLAlchemyFastTrackRepository,
)
from app.infrastructure.persistence.repositories.job_description_repo import (
    SQLAlchemyJobDescriptionRepository,
)
from app.infrastructure.persistence.repositories.resume_repo import (
    SQLAlchemyResumeRepository,
)

__all__ = [
    "SQLAlchemyJobDescriptionRepository",
    "SQLAlchemyResumeRepository",
    "SQLAlchemyFastTrackRepository",
    "SQLAlchemyDeepAnalysisRepository",
]

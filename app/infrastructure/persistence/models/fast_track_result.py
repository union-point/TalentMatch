from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.persistence.models.job_description import (
        JobDescriptionModel,
    )
    from app.infrastructure.persistence.models.resume import ResumeModel


class FastTrackResultModel(Base, UUIDMixin):
    __tablename__ = "fast_track_results"

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False
    )
    job_description_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id"), nullable=False
    )
    pass_fail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    resume: Mapped[ResumeModel] = relationship(back_populates="fast_track_results")
    job_description: Mapped[JobDescriptionModel] = relationship(back_populates="fast_track_results")

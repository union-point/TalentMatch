from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, Text
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
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["resume_id", "organization_id"],
            ["resumes.id", "resumes.organization_id"],
            name="fk_fast_track_result_resume_organization",
        ),
        ForeignKeyConstraint(
            ["job_description_id", "organization_id"],
            ["job_descriptions.id", "job_descriptions.organization_id"],
            name="fk_fast_track_result_job_organization",
        ),
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_fast_track_results_score_range"),
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_description_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pass_fail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    resume: Mapped[ResumeModel] = relationship(
        overlaps="resume,job_description,fast_track_results,deep_analyses",
        back_populates="fast_track_results",
    )
    job_description: Mapped[JobDescriptionModel] = relationship(
        overlaps="resume,job_description,fast_track_results,deep_analyses",
        back_populates="fast_track_results",
    )

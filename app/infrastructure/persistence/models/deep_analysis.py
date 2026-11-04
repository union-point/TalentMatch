from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.persistence.models.job_description import (
        JobDescriptionModel,
    )
    from app.infrastructure.persistence.models.resume import ResumeModel


class DeepAnalysisModel(Base, UUIDMixin):
    __tablename__ = "deep_analyses"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["resume_id", "organization_id"],
            ["resumes.id", "resumes.organization_id"],
            name="fk_deep_analysis_resume_organization",
        ),
        ForeignKeyConstraint(
            ["job_description_id", "organization_id"],
            ["job_descriptions.id", "job_descriptions.organization_id"],
            name="fk_deep_analysis_job_organization",
        ),
        Index("ix_deep_analyses_dispatch", "status", "next_dispatch_at"),
        CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="ck_deep_analyses_overall_score_range"
        ),
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_description_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strengths: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    weaknesses: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    risks: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    detailed_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    next_dispatch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    resume: Mapped[ResumeModel] = relationship(
        overlaps="resume,job_description,fast_track_results,deep_analyses",
        back_populates="deep_analyses",
    )
    job_description: Mapped[JobDescriptionModel] = relationship(
        overlaps="resume,job_description,fast_track_results,deep_analyses",
        back_populates="deep_analyses",
    )

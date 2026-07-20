from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
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

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False
    )
    job_description_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id"), nullable=False
    )
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strengths: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    weaknesses: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    risks: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    detailed_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    resume: Mapped[ResumeModel] = relationship(back_populates="deep_analyses")
    job_description: Mapped[JobDescriptionModel] = relationship(back_populates="deep_analyses")

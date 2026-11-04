from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.persistence.models.deep_analysis import DeepAnalysisModel
    from app.infrastructure.persistence.models.fast_track_result import (
        FastTrackResultModel,
    )


class JobDescriptionModel(Base, UUIDMixin):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_job_description_organization"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    injection_scan_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    injection_scan_details: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    fast_track_results: Mapped[list[FastTrackResultModel]] = relationship(
        overlaps="fast_track_results,deep_analyses",
        back_populates="job_description",
        cascade="all, delete-orphan",
    )
    deep_analyses: Mapped[list[DeepAnalysisModel]] = relationship(
        overlaps="fast_track_results,deep_analyses",
        back_populates="job_description",
        cascade="all, delete-orphan",
    )

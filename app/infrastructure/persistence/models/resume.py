from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.infrastructure.persistence.models.deep_analysis import DeepAnalysisModel
    from app.infrastructure.persistence.models.fast_track_result import (
        FastTrackResultModel,
    )


class ResumeModel(Base, UUIDMixin):
    __tablename__ = "resumes"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    injection_scan_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    injection_scan_details: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    fast_track_results: Mapped[list[FastTrackResultModel]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    deep_analyses: Mapped[list[DeepAnalysisModel]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )

"""Identity persistence. Tokens and recovery codes are never stored in plaintext."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, UUIDMixin


class UserModel(Base, UUIDMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    pending_organization_name: Mapped[str | None] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrganizationModel(Base, UUIDMixin):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(255))
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class MembershipModel(Base):
    __tablename__ = "memberships"
    __table_args__ = (CheckConstraint("role IN ('owner', 'member')", name="ck_membership_role"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))


class AuthSessionModel(Base, UUIDMixin):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(40))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ActionTokenModel(Base, UUIDMixin):
    __tablename__ = "action_tokens"
    email: Mapped[str] = mapped_column(String(254))
    purpose: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(String(10), default="member")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MfaCredentialModel(Base):
    __tablename__ = "mfa_credentials"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    encrypted_secret: Mapped[str | None] = mapped_column(Text)
    pending_session_id: Mapped[UUID | None] = mapped_column()
    pending_secret: Mapped[str | None] = mapped_column(Text)
    pending_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_step: Mapped[int] = mapped_column(Integer, default=-1)


class RecoveryCodeModel(Base):
    __tablename__ = "recovery_codes"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)


class OutboxEmailModel(Base, UUIDMixin):
    __tablename__ = "email_outbox"
    encrypted_payload: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

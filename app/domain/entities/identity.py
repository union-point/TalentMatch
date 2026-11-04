"""Framework-independent identity records."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

Role = Literal["owner", "member"]
SessionState = Literal[
    "anonymous",
    "email_verification_required",
    "mfa_enrollment_required",
    "mfa_challenge_required",
    "authenticated",
]
LEGACY_ORGANIZATION_ID = UUID("00000000-0000-4000-8000-000000000001")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    email: str
    password_hash: str
    pending_organization_name: str | None = None
    verified_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class Organization:
    name: str
    locked: bool = False
    id: UUID = field(default_factory=uuid4)


@dataclass
class Membership:
    user_id: UUID
    organization_id: UUID
    role: Role


@dataclass
class AuthSession:
    token_hash: str
    csrf_token: str
    state: SessionState
    expires_at: datetime
    last_seen_at: datetime
    user_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class ActionToken:
    email: str
    purpose: str
    token_hash: str
    expires_at: datetime
    user_id: UUID | None = None
    organization_id: UUID | None = None
    role: Role = "member"
    consumed_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class MfaCredential:
    user_id: UUID
    encrypted_secret: str | None = None
    pending_secret: str | None = None
    pending_session_id: UUID | None = None
    pending_expires_at: datetime | None = None
    last_used_step: int = -1


@dataclass
class OutboxEmail:
    encrypted_payload: str | None
    expires_at: datetime
    next_attempt_at: datetime = field(default_factory=utcnow)
    attempts: int = 0
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    organization_id: UUID
    role: Role

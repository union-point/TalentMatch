from dataclasses import dataclass
from typing import Literal

from app.domain.entities.identity import AuthSession, Membership, Organization, User

VerificationResult = Literal["verified", "already_verified"]


@dataclass
class AuthContext:
    session: AuthSession
    user: User | None = None
    membership: Membership | None = None
    organization: Organization | None = None
    mfa_enabled: bool = False
    cookie_token: str | None = None


@dataclass(frozen=True)
class AuthPolicy:
    public_origin: str
    idle_seconds: int = 1800
    absolute_seconds: int = 43200
    challenge_seconds: int = 600
    verification_seconds: int = 86400
    reset_seconds: int = 1800
    invitation_seconds: int = 259200

from dataclasses import dataclass
from functools import lru_cache

from redis.asyncio import Redis

from app.application.dto.auth import AuthPolicy
from app.application.services.auth_service import AuthService
from app.application.services.auth_sessions import SessionService
from app.application.services.mfa_service import MfaService
from app.application.services.organization_service import OrganizationService
from app.config import settings
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.repositories.identity_repo import SQLAlchemyIdentityTransaction
from app.infrastructure.security.auth_throttle import AuthThrottle
from app.infrastructure.security.identity import ArgonPasswordHasher, EncryptedIdentitySecrets


@dataclass
class AuthServices:
    sessions: SessionService
    auth: AuthService
    mfa: MfaService
    organizations: OrganizationService
    throttle: AuthThrottle


@lru_cache(maxsize=1)
def get_auth_services() -> AuthServices:
    transaction = SQLAlchemyIdentityTransaction(async_session)
    passwords = ArgonPasswordHasher()
    secrets = EncryptedIdentitySecrets(settings.auth_encryption_keys)
    policy = AuthPolicy(
        settings.public_origin,
        settings.auth_session_idle_seconds,
        settings.auth_session_absolute_seconds,
        settings.auth_challenge_seconds,
        settings.auth_verification_seconds,
        settings.auth_reset_seconds,
        settings.auth_invitation_seconds,
    )
    sessions = SessionService(transaction, secrets, policy)
    auth = AuthService(transaction, passwords, secrets, policy, sessions)
    return AuthServices(
        sessions,
        auth,
        MfaService(transaction, secrets, policy, auth, sessions),
        OrganizationService(transaction, passwords, secrets, policy, auth, sessions),
        AuthThrottle(
            Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        ),
    )

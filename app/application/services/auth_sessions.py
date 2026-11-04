import hmac
from datetime import timedelta

from app.application.dto.auth import AuthContext, AuthPolicy
from app.core.exceptions import AppError
from app.domain.entities.identity import (
    AuthSession,
    Membership,
    MfaCredential,
    Principal,
    SessionState,
    User,
    utcnow,
)
from app.domain.ports.identity import IdentityRepository, IdentitySecrets, IdentityTransaction


class AuthError(AppError):
    def __init__(self, code: str, detail: str, status: int = 400) -> None:
        self.code = code
        self.detail = detail
        self.status = status
        super().__init__(detail)


def login_state(
    user: User, membership: Membership | None, mfa: MfaCredential | None
) -> SessionState:
    if user.verified_at is None:
        return "email_verification_required"
    if mfa and mfa.encrypted_secret:
        return "mfa_challenge_required"
    if membership and membership.role == "owner":
        return "mfa_enrollment_required"
    return "authenticated"


def require_user(context: AuthContext) -> User:
    if context.user is None:
        raise AuthError("authentication_required", "Please sign in.", 401)
    return context.user


def principal(context: AuthContext, owner: bool = False) -> Principal:
    user = require_user(context)
    if context.session.state != "authenticated":
        raise AuthError(context.session.state, "Complete sign-in before continuing.", 403)
    membership, organization = context.membership, context.organization
    if membership is None or organization is None or organization.locked:
        raise AuthError(
            "organization_required", "An active organization membership is required.", 403
        )
    if owner and membership.role != "owner":
        raise AuthError("owner_required", "Only the organization owner can do this.", 403)
    return Principal(user.id, membership.organization_id, membership.role)


class SessionService:
    def __init__(
        self, transaction: IdentityTransaction, secrets: IdentitySecrets, policy: AuthPolicy
    ) -> None:
        self._transaction = transaction
        self._secrets = secrets
        self._policy = policy

    async def context(
        self, repo: IdentityRepository, session: AuthSession, cookie_token: str | None = None
    ) -> AuthContext:
        user = await repo.user(session.user_id) if session.user_id else None
        membership = await repo.membership(user.id) if user else None
        organization = await repo.organization(membership.organization_id) if membership else None
        mfa = await repo.mfa(user.id) if user else None
        return AuthContext(
            session,
            user,
            membership,
            organization,
            bool(mfa and mfa.encrypted_secret),
            cookie_token,
        )

    async def issue(
        self,
        repo: IdentityRepository,
        user: User | None = None,
        state: SessionState = "anonymous",
        old: AuthSession | None = None,
    ) -> AuthContext:
        if old:
            await repo.delete_session(old.id)
        raw = self._secrets.token()
        seconds = (
            self._policy.absolute_seconds
            if state == "authenticated"
            else self._policy.challenge_seconds
        )
        now = utcnow()
        session = AuthSession(
            self._secrets.digest(raw),
            self._secrets.token(),
            state,
            now + timedelta(seconds=seconds),
            now,
            user.id if user else None,
        )
        await repo.save_session(session)
        return await self.context(repo, session, raw)

    async def resolve(
        self,
        raw: str | None,
        *,
        bootstrap: bool = False,
        csrf: str | None = None,
        origin: str | None = None,
        unsafe: bool = False,
    ) -> AuthContext:
        async with self._transaction() as repo:
            session = await repo.session(self._secrets.digest(raw)) if raw else None
            now = utcnow()
            if session and (
                session.expires_at <= now
                or (now - session.last_seen_at).total_seconds() > self._policy.idle_seconds
            ):
                await repo.delete_session(session.id)
                session = None
            if session is None:
                if bootstrap:
                    return await self.issue(repo)
                raise AuthError("session_expired", "Your session expired. Please sign in.", 401)
            if unsafe and (
                origin != self._policy.public_origin
                or not csrf
                or not csrf.isascii()
                or not hmac.compare_digest(csrf, session.csrf_token)
            ):
                raise AuthError(
                    "csrf_failed", "Request verification failed. Reload and try again.", 403
                )
            session.last_seen_at = now
            await repo.save_session(session)
            return await self.context(repo, session)

    async def logout(self, context: AuthContext, all_sessions: bool = False) -> None:
        async with self._transaction() as repo:
            if all_sessions:
                user = require_user(context)
                await repo.revoke_sessions(user.id)
            else:
                await repo.delete_session(context.session.id)

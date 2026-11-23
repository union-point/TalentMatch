from datetime import timedelta
from uuid import UUID

from app.application.dto.auth import AuthContext, AuthPolicy
from app.application.services.auth_service import AuthService
from app.application.services.auth_sessions import AuthError, SessionService, require_user
from app.domain.entities.identity import MfaCredential, User, utcnow
from app.domain.ports.identity import IdentityRepository, IdentitySecrets, IdentityTransaction


class MfaService:
    def __init__(
        self,
        transaction: IdentityTransaction,
        secrets: IdentitySecrets,
        policy: AuthPolicy,
        auth: AuthService,
        sessions: SessionService,
    ) -> None:
        self._transaction = transaction
        self._secrets = secrets
        self._policy = policy
        self._auth = auth
        self._sessions = sessions

    async def _require_live_session(self, repo: IdentityRepository, context: AuthContext) -> None:
        session = await repo.session(context.session.token_hash)
        if session is None or session.id != context.session.id or session.expires_at <= utcnow():
            raise AuthError("session_expired", "Your session expired. Please sign in.", 401)

    async def verify_factor(self, repo: IdentityRepository, user_id: UUID, code: str) -> None:
        credential = await repo.mfa(user_id)
        if credential is None or credential.encrypted_secret is None:
            raise AuthError("invalid_factor", "The authentication code is invalid.", 401)
        step = self._secrets.totp_step(
            self._secrets.decrypt(credential.encrypted_secret), code, credential.last_used_step
        )
        if step is not None:
            credential.last_used_step = step
            await repo.save_mfa(credential)
        elif not await repo.consume_recovery(user_id, self._secrets.digest(code)):
            raise AuthError(
                "invalid_factor", "The authentication code is invalid or already used.", 401
            )

    async def challenge(self, context: AuthContext, code: str) -> AuthContext:
        user = require_user(context)
        if context.session.state != "mfa_challenge_required":
            raise AuthError("invalid_state", "No MFA challenge is pending.", 403)
        async with self._transaction() as repo:
            await repo.user(user.id)  # serialize credential/recovery changes for this user
            await self._require_live_session(repo, context)
            await self.verify_factor(repo, user.id, code)
            return await self._sessions.issue(repo, user, "authenticated", context.session)

    async def begin(self, context: AuthContext, password: str, code: str | None) -> tuple[str, str]:
        if context.session.state != "authenticated":
            raise AuthError("invalid_state", "Complete email verification and sign-in first.", 403)
        async with self._transaction() as repo:
            user = await self._auth.check_password(repo, context, password)
            await self._require_live_session(repo, context)
            if user.verified_at is None:
                raise AuthError("email_verification_required", "Verify your email first.", 403)
            credential = await repo.mfa(user.id) or MfaCredential(user.id)
            if credential.encrypted_secret:
                await self.verify_factor(repo, user.id, code or "")
                credential = await repo.mfa(user.id) or credential
            secret = self._secrets.totp_secret()
            credential.pending_secret = self._secrets.encrypt(secret)
            credential.pending_expires_at = utcnow() + timedelta(
                seconds=self._policy.challenge_seconds
            )
            credential.pending_session_id = context.session.id
            await repo.save_mfa(credential)
            return self._secrets.provisioning(secret, user.email)

    async def _recovery_codes(self, repo: IdentityRepository, user: User) -> list[str]:
        codes = [self._secrets.token() for _ in range(10)]
        await repo.replace_recovery(user.id, [self._secrets.digest(code) for code in codes])
        return codes

    async def confirm(self, context: AuthContext, code: str) -> tuple[AuthContext, list[str]]:
        if context.session.state != "authenticated":
            raise AuthError("invalid_state", "Complete sign-in first.", 403)
        user = require_user(context)
        async with self._transaction() as repo:
            await repo.user(user.id)
            await self._require_live_session(repo, context)
            credential = await repo.mfa(user.id)
            if (
                credential is None
                or credential.pending_secret is None
                or credential.pending_expires_at is None
                or credential.pending_expires_at <= utcnow()
                or credential.pending_session_id != context.session.id
            ):
                raise AuthError("enrollment_expired", "Start authenticator enrollment again.")
            secret = self._secrets.decrypt(credential.pending_secret)
            step = self._secrets.totp_step(secret, code, -1)
            if step is None:
                raise AuthError("invalid_factor", "The authentication code is invalid.", 401)
            credential.encrypted_secret = credential.pending_secret
            credential.pending_secret = None
            credential.pending_expires_at = None
            credential.pending_session_id = None
            credential.last_used_step = step
            await repo.save_mfa(credential)
            codes = await self._recovery_codes(repo, user)
            await repo.revoke_sessions(user.id)
            return await self._sessions.issue(repo, user, "authenticated"), codes

    async def manage(
        self, context: AuthContext, password: str, code: str, disable: bool = False
    ) -> tuple[AuthContext, list[str]]:
        if context.session.state != "authenticated":
            raise AuthError("invalid_state", "Complete sign-in first.", 403)
        async with self._transaction() as repo:
            user = await self._auth.check_password(repo, context, password)
            await self._require_live_session(repo, context)
            await self.verify_factor(repo, user.id, code)
            if disable:
                await repo.delete_mfa(user.id)
                codes: list[str] = []
            else:
                codes = await self._recovery_codes(repo, user)
            await repo.revoke_sessions(user.id)
            return await self._sessions.issue(repo, user, "authenticated"), codes

import json
from contextlib import suppress
from datetime import timedelta

from app.application.dto.auth import AuthContext, AuthPolicy
from app.application.services.auth_sessions import (
    AuthError,
    SessionService,
    login_state,
    require_user,
)
from app.core.exceptions import IdentityConflictError
from app.domain.entities.identity import (
    ActionToken,
    Membership,
    Organization,
    OutboxEmail,
    User,
    utcnow,
)
from app.domain.ports.identity import (
    IdentityRepository,
    IdentitySecrets,
    IdentityTransaction,
    PasswordHasher,
)

GENERIC_EMAIL_MESSAGE = "If this request can be completed, an email will arrive shortly."


class AuthService:
    def __init__(
        self,
        transaction: IdentityTransaction,
        passwords: PasswordHasher,
        secrets: IdentitySecrets,
        policy: AuthPolicy,
        sessions: SessionService,
    ) -> None:
        self._transaction = transaction
        self._passwords = passwords
        self._secrets = secrets
        self._policy = policy
        self._sessions = sessions

    async def send_token(self, repo: IdentityRepository, token: ActionToken) -> None:
        raw = self._secrets.token()
        token.token_hash = self._secrets.digest(raw)
        await repo.save_token(token)
        path = {"verify": "verify-email", "reset": "reset-password", "invite": "accept-invitation"}[
            token.purpose
        ]
        payload = json.dumps(
            {
                "to": token.email,
                "subject": f"TalentMatch: {path.replace('-', ' ')}",
                "body": f"Open {self._policy.public_origin}/{path}#token={raw}\n"
                "If you did not request this, ignore this email.",
            }
        )
        await repo.queue_email(OutboxEmail(self._secrets.encrypt(payload), token.expires_at))

    async def register(self, email: str, password: str, organization_name: str) -> None:
        # Hash even for an existing email to avoid a cheap timing oracle.
        hashed = await self._passwords.hash(password)
        with suppress(IdentityConflictError):
            async with self._transaction() as repo:
                if await repo.user_by_email(email):
                    return
                user = User(email, hashed, organization_name)
                await repo.save_user(user)
                await self.send_token(
                    repo,
                    ActionToken(
                        email,
                        "verify",
                        "",
                        utcnow() + timedelta(seconds=self._policy.verification_seconds),
                        user_id=user.id,
                    ),
                )

    async def request_email(self, email: str, purpose: str) -> None:
        async with self._transaction() as repo:
            user = await repo.user_by_email(email)
            if user is None or (purpose == "verify" and user.verified_at is not None):
                return
            if purpose == "reset" and user.verified_at is None:
                return
            await repo.invalidate_tokens(user.id, purpose)
            seconds = (
                self._policy.reset_seconds
                if purpose == "reset"
                else self._policy.verification_seconds
            )
            await self.send_token(
                repo,
                ActionToken(
                    email, purpose, "", utcnow() + timedelta(seconds=seconds), user_id=user.id
                ),
            )

    async def valid_token(self, repo: IdentityRepository, raw: str, purpose: str) -> ActionToken:
        token = await repo.token(self._secrets.digest(raw), purpose)
        if token is None or token.consumed_at is not None or token.expires_at <= utcnow():
            raise AuthError("invalid_token", "This link is invalid or expired.")
        return token

    async def verify_email(self, raw: str) -> None:
        async with self._transaction() as repo:
            token = await self.valid_token(repo, raw, "verify")
            user = await repo.user(token.user_id) if token.user_id else None
            if user is None:
                raise AuthError("invalid_token", "This link is invalid or expired.")
            if user.verified_at is None:
                user.verified_at = utcnow()
                if user.pending_organization_name:
                    organization = Organization(user.pending_organization_name)
                    await repo.save_organization(organization)
                    await repo.save_membership(Membership(user.id, organization.id, "owner"))
                user.pending_organization_name = None
                await repo.save_user(user)
            token.consumed_at = utcnow()
            await repo.save_token(token)
            await repo.invalidate_tokens(user.id, "verify")
            await repo.revoke_sessions(user.id)

    async def login(self, email: str, password: str, context: AuthContext) -> AuthContext:
        async with self._transaction() as repo:
            user = await repo.user_by_email(email)
            if user is None:
                # Same expensive verification path for unknown users.
                await self._passwords.verify_missing(password)
                raise AuthError("invalid_credentials", "Email or password is incorrect.", 401)
            if not await self._passwords.verify(password, user.password_hash):
                raise AuthError("invalid_credentials", "Email or password is incorrect.", 401)
            membership = await repo.membership(user.id)
            mfa = await repo.mfa(user.id)
            return await self._sessions.issue(
                repo, user, login_state(user, membership, mfa), context.session
            )

    async def reset_password(self, raw: str, password: str) -> None:
        hashed = await self._passwords.hash(password)
        async with self._transaction() as repo:
            token = await self.valid_token(repo, raw, "reset")
            user = await repo.user(token.user_id) if token.user_id else None
            if user is None:
                raise AuthError("invalid_token", "This link is invalid or expired.")
            user.password_hash = hashed
            await repo.save_user(user)
            await repo.invalidate_tokens(user.id, "reset")
            await repo.revoke_sessions(user.id)

    async def check_password(
        self, repo: IdentityRepository, context: AuthContext, password: str
    ) -> User:
        user = await repo.user(require_user(context).id)
        if user is None or not await self._passwords.verify(password, user.password_hash):
            raise AuthError("invalid_credentials", "The password is incorrect.", 401)
        return user

    async def change_password(
        self, context: AuthContext, password: str, new_password: str
    ) -> AuthContext:
        if context.session.state != "authenticated":
            raise AuthError("authentication_required", "Complete sign-in first.", 403)
        hashed = await self._passwords.hash(new_password)
        async with self._transaction() as repo:
            user = await self.check_password(repo, context, password)
            user.password_hash = hashed
            await repo.save_user(user)
            await repo.revoke_sessions(user.id)
            return await self._sessions.issue(repo, user, "authenticated")

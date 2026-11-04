from datetime import timedelta
from uuid import UUID

from app.application.dto.auth import AuthContext, AuthPolicy
from app.application.services.auth_service import AuthService
from app.application.services.auth_sessions import AuthError, SessionService, login_state, principal
from app.domain.entities.identity import (
    LEGACY_ORGANIZATION_ID,
    ActionToken,
    Membership,
    User,
    utcnow,
)
from app.domain.ports.identity import IdentitySecrets, IdentityTransaction, PasswordHasher


class OrganizationService:
    def __init__(
        self,
        transaction: IdentityTransaction,
        passwords: PasswordHasher,
        secrets: IdentitySecrets,
        policy: AuthPolicy,
        auth: AuthService,
        sessions: SessionService,
    ) -> None:
        self._transaction = transaction
        self._passwords = passwords
        self._secrets = secrets
        self._policy = policy
        self._auth = auth
        self._sessions = sessions

    async def invite(self, context: AuthContext, email: str) -> None:
        actor = principal(context, owner=True)
        async with self._transaction() as repo:
            organization = await repo.organization(actor.organization_id)
            if organization is None:
                raise AuthError("not_found", "Organization not found.", 404)
            # Reissuing an invitation invalidates the old link.
            for invitation in await repo.invitations(actor.organization_id):
                if invitation.email == email:
                    invitation.consumed_at = utcnow()
                    await repo.save_token(invitation)
            await self._auth.send_token(
                repo,
                ActionToken(
                    email,
                    "invite",
                    "",
                    utcnow() + timedelta(seconds=self._policy.invitation_seconds),
                    organization_id=actor.organization_id,
                ),
            )

    async def accept(self, context: AuthContext, raw: str, password: str | None) -> AuthContext:
        async with self._transaction() as repo:
            invitation = await self._auth.valid_token(repo, raw, "invite")
            user = await repo.user_by_email(invitation.email)
            if user is None:
                if password is None:
                    raise AuthError(
                        "password_required", "Set a password to accept this invitation."
                    )
                user = User(
                    invitation.email, await self._passwords.hash(password), verified_at=utcnow()
                )
                await repo.save_user(user)
            else:
                if (
                    context.user is None
                    or context.user.id != user.id
                    or context.session.state != "authenticated"
                    or user.verified_at is None
                ):
                    raise AuthError(
                        "sign_in_required", "Sign in to the invited account first.", 403
                    )
            if await repo.membership(user.id):
                raise AuthError(
                    "already_member", "This account already belongs to an organization.", 409
                )
            if invitation.organization_id is None:
                raise AuthError("invalid_token", "This invitation is invalid.")
            organization = await repo.organization(invitation.organization_id)
            if organization is None:
                raise AuthError("invalid_token", "This invitation is invalid.")
            if organization.locked and invitation.role != "owner":
                raise AuthError("organization_locked", "This organization is not active.", 403)
            if invitation.role == "owner" and any(
                m.role == "owner" for _, m in await repo.members(invitation.organization_id)
            ):
                raise AuthError("already_claimed", "This organization already has an owner.", 409)
            user.verified_at = utcnow()
            user.pending_organization_name = None
            await repo.save_user(user)
            await repo.invalidate_tokens(user.id, "verify")
            membership = Membership(user.id, organization.id, invitation.role)
            await repo.save_membership(membership)
            invitation.consumed_at = utcnow()
            await repo.save_token(invitation)
            await repo.revoke_sessions(user.id)
            mfa = await repo.mfa(user.id)
            return await self._sessions.issue(
                repo, user, login_state(user, membership, mfa), context.session
            )

    async def list_members(self, context: AuthContext) -> list[tuple[User, Membership]]:
        actor = principal(context)
        async with self._transaction() as repo:
            return await repo.members(actor.organization_id)

    async def list_invitations(self, context: AuthContext) -> list[ActionToken]:
        actor = principal(context, owner=True)
        async with self._transaction() as repo:
            return await repo.invitations(actor.organization_id)

    async def revoke_invitation(self, context: AuthContext, token_id: UUID) -> None:
        actor = principal(context, owner=True)
        async with self._transaction() as repo:
            token = await repo.token_by_id(token_id)
            if (
                token is None
                or token.organization_id != actor.organization_id
                or token.purpose != "invite"
            ):
                raise AuthError("not_found", "Invitation not found.", 404)
            token.consumed_at = utcnow()
            await repo.save_token(token)

    async def remove_member(self, context: AuthContext, user_id: UUID) -> None:
        actor = principal(context, owner=True)
        if user_id == actor.user_id:
            raise AuthError("owner_removal_forbidden", "Owners cannot remove themselves.", 403)
        async with self._transaction() as repo:
            await repo.user(user_id)
            membership = await repo.membership(user_id)
            if membership is None or membership.organization_id != actor.organization_id:
                raise AuthError("not_found", "Member not found.", 404)
            if membership.role == "owner":
                raise AuthError("owner_removal_forbidden", "Owners cannot be removed.", 403)
            await repo.remove_membership(user_id)
            await repo.revoke_sessions(user_id)

    async def invite_legacy_owner(self, email: str) -> None:
        async with self._transaction() as repo:
            user = await repo.user_by_email(email)
            if user and (user.verified_at is None or await repo.membership(user.id)):
                raise AuthError(
                    "already_member",
                    "Use a new account or a verified account without membership.",
                    409,
                )
            organization = await repo.organization(LEGACY_ORGANIZATION_ID)
            if (
                organization is None
                or not organization.locked
                or await repo.members(organization.id)
            ):
                raise AuthError(
                    "already_claimed", "The legacy organization is absent or already assigned.", 409
                )
            for invitation in await repo.invitations(organization.id):
                invitation.consumed_at = utcnow()
                await repo.save_token(invitation)
            await self._auth.send_token(
                repo,
                ActionToken(
                    email,
                    "invite",
                    "",
                    utcnow() + timedelta(seconds=self._policy.invitation_seconds),
                    organization_id=organization.id,
                    role="owner",
                ),
            )

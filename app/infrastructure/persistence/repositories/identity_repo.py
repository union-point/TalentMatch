from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import TypeVar, cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities.identity import (
    ActionToken,
    AuthSession,
    Membership,
    MfaCredential,
    Organization,
    OutboxEmail,
    User,
    utcnow,
)
from app.domain.ports.identity import IdentityRepository
from app.infrastructure.persistence.models.identity import (
    ActionTokenModel,
    AuthSessionModel,
    MembershipModel,
    MfaCredentialModel,
    OrganizationModel,
    OutboxEmailModel,
    RecoveryCodeModel,
    UserModel,
)

Record = TypeVar("Record", User, Organization, Membership, AuthSession, ActionToken, MfaCredential)


def _record(kind: type[Record], model: object | None) -> Record | None:
    if model is None:
        return None
    return kind(**{name: getattr(model, name) for name in kind.__dataclass_fields__})


class SQLAlchemyIdentityRepository:
    """Used within a short transaction; security-sensitive reads lock their rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_by_email(self, email: str) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(UserModel.email == email).with_for_update()
        )
        return _record(User, model)

    async def user(self, user_id: UUID) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(UserModel.id == user_id).with_for_update()
        )
        return _record(User, model)

    async def save_user(self, user: User) -> None:
        await self._session.merge(UserModel(**asdict(user)))
        await self._session.flush()

    async def organization(self, organization_id: UUID) -> Organization | None:
        return _record(
            Organization,
            await self._session.scalar(
                select(OrganizationModel)
                .where(OrganizationModel.id == organization_id)
                .with_for_update()
            ),
        )

    async def save_organization(self, organization: Organization) -> None:
        await self._session.merge(OrganizationModel(**asdict(organization)))
        await self._session.flush()

    async def membership(self, user_id: UUID) -> Membership | None:
        return _record(Membership, await self._session.get(MembershipModel, user_id))

    async def save_membership(self, membership: Membership) -> None:
        await self._session.merge(MembershipModel(**asdict(membership)))
        await self._session.flush()

    async def remove_membership(self, user_id: UUID) -> None:
        await self._session.execute(
            delete(MembershipModel).where(MembershipModel.user_id == user_id)
        )

    async def members(self, organization_id: UUID) -> list[tuple[User, Membership]]:
        rows = await self._session.execute(
            select(UserModel, MembershipModel)
            .join(MembershipModel, MembershipModel.user_id == UserModel.id)
            .where(MembershipModel.organization_id == organization_id)
            .order_by(UserModel.email)
        )
        return [
            (cast(User, _record(User, u)), cast(Membership, _record(Membership, m)))
            for u, m in rows
        ]

    async def session(self, token_hash: str) -> AuthSession | None:
        return _record(
            AuthSession,
            await self._session.scalar(
                select(AuthSessionModel)
                .where(AuthSessionModel.token_hash == token_hash)
                .with_for_update()
            ),
        )

    async def save_session(self, session: AuthSession) -> None:
        await self._session.merge(AuthSessionModel(**asdict(session)))
        await self._session.flush()

    async def delete_session(self, session_id: UUID) -> None:
        await self._session.execute(
            delete(AuthSessionModel).where(AuthSessionModel.id == session_id)
        )

    async def revoke_sessions(self, user_id: UUID) -> None:
        await self._session.execute(
            delete(AuthSessionModel).where(AuthSessionModel.user_id == user_id)
        )

    async def token(self, token_hash: str, purpose: str) -> ActionToken | None:
        return _record(
            ActionToken,
            await self._session.scalar(
                select(ActionTokenModel)
                .where(
                    ActionTokenModel.token_hash == token_hash, ActionTokenModel.purpose == purpose
                )
                .with_for_update()
            ),
        )

    async def token_by_id(self, token_id: UUID) -> ActionToken | None:
        return _record(
            ActionToken,
            await self._session.scalar(
                select(ActionTokenModel).where(ActionTokenModel.id == token_id).with_for_update()
            ),
        )

    async def save_token(self, token: ActionToken) -> None:
        await self._session.merge(ActionTokenModel(**asdict(token)))
        await self._session.flush()

    async def invalidate_tokens(self, user_id: UUID, purpose: str) -> None:
        await self._session.execute(
            update(ActionTokenModel)
            .where(
                ActionTokenModel.user_id == user_id,
                ActionTokenModel.purpose == purpose,
                ActionTokenModel.consumed_at.is_(None),
            )
            .values(consumed_at=utcnow())
        )

    async def invitations(self, organization_id: UUID) -> list[ActionToken]:
        rows = await self._session.scalars(
            select(ActionTokenModel)
            .where(
                ActionTokenModel.organization_id == organization_id,
                ActionTokenModel.purpose == "invite",
                ActionTokenModel.consumed_at.is_(None),
                ActionTokenModel.expires_at > utcnow(),
            )
            .order_by(ActionTokenModel.email)
        )
        return [cast(ActionToken, _record(ActionToken, row)) for row in rows]

    async def mfa(self, user_id: UUID) -> MfaCredential | None:
        return _record(
            MfaCredential,
            await self._session.scalar(
                select(MfaCredentialModel)
                .where(MfaCredentialModel.user_id == user_id)
                .with_for_update()
            ),
        )

    async def save_mfa(self, credential: MfaCredential) -> None:
        await self._session.merge(MfaCredentialModel(**asdict(credential)))
        await self._session.flush()

    async def delete_mfa(self, user_id: UUID) -> None:
        await self._session.execute(
            delete(MfaCredentialModel).where(MfaCredentialModel.user_id == user_id)
        )
        await self.replace_recovery(user_id, [])

    async def consume_recovery(self, user_id: UUID, code_hash: str) -> bool:
        result = await self._session.scalar(
            delete(RecoveryCodeModel)
            .where(
                RecoveryCodeModel.user_id == user_id,
                RecoveryCodeModel.code_hash == code_hash,
            )
            .returning(RecoveryCodeModel.code_hash)
        )
        return result is not None

    async def replace_recovery(self, user_id: UUID, hashes: list[str]) -> None:
        await self._session.execute(
            delete(RecoveryCodeModel).where(RecoveryCodeModel.user_id == user_id)
        )
        self._session.add_all([RecoveryCodeModel(user_id=user_id, code_hash=h) for h in hashes])
        await self._session.flush()

    async def queue_email(self, email: OutboxEmail) -> None:
        self._session.add(OutboxEmailModel(**asdict(email)))
        await self._session.flush()


class SQLAlchemyIdentityTransaction:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[IdentityRepository]:
        async with self._factory() as session, session.begin():
            yield SQLAlchemyIdentityRepository(session)

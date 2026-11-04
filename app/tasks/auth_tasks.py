"""Leased transactional email delivery and bounded identity housekeeping."""

import asyncio
import json
import logging
from datetime import timedelta

from sqlalchemy import delete, or_, select, update

from app.config import settings
from app.domain.entities.identity import utcnow
from app.infrastructure.persistence.database import async_session, engine
from app.infrastructure.persistence.models.identity import (
    ActionTokenModel,
    AuthSessionModel,
    OutboxEmailModel,
)
from app.infrastructure.security.identity import EncryptedIdentitySecrets
from app.infrastructure.security.smtp import send_email
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def deliver_outbox() -> None:
    """Lease before SMTP; crashes retry with the same single-use email link."""
    secrets = EncryptedIdentitySecrets(settings.auth_encryption_keys)
    for _ in range(20):
        async with async_session() as session, session.begin():
            now = utcnow()
            await session.execute(
                update(OutboxEmailModel)
                .where(
                    OutboxEmailModel.expires_at <= now,
                    OutboxEmailModel.encrypted_payload.is_not(None),
                )
                .values(encrypted_payload=None)
            )
            row = await session.scalar(
                select(OutboxEmailModel)
                .where(
                    OutboxEmailModel.encrypted_payload.is_not(None),
                    OutboxEmailModel.expires_at > now,
                    OutboxEmailModel.next_attempt_at <= now,
                    OutboxEmailModel.attempts < 5,
                )
                .order_by(OutboxEmailModel.next_attempt_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if row is None:
                return
            identifier, payload, attempt = row.id, row.encrypted_payload, row.attempts + 1
            row.attempts = attempt
            row.next_attempt_at = now + timedelta(
                seconds=max(60, settings.smtp_timeout_seconds + 30)
            )
        try:
            assert payload is not None
            data = json.loads(secrets.decrypt(payload))
            await asyncio.to_thread(send_email, data["to"], data["subject"], data["body"])
        except Exception as exc:
            # SMTP exceptions may contain recipients or server output; never log their text.
            logger.warning(
                "Email delivery failed id=%s error_type=%s attempt=%s",
                identifier,
                type(exc).__name__,
                attempt,
            )
            async with async_session() as session, session.begin():
                await session.execute(
                    update(OutboxEmailModel)
                    .where(
                        OutboxEmailModel.id == identifier,
                        OutboxEmailModel.attempts == attempt,
                    )
                    .values(
                        next_attempt_at=utcnow() + timedelta(seconds=min(3600, 30 * 2**attempt)),
                        encrypted_payload=None if attempt >= 5 else payload,
                    )
                )
        else:
            async with async_session() as session, session.begin():
                await session.execute(
                    update(OutboxEmailModel)
                    .where(
                        OutboxEmailModel.id == identifier,
                    )
                    .values(encrypted_payload=None)
                )


@celery_app.task(name="tasks.deliver_auth_email")  # type: ignore[untyped-decorator]
def deliver_auth_email() -> None:
    async def run() -> None:
        await engine.dispose()
        await deliver_outbox()

    asyncio.run(run())


@celery_app.task(name="tasks.cleanup_identity")  # type: ignore[untyped-decorator]
def cleanup_identity() -> None:
    async def run() -> None:
        await engine.dispose()
        async with async_session() as session, session.begin():
            now = utcnow()
            await session.execute(
                delete(AuthSessionModel).where(
                    or_(
                        AuthSessionModel.expires_at <= now,
                        AuthSessionModel.last_seen_at
                        <= now - timedelta(seconds=settings.auth_session_idle_seconds),
                    )
                )
            )
            await session.execute(
                delete(ActionTokenModel).where(ActionTokenModel.expires_at <= now)
            )
            await session.execute(
                delete(OutboxEmailModel).where(OutboxEmailModel.expires_at <= now)
            )

    asyncio.run(run())

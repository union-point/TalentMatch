import asyncio
import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.application.services.auth_sessions import AuthError
from app.config import settings
from app.domain.entities.identity import utcnow
from app.infrastructure.persistence.models.identity import OutboxEmailModel
from app.infrastructure.security.auth_throttle import AuthThrottle, ThrottleError
from app.infrastructure.security.identity import EncryptedIdentitySecrets

pytestmark = [pytest.mark.integration, pytest.mark.real_auth]


@pytest.mark.parametrize("expired", [False, True])
async def test_email_outbox_delivery_erases_payload_and_concurrent_sweeps_do_not_duplicate(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, expired: bool
) -> None:
    from app.tasks import auth_tasks

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "auth_encryption_keys", [key])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(auth_tasks, "async_session", factory)
    crypto = EncryptedIdentitySecrets([key])
    identifier = uuid4()
    payload = {
        "to": "person@example.com",
        "subject": "Verify email",
        "body": "A private single-use link",
    }
    async with factory() as db, db.begin():
        db.add(
            OutboxEmailModel(
                id=identifier,
                encrypted_payload=crypto.encrypt(json.dumps(payload)),
                expires_at=utcnow() + timedelta(hours=-1 if expired else 1),
                next_attempt_at=utcnow(),
                attempts=0,
            )
        )
    with patch.object(auth_tasks, "send_email") as sender:
        await asyncio.gather(auth_tasks.deliver_outbox(), auth_tasks.deliver_outbox())
        assert sender.call_count == (0 if expired else 1)
        if not expired:
            sender.assert_called_once_with(payload["to"], payload["subject"], payload["body"])
    async with factory() as db:
        row = await db.get(OutboxEmailModel, identifier)
        assert row.encrypted_payload is None


async def test_email_outbox_retries_then_erases_failed_secrets(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.tasks import auth_tasks

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "auth_encryption_keys", [key])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(auth_tasks, "async_session", factory)
    crypto = EncryptedIdentitySecrets([key])
    identifier = uuid4()
    async with factory() as db, db.begin():
        db.add(
            OutboxEmailModel(
                id=identifier,
                encrypted_payload=crypto.encrypt(
                    json.dumps(
                        {
                            "to": "person@example.com",
                            "subject": "Verify",
                            "body": "TOP-SECRET-TOKEN",
                        }
                    )
                ),
                expires_at=utcnow() + timedelta(hours=1),
                next_attempt_at=utcnow(),
                attempts=0,
            )
        )
    with patch.object(auth_tasks, "send_email", side_effect=OSError("TOP-SECRET-TOKEN")) as sender:
        for attempt in range(1, 6):
            await auth_tasks.deliver_outbox()
            async with factory() as db, db.begin():
                row = await db.get(OutboxEmailModel, identifier)
                assert row.attempts == attempt
                assert row.next_attempt_at > utcnow()
                assert (row.encrypted_payload is None) == (attempt == 5)
                row.next_attempt_at = utcnow() - timedelta(seconds=1)
        await auth_tasks.deliver_outbox()
        assert sender.call_count == 5
    assert "TOP-SECRET-TOKEN" not in caplog.text


async def test_real_redis_auth_limits_are_shared_and_fail_closed() -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
    operation = "test:" + uuid4().hex
    limiter = AuthThrottle(redis)
    other_process = AuthThrottle(redis)
    keys = None
    try:
        keys = await limiter.reserve(operation, "person@example.com", "test-ip", 2, 10, 60)
        await other_process.reserve(operation, "person@example.com", "test-ip", 2, 10, 60)
        with pytest.raises(ThrottleError) as denied:
            await limiter.reserve(operation, "person@example.com", "test-ip", 2, 10, 60)
        assert 1 <= denied.value.retry_after <= 60
        await limiter.release(keys)
        await other_process.reserve(operation, "person@example.com", "test-ip", 2, 10, 60)
    finally:
        if keys:
            await redis.delete(*keys)
        await redis.aclose()
    broken = AsyncMock()
    broken.eval.side_effect = RedisConnectionError("not available")
    with pytest.raises(AuthError) as unavailable:
        await AuthThrottle(broken).reserve("login", "email", "ip", 5, 30, 300)
    assert unavailable.value.status == 503

"""Authentication tests use real PostgreSQL and real cryptography, without identity overrides."""

import json
from asyncio import gather
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pyotp
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.dto.auth import AuthPolicy
from app.application.services.auth_service import AuthService
from app.application.services.auth_sessions import SessionService
from app.application.services.mfa_service import MfaService
from app.application.services.organization_service import OrganizationService
from app.config import settings
from app.domain.entities.identity import utcnow
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models.identity import (
    ActionTokenModel,
    AuthSessionModel,
    MembershipModel,
    OrganizationModel,
    OutboxEmailModel,
    RecoveryCodeModel,
    UserModel,
)
from app.infrastructure.persistence.repositories.identity_repo import SQLAlchemyIdentityTransaction
from app.infrastructure.security.auth_services import AuthServices, get_auth_services
from app.infrastructure.security.auth_throttle import ThrottleError
from app.infrastructure.security.identity import ArgonPasswordHasher, EncryptedIdentitySecrets
from app.main import app
from app.presentation.api.middleware import _request_history

pytestmark = [pytest.mark.integration, pytest.mark.real_auth]
AuthEnv = tuple[
    AsyncClient, async_sessionmaker[AsyncSession], EncryptedIdentitySecrets, AuthServices
]

PASSWORD = "a very long test password with spaces"


@pytest_asyncio.fixture
async def auth_env(engine: AsyncEngine) -> AsyncIterator[AuthEnv]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    crypto = EncryptedIdentitySecrets([Fernet.generate_key().decode()])
    transaction = SQLAlchemyIdentityTransaction(factory)
    policy = AuthPolicy("http://test")
    passwords = ArgonPasswordHasher()
    sessions = SessionService(transaction, crypto, policy)
    auth = AuthService(transaction, passwords, crypto, policy, sessions)
    throttle = AsyncMock()
    throttle.reserve.return_value = ("account", "ip")
    services = AuthServices(
        sessions,
        auth,
        MfaService(transaction, crypto, policy, auth, sessions),
        OrganizationService(transaction, passwords, crypto, policy, auth, sessions),
        throttle,
    )

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_auth_services] = lambda: services
    app.dependency_overrides[get_db] = override_db
    _request_history.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory, crypto, services
    app.dependency_overrides.clear()
    _request_history.clear()


async def post(
    client: AsyncClient, path: str, body: dict[str, Any] | None = None, method: str = "POST"
) -> Response:
    bootstrap = await client.get("/api/v1/auth/session")
    assert bootstrap.status_code == 200, bootstrap.text
    return await client.request(
        method,
        "/api/v1/" + path,
        json=body,
        headers={"Origin": "http://test", "X-CSRF-Token": bootstrap.json()["csrf_token"]},
    )


async def email_token(
    factory: async_sessionmaker[AsyncSession],
    crypto: EncryptedIdentitySecrets,
    email: str,
    purpose: str,
) -> str:
    async with factory() as session:
        rows = (
            await session.scalars(
                select(OutboxEmailModel).order_by(OutboxEmailModel.created_at.desc())
            )
        ).all()
        for row in rows:
            data = json.loads(crypto.decrypt(row.encrypted_payload))
            if data["to"] == email and purpose in data["body"]:
                return parse_qs(urlsplit(data["body"].split("Open ")[1].split("\n")[0]).fragment)[
                    "token"
                ][0]
    raise AssertionError("Expected queued email")


async def owner(
    client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
    crypto: EncryptedIdentitySecrets,
    email: str = "owner@example.com",
) -> dict[str, Any]:
    response = await post(
        client,
        "auth/register",
        {"email": email, "password": PASSWORD, "organization_name": "Example"},
    )
    assert response.status_code == 202, response.text
    token = await email_token(factory, crypto, email, "verify-email")
    response = await post(client, "auth/verify-email", {"token": token})
    assert response.status_code == 200, response.text
    response = await post(client, "auth/login", {"email": email, "password": PASSWORD})
    assert response.json()["state"] == "authenticated", response.text
    assert not response.json()["mfa_enabled"]
    return response.json()


async def enroll(
    client: AsyncClient, factory: async_sessionmaker[AsyncSession], crypto: EncryptedIdentitySecrets
) -> tuple[str, list[str]]:
    response = await post(client, "auth/mfa/enroll", {"password": PASSWORD})
    assert response.status_code == 200, response.text
    secret = parse_qs(urlsplit(response.json()["uri"]).query)["secret"][0]
    response = await post(client, "auth/mfa/confirm", {"code": pyotp.TOTP(secret).now()})
    assert response.status_code == 200, response.text
    return secret, response.json()["recovery_codes"]


async def test_owner_signup_verification_mfa_csrf_and_logout(auth_env: AuthEnv) -> None:
    client, factory, crypto, _ = auth_env
    denied = await client.get("/api/v1/job-descriptions")
    assert denied.status_code == 401
    assert (await client.get("/health")).status_code == 200
    await client.get("/api/v1/auth/session")
    denied = await client.post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": PASSWORD, "organization_name": "Acme"},
    )
    assert denied.status_code == 403 and denied.json()["title"] == "csrf_failed"
    await owner(client, factory, crypto)
    assert (await client.get("/api/v1/job-descriptions")).status_code == 200
    before = client.cookies.get(settings.auth_cookie_name)
    _, codes = await enroll(client, factory, crypto)
    assert len(codes) == 10 and len(set(codes)) == 10
    assert client.cookies.get(settings.auth_cookie_name) != before
    assert (await client.get("/api/v1/job-descriptions")).status_code == 200
    async with factory() as db:
        hashes = (await db.scalars(select(RecoveryCodeModel.code_hash))).all()
        assert set(hashes) == {crypto.digest(code) for code in codes}
        assert await db.scalar(select(func.count()).select_from(MembershipModel)) == 1
    response = await post(client, "auth/logout")
    assert response.status_code == 204 and response.content == b""
    assert (await client.get("/api/v1/job-descriptions")).status_code == 401


async def test_duplicate_signup_tokens_and_generic_email_requests(auth_env: AuthEnv) -> None:
    client, factory, crypto, _ = auth_env
    body = {"email": "OWNER@EXAMPLE.COM", "password": PASSWORD, "organization_name": "First"}
    first = await post(client, "auth/register", body)
    duplicate = await post(client, "auth/register", {**body, "organization_name": "Second"})
    assert first.status_code == duplicate.status_code == 202
    assert first.json() == duplicate.json()
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(UserModel)) == 1
        assert await db.scalar(select(func.count()).select_from(MembershipModel)) == 0
    token = await email_token(factory, crypto, "owner@example.com", "verify-email")
    verified = await post(client, "auth/verify-email", {"token": token})
    assert verified.status_code == 200 and verified.json()["status"] == "verified"
    replay = await post(client, "auth/verify-email", {"token": token})
    assert replay.status_code == 200 and replay.json()["status"] == "already_verified"
    assert (await client.get("/api/v1/auth/session")).json()["state"] == "anonymous"
    known = await post(client, "auth/forgot-password", {"email": "owner@example.com"})
    unknown = await post(client, "auth/forgot-password", {"email": "missing@example.com"})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    reset = await email_token(factory, crypto, "owner@example.com", "reset-password")
    async with factory() as db, db.begin():
        await db.execute(
            update(ActionTokenModel)
            .where(ActionTokenModel.token_hash == crypto.digest(reset))
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )
    assert (
        await post(client, "auth/reset-password", {"token": reset, "password": PASSWORD + "!"})
    ).status_code == 400


async def test_mfa_replay_recovery_and_password_reset_preserves_factor(auth_env: AuthEnv) -> None:
    client, factory, crypto, _ = auth_env
    await owner(client, factory, crypto)
    secret, codes = await enroll(client, factory, crypto)
    await post(client, "auth/logout")
    login = await post(client, "auth/login", {"email": "owner@example.com", "password": PASSWORD})
    assert login.json()["state"] == "mfa_challenge_required"
    assert (await client.get("/api/v1/job-descriptions")).status_code == 403
    assert (await post(client, "auth/mfa/enroll", {"password": PASSWORD})).status_code == 403
    assert (await post(client, "auth/mfa/confirm", {"code": "123456"})).status_code == 403
    reused = await post(client, "auth/mfa/challenge", {"code": pyotp.TOTP(secret).now()})
    assert reused.status_code == 401
    response = await post(client, "auth/mfa/challenge", {"code": codes[0]})
    assert response.json()["state"] == "authenticated"
    await post(client, "auth/forgot-password", {"email": "owner@example.com"})
    reset = await email_token(factory, crypto, "owner@example.com", "reset-password")
    assert (
        await post(client, "auth/reset-password", {"token": reset, "password": PASSWORD + "new"})
    ).status_code == 200
    assert (await client.get("/api/v1/job-descriptions")).status_code == 401
    login = await post(
        client, "auth/login", {"email": "owner@example.com", "password": PASSWORD + "new"}
    )
    assert login.json()["state"] == "mfa_challenge_required"
    assert (await post(client, "auth/mfa/challenge", {"code": codes[0]})).status_code == 401
    assert (await post(client, "auth/mfa/challenge", {"code": codes[2]})).status_code == 200
    disable = await post(
        client, "auth/mfa/disable", {"password": PASSWORD + "new", "code": codes[1]}
    )
    assert disable.status_code == 200 and not disable.json()["mfa_enabled"]
    await post(client, "auth/logout")
    login = await post(
        client, "auth/login", {"email": "owner@example.com", "password": PASSWORD + "new"}
    )
    assert login.json()["state"] == "authenticated"


async def test_invited_member_permissions_revocation_and_optional_mfa(auth_env: AuthEnv) -> None:
    client, factory, crypto, _ = auth_env
    await owner(client, factory, crypto)
    _, owner_codes = await enroll(client, factory, crypto)
    assert (
        await post(client, "organization/invitations", {"email": "member@example.com"})
    ).status_code == 202
    invitation = await email_token(factory, crypto, "member@example.com", "accept-invitation")
    await post(client, "auth/logout")
    result = await post(
        client, "auth/accept-invitation", {"token": invitation, "password": PASSWORD}
    )
    assert result.status_code == 200, result.text
    assert (
        result.json()["state"] == "authenticated"
        and result.json()["organization"]["role"] == "member"
    )
    member_id = result.json()["user"]["id"]
    assert (await client.get("/api/v1/job-descriptions")).status_code == 200
    assert (
        await post(client, "organization/invitations", {"email": "other@example.com"})
    ).status_code == 403
    _, codes = await enroll(client, factory, crypto)
    disable = await post(client, "auth/mfa/disable", {"password": PASSWORD, "code": codes[0]})
    assert disable.status_code == 200 and not disable.json()["mfa_enabled"]
    # Keep the member's cookie alive in a separate client while the owner removes them.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as owner_client:
        await post(owner_client, "auth/login", {"email": "owner@example.com", "password": PASSWORD})
        await post(owner_client, "auth/mfa/challenge", {"code": owner_codes[0]})
        assert (await client.get("/api/v1/job-descriptions")).status_code == 200
        assert (
            await post(owner_client, f"organization/members/{member_id}", method="DELETE")
        ).status_code == 204
        owner_id = (await owner_client.get("/api/v1/auth/session")).json()["user"]["id"]
        assert (
            await post(owner_client, f"organization/members/{owner_id}", method="DELETE")
        ).status_code == 403
    assert (await client.get("/api/v1/job-descriptions")).status_code == 401


async def test_session_expiration_and_cookie_attributes(
    auth_env: AuthEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, crypto, services = auth_env
    response = await client.get("/api/v1/auth/session")
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert response.headers["cache-control"] == "no-store"
    assert "csrf_token" in response.json()
    async with factory() as db, db.begin():
        await db.execute(
            update(AuthSessionModel).values(expires_at=utcnow() - timedelta(seconds=1))
        )
    assert (await client.get("/api/v1/job-descriptions")).status_code == 401
    fresh = await client.get("/api/v1/auth/session")
    assert fresh.status_code == 200 and fresh.json()["csrf_token"] != response.json()["csrf_token"]
    from fastapi import Response

    from app.presentation.api.auth_dependencies import set_auth_cookie

    context = await services.sessions.resolve(client.cookies.get(settings.auth_cookie_name))
    context.cookie_token = "random-test-token"
    monkeypatch.setattr(settings, "auth_allow_insecure_cookies", False)
    production_response = Response()
    set_auth_cookie(production_response, context)
    assert "__Host-talentmatch=" in production_response.headers["set-cookie"]
    assert "; Secure" in production_response.headers["set-cookie"]


async def test_origin_csrf_rejection_and_auth_throttle_failure(auth_env: AuthEnv) -> None:
    client, _, _, services = auth_env
    csrf = (await client.get("/api/v1/auth/session")).json()["csrf_token"]
    body = {"email": "person@example.com", "password": PASSWORD}
    for origin, token in [("https://evil.example", csrf), ("http://test", "wrong"), (None, csrf)]:
        headers = {"X-CSRF-Token": token}
        if origin:
            headers["Origin"] = origin
        response = await client.post("/api/v1/auth/login", json=body, headers=headers)
        assert response.status_code == 403
    from app.infrastructure.security.auth_throttle import ThrottleError

    services.throttle.reserve.side_effect = ThrottleError(120)
    response = await client.get("/api/v1/auth/session")
    assert response.status_code == 429 and response.headers["retry-after"] == "120"


async def test_every_hiring_endpoint_is_scoped_and_cross_org_analysis_has_no_side_effects(
    auth_env: AuthEnv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock, patch
    from uuid import UUID, uuid4

    from app.infrastructure.persistence.models import (
        DeepAnalysisModel,
        FastTrackResultModel,
        JobDescriptionModel,
        ResumeModel,
    )

    client, factory, crypto, _ = auth_env
    identity = await owner(client, factory, crypto)
    await enroll(client, factory, crypto)
    own_org = UUID(identity["organization"]["id"])
    other_org, own_job, foreign_job, own_resume, foreign_resume, foreign_deep = [
        uuid4() for _ in range(6)
    ]
    file = tmp_path / "private.pdf"
    file.write_bytes(b"private resume bytes")
    async with factory() as db, db.begin():
        db.add(OrganizationModel(id=other_org, name="Other team", locked=False))
        await db.flush()
        for job, org in [(own_job, own_org), (foreign_job, other_org)]:
            db.add(
                JobDescriptionModel(
                    id=job,
                    organization_id=org,
                    title="Engineer",
                    company="Team",
                    original_content="Job",
                    normalized_content="Job",
                    file_path=str(file),
                    file_type="pdf",
                    injection_scan_passed=True,
                )
            )
        for resume, org in [(own_resume, own_org), (foreign_resume, other_org)]:
            db.add(
                ResumeModel(
                    id=resume,
                    organization_id=org,
                    filename="private.pdf",
                    original_content="Resume",
                    normalized_content="Resume",
                    file_path=str(file),
                    file_type="pdf",
                    injection_scan_passed=True,
                )
            )
        await db.flush()
        for job, resume, org in [
            (own_job, own_resume, own_org),
            (foreign_job, foreign_resume, other_org),
        ]:
            db.add(
                FastTrackResultModel(
                    organization_id=org,
                    job_description_id=job,
                    resume_id=resume,
                    score=80,
                    pass_fail=True,
                    explanation="Match",
                )
            )
        db.add(
            DeepAnalysisModel(
                id=foreign_deep,
                organization_id=other_org,
                job_description_id=foreign_job,
                resume_id=foreign_resume,
                status="pending",
            )
        )
    listing = await client.get("/api/v1/job-descriptions")
    assert [UUID(item["id"]) for item in listing.json()["items"]] == [own_job]
    detail = await client.get(f"/api/v1/job-descriptions/{own_job}")
    assert detail.status_code == 200
    assert UUID(detail.json()["id"]) == own_job
    assert detail.json()["normalized_content"] == "Job"
    for path in [
        f"job-descriptions/{foreign_job}",
        f"dashboard/jobs/{foreign_job}/candidates",
        f"dashboard/jobs/{foreign_job}/unscored-resumes",
        f"dashboard/candidates/{foreign_resume}/job/{own_job}",
        f"dashboard/candidates/{own_resume}/job/{foreign_job}",
        f"dashboard/candidates/{foreign_resume}/resume-file",
        f"analysis/deep/{foreign_deep}",
    ]:
        response = await client.get("/api/v1/" + path)
        assert response.status_code == 404, (path, response.text)
    assert (await client.get(f"/api/v1/dashboard/jobs/{own_job}/candidates")).json()["total"] == 1
    unscored = await client.get(f"/api/v1/dashboard/jobs/{own_job}/unscored-resumes")
    assert unscored.status_code == 200 and unscored.json()["total"] == 0
    assert (
        await client.get(f"/api/v1/dashboard/candidates/{own_resume}/job/{own_job}")
    ).status_code == 200
    download = await client.get(f"/api/v1/dashboard/candidates/{own_resume}/resume-file")
    assert download.status_code == 200 and download.content == file.read_bytes()
    assert download.headers["cache-control"] == "no-store"
    ai = AsyncMock()
    with patch("app.presentation.api.dependencies.AIServiceFactory.create", return_value=ai):
        for job, resume in [(own_job, foreign_resume), (foreign_job, own_resume)]:
            response = await post(
                client, "analysis/deep", {"job_description_id": str(job), "resume_id": str(resume)}
            )
            assert response.status_code == 404
        result = await post(
            client,
            "analysis/fast-track",
            {"job_description_id": str(own_job), "resume_ids": [str(foreign_resume)]},
        )
        assert result.status_code == 200 and result.json()["failed"] == 1
        assert "not found" in result.json()["results"][0]["error"]
        ai.analyze_fast_track.assert_not_awaited()
        ai.analyze_deep.assert_not_awaited()
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(DeepAnalysisModel)) == 1
        assert await db.scalar(select(func.count()).select_from(FastTrackResultModel)) == 2
    # The database also rejects inconsistent ownership, even if request checks are bypassed.
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        async with factory() as db, db.begin():
            db.add(
                DeepAnalysisModel(
                    organization_id=own_org,
                    resume_id=foreign_resume,
                    job_description_id=own_job,
                    status="pending",
                )
            )
            await db.flush()


async def test_protected_upload_transactions_and_denied_upload_cleanup(
    auth_env: AuthEnv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock, patch

    from app.infrastructure.storage.local_file_storage import get_local_file_storage

    client, factory, crypto, _ = auth_env
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    get_local_file_storage.cache_clear()
    parser = AsyncMock()
    parser.parse.return_value = "A candidate with Python experience"
    with patch("app.presentation.api.dependencies.get_parser_for_file", return_value=parser):
        rejected = await client.post(
            "/api/v1/resumes/upload", files={"file": ("resume.pdf", b"PDF", "application/pdf")}
        )
        assert rejected.status_code == 401
        parser.parse.assert_not_awaited()
        assert not list(tmp_path.rglob("*.pdf"))
        await owner(client, factory, crypto)
        await enroll(client, factory, crypto)
        csrf = (await client.get("/api/v1/auth/session")).json()["csrf_token"]
        result = await client.post(
            "/api/v1/resumes/upload",
            files={"file": ("resume.pdf", b"PDF", "application/pdf")},
            headers={"Origin": "http://test", "X-CSRF-Token": csrf},
        )
        assert result.status_code == 200, result.text
        parser.parse.assert_awaited_once()
        assert len(list(tmp_path.rglob("*.pdf"))) == 1

        from app.core.exceptions import ParsingError
        from app.infrastructure.persistence.models import ResumeModel

        parser.parse.side_effect = ["Good resume", ParsingError("internal detail"), "Later resume"]
        batch = await client.post(
            "/api/v1/resumes/batch-upload",
            files=[
                ("files", ("good.pdf", b"good", "application/pdf")),
                ("files", ("bad.pdf", b"bad", "application/pdf")),
                ("files", ("later.pdf", b"later", "application/pdf")),
            ],
            headers={"Origin": "http://test", "X-CSRF-Token": csrf},
        )
        assert batch.status_code == 200, batch.text
        assert batch.json()["succeeded"] == 2 and batch.json()["failed"] == 1
        assert batch.json()["errors"] == [
            {
                "index": 1,
                "filename": "bad.pdf",
                "error": "Could not parse the uploaded document.",
            }
        ]
        async with factory() as db:
            filenames = (await db.scalars(select(ResumeModel.filename))).all()
        assert set(filenames) == {"resume.pdf", "good.pdf", "later.pdf"}
        assert len(list(tmp_path.rglob("*.pdf"))) == 3
    get_local_file_storage.cache_clear()


async def test_mfa_concurrent_recovery_and_authenticator_replacement(auth_env: AuthEnv) -> None:
    import asyncio

    from app.application.services.auth_sessions import AuthError

    client, factory, crypto, services = auth_env
    await owner(client, factory, crypto)
    _, codes = await enroll(client, factory, crypto)
    await post(client, "auth/logout")
    await post(client, "auth/login", {"email": "owner@example.com", "password": PASSWORD})
    context = await services.sessions.resolve(client.cookies.get(settings.auth_cookie_name))
    results = await asyncio.gather(
        services.mfa.challenge(context, codes[0]),
        services.mfa.challenge(context, codes[0]),
        return_exceptions=True,
    )
    assert sum(isinstance(result, AuthError) for result in results) == 1
    authenticated = next(result for result in results if not isinstance(result, BaseException))
    uri, _ = await services.mfa.begin(authenticated, PASSWORD, codes[1])
    secret = parse_qs(urlsplit(uri).query)["secret"][0]
    current, replacement_codes = await services.mfa.confirm(authenticated, pyotp.TOTP(secret).now())
    assert current.mfa_enabled and len(replacement_codes) == 10
    async with factory() as db:
        hashes = set((await db.scalars(select(RecoveryCodeModel.code_hash))).all())
        assert crypto.digest(codes[2]) not in hashes
        assert hashes == {crypto.digest(code) for code in replacement_codes}


async def test_legacy_owner_invitation_unlocks_workspace_without_mfa(auth_env: AuthEnv) -> None:
    from app.application.services.auth_sessions import AuthError
    from app.domain.entities.identity import LEGACY_ORGANIZATION_ID

    client, factory, crypto, services = auth_env
    async with factory() as db, db.begin():
        await db.execute(
            update(OrganizationModel)
            .where(OrganizationModel.id == LEGACY_ORGANIZATION_ID)
            .values(locked=True)
        )
    await services.organizations.invite_legacy_owner("legacy@example.com")
    token = await email_token(factory, crypto, "legacy@example.com", "accept-invitation")
    accepted = await post(client, "auth/accept-invitation", {"token": token, "password": PASSWORD})
    assert accepted.json()["state"] == "authenticated"
    assert not accepted.json()["mfa_enabled"]
    assert not accepted.json()["organization"]["locked"]
    assert (await client.get("/api/v1/job-descriptions")).status_code == 200
    with pytest.raises(AuthError):
        await services.organizations.invite_legacy_owner("replacement@example.com")


async def test_verification_resend_and_token_outcomes(auth_env: AuthEnv) -> None:
    client, factory, crypto, services = auth_env
    email = "owner@example.com"
    signup = await post(
        client,
        "auth/register",
        {"email": email, "password": PASSWORD, "organization_name": "Example"},
    )
    original = await email_token(factory, crypto, email, "verify-email")
    known = await post(client, "auth/resend-verification", {"email": email})
    unknown = await post(client, "auth/resend-verification", {"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == signup.status_code == 202
    assert known.json() == unknown.json() == signup.json()
    replacement = await email_token(factory, crypto, email, "verify-email")
    assert replacement != original

    invalid = await post(client, "auth/verify-email", {"token": crypto.token()})
    assert invalid.status_code == 400 and invalid.json()["title"] == "invalid_token"
    async with factory() as db, db.begin():
        await db.execute(
            update(ActionTokenModel)
            .where(ActionTokenModel.token_hash == crypto.digest(replacement))
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )
    expired = await post(client, "auth/verify-email", {"token": replacement})
    assert expired.status_code == 400 and expired.json()["title"] == "expired_token"
    await post(client, "auth/resend-verification", {"email": email})
    alternate = await email_token(factory, crypto, email, "verify-email")

    pending = await post(client, "auth/login", {"email": email, "password": PASSWORD})
    assert pending.json()["state"] == "email_verification_required"
    assert (await client.get("/api/v1/job-descriptions")).status_code == 403
    assert (await post(client, "auth/verify-email", {"token": original})).json()["status"] == (
        "verified"
    )
    assert (await client.get("/api/v1/job-descriptions")).status_code == 401
    used = await post(client, "auth/verify-email", {"token": alternate})
    assert used.status_code == 400 and used.json()["title"] == "used_token"
    verified_address = await post(client, "auth/resend-verification", {"email": email})
    assert verified_address.status_code == unknown.status_code
    assert verified_address.json() == unknown.json()
    assert await email_token(factory, crypto, email, "verify-email") == alternate

    login = await post(client, "auth/login", {"email": email, "password": PASSWORD})
    assert login.json()["state"] == "authenticated"
    replay = await post(client, "auth/verify-email", {"token": original})
    assert replay.json()["status"] == "already_verified"
    assert (await client.get("/api/v1/job-descriptions")).status_code == 200
    csrf = (await client.get("/api/v1/auth/session")).json()["csrf_token"]
    reserve = services.throttle.reserve
    assert isinstance(reserve, AsyncMock)
    reserve.side_effect = ThrottleError(120)
    limited = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": email},
        headers={"Origin": "http://test", "X-CSRF-Token": csrf},
    )
    assert limited.status_code == 429 and limited.headers["Retry-After"] == "120"


async def test_concurrent_signup_and_verification_resend_are_atomic(auth_env: AuthEnv) -> None:
    _, factory, crypto, services = auth_env
    await gather(
        services.auth.register("concurrent@example.com", PASSWORD, "First"),
        services.auth.register("concurrent@example.com", PASSWORD, "Second"),
    )
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(UserModel)) == 1
    token = await email_token(factory, crypto, "concurrent@example.com", "verify-email")
    first, second, _ = await gather(
        services.auth.verify_email(token),
        services.auth.verify_email(token),
        services.auth.request_email("concurrent@example.com", "verify"),
    )
    assert {first, second} == {"verified", "already_verified"}
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(MembershipModel)) == 1
        assert (
            await db.scalar(
                select(func.count()).where(OrganizationModel.name.in_(("First", "Second")))
            )
            == 1
        )


async def test_password_reset_revokes_inflight_mfa_challenges(auth_env: AuthEnv) -> None:
    from app.application.services.auth_sessions import AuthError

    client, factory, crypto, services = auth_env
    await owner(client, factory, crypto)
    _, codes = await enroll(client, factory, crypto)
    await post(client, "auth/logout")
    await post(client, "auth/login", {"email": "owner@example.com", "password": PASSWORD})
    challenge = await services.sessions.resolve(client.cookies.get(settings.auth_cookie_name))
    await services.auth.request_email("owner@example.com", "reset")
    reset = await email_token(factory, crypto, "owner@example.com", "reset-password")
    await services.auth.reset_password(reset, PASSWORD + "new")
    with pytest.raises(AuthError) as expired:
        await services.mfa.challenge(challenge, codes[0])
    assert expired.value.status == 401
    async with factory() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuthSessionModel)
                .where(AuthSessionModel.user_id == challenge.user.id)
            )
            == 0
        )


async def test_revoked_session_cannot_be_resurrected_by_a_concurrent_read(
    auth_env: AuthEnv,
) -> None:
    import asyncio
    from unittest.mock import patch

    from app.application.services.auth_sessions import AuthError
    from app.domain.entities.identity import AuthSession
    from app.infrastructure.persistence.repositories.identity_repo import (
        SQLAlchemyIdentityRepository,
    )

    client, factory, crypto, services = auth_env
    await owner(client, factory, crypto)
    await enroll(client, factory, crypto)
    raw = client.cookies.get(settings.auth_cookie_name)
    context = await services.sessions.resolve(raw)
    read, resume = asyncio.Event(), asyncio.Event()
    original = SQLAlchemyIdentityRepository.session

    async def delayed(
        repository: SQLAlchemyIdentityRepository, token_hash: str
    ) -> AuthSession | None:
        session = await original(repository, token_hash)
        read.set()
        await resume.wait()
        return session

    with patch.object(SQLAlchemyIdentityRepository, "session", delayed):
        pending = asyncio.create_task(services.sessions.resolve(raw))
        await read.wait()
        await services.sessions.logout(context)
        resume.set()
        with pytest.raises(AuthError) as expired:
            await pending
        assert expired.value.status == 401
    async with factory() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuthSessionModel)
                .where(AuthSessionModel.user_id == context.user.id)
            )
            == 0
        )


async def test_logout_all_revokes_other_devices(auth_env: AuthEnv) -> None:
    client, factory, crypto, _ = auth_env
    await owner(client, factory, crypto)
    _, codes = await enroll(client, factory, crypto)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as device:
        await post(device, "auth/login", {"email": "owner@example.com", "password": PASSWORD})
        await post(device, "auth/mfa/challenge", {"code": codes[0]})
        assert (await device.get("/api/v1/job-descriptions")).status_code == 200
        assert (await post(client, "auth/logout-all")).status_code == 204
        assert (await device.get("/api/v1/job-descriptions")).status_code == 401
        assert (await client.get("/api/v1/job-descriptions")).status_code == 401


async def test_existing_members_cannot_join_another_org_and_revoked_invites_fail(
    auth_env: AuthEnv,
) -> None:
    client, factory, crypto, _ = auth_env
    await owner(client, factory, crypto)
    await enroll(client, factory, crypto)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await owner(other, factory, crypto, "other@example.com")
        await enroll(other, factory, crypto)
        await post(client, "organization/invitations", {"email": "other@example.com"})
        token = await email_token(factory, crypto, "other@example.com", "accept-invitation")
        denied = await post(other, "auth/accept-invitation", {"token": token})
        assert denied.status_code == 409
        invitation = (await client.get("/api/v1/organization/invitations")).json()[0]
        assert (
            await post(client, "organization/invitations/" + invitation["id"], method="DELETE")
        ).status_code == 204
        assert (await post(other, "auth/accept-invitation", {"token": token})).status_code == 400
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(MembershipModel)) == 2

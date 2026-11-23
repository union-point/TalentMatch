"""Upgrade and downgrade the full Alembic chain in the dedicated test database."""

import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from alembic import command
from app.domain.entities.identity import LEGACY_ORGANIZATION_ID, utcnow
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.models.identity import (
    AuthSessionModel,
    MembershipModel,
    MfaCredentialModel,
    OrganizationModel,
    UserModel,
)

pytestmark = [pytest.mark.integration, pytest.mark.real_auth]


@pytest.mark.parametrize("populated", [False, True])
async def test_identity_migration_preserves_legacy_data_and_can_be_reverted(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, populated: bool
) -> None:
    monkeypatch.setenv("DATABASE_URL", str(engine.url.render_as_string(hide_password=False)))
    # A filename-less config avoids Alembic replacing pytest's global logging handlers.
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await asyncio.to_thread(command.upgrade, config, "004_dispatch_leases")
    job, resume, fast, deep = [uuid4() for _ in range(4)]
    file = tmp_path / "original-resume.pdf"
    file.write_bytes(b"original private resume")
    if populated:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO job_descriptions (id,title,company,original_content,normalized"
                    "_content,file_path,file_type,injection_scan_passed) VALUES (:id,'Engineer'"
                    ",'Team','job','job',:path,'pdf',true)"
                ),
                {"id": job, "path": str(file)},
            )
            await connection.execute(
                text(
                    "INSERT INTO resumes (id,filename,original_content,normalized_content,file_"
                    "path,file_type,injection_scan_passed) VALUES (:id,'original-resume.pdf','r"
                    "esume','resume',:path,'pdf',true)"
                ),
                {"id": resume, "path": str(file)},
            )
            await connection.execute(
                text(
                    "INSERT INTO fast_track_results (id,resume_id,job_description_id,pass_fail,"
                    "score,explanation) VALUES (:id,:resume,:job,true,85,'Match')"
                ),
                {"id": fast, "resume": resume, "job": job},
            )
            await connection.execute(
                text(
                    "INSERT INTO deep_analyses (id,resume_id,job_description_id,status) VALUES "
                    "(:id,:resume,:job,'pending')"
                ),
                {"id": deep, "resume": resume, "job": job},
            )
    await asyncio.to_thread(command.upgrade, config, "head")
    async with engine.connect() as connection:
        assert await connection.scalar(
            text("SELECT locked FROM organizations WHERE id=:id"), {"id": LEGACY_ORGANIZATION_ID}
        )
        for table in ("job_descriptions", "resumes", "fast_track_results", "deep_analyses"):
            assert await connection.scalar(
                text(f"SELECT count(*) FROM {table} WHERE organization_id=:id"),
                {"id": LEGACY_ORGANIZATION_ID},
            ) == int(populated)
        if populated:
            assert await connection.scalar(
                text("SELECT file_path FROM resumes WHERE id=:id"), {"id": resume}
            ) == str(file)
    assert file.read_bytes() == b"original private resume"
    await asyncio.to_thread(command.downgrade, config, "004_dispatch_leases")
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM resumes")) == int(populated)
        assert not await connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='"
                "resumes' AND column_name='organization_id')"
            )
        )
    # Return to the current schema so the shared fixture can clean it normally.
    await asyncio.to_thread(command.upgrade, config, "head")


async def test_optional_mfa_migration_activates_only_claimed_legacy_workspace(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await asyncio.to_thread(command.upgrade, config, "006_organization_isolation")
    now = utcnow()
    owner, enrolled_owner, other_org = uuid4(), uuid4(), uuid4()
    obsolete, challenge, authenticated = uuid4(), uuid4(), uuid4()
    async with AsyncSession(engine) as db, db.begin():
        db.add_all(
            [
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    password_hash="unused",
                    verified_at=now,
                )
                for user_id in (owner, enrolled_owner)
            ]
        )
        db.add(OrganizationModel(id=other_org, name="Other locked workspace", locked=True))
        await db.flush()
        db.add_all(
            [
                MembershipModel(
                    user_id=owner, organization_id=LEGACY_ORGANIZATION_ID, role="owner"
                ),
                MembershipModel(user_id=enrolled_owner, organization_id=other_org, role="owner"),
                MfaCredentialModel(user_id=enrolled_owner, encrypted_secret="configured"),
            ]
        )
        for session_id, user_id, state in (
            (obsolete, owner, "mfa_enrollment_required"),
            (challenge, enrolled_owner, "mfa_challenge_required"),
            (authenticated, enrolled_owner, "authenticated"),
        ):
            db.add(
                AuthSessionModel(
                    id=session_id,
                    user_id=user_id,
                    state=state,
                    token_hash=str(session_id),
                    csrf_token="test",
                    expires_at=now + timedelta(minutes=10),
                    last_seen_at=now,
                )
            )
    await asyncio.to_thread(command.upgrade, config, "head")
    async with AsyncSession(engine) as db, db.begin():
        assert (
            await db.scalar(
                select(OrganizationModel.locked).where(
                    OrganizationModel.id == LEGACY_ORGANIZATION_ID
                )
            )
            is False
        )
        assert (
            await db.scalar(
                select(OrganizationModel.locked).where(OrganizationModel.id == other_org)
            )
            is True
        )
        assert set(await db.scalars(select(AuthSessionModel.id))) == {challenge, authenticated}
        db.add(
            AuthSessionModel(
                id=obsolete,
                user_id=owner,
                state="authenticated",
                token_hash=str(obsolete),
                csrf_token="test",
                expires_at=now + timedelta(minutes=10),
                last_seen_at=now,
            )
        )
    await asyncio.to_thread(command.downgrade, config, "006_organization_isolation")
    async with AsyncSession(engine) as db:
        assert set(await db.scalars(select(AuthSessionModel.id))) == {challenge, authenticated}

"""Add identity and transactional email tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_identity"
down_revision: str = "004_dispatch_leases"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _identity_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        *_identity_columns(),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("pending_organization_name", sa.String(255)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "organizations",
        *_identity_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(10), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'member')", name="ck_membership_role"),
    )
    op.create_table(
        "auth_sessions",
        *_identity_columns(),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(128), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "action_tokens",
        *_identity_columns(),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), index=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), index=True),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "mfa_credentials",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("encrypted_secret", sa.Text()),
        sa.Column("pending_secret", sa.Text()),
        sa.Column("pending_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_step", sa.Integer(), nullable=False),
    )
    op.create_table(
        "recovery_codes",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("code_hash", sa.String(64), primary_key=True),
    )
    op.create_table(
        "email_outbox",
        *_identity_columns(),
        sa.Column("encrypted_payload", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "email_outbox",
        "recovery_codes",
        "mfa_credentials",
        "action_tokens",
        "auth_sessions",
        "memberships",
        "organizations",
        "users",
    ):
        op.drop_table(table)

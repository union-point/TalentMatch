"""Distinguish completed email verification from invalidated links."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_email_verification_result"
down_revision: str = "007_optional_mfa"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "action_tokens",
        sa.Column(
            "verification_completed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("action_tokens", "verification_completed")

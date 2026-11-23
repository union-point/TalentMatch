"""Retire required MFA enrollment for organization owners."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_optional_mfa"
down_revision: str = "006_organization_isolation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

LEGACY = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM auth_sessions WHERE state = 'mfa_enrollment_required'"))
    op.execute(
        sa.text(
            """
            UPDATE organizations SET locked = false
            WHERE id = CAST(:legacy AS uuid) AND locked AND EXISTS (
                SELECT 1 FROM memberships
                JOIN users ON users.id = memberships.user_id
                WHERE memberships.organization_id = organizations.id
                    AND memberships.role = 'owner' AND users.verified_at IS NOT NULL
            )
            """
        ).bindparams(legacy=LEGACY)
    )


def downgrade() -> None:
    # The previous application assumes authenticated owners already verified a second factor.
    op.execute(
        sa.text(
            """
            DELETE FROM auth_sessions WHERE state = 'authenticated' AND user_id IN (
                SELECT memberships.user_id FROM memberships
                LEFT JOIN mfa_credentials ON mfa_credentials.user_id = memberships.user_id
                WHERE memberships.role = 'owner' AND mfa_credentials.encrypted_secret IS NULL
            )
            """
        )
    )

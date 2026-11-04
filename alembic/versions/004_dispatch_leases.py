"""Bound pending dispatch retries with durable publication leases."""

import sqlalchemy as sa

from alembic import op

revision: str = "004_dispatch_leases"
down_revision: str = "003_score_bounds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deep_analyses", sa.Column("next_dispatch_at", sa.DateTime(timezone=True)))
    op.create_index("ix_deep_analyses_dispatch", "deep_analyses", ["status", "next_dispatch_at"])


def downgrade() -> None:
    op.drop_index("ix_deep_analyses_dispatch", table_name="deep_analyses")
    op.drop_column("deep_analyses", "next_dispatch_at")

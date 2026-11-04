"""Backfill legacy records and enforce organization ownership."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_organization_isolation"
down_revision: str = "005_identity"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

LEGACY = "00000000-0000-4000-8000-000000000001"
TABLES = ("job_descriptions", "resumes", "fast_track_results", "deep_analyses")


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, locked) VALUES "
            f"('{LEGACY}', 'Legacy organization', true)"
        )
    )
    for table in TABLES:
        op.add_column(table, sa.Column("organization_id", sa.UUID(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET organization_id = '{LEGACY}'"))
        op.alter_column(table, "organization_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_organization", table, "organizations", ["organization_id"], ["id"]
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
    for table, name in (("resumes", "resume"), ("job_descriptions", "job_description")):
        op.create_unique_constraint(f"uq_{name}_organization", table, ["id", "organization_id"])
    for table, name in (
        ("fast_track_results", "fast_track_result"),
        ("deep_analyses", "deep_analysis"),
    ):
        for column, parent, label in (
            ("resume_id", "resumes", "resume"),
            ("job_description_id", "job_descriptions", "job"),
        ):
            op.drop_constraint(f"{table}_{column}_fkey", table, type_="foreignkey")
            op.create_foreign_key(
                f"fk_{name}_{label}_organization",
                table,
                parent,
                [column, "organization_id"],
                ["id", "organization_id"],
            )


def downgrade() -> None:
    for table, name in (
        ("fast_track_results", "fast_track_result"),
        ("deep_analyses", "deep_analysis"),
    ):
        for column, parent, label in (
            ("resume_id", "resumes", "resume"),
            ("job_description_id", "job_descriptions", "job"),
        ):
            op.drop_constraint(f"fk_{name}_{label}_organization", table, type_="foreignkey")
            op.create_foreign_key(f"{table}_{column}_fkey", table, parent, [column], ["id"])
    for table, name in (("resumes", "resume"), ("job_descriptions", "job_description")):
        op.drop_constraint(f"uq_{name}_organization", table, type_="unique")
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization", table, type_="foreignkey")
        op.drop_column(table, "organization_id")
    # Identity records remain until the preceding identity migration is reverted.

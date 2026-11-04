"""Constrain AI scores to the documented range."""

from alembic import op

revision: str = "003_score_bounds"
down_revision: str = "b67c7dd2e97e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing malformed scores must be corrected before this migration can succeed.
    op.create_check_constraint(
        "ck_fast_track_results_score_range", "fast_track_results", "score BETWEEN 0 AND 100"
    )
    op.create_check_constraint(
        "ck_deep_analyses_overall_score_range", "deep_analyses", "overall_score BETWEEN 0 AND 100"
    )


def downgrade() -> None:
    op.drop_constraint("ck_deep_analyses_overall_score_range", "deep_analyses", type_="check")
    op.drop_constraint("ck_fast_track_results_score_range", "fast_track_results", type_="check")

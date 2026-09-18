"""Record applicant handover separately from Immigration acceptance.

Revision ID: 0007_submission_handover_timestamp
Revises: 0006_rule_versions_and_activation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_submission_handover_timestamp"
down_revision: str | Sequence[str] | None = "0006_rule_versions_and_activation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "case_submission",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE case_submission SET submitted_at = COALESCE(accepted_at, confirmed_at, now())"
    )
    op.alter_column(
        "case_submission",
        "submitted_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.drop_column("case_submission", "submitted_at")

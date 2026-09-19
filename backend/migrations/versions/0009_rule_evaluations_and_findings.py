"""Create immutable rule evaluation history.

Revision ID: 0009_rule_evaluations_and_findings
Revises: 0008_case_rule_assignments_and_requirements
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_rule_evaluations_and_findings"
down_revision: str | Sequence[str] | None = "0008_case_rule_assignments_and_requirements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_evaluation",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_set_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_evaluation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["rule_set_version_id"], ["rule_set_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_evaluation_id"], ["rule_evaluation.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_evaluation")),
        sa.CheckConstraint(
            "outcome IN ('pass','manual_review','action_required','unsupported_scope')",
            name="rule_evaluation_outcome_allowed",
        ),
    )
    op.create_index("ix_rule_evaluation_case_id", "rule_evaluation", ["case_id"])
    op.create_table(
        "evaluation_finding",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rule_evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_evaluation_id"], ["rule_evaluation.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["rule_version_id"], ["rule_version.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_finding")),
        sa.CheckConstraint(
            "outcome IN ('pass','manual_review','action_required','unsupported_scope')",
            name="evaluation_finding_outcome_allowed",
        ),
    )
    op.create_index(
        "ix_evaluation_finding_evaluation_id", "evaluation_finding", ["rule_evaluation_id"]
    )
    for table_name in ("rule_evaluation", "evaluation_finding"):
        op.execute(
            f"CREATE TRIGGER prevent_{table_name}_mutation BEFORE UPDATE OR DELETE ON "
            f"{table_name} FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation()"
        )


def downgrade() -> None:
    for table_name in ("evaluation_finding", "rule_evaluation"):
        op.execute(f"DROP TRIGGER prevent_{table_name}_mutation ON {table_name}")
    op.drop_table("evaluation_finding")
    op.drop_table("rule_evaluation")

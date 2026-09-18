"""Create immutable case rule assignments and materialized requirements.

Revision ID: 0008_case_rule_assignments_and_requirements
Revises: 0007_submission_handover_timestamp
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_case_rule_assignments_and_requirements"
down_revision: str | Sequence[str] | None = "0007_submission_handover_timestamp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "case",
        sa.Column("current_rule_set_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_case_current_rule_set_version_id_rule_set_version",
        "case",
        "rule_set_version",
        ["current_rule_set_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "case_submission",
        sa.Column("applicable_rule_set_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_submission_applicable_rule_set_version",
        "case_submission",
        "rule_set_version",
        ["applicable_rule_set_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "case_rule_assignment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_set_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignment_reason", sa.Text(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supersedes_assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["rule_set_version_id"], ["rule_set_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["assigned_by_actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_assignment_id"], ["case_rule_assignment.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_rule_assignment")),
    )
    op.create_index("ix_case_rule_assignment_case_id", "case_rule_assignment", ["case_id"])
    op.create_index(
        "ix_case_rule_assignment_rule_set_version_id",
        "case_rule_assignment",
        ["rule_set_version_id"],
    )
    op.create_table(
        "case_requirement",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("satisfied_by_document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requirement_version_id"], ["requirement_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["satisfied_by_document_version_id"], ["document_version.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_requirement")),
        sa.UniqueConstraint(
            "case_id", "requirement_version_id", name="uq_case_requirement_version"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','SATISFIED','NOT_APPLICABLE')",
            name="case_requirement_status_allowed",
        ),
    )
    op.create_index("ix_case_requirement_case_id", "case_requirement", ["case_id"])
    for table_name in ("case_rule_assignment", "case_requirement"):
        op.execute(
            f"CREATE TRIGGER prevent_{table_name}_mutation BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation()"
        )


def downgrade() -> None:
    for table_name in ("case_requirement", "case_rule_assignment"):
        op.execute(f"DROP TRIGGER prevent_{table_name}_mutation ON {table_name}")
    op.drop_index("ix_case_requirement_case_id", table_name="case_requirement")
    op.drop_table("case_requirement")
    op.drop_index("ix_case_rule_assignment_rule_set_version_id", table_name="case_rule_assignment")
    op.drop_index("ix_case_rule_assignment_case_id", table_name="case_rule_assignment")
    op.drop_table("case_rule_assignment")
    op.drop_constraint(
        "fk_submission_applicable_rule_set_version",
        "case_submission",
        type_="foreignkey",
    )
    op.drop_column("case_submission", "applicable_rule_set_version_id")
    op.drop_constraint(
        "fk_case_current_rule_set_version_id_rule_set_version",
        "case",
        type_="foreignkey",
    )
    op.drop_column("case", "current_rule_set_version_id")

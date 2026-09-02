"""Create event and audit history with database immutability protections.

Revision ID: 0004_events_audit_and_immutability
Revises: 0003_submissions_and_documents
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_events_audit_and_immutability"
down_revision: str | Sequence[str] | None = "0003_submissions_and_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "document_version",
    "document_check",
    "case_status_history",
    "case_event",
    "audit_event",
)


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    op.create_table(
        "case_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "event_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case.id"],
            name=op.f("fk_case_event_case_id_case"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actor.id"],
            name=op.f("fk_case_event_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_event")),
    )
    op.create_index(
        "ix_case_event_case_id_occurred_at",
        "case_event",
        ["case_id", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "audit_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "before_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "after_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case.id"],
            name=op.f("fk_audit_event_case_id_case"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actor.id"],
            name=op.f("fk_audit_event_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_event")),
    )
    op.create_index(
        "ix_audit_event_case_id_occurred_at",
        "audit_event",
        ["case_id", "occurred_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION prevent_append_only_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$
        """
    )
    for table_name in APPEND_ONLY_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER prevent_{table_name}_mutation
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION prevent_append_only_mutation()
            """
        )

    op.execute(
        """
        CREATE FUNCTION prevent_confirmed_initial_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.submission_type = 'INITIAL' AND OLD.confirmed_at IS NOT NULL THEN
                RAISE EXCEPTION 'confirmed initial submission is immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_confirmed_initial_mutation
        BEFORE UPDATE OR DELETE ON case_submission
        FOR EACH ROW
        EXECUTE FUNCTION prevent_confirmed_initial_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER prevent_confirmed_initial_mutation ON case_submission")
    for table_name in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER prevent_{table_name}_mutation ON {table_name}")

    op.execute("DROP FUNCTION prevent_confirmed_initial_mutation()")
    op.execute("DROP FUNCTION prevent_append_only_mutation()")
    op.drop_table("audit_event")
    op.drop_table("case_event")

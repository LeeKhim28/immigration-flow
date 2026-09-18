"""Create versioned official sources and requirements.

Revision ID: 0005_knowledge_sources_and_requirements
Revises: 0004_events_audit_and_immutability
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_knowledge_sources_and_requirements"
down_revision: str | Sequence[str] | None = "0004_events_audit_and_immutability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHA_CHECK = "^[0-9a-f]{40,64}$"
HASH_CHECK = "^[0-9a-f]{64}$"
APPEND_ONLY_TABLES = (
    "source_revision",
    "requirement_version",
    "requirement_source",
)


def _uuid_id() -> sa.Column[object]:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "knowledge_sync_run",
        _uuid_id(),
        sa.Column("git_commit_sha", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('STARTED', 'SUCCEEDED', 'FAILED')",
            name=op.f("ck_knowledge_sync_run_status_allowed"),
        ),
        sa.CheckConstraint(
            f"git_commit_sha ~ '{SHA_CHECK}'",
            name=op.f("ck_knowledge_sync_run_git_sha"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_sync_run")),
    )
    op.create_index(
        "uq_knowledge_sync_run_success_git_sha",
        "knowledge_sync_run",
        ["git_commit_sha"],
        unique=True,
        postgresql_where=sa.text("status = 'SUCCEEDED'"),
    )

    op.create_table(
        "knowledge_source",
        _uuid_id(),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authority", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("topics", postgresql.JSONB(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('CANDIDATE', 'REVIEWED', 'SUPERSEDED', 'RETIRED')",
            name=op.f("ck_knowledge_source_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_source")),
        sa.UniqueConstraint("source_code", name=op.f("uq_knowledge_source_source_code")),
        sa.UniqueConstraint(
            "canonical_url",
            name=op.f("uq_knowledge_source_canonical_url"),
        ),
    )

    op.create_table(
        "source_revision",
        _uuid_id(),
        sa.Column("knowledge_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_content_hash", sa.Text(), nullable=False),
        sa.Column("repository_snapshot_reference", sa.Text(), nullable=False),
        sa.Column("git_commit_sha", sa.Text(), nullable=False),
        sa.Column("knowledge_sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            f"normalized_content_hash ~ '{HASH_CHECK}'",
            name=op.f("ck_source_revision_content_hash"),
        ),
        sa.CheckConstraint(
            f"git_commit_sha ~ '{SHA_CHECK}'",
            name=op.f("ck_source_revision_git_sha"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from",
            name=op.f("ck_source_revision_effective_window"),
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_source_id"],
            ["knowledge_source.id"],
            name=op.f("fk_source_revision_knowledge_source_id_knowledge_source"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_sync_run_id"],
            ["knowledge_sync_run.id"],
            name=op.f("fk_source_revision_knowledge_sync_run_id_knowledge_sync_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_revision")),
    )

    op.create_table(
        "requirement",
        _uuid_id(),
        sa.Column("requirement_code", sa.Text(), nullable=False),
        sa.Column("service_type", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "service_type IN ('STUDENT_PASS')",
            name=op.f("ck_requirement_service_type_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirement")),
        sa.UniqueConstraint(
            "requirement_code",
            name=op.f("uq_requirement_requirement_code"),
        ),
    )

    op.create_table(
        "requirement_version",
        _uuid_id(),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("responsible_actor", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("condition_document", postgresql.JSONB(), nullable=False),
        sa.Column("machine_handling", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("git_commit_sha", sa.Text(), nullable=False),
        sa.Column("knowledge_sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "version_number > 0",
            name=op.f("ck_requirement_version_number_positive"),
        ),
        sa.CheckConstraint(
            f"fingerprint ~ '{HASH_CHECK}'",
            name=op.f("ck_requirement_version_fingerprint"),
        ),
        sa.CheckConstraint(
            f"git_commit_sha ~ '{SHA_CHECK}'",
            name=op.f("ck_requirement_version_git_sha"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from",
            name=op.f("ck_requirement_version_effective_window"),
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name=op.f("fk_requirement_version_requirement_id_requirement"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_sync_run_id"],
            ["knowledge_sync_run.id"],
            name=op.f("fk_requirement_version_knowledge_sync_run_id_knowledge_sync_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirement_version")),
        sa.UniqueConstraint(
            "requirement_id",
            "version_number",
            name=op.f("uq_requirement_version_requirement_id_version_number"),
        ),
        sa.UniqueConstraint(
            "fingerprint",
            name=op.f("uq_requirement_version_fingerprint"),
        ),
    )

    op.create_table(
        "requirement_source",
        sa.Column("requirement_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("support_type", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "support_type IN ('PRIMARY', 'SUPPORTING')",
            name=op.f("ck_requirement_source_support_type_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_id"],
            ["requirement_version.id"],
            name=op.f("fk_requirement_source_requirement_version_id_requirement_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_revision_id"],
            ["source_revision.id"],
            name=op.f("fk_requirement_source_source_revision_id_source_revision"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "requirement_version_id",
            "source_revision_id",
            "locator",
            name=op.f("pk_requirement_source"),
        ),
    )

    op.execute(
        """
        CREATE FUNCTION prevent_knowledge_history_mutation()
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
            EXECUTE FUNCTION prevent_knowledge_history_mutation()
            """
        )

    op.execute(
        """
        CREATE FUNCTION enforce_requirement_source_provenance()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            affected_requirement_version_id uuid;
        BEGIN
            IF TG_TABLE_NAME = 'requirement_source' THEN
                affected_requirement_version_id :=
                    COALESCE(NEW.requirement_version_id, OLD.requirement_version_id);
            ELSE
                affected_requirement_version_id := NEW.id;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM requirement_version
                WHERE id = affected_requirement_version_id
            ) AND NOT EXISTS (
                SELECT 1
                FROM requirement_source
                WHERE requirement_version_id = affected_requirement_version_id
            ) THEN
                RAISE EXCEPTION 'requirement version requires source provenance'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER enforce_requirement_source_provenance_on_version
        AFTER INSERT ON requirement_version
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_requirement_source_provenance()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER enforce_requirement_source_provenance_on_link
        AFTER INSERT OR UPDATE OR DELETE ON requirement_source
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_requirement_source_provenance()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER enforce_requirement_source_provenance_on_link ON requirement_source")
    op.execute(
        "DROP TRIGGER enforce_requirement_source_provenance_on_version ON requirement_version"
    )
    op.execute("DROP FUNCTION enforce_requirement_source_provenance()")
    for table_name in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER prevent_{table_name}_mutation ON {table_name}")
    op.execute("DROP FUNCTION prevent_knowledge_history_mutation()")
    op.drop_table("requirement_source")
    op.drop_table("requirement_version")
    op.drop_table("requirement")
    op.drop_table("source_revision")
    op.drop_table("knowledge_source")
    op.drop_index(
        "uq_knowledge_sync_run_success_git_sha",
        table_name="knowledge_sync_run",
    )
    op.drop_table("knowledge_sync_run")

"""Add governed rule releases, approvals, and governance audit entities.

Revision ID: 0006_rule_versions_and_activation
Revises: 0005_knowledge_sources_and_requirements
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_rule_versions_and_activation"
down_revision: str | Sequence[str] | None = "0005_knowledge_sources_and_requirements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_set",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rule_set_code", sa.Text(), nullable=False),
        sa.Column("service_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_set")),
        sa.UniqueConstraint("rule_set_code", name=op.f("uq_rule_set_rule_set_code")),
        sa.CheckConstraint(
            "service_type IN ('STUDENT_PASS')", name="rule_set_service_type_allowed"
        ),
    )
    op.create_table(
        "rule_set_version",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rule_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("semantic_version", sa.Text(), nullable=False),
        sa.Column("scope_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome_contract", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("default_outcome", sa.Text(), nullable=False),
        sa.Column("dataset_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applicability_basis", sa.Text(), nullable=False),
        sa.Column("submission_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transition_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("supersedes_rule_set_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("knowledge_sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("git_commit_sha", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["rule_set_id"], ["rule_set.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_rule_set_version_id"], ["rule_set_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_sync_run_id"], ["knowledge_sync_run.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_set_version")),
        sa.UniqueConstraint(
            "rule_set_id", "semantic_version", name=op.f("uq_rule_set_version_semantic_version")
        ),
        sa.CheckConstraint(
            "semantic_version ~ '^[0-9]+\\.[0-9]+\\.[0-9]+$'", name="rule_set_version_semver"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','REVIEW','ACTIVE','RETIRED')",
            name="rule_set_version_status_allowed",
        ),
        sa.CheckConstraint(
            "applicability_basis = 'IMMIGRATION_SUBMISSION_DATE'",
            name="rule_set_version_basis_allowed",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(outcome_contract) = 'array' AND jsonb_array_length(outcome_contract) > 0",
            name="rule_set_version_outcomes_nonempty",
        ),
        sa.CheckConstraint(
            "default_outcome IN ('pass','manual_review','action_required','unsupported_scope')",
            name="rule_set_version_default_outcome_allowed",
        ),
        sa.CheckConstraint(
            "fingerprint ~ '^[0-9a-f]{64}$'", name="rule_set_version_fingerprint_format"
        ),
        sa.CheckConstraint(
            "git_commit_sha ~ '^[0-9a-f]{40}$'", name="rule_set_version_git_sha_format"
        ),
    )
    op.create_index(
        "uq_rule_set_one_active",
        "rule_set_version",
        ["rule_set_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "rule_definition",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_definition")),
        sa.UniqueConstraint("rule_code", name=op.f("uq_rule_definition_rule_code")),
    )
    op.create_table(
        "rule_version",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rule_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_set_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("condition_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("finding_code", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=True),
        sa.Column(
            "supplemental_source_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("git_commit_sha", sa.Text(), nullable=False),
        sa.Column("knowledge_sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_definition_id"], ["rule_definition.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_version_id"], ["rule_set_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_sync_run_id"], ["knowledge_sync_run.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_version")),
        sa.UniqueConstraint(
            "rule_set_version_id",
            "rule_definition_id",
            name=op.f("uq_rule_version_definition_release"),
        ),
        sa.CheckConstraint("priority >= 0", name="rule_version_priority_nonnegative"),
        sa.CheckConstraint(
            "outcome IN ('pass','manual_review','action_required','unsupported_scope')",
            name="rule_version_outcome_allowed",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(supplemental_source_codes) = 'array'", name="rule_version_sources_array"
        ),
        sa.CheckConstraint(
            "fingerprint ~ '^[0-9a-f]{64}$'", name="rule_version_fingerprint_format"
        ),
        sa.CheckConstraint("git_commit_sha ~ '^[0-9a-f]{40}$'", name="rule_version_git_sha_format"),
    )
    op.create_table(
        "rule_requirement",
        sa.Column("rule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["rule_version_id"], ["rule_version.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requirement_version_id"], ["requirement_version.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint(
            "rule_version_id", "requirement_version_id", name=op.f("pk_rule_requirement")
        ),
    )
    op.create_table(
        "approval_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rule_set_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("decided_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["rule_set_version_id"], ["rule_set_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["decided_by_actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_event")),
        sa.UniqueConstraint("rule_set_version_id", name=op.f("uq_approval_event_rule_set_version")),
        sa.CheckConstraint(
            "decision IN ('APPROVED','REJECTED')", name="approval_event_decision_allowed"
        ),
    )

    op.alter_column(
        "audit_event",
        "case_id",
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
        nullable=True,
    )
    op.create_check_constraint(
        "audit_event_case_or_governance_entity",
        "audit_event",
        "case_id IS NOT NULL OR entity_type IN "
        "('KNOWLEDGE_SYNC_RUN','RULE_SET_VERSION','APPROVAL_EVENT')",
    )
    op.create_index(
        "ix_audit_event_entity_id_occurred_at",
        "audit_event",
        ["entity_type", "entity_id", "occurred_at"],
    )

    for table_name in ("rule_version", "rule_requirement", "approval_event"):
        op.execute(
            f"CREATE TRIGGER prevent_{table_name}_mutation BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation()"
        )
    op.execute(
        """
        CREATE FUNCTION prevent_rule_set_version_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'rule_set_version is append-only'; END IF;
            IF NEW.rule_set_id IS DISTINCT FROM OLD.rule_set_id
                OR NEW.semantic_version IS DISTINCT FROM OLD.semantic_version
                OR NEW.scope_document IS DISTINCT FROM OLD.scope_document
                OR NEW.outcome_contract IS DISTINCT FROM OLD.outcome_contract
                OR NEW.default_outcome IS DISTINCT FROM OLD.default_outcome
                OR NEW.dataset_snapshots IS DISTINCT FROM OLD.dataset_snapshots
                OR NEW.effective_at IS DISTINCT FROM OLD.effective_at
                OR NEW.applicability_basis IS DISTINCT FROM OLD.applicability_basis
                OR NEW.submission_cutoff_at IS DISTINCT FROM OLD.submission_cutoff_at
                OR NEW.transition_policy IS DISTINCT FROM OLD.transition_policy
                OR NEW.knowledge_sync_run_id IS DISTINCT FROM OLD.knowledge_sync_run_id
                OR NEW.fingerprint IS DISTINCT FROM OLD.fingerprint
                OR NEW.git_commit_sha IS DISTINCT FROM OLD.git_commit_sha
            THEN RAISE EXCEPTION 'rule_set_version content is immutable'; END IF;
            IF NOT ((OLD.status = 'DRAFT' AND NEW.status IN ('DRAFT','REVIEW'))
                OR (OLD.status = 'REVIEW' AND NEW.status IN ('REVIEW','ACTIVE','RETIRED'))
                OR (OLD.status = 'ACTIVE' AND NEW.status IN ('ACTIVE','RETIRED'))
                OR (OLD.status = 'RETIRED' AND NEW.status = 'RETIRED'))
            THEN RAISE EXCEPTION 'invalid rule_set_version status transition'; END IF;
            RETURN NEW;
        END; $$
        """
    )
    op.execute(
        "CREATE TRIGGER prevent_rule_set_version_mutation BEFORE UPDATE OR DELETE "
        "ON rule_set_version "
        "FOR EACH ROW EXECUTE FUNCTION prevent_rule_set_version_mutation()"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_rule_set_version_has_rule() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM rule_set_version WHERE id = NEW.id)
                AND NOT EXISTS (SELECT 1 FROM rule_version WHERE rule_set_version_id = NEW.id)
            THEN RAISE EXCEPTION 'rule set version requires a rule'; END IF;
            RETURN NEW;
        END; $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER rule_set_version_requires_rule AFTER INSERT "
        "ON rule_set_version DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION enforce_rule_set_version_has_rule()"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_rule_version_has_requirement()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE target_id uuid;
        BEGIN
            IF TG_TABLE_NAME = 'rule_requirement' THEN
                IF TG_OP = 'DELETE' THEN target_id := OLD.rule_version_id;
                ELSE target_id := NEW.rule_version_id;
                END IF;
            ELSE
                IF TG_OP = 'DELETE' THEN target_id := OLD.id;
                ELSE target_id := NEW.id;
                END IF;
            END IF;
            IF EXISTS (SELECT 1 FROM rule_version WHERE id = target_id)
                AND NOT EXISTS (SELECT 1 FROM rule_requirement WHERE rule_version_id = target_id)
            THEN RAISE EXCEPTION 'rule version requires requirement provenance'; END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END; $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER rule_version_requires_requirement AFTER INSERT ON rule_version "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION enforce_rule_version_has_requirement()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER rule_requirement_requires_version AFTER INSERT OR UPDATE "
        "OR DELETE "
        "ON rule_requirement DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION enforce_rule_version_has_requirement()"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_administrator_approval() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM actor
                WHERE id = NEW.decided_by_actor_id AND actor_type = 'ADMINISTRATOR'
            )
            THEN RAISE EXCEPTION 'approval requires administrator'; END IF;
            RETURN NEW;
        END; $$
        """
    )
    op.execute(
        "CREATE TRIGGER approval_requires_administrator BEFORE INSERT ON approval_event "
        "FOR EACH ROW EXECUTE FUNCTION enforce_administrator_approval()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER approval_requires_administrator ON approval_event")
    op.execute("DROP FUNCTION enforce_administrator_approval()")
    op.execute("DROP TRIGGER rule_requirement_requires_version ON rule_requirement")
    op.execute("DROP TRIGGER rule_version_requires_requirement ON rule_version")
    op.execute("DROP FUNCTION enforce_rule_version_has_requirement()")
    op.execute("DROP TRIGGER rule_set_version_requires_rule ON rule_set_version")
    op.execute("DROP FUNCTION enforce_rule_set_version_has_rule()")
    op.execute("DROP TRIGGER prevent_rule_set_version_mutation ON rule_set_version")
    op.execute("DROP FUNCTION prevent_rule_set_version_mutation()")
    for table_name in ("rule_version", "rule_requirement", "approval_event"):
        op.execute(f"DROP TRIGGER prevent_{table_name}_mutation ON {table_name}")
    op.drop_index("ix_audit_event_entity_id_occurred_at", table_name="audit_event")
    op.drop_constraint("audit_event_case_or_governance_entity", "audit_event", type_="check")
    op.alter_column(
        "audit_event",
        "case_id",
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=True,
        nullable=False,
    )
    op.drop_table("approval_event")
    op.drop_table("rule_requirement")
    op.drop_table("rule_version")
    op.drop_index("uq_rule_set_one_active", table_name="rule_set_version")
    op.drop_table("rule_definition")
    op.drop_table("rule_set_version")
    op.drop_table("rule_set")

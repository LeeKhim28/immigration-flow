"""Create generic cases and Student Pass profiles.

Revision ID: 0002_case_and_student_pass
Revises: 0001_identity_and_reference
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_case_and_student_pass"
down_revision: str | Sequence[str] | None = "0001_identity_and_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_number", sa.Text(), nullable=False),
        sa.Column("applicant_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("created_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_to_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "row_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "service_type IN ('STUDENT_PASS')",
            name=op.f("ck_case_service_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN "
            "('DRAFT','SUBMITTED','IN_PROCESS','ACTION_REQUIRED','COMPLETED','WITHDRAWN')",
            name=op.f("ck_case_status_allowed"),
        ),
        sa.CheckConstraint(
            "stage IN ('PRE_SUBMISSION','IMMIGRATION_PROCESSING','POST_ARRIVAL','CLOSED')",
            name=op.f("ck_case_stage_allowed"),
        ),
        sa.CheckConstraint(
            "row_version >= 1",
            name=op.f("ck_case_row_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["applicant_profile_id"],
            ["applicant_profile.id"],
            name=op.f("fk_case_applicant_profile_id_applicant_profile"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actor.id"],
            name=op.f("fk_case_created_by_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_actor_id"],
            ["actor.id"],
            name=op.f("fk_case_assigned_to_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case")),
        sa.UniqueConstraint("case_number", name=op.f("uq_case_case_number")),
    )
    op.create_index(
        "ix_case_applicant_profile_id",
        "case",
        ["applicant_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_case_created_by_actor_id",
        "case",
        ["created_by_actor_id"],
        unique=False,
    )
    op.create_index(
        "ix_case_assigned_to_actor_id",
        "case",
        ["assigned_to_actor_id"],
        unique=False,
    )
    op.create_index(
        "ix_case_status_stage",
        "case",
        ["status", "stage"],
        unique=False,
    )

    op.create_table(
        "student_pass_case_profile",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_type", sa.Text(), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("programme_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_type", sa.Text(), nullable=False),
        sa.Column("region_code", sa.Text(), nullable=False),
        sa.Column("applicant_location", sa.Text(), nullable=False),
        sa.Column("nationality_code", sa.Text(), nullable=False),
        sa.Column("passport_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "application_type IN ('NEW')",
            name=op.f("ck_student_pass_case_profile_application_type_allowed"),
        ),
        sa.CheckConstraint(
            "institution_type IN ('UA','IPTS')",
            name=op.f("ck_student_pass_case_profile_institution_type_allowed"),
        ),
        sa.CheckConstraint(
            "applicant_location IN ('OUTSIDE_MALAYSIA')",
            name=op.f("ck_student_pass_case_profile_applicant_location_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case.id"],
            name=op.f("fk_student_pass_case_profile_case_id_case"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institution.id"],
            name=op.f("fk_student_pass_case_profile_institution_id_institution"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["programme_id", "institution_id"],
            ["programme.id", "programme.institution_id"],
            name="fk_student_pass_profile_programme_institution",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("case_id", name=op.f("pk_student_pass_case_profile")),
    )
    op.create_index(
        "ix_student_pass_case_profile_institution_id",
        "student_pass_case_profile",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_pass_case_profile_programme_id",
        "student_pass_case_profile",
        ["programme_id"],
        unique=False,
    )

    op.create_table(
        "case_status_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("changed_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('DRAFT','SUBMITTED','IN_PROCESS','ACTION_REQUIRED','COMPLETED','WITHDRAWN')",
            name=op.f("ck_case_status_history_from_status_allowed"),
        ),
        sa.CheckConstraint(
            "to_status IN "
            "('DRAFT','SUBMITTED','IN_PROCESS','ACTION_REQUIRED','COMPLETED','WITHDRAWN')",
            name=op.f("ck_case_status_history_to_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case.id"],
            name=op.f("fk_case_status_history_case_id_case"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_actor_id"],
            ["actor.id"],
            name=op.f("fk_case_status_history_changed_by_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_status_history")),
    )
    op.create_index(
        "ix_case_status_history_case_id",
        "case_status_history",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_case_status_history_changed_by_actor_id",
        "case_status_history",
        ["changed_by_actor_id"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION enforce_student_pass_case_profile()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            case_id_to_check uuid;
            affected_case_ids uuid[];
            service text;
        BEGIN
            IF TG_TABLE_NAME = 'case' THEN
                IF TG_OP = 'DELETE' THEN
                    affected_case_ids := ARRAY[OLD.id];
                ELSIF TG_OP = 'UPDATE' THEN
                    affected_case_ids := ARRAY[NEW.id, OLD.id];
                ELSE
                    affected_case_ids := ARRAY[NEW.id];
                END IF;
            ELSE
                IF TG_OP = 'DELETE' THEN
                    affected_case_ids := ARRAY[OLD.case_id];
                ELSIF TG_OP = 'UPDATE' THEN
                    affected_case_ids := ARRAY[NEW.case_id, OLD.case_id];
                ELSE
                    affected_case_ids := ARRAY[NEW.case_id];
                END IF;
            END IF;

            FOREACH case_id_to_check IN ARRAY affected_case_ids LOOP
                SELECT service_type INTO service
                FROM "case" WHERE id = case_id_to_check;

                IF FOUND AND service = 'STUDENT_PASS'
                   AND NOT EXISTS (
                       SELECT 1 FROM student_pass_case_profile
                       WHERE case_id = case_id_to_check
                   ) THEN
                    RAISE EXCEPTION 'Student Pass case requires exactly one profile'
                        USING ERRCODE = '23514';
                END IF;

                IF FOUND AND service <> 'STUDENT_PASS'
                   AND EXISTS (
                       SELECT 1 FROM student_pass_case_profile
                       WHERE case_id = case_id_to_check
                   ) THEN
                    RAISE EXCEPTION 'profile is only valid for Student Pass cases'
                        USING ERRCODE = '23514';
                END IF;
            END LOOP;

            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER enforce_student_pass_profile_on_case
        AFTER INSERT OR UPDATE OR DELETE ON "case"
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_student_pass_case_profile()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER enforce_student_pass_profile_on_profile
        AFTER INSERT OR UPDATE OR DELETE ON student_pass_case_profile
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_student_pass_case_profile()
        """
    )


def downgrade() -> None:
    op.execute('DROP TRIGGER enforce_student_pass_profile_on_case ON "case"')
    op.execute("DROP TRIGGER enforce_student_pass_profile_on_profile ON student_pass_case_profile")
    op.execute("DROP FUNCTION enforce_student_pass_case_profile()")
    op.drop_table("case_status_history")
    op.drop_table("student_pass_case_profile")
    op.drop_table("case")

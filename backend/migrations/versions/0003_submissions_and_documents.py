"""Create formal submissions and document version metadata.

Revision ID: 0003_submissions_and_documents
Revises: 0002_case_and_student_pass
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_submissions_and_documents"
down_revision: str | Sequence[str] | None = "0002_case_and_student_pass"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.Text(), nullable=False),
        sa.Column("owner_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
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
        sa.CheckConstraint(
            "document_type IN ("
            "'PHOTO','PASSPORT_BIODATA','PASSPORT_VISA_PAGES',"
            "'PASSPORT_OBSERVATION_PAGES','PASSPORT_ALL_PAGES','OFFER_LETTER',"
            "'HEALTH_DECLARATION','ACADEMIC_RECORDS','ENGLISH_EVIDENCE','LOE','NOC',"
            "'PERSONAL_BOND','YELLOW_FEVER_CERTIFICATE','IMMIGRATION_RECEIPT','OTHER'"
            ")",
            name=op.f("ck_document_document_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','SUPERSEDED','VOID')",
            name=op.f("ck_document_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case.id"],
            name=op.f("fk_document_case_id_case"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_actor_id"],
            ["actor.id"],
            name=op.f("fk_document_owner_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document")),
    )
    op.create_index("ix_document_case_id", "document", ["case_id"], unique=False)
    op.create_index(
        "ix_document_owner_actor_id",
        "document",
        ["owner_actor_id"],
        unique=False,
    )

    op.create_table(
        "document_version",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_reference", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "version_number >= 1",
            name=op.f("ck_document_version_version_number_positive"),
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name=op.f("ck_document_version_size_bytes_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_document_version_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actor.id"],
            name=op.f("fk_document_version_created_by_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_version")),
        sa.UniqueConstraint(
            "document_id",
            "version_number",
            name=op.f("uq_document_version_document_id_version_number"),
        ),
    )
    op.create_index(
        "ix_document_version_document_id",
        "document_version",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_version_created_by_actor_id",
        "document_version",
        ["created_by_actor_id"],
        unique=False,
    )

    op.create_table(
        "case_submission",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_type", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("submitted_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("immigration_reference", sa.Text(), nullable=True),
        sa.Column(
            "receipt_document_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "submission_type IN ('INITIAL','SUPPLEMENTARY')",
            name=op.f("ck_case_submission_submission_type_allowed"),
        ),
        sa.CheckConstraint(
            "channel IN ("
            "'EMGS','IMMIGRATION_COUNTER','ONLINE_PORTAL','INSTITUTION_REPRESENTATIVE'"
            ")",
            name=op.f("ck_case_submission_channel_allowed"),
        ),
        sa.CheckConstraint(
            "accepted_at IS NULL OR ("
            "immigration_reference IS NOT NULL "
            "AND btrim(immigration_reference) <> '' "
            "AND receipt_document_version_id IS NOT NULL"
            ")",
            name=op.f("ck_case_submission_accepted_requires_evidence"),
        ),
        sa.CheckConstraint(
            "confirmed_at IS NULL OR accepted_at IS NOT NULL",
            name=op.f("ck_case_submission_confirmed_requires_accepted"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case.id"],
            name=op.f("fk_case_submission_case_id_case"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_actor_id"],
            ["actor.id"],
            name=op.f("fk_case_submission_submitted_by_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_submission")),
    )
    op.create_foreign_key(
        op.f("fk_case_submission_receipt_document_version_id_document_version"),
        "case_submission",
        "document_version",
        ["receipt_document_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_case_submission_case_id",
        "case_submission",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_case_submission_submitted_by_actor_id",
        "case_submission",
        ["submitted_by_actor_id"],
        unique=False,
    )
    op.create_index(
        "ix_case_submission_receipt_document_version_id",
        "case_submission",
        ["receipt_document_version_id"],
        unique=False,
    )
    op.create_index(
        "uq_case_submission_confirmed_initial",
        "case_submission",
        ["case_id"],
        unique=True,
        postgresql_where=sa.text("submission_type = 'INITIAL' AND confirmed_at IS NOT NULL"),
    )

    op.create_table(
        "submission_document",
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column(
            "included_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["case_submission.id"],
            name=op.f("fk_submission_document_submission_id_case_submission"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_version.id"],
            name=op.f("fk_submission_document_document_version_id_document_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "submission_id",
            "document_version_id",
            "purpose",
            name=op.f("pk_submission_document"),
        ),
    )
    op.create_index(
        "ix_submission_document_document_version_id",
        "submission_document",
        ["document_version_id"],
        unique=False,
    )

    op.create_table(
        "document_check",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("check_type", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("checked_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "result IN ('PASS','FAIL','MANUAL_REVIEW')",
            name=op.f("ck_document_check_result_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_version.id"],
            name=op.f("fk_document_check_document_version_id_document_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["checked_by_actor_id"],
            ["actor.id"],
            name=op.f("fk_document_check_checked_by_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_check")),
    )
    op.create_index(
        "ix_document_check_document_version_id",
        "document_check",
        ["document_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_check_checked_by_actor_id",
        "document_check",
        ["checked_by_actor_id"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION enforce_same_case_submission_receipt()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            receipt_case_id uuid;
        BEGIN
            SELECT d.case_id INTO receipt_case_id
            FROM document_version dv
            JOIN document d ON d.id = dv.document_id
            WHERE dv.id = NEW.receipt_document_version_id;

            IF NEW.receipt_document_version_id IS NOT NULL
               AND (receipt_case_id IS NULL OR receipt_case_id <> NEW.case_id) THEN
                RAISE EXCEPTION 'receipt document version must belong to submission case'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER enforce_same_case_submission_receipt
        AFTER INSERT OR UPDATE ON case_submission
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_same_case_submission_receipt()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER enforce_same_case_submission_receipt ON case_submission")
    op.execute("DROP FUNCTION enforce_same_case_submission_receipt()")
    op.drop_table("document_check")
    op.drop_table("submission_document")
    op.drop_table("case_submission")
    op.drop_table("document_version")
    op.drop_table("document")

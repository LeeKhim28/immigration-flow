from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database.base import Base
from app.database.enums import SubmissionChannel, SubmissionType


class SubmissionTypeText(TypeDecorator[SubmissionType]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: SubmissionType | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, SubmissionType):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> SubmissionType | None:
        if value is None:
            return None
        return SubmissionType(value)


class SubmissionChannelText(TypeDecorator[SubmissionChannel]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: SubmissionChannel | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, SubmissionChannel):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> SubmissionChannel | None:
        if value is None:
            return None
        return SubmissionChannel(value)


class CaseSubmission(Base):
    __tablename__ = "case_submission"
    __table_args__ = (
        CheckConstraint(
            "submission_type IN ('INITIAL','SUPPLEMENTARY')",
            name="submission_type_allowed",
        ),
        CheckConstraint(
            "channel IN ("
            "'EMGS','IMMIGRATION_COUNTER','ONLINE_PORTAL','INSTITUTION_REPRESENTATIVE'"
            ")",
            name="channel_allowed",
        ),
        CheckConstraint(
            "accepted_at IS NULL OR ("
            "immigration_reference IS NOT NULL "
            "AND btrim(immigration_reference) <> '' "
            "AND receipt_document_version_id IS NOT NULL"
            ")",
            name="accepted_requires_evidence",
        ),
        CheckConstraint(
            "confirmed_at IS NULL OR accepted_at IS NOT NULL",
            name="confirmed_requires_accepted",
        ),
        Index("ix_case_submission_case_id", "case_id"),
        Index("ix_case_submission_submitted_by_actor_id", "submitted_by_actor_id"),
        Index(
            "ix_case_submission_receipt_document_version_id",
            "receipt_document_version_id",
        ),
        Index(
            "uq_case_submission_confirmed_initial",
            "case_id",
            unique=True,
            postgresql_where=text("submission_type = 'INITIAL' AND confirmed_at IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("case.id", ondelete="RESTRICT"),
        nullable=False,
    )
    submission_type: Mapped[SubmissionType] = mapped_column(
        SubmissionTypeText(),
        nullable=False,
    )
    channel: Mapped[SubmissionChannel] = mapped_column(
        SubmissionChannelText(),
        nullable=False,
    )
    submitted_by_actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    immigration_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_document_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="RESTRICT"),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class SubmissionDocument(Base):
    __tablename__ = "submission_document"
    __table_args__ = (Index("ix_submission_document_document_version_id", "document_version_id"),)

    submission_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("case_submission.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    document_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    purpose: Mapped[str] = mapped_column(Text, primary_key=True)
    included_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

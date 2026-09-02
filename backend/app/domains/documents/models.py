from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database.base import Base
from app.database.enums import DocumentCheckResult, DocumentStatus, DocumentType


class DocumentTypeText(TypeDecorator[DocumentType]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: DocumentType | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, DocumentType):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> DocumentType | None:
        if value is None:
            return None
        return DocumentType(value)


class DocumentStatusText(TypeDecorator[DocumentStatus]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: DocumentStatus | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, DocumentStatus):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> DocumentStatus | None:
        if value is None:
            return None
        return DocumentStatus(value)


class DocumentCheckResultText(TypeDecorator[DocumentCheckResult]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: DocumentCheckResult | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, DocumentCheckResult):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> DocumentCheckResult | None:
        if value is None:
            return None
        return DocumentCheckResult(value)


class Document(Base):
    __tablename__ = "document"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ("
            "'PHOTO','PASSPORT_BIODATA','PASSPORT_VISA_PAGES',"
            "'PASSPORT_OBSERVATION_PAGES','PASSPORT_ALL_PAGES','OFFER_LETTER',"
            "'HEALTH_DECLARATION','ACADEMIC_RECORDS','ENGLISH_EVIDENCE','LOE','NOC',"
            "'PERSONAL_BOND','YELLOW_FEVER_CERTIFICATE','IMMIGRATION_RECEIPT','OTHER'"
            ")",
            name="document_type_allowed",
        ),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','SUPERSEDED','VOID')",
            name="status_allowed",
        ),
        Index("ix_document_case_id", "case_id"),
        Index("ix_document_owner_actor_id", "owner_actor_id"),
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
    document_type: Mapped[DocumentType] = mapped_column(
        DocumentTypeText(),
        nullable=False,
    )
    owner_actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        DocumentStatusText(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class DocumentVersion(Base):
    __tablename__ = "document_version"
    __table_args__ = (
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("size_bytes >= 0", name="size_bytes_nonnegative"),
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_version_document_id_version_number",
        ),
        Index("ix_document_version_document_id", "document_id"),
        Index("ix_document_version_created_by_actor_id", "created_by_actor_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_reference: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_by_actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )


class DocumentCheck(Base):
    __tablename__ = "document_check"
    __table_args__ = (
        CheckConstraint(
            "result IN ('PASS','FAIL','MANUAL_REVIEW')",
            name="result_allowed",
        ),
        Index("ix_document_check_document_version_id", "document_version_id"),
        Index("ix_document_check_checked_by_actor_id", "checked_by_actor_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    check_type: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[DocumentCheckResult] = mapped_column(
        DocumentCheckResultText(),
        nullable=False,
    )
    details: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    checked_by_actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

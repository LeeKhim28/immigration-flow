from datetime import datetime
from uuid import UUID

from sqlalchemy import (
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
from app.database.enums import CaseStage, CaseStatus, ServiceType


class ServiceTypeText(TypeDecorator[ServiceType]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: ServiceType | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, ServiceType):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> ServiceType | None:
        if value is None:
            return None
        return ServiceType(value)


class CaseStatusText(TypeDecorator[CaseStatus]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: CaseStatus | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, CaseStatus):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> CaseStatus | None:
        if value is None:
            return None
        return CaseStatus(value)


class CaseStageText(TypeDecorator[CaseStage]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: CaseStage | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, CaseStage):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> CaseStage | None:
        if value is None:
            return None
        return CaseStage(value)


class ImmigrationCase(Base):
    __tablename__ = "case"
    __table_args__ = (
        CheckConstraint(
            "service_type IN ('STUDENT_PASS')",
            name="service_type_allowed",
        ),
        CheckConstraint(
            "status IN "
            "('DRAFT','SUBMITTED','IN_PROCESS','ACTION_REQUIRED','COMPLETED','WITHDRAWN')",
            name="status_allowed",
        ),
        CheckConstraint(
            "stage IN ('PRE_SUBMISSION','IMMIGRATION_PROCESSING','POST_ARRIVAL','CLOSED')",
            name="stage_allowed",
        ),
        CheckConstraint("row_version >= 1", name="row_version_positive"),
        UniqueConstraint("case_number", name="uq_case_case_number"),
        Index("ix_case_applicant_profile_id", "applicant_profile_id"),
        Index("ix_case_created_by_actor_id", "created_by_actor_id"),
        Index("ix_case_assigned_to_actor_id", "assigned_to_actor_id"),
        Index("ix_case_status_stage", "status", "stage"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    case_number: Mapped[str] = mapped_column(Text, nullable=False)
    applicant_profile_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("applicant_profile.id", ondelete="RESTRICT"),
        nullable=False,
    )
    service_type: Mapped[ServiceType] = mapped_column(ServiceTypeText(), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(CaseStatusText(), nullable=False)
    stage: Mapped[CaseStage] = mapped_column(CaseStageText(), nullable=False)
    created_by_actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to_actor_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
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
    row_version: Mapped[int] = mapped_column(
        Integer,
        server_default=text("1"),
        nullable=False,
    )


class CaseStatusHistory(Base):
    __tablename__ = "case_status_history"
    __table_args__ = (
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('DRAFT','SUBMITTED','IN_PROCESS','ACTION_REQUIRED','COMPLETED','WITHDRAWN')",
            name="from_status_allowed",
        ),
        CheckConstraint(
            "to_status IN "
            "('DRAFT','SUBMITTED','IN_PROCESS','ACTION_REQUIRED','COMPLETED','WITHDRAWN')",
            name="to_status_allowed",
        ),
        Index("ix_case_status_history_case_id", "case_id"),
        Index("ix_case_status_history_changed_by_actor_id", "changed_by_actor_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("case.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[CaseStatus | None] = mapped_column(
        CaseStatusText(),
        nullable=True,
    )
    to_status: Mapped[CaseStatus] = mapped_column(CaseStatusText(), nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by_actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CaseEvent(Base):
    __tablename__ = "case_event"
    __table_args__ = (Index("ix_case_event_case_id_occurred_at", "case_id", "occurred_at"),)

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
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
    )


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_event_case_id_occurred_at", "case_id", "occurred_at"),)

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
    actor_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    before_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    after_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

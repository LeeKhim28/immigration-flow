from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database.base import Base
from app.database.enums import ActorType


class ActorTypeText(TypeDecorator[ActorType]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: ActorType | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, ActorType):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> ActorType | None:
        if value is None:
            return None
        return ActorType(value)


class Actor(Base):
    __tablename__ = "actor"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('APPLICANT','INSTITUTION_WORKER','OFFICER','ADMINISTRATOR','SYSTEM')",
            name="actor_type_allowed",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    actor_type: Mapped[ActorType] = mapped_column(ActorTypeText(), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class ApplicantProfile(Base):
    __tablename__ = "applicant_profile"
    __table_args__ = (
        UniqueConstraint("actor_id", name="uq_applicant_profile_actor_id"),
        UniqueConstraint(
            "synthetic_reference",
            name="uq_applicant_profile_synthetic_reference",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    synthetic_reference: Mapped[str] = mapped_column(Text, nullable=False)
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

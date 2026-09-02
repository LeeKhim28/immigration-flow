from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database.base import Base
from app.database.enums import ApplicantLocation, ApplicationType, InstitutionType


class ApplicationTypeText(TypeDecorator[ApplicationType]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: ApplicationType | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, ApplicationType):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> ApplicationType | None:
        if value is None:
            return None
        return ApplicationType(value)


class InstitutionTypeText(TypeDecorator[InstitutionType]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: InstitutionType | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, InstitutionType):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> InstitutionType | None:
        if value is None:
            return None
        return InstitutionType(value)


class ApplicantLocationText(TypeDecorator[ApplicantLocation]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: ApplicantLocation | str | None,
        dialect: Dialect,
    ) -> str | None:
        if isinstance(value, ApplicantLocation):
            return value.value
        return value

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> ApplicantLocation | None:
        if value is None:
            return None
        return ApplicantLocation(value)


class StudentPassCaseProfile(Base):
    __tablename__ = "student_pass_case_profile"
    __table_args__ = (
        ForeignKeyConstraint(
            ["programme_id", "institution_id"],
            ["programme.id", "programme.institution_id"],
            name="fk_student_pass_profile_programme_institution",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "application_type IN ('NEW')",
            name="application_type_allowed",
        ),
        CheckConstraint(
            "institution_type IN ('UA','IPTS')",
            name="institution_type_allowed",
        ),
        CheckConstraint(
            "applicant_location IN ('OUTSIDE_MALAYSIA')",
            name="applicant_location_allowed",
        ),
        Index("ix_student_pass_case_profile_institution_id", "institution_id"),
        Index("ix_student_pass_case_profile_programme_id", "programme_id"),
    )

    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("case.id", ondelete="CASCADE"),
        primary_key=True,
    )
    application_type: Mapped[ApplicationType] = mapped_column(
        ApplicationTypeText(),
        nullable=False,
    )
    institution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("institution.id", ondelete="RESTRICT"),
        nullable=False,
    )
    programme_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    institution_type: Mapped[InstitutionType] = mapped_column(
        InstitutionTypeText(),
        nullable=False,
    )
    region_code: Mapped[str] = mapped_column(Text, nullable=False)
    applicant_location: Mapped[ApplicantLocation] = mapped_column(
        ApplicantLocationText(),
        nullable=False,
    )
    nationality_code: Mapped[str] = mapped_column(Text, nullable=False)
    passport_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    arrival_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

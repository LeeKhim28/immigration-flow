from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.enums import (
    ActorType,
    ApplicantLocation,
    ApplicationType,
    CaseStage,
    CaseStatus,
    InstitutionType,
    ServiceType,
)
from app.database.models import (
    Actor,
    ApplicantProfile,
    CaseStatusHistory,
    ImmigrationCase,
    Institution,
    Programme,
    StudentPassCaseProfile,
)


@pytest.fixture
def session(test_database_url: str) -> Iterator[Session]:
    engine: Engine = create_engine(test_database_url)
    _truncate_case_test_data(engine)
    database_session = Session(engine)
    try:
        yield database_session
    finally:
        database_session.rollback()
        database_session.close()
        _truncate_case_test_data(engine)
        engine.dispose()


def _truncate_case_test_data(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    case_status_history,
                    student_pass_case_profile,
                    "case",
                    programme,
                    institution,
                    applicant_profile,
                    actor
                CASCADE
                """
            )
        )


def _reference_records(
    session: Session,
    suffix: str,
) -> tuple[ApplicantProfile, Actor, Institution, Programme]:
    applicant_actor = Actor(
        actor_type=ActorType.APPLICANT,
        display_name=f"Applicant {suffix}",
    )
    creator = Actor(
        actor_type=ActorType.SYSTEM,
        display_name=f"Creator {suffix}",
    )
    institution = Institution(
        institution_code=f"INST-{suffix}",
        name=f"Institution {suffix}",
        institution_type="UA",
        region_code="MY-14",
        active=True,
    )
    session.add_all([applicant_actor, creator, institution])
    session.flush()

    applicant_profile = ApplicantProfile(
        actor_id=applicant_actor.id,
        synthetic_reference=f"SYN-{suffix}",
    )
    programme = Programme(
        institution_id=institution.id,
        programme_code=f"PROG-{suffix}",
        name=f"Programme {suffix}",
        level="BACHELOR",
        active=True,
    )
    session.add_all([applicant_profile, programme])
    session.flush()
    return applicant_profile, creator, institution, programme


def _case(
    applicant_profile: ApplicantProfile,
    creator: Actor,
    suffix: str,
    **overrides: object,
) -> ImmigrationCase:
    values: dict[str, object] = {
        "case_number": f"CASE-{suffix}",
        "applicant_profile_id": applicant_profile.id,
        "service_type": ServiceType.STUDENT_PASS,
        "status": CaseStatus.DRAFT,
        "stage": CaseStage.PRE_SUBMISSION,
        "created_by_actor_id": creator.id,
    }
    values.update(overrides)
    return ImmigrationCase(**values)


def _student_pass_profile(
    case: ImmigrationCase,
    institution: Institution,
    programme: Programme,
    **overrides: object,
) -> StudentPassCaseProfile:
    values: dict[str, object] = {
        "case_id": case.id,
        "application_type": ApplicationType.NEW,
        "institution_id": institution.id,
        "programme_id": programme.id,
        "institution_type": InstitutionType.UA,
        "region_code": "MY-14",
        "applicant_location": ApplicantLocation.OUTSIDE_MALAYSIA,
        "nationality_code": "MY",
        "passport_expires_at": datetime(2030, 1, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return StudentPassCaseProfile(**values)


def _persist_valid_case(session: Session, suffix: str) -> tuple[ImmigrationCase, Actor]:
    applicant_profile, creator, institution, programme = _reference_records(session, suffix)
    case = _case(applicant_profile, creator, suffix)
    session.add(case)
    session.flush()
    session.add(_student_pass_profile(case, institution, programme))
    session.commit()
    return case, creator


def test_valid_student_pass_case_and_profile_commit_together(session: Session) -> None:
    applicant_profile, creator, institution, programme = _reference_records(session, "VALID")
    assigned_officer = Actor(
        actor_type=ActorType.OFFICER,
        display_name="Assigned Officer",
    )
    session.add(assigned_officer)
    session.flush()

    case = _case(
        applicant_profile,
        creator,
        "VALID",
        assigned_to_actor_id=assigned_officer.id,
    )
    session.add(case)
    session.flush()
    profile = _student_pass_profile(case, institution, programme)
    session.add(profile)
    session.flush()
    history = CaseStatusHistory(
        case_id=case.id,
        from_status=None,
        to_status=CaseStatus.DRAFT,
        reason_code="CASE_CREATED",
        changed_by_actor_id=creator.id,
    )
    session.add(history)
    session.commit()
    session.expire_all()

    assert isinstance(case.id, UUID)
    assert case.service_type is ServiceType.STUDENT_PASS
    assert case.status is CaseStatus.DRAFT
    assert case.stage is CaseStage.PRE_SUBMISSION
    assert case.row_version == 1
    assert case.created_at.tzinfo is not None
    assert case.updated_at.tzinfo is not None
    assert profile.application_type is ApplicationType.NEW
    assert profile.institution_type is InstitutionType.UA
    assert profile.applicant_location is ApplicantLocation.OUTSIDE_MALAYSIA
    assert profile.arrival_at is None
    assert history.changed_at.tzinfo is not None


def test_student_pass_case_requires_profile_at_transaction_commit(session: Session) -> None:
    applicant_profile, creator, _institution, _programme = _reference_records(session, "NO-PROFILE")
    session.add(_case(applicant_profile, creator, "NO-PROFILE"))

    with pytest.raises(
        IntegrityError,
        match="Student Pass case requires exactly one profile",
    ):
        session.commit()


def test_profile_rejects_programme_from_another_institution(session: Session) -> None:
    applicant_profile, creator, institution, _programme = _reference_records(
        session, "WRONG-INST-A"
    )
    _other_profile, _other_creator, _other_institution, other_programme = _reference_records(
        session, "WRONG-INST-B"
    )
    case = _case(applicant_profile, creator, "WRONG-INST")
    session.add(case)
    session.flush()
    session.add(_student_pass_profile(case, institution, other_programme))

    with pytest.raises(IntegrityError):
        session.commit()


def test_case_rejects_second_profile(session: Session) -> None:
    applicant_profile, creator, institution, programme = _reference_records(session, "SECOND")
    case = _case(applicant_profile, creator, "SECOND")
    session.add(case)
    session.flush()
    session.add_all(
        [
            _student_pass_profile(case, institution, programme),
            _student_pass_profile(case, institution, programme),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("service_type", "WORK_PERMIT"),
        ("status", "UNKNOWN"),
        ("stage", "UNKNOWN"),
    ],
)
def test_case_rejects_unsupported_enum_values(
    session: Session,
    field: str,
    invalid_value: str,
) -> None:
    applicant_profile, creator, _institution, _programme = _reference_records(
        session, f"BAD-CASE-{field}"
    )
    case = _case(
        applicant_profile,
        creator,
        f"BAD-{field}",
        **{field: invalid_value},
    )
    session.add(case)

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("application_type", "RENEWAL"),
        ("institution_type", "COLLEGE"),
        ("applicant_location", "INSIDE_MALAYSIA"),
    ],
)
def test_profile_rejects_unsupported_enum_values(
    session: Session,
    field: str,
    invalid_value: str,
) -> None:
    applicant_profile, creator, institution, programme = _reference_records(
        session, f"BAD-PROFILE-{field}"
    )
    case = _case(applicant_profile, creator, f"BAD-PROFILE-{field}")
    session.add(case)
    session.flush()
    session.add(
        _student_pass_profile(
            case,
            institution,
            programme,
            **{field: invalid_value},
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_case_rejects_duplicate_case_number(session: Session) -> None:
    first_profile, first_creator, _first_institution, _first_programme = _reference_records(
        session, "DUP-A"
    )
    second_profile, second_creator, _second_institution, _second_programme = _reference_records(
        session, "DUP-B"
    )
    first_case = _case(first_profile, first_creator, "DUP")
    second_case = _case(second_profile, second_creator, "DUP")
    session.add_all([first_case, second_case])

    with pytest.raises(IntegrityError):
        session.flush()


def test_case_rejects_non_positive_row_version(session: Session) -> None:
    applicant_profile, creator, _institution, _programme = _reference_records(session, "VERSION")
    case = _case(applicant_profile, creator, "VERSION", row_version=0)
    session.add(case)

    with pytest.raises(IntegrityError):
        session.flush()


def test_direct_sql_cannot_bypass_profile_requirement(session: Session) -> None:
    applicant_profile, creator, _institution, _programme = _reference_records(session, "DIRECT")
    session.execute(
        text(
            """
            INSERT INTO "case" (
                id, case_number, applicant_profile_id, service_type, status, stage,
                created_by_actor_id, row_version
            ) VALUES (
                :id, :case_number, :applicant_profile_id, 'STUDENT_PASS', 'DRAFT',
                'PRE_SUBMISSION', :created_by_actor_id, 1
            )
            """
        ),
        {
            "id": uuid4(),
            "case_number": "CASE-DIRECT",
            "applicant_profile_id": applicant_profile.id,
            "created_by_actor_id": creator.id,
        },
    )

    with pytest.raises(
        IntegrityError,
        match="Student Pass case requires exactly one profile",
    ):
        session.commit()


def test_direct_sql_profile_delete_is_checked_at_commit(session: Session) -> None:
    case, _creator = _persist_valid_case(session, "DELETE-PROFILE")
    session.execute(
        text("DELETE FROM student_pass_case_profile WHERE case_id = :case_id"),
        {"case_id": case.id},
    )

    with pytest.raises(
        IntegrityError,
        match="Student Pass case requires exactly one profile",
    ):
        session.commit()


def test_profile_reassignment_checks_old_and_new_case_ids(session: Session) -> None:
    first_case, _first_creator = _persist_valid_case(session, "MOVE-A")
    second_case, _second_creator = _persist_valid_case(session, "MOVE-B")
    session.execute(
        text("DELETE FROM student_pass_case_profile WHERE case_id = :case_id"),
        {"case_id": second_case.id},
    )
    session.execute(
        text(
            """
            UPDATE student_pass_case_profile
            SET case_id = :new_case_id
            WHERE case_id = :old_case_id
            """
        ),
        {"new_case_id": second_case.id, "old_case_id": first_case.id},
    )

    with pytest.raises(
        IntegrityError,
        match="Student Pass case requires exactly one profile",
    ):
        session.commit()

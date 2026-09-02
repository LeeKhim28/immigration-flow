from collections.abc import Iterator
from datetime import UTC
from uuid import UUID

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.enums import ActorType
from app.database.models import Actor, ApplicantProfile, Institution, Programme


@pytest.fixture
def session(test_database_url: str) -> Iterator[Session]:
    engine: Engine = create_engine(test_database_url)
    connection = engine.connect()
    transaction = connection.begin()
    database_session = Session(bind=connection)
    try:
        yield database_session
    finally:
        database_session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        engine.dispose()


def test_valid_identity_and_reference_records_use_server_defaults(session: Session) -> None:
    applicant = Actor(actor_type=ActorType.APPLICANT, display_name="Synthetic Applicant")
    session.add(applicant)
    session.flush()

    profile = ApplicantProfile(actor_id=applicant.id, synthetic_reference="SYN-VALID")
    institution = Institution(
        institution_code="INST-VALID",
        name="Synthetic University",
        institution_type="UA",
        region_code="MY-14",
        active=True,
    )
    session.add_all([profile, institution])
    session.flush()

    programme = Programme(
        institution_id=institution.id,
        programme_code="PROG-VALID",
        name="Synthetic Computing",
        level="BACHELOR",
        active=True,
    )
    session.add(programme)
    session.commit()
    session.expire(applicant, ["actor_type"])

    assert all(
        isinstance(record.id, UUID) for record in (applicant, profile, institution, programme)
    )
    assert applicant.actor_type is ActorType.APPLICANT
    assert applicant.created_at.tzinfo is not None
    assert applicant.created_at.utcoffset() == UTC.utcoffset(applicant.created_at)
    assert applicant.updated_at.tzinfo is not None
    assert profile.actor_id == applicant.id
    assert programme.institution_id == institution.id
    assert institution.active is True
    assert programme.active is True


def test_actor_type_check_rejects_unknown_value(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.add(Actor(actor_type="UNKNOWN", display_name="Invalid"))
        session.commit()


def test_applicant_profile_rejects_second_profile_for_actor(session: Session) -> None:
    applicant = Actor(actor_type="APPLICANT", display_name="Synthetic Applicant")
    session.add(applicant)
    session.flush()

    with pytest.raises(IntegrityError):
        session.add_all(
            [
                ApplicantProfile(actor_id=applicant.id, synthetic_reference="SYN-001"),
                ApplicantProfile(actor_id=applicant.id, synthetic_reference="SYN-002"),
            ]
        )
        session.commit()


def test_applicant_profile_rejects_duplicate_synthetic_reference(session: Session) -> None:
    applicants = [
        Actor(actor_type="APPLICANT", display_name="Synthetic Applicant One"),
        Actor(actor_type="APPLICANT", display_name="Synthetic Applicant Two"),
    ]
    session.add_all(applicants)
    session.flush()

    with pytest.raises(IntegrityError):
        session.add_all(
            [
                ApplicantProfile(actor_id=applicants[0].id, synthetic_reference="SYN-DUP"),
                ApplicantProfile(actor_id=applicants[1].id, synthetic_reference="SYN-DUP"),
            ]
        )
        session.commit()


def test_institution_rejects_duplicate_institution_code(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.add_all(
            [
                Institution(
                    institution_code="INST-DUP",
                    name="Synthetic University One",
                    institution_type="UA",
                    region_code="MY-14",
                    active=True,
                ),
                Institution(
                    institution_code="INST-DUP",
                    name="Synthetic University Two",
                    institution_type="IPTS",
                    region_code="MY-10",
                    active=True,
                ),
            ]
        )
        session.commit()


def test_programme_rejects_duplicate_code_within_institution(session: Session) -> None:
    institution = Institution(
        institution_code="INST-PROG-DUP",
        name="Synthetic University",
        institution_type="UA",
        region_code="MY-14",
        active=True,
    )
    session.add(institution)
    session.flush()

    with pytest.raises(IntegrityError):
        session.add_all(
            [
                Programme(
                    institution_id=institution.id,
                    programme_code="PROG-DUP",
                    name="Synthetic Computing One",
                    level="BACHELOR",
                    active=True,
                ),
                Programme(
                    institution_id=institution.id,
                    programme_code="PROG-DUP",
                    name="Synthetic Computing Two",
                    level="MASTER",
                    active=True,
                ),
            ]
        )
        session.commit()


def test_applicant_profile_foreign_key_restricts_deleting_actor(session: Session) -> None:
    applicant = Actor(actor_type="APPLICANT", display_name="Synthetic Applicant")
    session.add(applicant)
    session.flush()
    session.add(ApplicantProfile(actor_id=applicant.id, synthetic_reference="SYN-RESTRICT"))
    session.commit()

    with pytest.raises(IntegrityError):
        session.delete(applicant)
        session.commit()


def test_programme_foreign_key_restricts_deleting_institution(session: Session) -> None:
    institution = Institution(
        institution_code="INST-RESTRICT",
        name="Synthetic University",
        institution_type="UA",
        region_code="MY-14",
        active=True,
    )
    session.add(institution)
    session.flush()
    session.add(
        Programme(
            institution_id=institution.id,
            programme_code="PROG-RESTRICT",
            name="Synthetic Computing",
            level="BACHELOR",
            active=True,
        )
    )
    session.commit()

    with pytest.raises(IntegrityError):
        session.delete(institution)
        session.commit()

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session

from app.database.enums import ActorType
from app.database.models import (
    Actor,
    ApplicantProfile,
    AuditEvent,
    CaseEvent,
    CaseStatusHistory,
    CaseSubmission,
    Document,
    DocumentVersion,
    ImmigrationCase,
    Institution,
    Programme,
)


@pytest.fixture
def session(test_database_url: str) -> Iterator[Session]:
    engine: Engine = create_engine(test_database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE actor, institution CASCADE"))
    database_session = Session(engine)
    try:
        yield database_session
    finally:
        database_session.rollback()
        database_session.close()
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE TABLE actor, institution CASCADE"))
        engine.dispose()


def _seed_applicant_context(
    session: Session,
    suffix: str,
) -> tuple[Actor, ApplicantProfile, Institution, Programme]:
    applicant = Actor(
        actor_type=ActorType.APPLICANT,
        display_name=f"Applicant {suffix}",
    )
    institution = Institution(
        institution_code=f"INST-{suffix}",
        name=f"Institution {suffix}",
        institution_type="IPTS",
        region_code="MY-10",
        active=True,
    )
    session.add_all([applicant, institution])
    session.flush()
    profile = ApplicantProfile(
        actor_id=applicant.id,
        synthetic_reference=f"SYN-{suffix}",
    )
    programme = Programme(
        institution_id=institution.id,
        programme_code=f"PROG-{suffix}",
        name=f"Programme {suffix}",
        level="BACHELOR",
        active=True,
    )
    session.add_all([profile, programme])
    session.commit()
    return applicant, profile, institution, programme


def _draft_payload(
    applicant_profile_id: UUID,
    institution_id: UUID,
    programme_id: UUID,
    *,
    case_number: str = "CASE-API-001",
) -> dict[str, str]:
    return {
        "case_number": case_number,
        "applicant_profile_id": str(applicant_profile_id),
        "application_type": "NEW",
        "institution_id": str(institution_id),
        "programme_id": str(programme_id),
        "institution_type": "IPTS",
        "region_code": "MY-10",
        "applicant_location": "OUTSIDE_MALAYSIA",
        "nationality_code": "CN",
        "passport_expires_at": datetime(2030, 1, 1, tzinfo=UTC).isoformat(),
    }


def _create_draft(
    client: TestClient,
    applicant: Actor,
    profile: ApplicantProfile,
    institution: Institution,
    programme: Programme,
    *,
    case_number: str,
) -> UUID:
    response = client.post(
        "/api/v1/applicant/cases",
        headers={"X-Actor-Id": str(applicant.id)},
        json=_draft_payload(
            profile.id,
            institution.id,
            programme.id,
            case_number=case_number,
        ),
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _seed_officer(session: Session, suffix: str) -> Actor:
    officer = Actor(
        actor_type=ActorType.OFFICER,
        display_name=f"Officer {suffix}",
    )
    session.add(officer)
    session.commit()
    return officer


def _submit_draft(client: TestClient, applicant: Actor, case_id: UUID) -> None:
    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/submit",
        headers={"X-Actor-Id": str(applicant.id)},
        json={"channel": "ONLINE_PORTAL"},
    )
    assert response.status_code == 201


def test_applicant_creates_student_pass_draft(client: TestClient, session: Session) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "DRAFT")

    response = client.post(
        "/api/v1/applicant/cases",
        headers={"X-Actor-Id": str(applicant.id)},
        json=_draft_payload(profile.id, institution.id, programme.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["case_number"] == "CASE-API-001"
    assert body["status"] == "DRAFT"
    assert body["stage"] == "PRE_SUBMISSION"
    assert body["applicant_profile_id"] == str(profile.id)


def test_applicant_records_document_metadata_for_owned_draft_case(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "DOCUMENT")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-DOCUMENT",
    )

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/documents",
        headers={"X-Actor-Id": str(applicant.id)},
        json={
            "document_type": "PASSPORT_BIODATA",
            "storage_reference": "metadata-only://case/passport-biodata-v1",
            "content_hash": "a" * 64,
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "captured_at": "2026-09-18T10:00:00Z",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["case_id"] == str(case_id)
    assert body["document_type"] == "PASSPORT_BIODATA"
    assert body["version_number"] == 1
    assert body["storage_reference"] == "metadata-only://case/passport-biodata-v1"
    assert session.scalar(select(func.count()).select_from(Document)) == 1
    assert session.scalar(select(func.count()).select_from(DocumentVersion)) == 1


def test_applicant_cannot_record_document_metadata_for_another_case(
    client: TestClient,
    session: Session,
) -> None:
    owner, profile, institution, programme = _seed_applicant_context(session, "DOCUMENT-OWNER")
    other, _other_profile, _other_institution, _other_programme = _seed_applicant_context(
        session,
        "DOCUMENT-OTHER",
    )
    case_id = _create_draft(
        client,
        owner,
        profile,
        institution,
        programme,
        case_number="CASE-API-DOCUMENT-OWNER",
    )

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/documents",
        headers={"X-Actor-Id": str(other.id)},
        json={
            "document_type": "PASSPORT_BIODATA",
            "storage_reference": "metadata-only://case/passport-biodata-v1",
            "content_hash": "b" * 64,
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "captured_at": "2026-09-18T10:00:00Z",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "actor does not own the case"}
    assert session.scalar(select(func.count()).select_from(Document)) == 0


def test_applicant_cannot_record_document_metadata_after_submission(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(
        session,
        "DOCUMENT-SUBMITTED",
    )
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-DOCUMENT-SUBMITTED",
    )
    _submit_draft(client, applicant, case_id)

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/documents",
        headers={"X-Actor-Id": str(applicant.id)},
        json={
            "document_type": "PASSPORT_BIODATA",
            "storage_reference": "metadata-only://case/passport-biodata-v1",
            "content_hash": "c" * 64,
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "captured_at": "2026-09-18T10:00:00Z",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "documents can only be recorded for a draft case"}
    assert session.scalar(select(func.count()).select_from(Document)) == 0


def test_applicant_submission_records_handover_and_moves_case_to_submitted(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "SUBMIT")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-SUBMIT",
    )

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/submit",
        headers={"X-Actor-Id": str(applicant.id)},
        json={"channel": "ONLINE_PORTAL"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["case_id"] == str(case_id)
    assert body["status"] == "SUBMITTED"
    assert body["submitted_at"] is not None
    assert body["accepted_at"] is None


def test_officer_lists_submitted_cases(client: TestClient, session: Session) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "QUEUE")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-QUEUE",
    )
    _submit_draft(client, applicant, case_id)
    officer = _seed_officer(session, "QUEUE")

    response = client.get(
        "/api/v1/officer/cases",
        headers={"X-Actor-Id": str(officer.id)},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(case_id)]
    assert response.json()[0]["status"] == "SUBMITTED"


def test_officer_starts_processing_and_records_transition_evidence(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "PROCESS")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-PROCESS",
    )
    _submit_draft(client, applicant, case_id)
    officer = _seed_officer(session, "PROCESS")

    response = client.post(
        f"/api/v1/officer/cases/{case_id}/start-processing",
        headers={"X-Actor-Id": str(officer.id)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROCESS"
    session.expire_all()
    case = session.get(ImmigrationCase, case_id)
    assert case is not None
    assert case.assigned_to_actor_id == officer.id
    assert (
        session.scalar(
            select(CaseStatusHistory.id).where(
                CaseStatusHistory.case_id == case_id,
                CaseStatusHistory.reason_code == "OFFICER_STARTED_PROCESSING",
            )
        )
        is not None
    )
    assert (
        session.scalar(
            select(CaseEvent.id).where(
                CaseEvent.case_id == case_id,
                CaseEvent.event_type == "CASE_PROCESSING_STARTED",
            )
        )
        is not None
    )
    assert (
        session.scalar(
            select(AuditEvent.id).where(
                AuditEvent.case_id == case_id,
                AuditEvent.action == "CASE_PROCESSING_STARTED",
            )
        )
        is not None
    )


def test_applicant_cannot_create_case_for_another_profile(
    client: TestClient,
    session: Session,
) -> None:
    applicant, _profile, institution, programme = _seed_applicant_context(session, "OWNER-A")
    _other, other_profile, _other_institution, _other_programme = _seed_applicant_context(
        session,
        "OWNER-B",
    )

    response = client.post(
        "/api/v1/applicant/cases",
        headers={"X-Actor-Id": str(applicant.id)},
        json=_draft_payload(
            other_profile.id,
            institution.id,
            programme.id,
            case_number="CASE-API-FOREIGN-PROFILE",
        ),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "actor does not own the applicant profile"}


def test_repeated_submission_returns_conflict_without_second_initial_submission(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "REPEAT")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-REPEAT",
    )
    _submit_draft(client, applicant, case_id)

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/submit",
        headers={"X-Actor-Id": str(applicant.id)},
        json={"channel": "ONLINE_PORTAL"},
    )

    assert response.status_code == 409
    assert (
        session.scalar(
            select(func.count())
            .select_from(CaseSubmission)
            .where(CaseSubmission.case_id == case_id)
        )
        == 1
    )


def test_applicant_cannot_access_officer_queue(client: TestClient, session: Session) -> None:
    applicant, _profile, _institution, _programme = _seed_applicant_context(session, "ROLE")

    response = client.get(
        "/api/v1/officer/cases",
        headers={"X-Actor-Id": str(applicant.id)},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "actor is not permitted for this action"}


def test_officer_cannot_start_processing_twice(client: TestClient, session: Session) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "TWICE")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-TWICE",
    )
    _submit_draft(client, applicant, case_id)
    officer = _seed_officer(session, "TWICE")
    first = client.post(
        f"/api/v1/officer/cases/{case_id}/start-processing",
        headers={"X-Actor-Id": str(officer.id)},
    )
    assert first.status_code == 200

    response = client.post(
        f"/api/v1/officer/cases/{case_id}/start-processing",
        headers={"X-Actor-Id": str(officer.id)},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "case is not in the required state"}

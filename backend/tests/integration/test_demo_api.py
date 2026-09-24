from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.enums import ActorType, CaseStage, CaseStatus, DocumentStatus, ServiceType
from app.database.models import (
    Actor,
    ApplicantProfile,
    Document,
    DocumentVersion,
    ImmigrationCase,
    StudentPassCaseProfile,
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


@pytest.fixture
def demo_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    yield client
    get_settings.cache_clear()


def test_demo_routes_are_hidden_when_demo_mode_is_disabled(client: TestClient) -> None:
    response = client.post("/api/v1/demo/session")

    assert response.status_code == 404


def test_demo_session_is_idempotent(demo_client: TestClient, session: Session) -> None:
    first = demo_client.post("/api/v1/demo/session")
    second = demo_client.post("/api/v1/demo/session")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["case_number"] == "IF-DEMO-STUDENT-PASS-001"
    assert session.scalar(select(func.count()).select_from(ImmigrationCase)) == 1


def _add_newer_non_demo_case_for_demo_applicant(
    session: Session,
    demo: dict[str, str],
) -> ImmigrationCase:
    demo_case = session.get(ImmigrationCase, demo["case_id"])
    assert demo_case is not None
    profile = session.scalar(
        select(ApplicantProfile).where(
            ApplicantProfile.actor_id == demo["applicant_actor_id"]
        )
    )
    assert profile is not None
    ordinary_case = ImmigrationCase(
        case_number="ORDINARY-CASE-BY-DEMO-ACTOR",
        applicant_profile_id=profile.id,
        service_type=ServiceType.STUDENT_PASS,
        status=CaseStatus.DRAFT,
        stage=CaseStage.PRE_SUBMISSION,
        created_by_actor_id=demo["applicant_actor_id"],
        created_at=demo_case.created_at + timedelta(seconds=1),
    )
    session.add(ordinary_case)
    session.flush()
    demo_profile = session.get(StudentPassCaseProfile, demo_case.id)
    assert demo_profile is not None
    session.add(
        StudentPassCaseProfile(
            case_id=ordinary_case.id,
            application_type=demo_profile.application_type,
            institution_id=demo_profile.institution_id,
            programme_id=demo_profile.programme_id,
            institution_type=demo_profile.institution_type,
            region_code=demo_profile.region_code,
            applicant_location=demo_profile.applicant_location,
            nationality_code=demo_profile.nationality_code,
            passport_expires_at=demo_profile.passport_expires_at,
        )
    )
    session.commit()
    return ordinary_case


def test_demo_session_ignores_non_demo_case_owned_by_demo_applicant(
    demo_client: TestClient,
    session: Session,
) -> None:
    original = demo_client.post("/api/v1/demo/session").json()
    ordinary_case = _add_newer_non_demo_case_for_demo_applicant(session, original)

    response = demo_client.post("/api/v1/demo/session")

    assert response.status_code == 200
    assert response.json()["case_id"] == original["case_id"]
    session.expire_all()
    reloaded = session.get(ImmigrationCase, ordinary_case.id)
    assert reloaded is not None
    assert reloaded.status == CaseStatus.DRAFT


def test_demo_reset_ignores_non_demo_case_owned_by_demo_applicant(
    demo_client: TestClient,
    session: Session,
) -> None:
    original = demo_client.post("/api/v1/demo/session").json()
    ordinary_case = _add_newer_non_demo_case_for_demo_applicant(session, original)

    response = demo_client.delete("/api/v1/demo/session")

    assert response.status_code == 200
    session.expire_all()
    demo_case = session.get(ImmigrationCase, original["case_id"])
    ordinary_case = session.get(ImmigrationCase, ordinary_case.id)
    assert demo_case is not None
    assert ordinary_case is not None
    assert demo_case.status == CaseStatus.WITHDRAWN
    assert ordinary_case.status == CaseStatus.DRAFT


def test_demo_session_seeds_metadata_only_core_documents(
    demo_client: TestClient,
    session: Session,
) -> None:
    response = demo_client.post("/api/v1/demo/session")

    assert response.status_code == 200
    case_id = response.json()["case_id"]
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.case_id == case_id)
            .order_by(Document.document_type)
        )
    )
    assert {document.document_type.value for document in documents} == {
        "ACADEMIC_RECORDS",
        "ENGLISH_EVIDENCE",
        "HEALTH_DECLARATION",
        "OFFER_LETTER",
        "PASSPORT_BIODATA",
        "PASSPORT_OBSERVATION_PAGES",
        "PASSPORT_VISA_PAGES",
        "PHOTO",
    }
    assert all(document.status is DocumentStatus.ACTIVE for document in documents)
    versions = list(session.scalars(select(DocumentVersion)))
    assert len(versions) == len(documents)
    assert all(
        version.storage_reference.startswith("metadata-only://demo/")
        for version in versions
    )
    assert all(version.size_bytes == 0 for version in versions)


def test_concurrent_demo_bootstrap_creates_one_scenario(
    demo_client: TestClient,
    session: Session,
) -> None:
    barrier = Barrier(2)

    def bootstrap() -> dict[str, str]:
        barrier.wait()
        response = demo_client.post("/api/v1/demo/session")
        assert response.status_code == 200
        return response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: bootstrap(), range(2)))

    assert responses[0] == responses[1]
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(ImmigrationCase)) == 1


def test_reset_preserves_non_demo_actor(
    demo_client: TestClient,
    session: Session,
) -> None:
    ordinary = Actor(
        actor_type=ActorType.SYSTEM,
        display_name="Ordinary system actor",
        external_reference="NOT-A-DEMO",
    )
    session.add(ordinary)
    session.commit()
    ordinary_id = ordinary.id
    original = demo_client.post("/api/v1/demo/session")
    assert original.status_code == 200

    response = demo_client.delete("/api/v1/demo/session")

    assert response.status_code == 200
    session.expire_all()
    assert session.get(Actor, ordinary_id) is not None
    old_case = session.get(ImmigrationCase, original.json()["case_id"])
    assert old_case is not None
    assert old_case.status == CaseStatus.WITHDRAWN

    assert response.json()["case_id"] != original.json()["case_id"]
    assert session.scalar(select(func.count()).select_from(ImmigrationCase)) == 2


def test_demo_reset_is_idempotent(demo_client: TestClient) -> None:
    first = demo_client.delete("/api/v1/demo/session")
    second = demo_client.delete("/api/v1/demo/session")
    assert first.status_code == second.status_code == 200
    assert first.json()["case_id"] != second.json()["case_id"]

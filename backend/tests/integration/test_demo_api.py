from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.enums import ActorType, CaseStatus
from app.database.models import Actor, ImmigrationCase


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

    assert response.status_code == 204
    session.expire_all()
    assert session.get(Actor, ordinary_id) is not None
    old_case = session.get(ImmigrationCase, original.json()["case_id"])
    assert old_case is not None
    assert old_case.status == CaseStatus.WITHDRAWN

    replacement = demo_client.post("/api/v1/demo/session")
    assert replacement.status_code == 200
    assert replacement.json()["case_id"] != original.json()["case_id"]
    assert session.scalar(select(func.count()).select_from(ImmigrationCase)) == 2


def test_demo_reset_is_idempotent(demo_client: TestClient) -> None:
    assert demo_client.delete("/api/v1/demo/session").status_code == 204
    assert demo_client.delete("/api/v1/demo/session").status_code == 204

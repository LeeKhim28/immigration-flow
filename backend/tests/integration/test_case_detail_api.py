from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.core.config import get_settings


@pytest.fixture
def clean_demo_database(test_database_url: str) -> Iterator[None]:
    engine: Engine = create_engine(test_database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE actor, institution CASCADE"))
    yield
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE actor, institution CASCADE"))
    engine.dispose()


@pytest.fixture
def demo(
    client: TestClient,
    clean_demo_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[dict[str, str]]:
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    response = client.post("/api/v1/demo/session")
    assert response.status_code == 200
    yield response.json()
    get_settings.cache_clear()


def applicant_headers(demo: dict[str, str]) -> dict[str, str]:
    return {"X-Actor-Id": demo["applicant_actor_id"]}


def officer_headers(demo: dict[str, str]) -> dict[str, str]:
    return {"X-Actor-Id": demo["officer_actor_id"]}


def test_applicant_detail_is_owned_and_synthetic(
    client: TestClient,
    demo: dict[str, str],
) -> None:
    response = client.get(
        f"/api/v1/applicant/cases/{demo['case_id']}",
        headers=applicant_headers(demo),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["synthetic"] is True
    assert body["institution"]["name"].endswith("(Synthetic)")
    assert body["programme"]["name"].endswith("(Synthetic)")
    assert body["nationality_code"] == "IDN"


def test_applicant_detail_rejects_another_actor(
    client: TestClient,
    demo: dict[str, str],
) -> None:
    response = client.get(
        f"/api/v1/applicant/cases/{demo['case_id']}",
        headers=officer_headers(demo),
    )

    assert response.status_code == 403


def test_applicant_timeline_is_chronological(
    client: TestClient,
    demo: dict[str, str],
) -> None:
    response = client.get(
        f"/api/v1/applicant/cases/{demo['case_id']}/timeline",
        headers=applicant_headers(demo),
    )

    assert response.status_code == 200
    events = response.json()["events"]
    event_types = [event["event_type"] for event in events]
    assert event_types[0] == "CASE_CREATED"
    assert event_types.count("DOCUMENT_METADATA_RECORDED") == 8
    assert events == sorted(events, key=lambda event: (event["occurred_at"], event["id"]))


def test_draft_case_has_a_valid_empty_evaluation_history(
    client: TestClient,
    demo: dict[str, str],
) -> None:
    response = client.get(
        f"/api/v1/applicant/cases/{demo['case_id']}/evaluation",
        headers=applicant_headers(demo),
    )

    assert response.status_code == 200
    assert response.json() == {"evaluations": []}


def test_officer_can_read_case_detail_but_applicant_cannot_use_officer_route(
    client: TestClient,
    demo: dict[str, str],
) -> None:
    path = f"/api/v1/officer/cases/{demo['case_id']}"

    officer_response = client.get(path, headers=officer_headers(demo))
    applicant_response = client.get(path, headers=applicant_headers(demo))

    assert officer_response.status_code == 200
    assert officer_response.json()["case_number"] == demo["case_number"]
    assert officer_response.json()["evaluations"] == []
    assert officer_response.json()["checklist"]["requirements"] == []
    event_types = [item["event_type"] for item in officer_response.json()["events"]]
    assert event_types[0] == "CASE_CREATED"
    assert event_types.count("DOCUMENT_METADATA_RECORDED") == 8
    assert applicant_response.status_code == 403

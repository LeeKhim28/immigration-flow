from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import create_app


def test_test_database_guard_rejects_development_database() -> None:
    from app.database.session import assert_test_database_url

    with pytest.raises(ValueError, match="_test"):
        assert_test_database_url(
            "postgresql+psycopg://immigration_flow:x@localhost/immigration_flow"
        )


def test_database_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_hides_connection_details_when_database_fails() -> None:
    from app.database.session import get_db_session

    class FailingSession:
        def execute(self, statement: Any) -> None:
            raise OperationalError(
                "SELECT 1",
                {},
                RuntimeError("postgresql+psycopg://secret:password@db/private"),
            )

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: FailingSession()

    response = TestClient(app).get("/health/database")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "postgresql" not in response.text
    assert "password" not in response.text


def test_database_session_rolls_back_and_closes_after_an_exception(
    monkeypatch: pytest.MonkeyPatch,
    test_database_url: str,
) -> None:
    from app.database import session as database_session

    class RecordingSession:
        rolled_back = False
        closed = False

        def rollback(self) -> None:
            self.rolled_back = True

        def close(self) -> None:
            self.closed = True

    recording_session = RecordingSession()
    monkeypatch.setattr(
        database_session,
        "_get_session_factory",
        lambda database_url: lambda: recording_session,
    )

    sessions: Iterator[RecordingSession] = database_session.get_db_session()
    assert next(sessions) is recording_session
    with pytest.raises(RuntimeError, match="request failed"):
        sessions.throw(RuntimeError("request failed"))

    assert recording_session.rolled_back
    assert recording_session.closed

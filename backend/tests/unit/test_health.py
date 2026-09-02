from fastapi.testclient import TestClient

from app.main import create_app


def test_process_health_does_not_require_database() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

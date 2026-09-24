from app.core.config import Settings


def test_settings_reject_an_empty_database_url() -> None:
    try:
        Settings(database_url="", app_env="test")
    except ValueError:
        return
    raise AssertionError("empty database_url must be rejected")


def test_demo_mode_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_MODE", raising=False)

    assert Settings(database_url="postgresql+psycopg://example/test").demo_mode is False


def test_demo_mode_accepts_an_explicit_true(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")

    assert Settings(database_url="postgresql+psycopg://example/test").demo_mode is True

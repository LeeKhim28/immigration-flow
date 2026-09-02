from app.core.config import Settings


def test_settings_reject_an_empty_database_url() -> None:
    try:
        Settings(database_url="", app_env="test")
    except ValueError:
        return
    raise AssertionError("empty database_url must be rejected")

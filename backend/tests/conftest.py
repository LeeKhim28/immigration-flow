import os
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.session import assert_test_database_url
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def build_alembic_config(database_url: str) -> Config:
    assert_test_database_url(database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@contextmanager
def _guarded_database_settings(database_url: str) -> Generator[None]:
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        yield
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()


def alembic_upgrade(revision: str) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    config = build_alembic_config(database_url)
    with _guarded_database_settings(database_url):
        command.upgrade(config, revision)


def alembic_downgrade(revision: str) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    config = build_alembic_config(database_url)
    with _guarded_database_settings(database_url):
        command.downgrade(config, revision)


def run_with_restoration(
    body: Callable[[], None],
    restore: Callable[[], None],
) -> None:
    body_error: Exception | None = None
    body_traceback: TracebackType | None = None
    try:
        body()
    except Exception as error:
        body_error = error
        body_traceback = error.__traceback__
    finally:
        try:
            restore()
        except Exception as restoration_error:
            if body_error is not None:
                raise body_error.with_traceback(body_traceback) from restoration_error
            raise

    if body_error is not None:
        raise body_error.with_traceback(body_traceback)


@pytest.fixture
def test_database_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert_test_database_url(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    yield database_url
    get_settings.cache_clear()


@pytest.fixture
def client(test_database_url: str) -> TestClient:
    return TestClient(create_app())

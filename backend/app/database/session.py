from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def assert_test_database_url(database_url: str) -> None:
    database = make_url(database_url).database or ""
    if not database.endswith("_test"):
        raise ValueError("test database name must end with _test")


def build_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@lru_cache
def _get_session_factory(database_url: str) -> sessionmaker[Session]:
    return build_session_factory(build_engine(database_url))


def get_db_session() -> Iterator[Session]:
    session = _get_session_factory(get_settings().database_url)()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

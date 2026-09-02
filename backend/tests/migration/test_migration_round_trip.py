from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import cast

import conftest
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.database.models import Base

EXPECTED_REVISIONS = (
    ("0004_events_audit_and_immutability", "0003_submissions_and_documents"),
    ("0003_submissions_and_documents", "0002_case_and_student_pass"),
    ("0002_case_and_student_pass", "0001_identity_and_reference"),
    ("0001_identity_and_reference", None),
)
EXPECTED_TABLES = {
    "actor",
    "applicant_profile",
    "institution",
    "programme",
    "case",
    "student_pass_case_profile",
    "case_status_history",
    "case_submission",
    "document",
    "document_version",
    "submission_document",
    "document_check",
    "case_event",
    "audit_event",
}
APPLICATION_SCHEMA = "public"
FunctionIdentity = tuple[str, str, str]
EXPECTED_FUNCTIONS = {
    (APPLICATION_SCHEMA, "enforce_same_case_submission_receipt", ""),
    (APPLICATION_SCHEMA, "enforce_student_pass_case_profile", ""),
    (APPLICATION_SCHEMA, "prevent_append_only_mutation", ""),
    (APPLICATION_SCHEMA, "prevent_confirmed_initial_mutation", ""),
}
EXPECTED_TRIGGERS = {
    (
        "enforce_same_case_submission_receipt",
        APPLICATION_SCHEMA,
        "case_submission",
        APPLICATION_SCHEMA,
        "enforce_same_case_submission_receipt",
        "",
    ),
    (
        "enforce_student_pass_profile_on_case",
        APPLICATION_SCHEMA,
        "case",
        APPLICATION_SCHEMA,
        "enforce_student_pass_case_profile",
        "",
    ),
    (
        "enforce_student_pass_profile_on_profile",
        APPLICATION_SCHEMA,
        "student_pass_case_profile",
        APPLICATION_SCHEMA,
        "enforce_student_pass_case_profile",
        "",
    ),
    (
        "prevent_audit_event_mutation",
        APPLICATION_SCHEMA,
        "audit_event",
        APPLICATION_SCHEMA,
        "prevent_append_only_mutation",
        "",
    ),
    (
        "prevent_case_event_mutation",
        APPLICATION_SCHEMA,
        "case_event",
        APPLICATION_SCHEMA,
        "prevent_append_only_mutation",
        "",
    ),
    (
        "prevent_case_status_history_mutation",
        APPLICATION_SCHEMA,
        "case_status_history",
        APPLICATION_SCHEMA,
        "prevent_append_only_mutation",
        "",
    ),
    (
        "prevent_confirmed_initial_mutation",
        APPLICATION_SCHEMA,
        "case_submission",
        APPLICATION_SCHEMA,
        "prevent_confirmed_initial_mutation",
        "",
    ),
    (
        "prevent_document_check_mutation",
        APPLICATION_SCHEMA,
        "document_check",
        APPLICATION_SCHEMA,
        "prevent_append_only_mutation",
        "",
    ),
    (
        "prevent_document_version_mutation",
        APPLICATION_SCHEMA,
        "document_version",
        APPLICATION_SCHEMA,
        "prevent_append_only_mutation",
        "",
    ),
}


def _migration_helper(name: str) -> Callable[[str], None]:
    helper = getattr(conftest, name, None)
    assert callable(helper), f"tests.conftest must provide {name}(revision: str)"
    return cast(Callable[[str], None], helper)


def _alembic_config(test_database_url: str) -> Config:
    helper = getattr(conftest, "build_alembic_config", None)
    assert callable(helper), "tests.conftest must provide build_alembic_config(database_url)"
    return cast(Callable[[str], Config], helper)(test_database_url)


def _restoration_runner() -> Callable[[Callable[[], None], Callable[[], None]], None]:
    helper = getattr(conftest, "run_with_restoration", None)
    assert callable(helper), "tests.conftest must provide run_with_restoration(body, restore)"
    return cast(Callable[[Callable[[], None], Callable[[], None]], None], helper)


def _normalize_function_identities(
    rows: Iterable[tuple[object, ...] | str],
) -> set[FunctionIdentity]:
    identities: set[FunctionIdentity] = set()
    for row in rows:
        if isinstance(row, str) or len(row) != 3:
            raise TypeError("function identity row must contain exactly three strings")
        schema, name, identity_arguments = row
        if (
            not isinstance(schema, str)
            or not isinstance(name, str)
            or not isinstance(identity_arguments, str)
        ):
            raise TypeError("function identity row must contain exactly three strings")
        identities.add((schema, name, identity_arguments))
    return identities


class _FunctionCatalogResult:
    def __init__(self, rows: list[FunctionIdentity]) -> None:
        self.rows = rows
        self.tuples_called = False

    def tuples(self) -> Iterator[FunctionIdentity]:
        self.tuples_called = True
        return iter(self.rows)

    def scalars(self) -> Iterator[str]:
        raise AssertionError("scalar consumption collapses function identity rows")


class _FunctionCatalogConnection:
    def __init__(self, result: _FunctionCatalogResult) -> None:
        self.result = result
        self.statement: object | None = None

    def execute(self, statement: object) -> _FunctionCatalogResult:
        self.statement = statement
        return self.result


class _FunctionCatalogEngine:
    def __init__(self, connection: _FunctionCatalogConnection) -> None:
        self.connection = connection
        self.disposed = False

    @contextmanager
    def connect(self) -> Iterator[_FunctionCatalogConnection]:
        yield self.connection

    def dispose(self) -> None:
        self.disposed = True


def _catalog_tables(test_database_url: str) -> set[str]:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            return set(
                connection.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = current_schema()
                          AND table_type = 'BASE TABLE'
                        """
                    )
                ).scalars()
            )
    finally:
        engine.dispose()


def _catalog_columns(test_database_url: str) -> set[tuple[str, str]]:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            return set(
                connection.execute(
                    text(
                        """
                        SELECT table_name, column_name
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name <> 'alembic_version'
                        """
                    )
                ).tuples()
            )
    finally:
        engine.dispose()


def _catalog_functions(test_database_url: str) -> set[tuple[str, str, str]]:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        ns.nspname,
                        proc.proname,
                        pg_catalog.pg_get_function_identity_arguments(proc.oid)
                    FROM pg_catalog.pg_proc AS proc
                    JOIN pg_catalog.pg_namespace AS ns
                      ON ns.oid = proc.pronamespace
                    WHERE ns.nspname = current_schema()
                      AND proc.prokind = 'f'
                    """
                )
            ).tuples()
            return _normalize_function_identities(rows)
    finally:
        engine.dispose()


def _catalog_triggers(
    test_database_url: str,
) -> set[tuple[str, str, str, str, str, str]]:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            return set(
                connection.execute(
                    text(
                        """
                        SELECT
                            trg.tgname,
                            target_ns.nspname,
                            target.relname,
                            proc_ns.nspname,
                            proc.proname,
                            pg_catalog.pg_get_function_identity_arguments(proc.oid)
                        FROM pg_catalog.pg_trigger AS trg
                        JOIN pg_catalog.pg_class AS target
                          ON target.oid = trg.tgrelid
                        JOIN pg_catalog.pg_namespace AS target_ns
                          ON target_ns.oid = target.relnamespace
                        JOIN pg_catalog.pg_proc AS proc
                          ON proc.oid = trg.tgfoid
                        JOIN pg_catalog.pg_namespace AS proc_ns
                          ON proc_ns.oid = proc.pronamespace
                        WHERE target_ns.nspname = current_schema()
                          AND NOT trg.tgisinternal
                        """
                    )
                ).tuples()
            )
    finally:
        engine.dispose()


def _alembic_version_width(test_database_url: str) -> int:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            width: object = connection.execute(
                text(
                    """
                    SELECT character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'alembic_version'
                      AND column_name = 'version_num'
                    """
                )
            ).scalar_one()
            if not isinstance(width, int):
                raise TypeError("alembic version column width must be an integer")
            return width
    finally:
        engine.dispose()


def _alembic_versions(test_database_url: str) -> set[str]:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            return set(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
            )
    finally:
        engine.dispose()


def _assert_revision_graph(test_database_url: str) -> None:
    script = ScriptDirectory.from_config(_alembic_config(test_database_url))
    revisions = tuple(
        (revision.revision, revision.down_revision)
        for revision in script.walk_revisions(base="base", head="heads")
    )

    assert script.get_heads() == [EXPECTED_REVISIONS[0][0]]
    assert revisions == EXPECTED_REVISIONS


def _assert_head_schema(test_database_url: str) -> None:
    assert _catalog_tables(test_database_url) == EXPECTED_TABLES | {"alembic_version"}
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert _catalog_columns(test_database_url) == {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
    }
    assert _catalog_functions(test_database_url) == EXPECTED_FUNCTIONS
    assert _catalog_triggers(test_database_url) == EXPECTED_TRIGGERS
    assert _alembic_version_width(test_database_url) == 64
    assert _alembic_versions(test_database_url) == {EXPECTED_REVISIONS[0][0]}


@pytest.mark.parametrize("helper_name", ["alembic_upgrade", "alembic_downgrade"])
def test_migration_helpers_reject_development_database(
    monkeypatch: pytest.MonkeyPatch,
    helper_name: str,
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://immigration_flow:local@localhost:5432/immigration_flow",
    )

    with pytest.raises(ValueError, match="must end with _test"):
        _migration_helper(helper_name)("head")


def test_restoration_runner_preserves_body_error_when_restoration_succeeds() -> None:
    events: list[str] = []
    body_error = RuntimeError("body failed")

    def raise_body_error() -> None:
        events.append("body")
        raise body_error

    def restore() -> None:
        events.append("restore")

    with pytest.raises(RuntimeError) as exc_info:
        _restoration_runner()(raise_body_error, restore)

    traceback_names = []
    traceback = exc_info.value.__traceback__
    while traceback is not None:
        traceback_names.append(traceback.tb_frame.f_code.co_name)
        traceback = traceback.tb_next

    assert exc_info.value is body_error
    assert exc_info.value.__cause__ is None
    assert "raise_body_error" in traceback_names
    assert events == ["body", "restore"]


def test_restoration_runner_propagates_restoration_error_when_body_succeeds() -> None:
    events: list[str] = []
    restoration_error = RuntimeError("restoration failed")

    def body() -> None:
        events.append("body")

    def raise_restoration_error() -> None:
        events.append("restore")
        raise restoration_error

    with pytest.raises(RuntimeError) as exc_info:
        _restoration_runner()(body, raise_restoration_error)

    assert exc_info.value is restoration_error
    assert events == ["body", "restore"]


def test_restoration_runner_keeps_body_error_primary_when_both_fail() -> None:
    events: list[str] = []
    body_error = RuntimeError("body failed")
    restoration_error = RuntimeError("restoration failed")

    def raise_body_error() -> None:
        events.append("body")
        raise body_error

    def raise_restoration_error() -> None:
        events.append("restore")
        raise restoration_error

    with pytest.raises(RuntimeError) as exc_info:
        _restoration_runner()(raise_body_error, raise_restoration_error)

    assert exc_info.value is body_error
    assert exc_info.value.__cause__ is restoration_error
    assert events == ["body", "restore"]


def test_function_identity_rows_reject_collapsed_scalar_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = [
        ("public", "same_name", ""),
        ("public", "same_name", "integer"),
    ]
    result = _FunctionCatalogResult(identities)
    connection = _FunctionCatalogConnection(result)
    engine = _FunctionCatalogEngine(connection)

    def create_fake_engine(database_url: str) -> _FunctionCatalogEngine:
        assert database_url.endswith("/immigration_flow_test")
        return engine

    monkeypatch.setitem(globals(), "create_engine", create_fake_engine)

    assert _catalog_functions(
        "postgresql+psycopg://test:test@localhost:5433/immigration_flow_test"
    ) == set(identities)
    assert result.tuples_called
    assert connection.statement is not None
    assert engine.disposed


def test_migrations_round_trip_and_restore_schema(test_database_url: str) -> None:
    alembic_upgrade = _migration_helper("alembic_upgrade")
    alembic_downgrade = _migration_helper("alembic_downgrade")

    def round_trip() -> None:
        _assert_revision_graph(test_database_url)
        alembic_downgrade("base")
        alembic_upgrade("head")
        _assert_head_schema(test_database_url)

        alembic_downgrade("base")
        assert _catalog_tables(test_database_url) == {"alembic_version"}
        assert _catalog_functions(test_database_url) == set()
        assert _catalog_triggers(test_database_url) == set()
        assert _alembic_version_width(test_database_url) == 64
        assert _alembic_versions(test_database_url) == set()

        alembic_upgrade("head")
        _assert_head_schema(test_database_url)

    _restoration_runner()(round_trip, lambda: alembic_upgrade("head"))

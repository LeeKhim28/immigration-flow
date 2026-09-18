from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.database.enums import (
    KnowledgeSourceStatus,
    KnowledgeSyncStatus,
    RequirementSupportType,
    ServiceType,
)
from app.database.models import (
    KnowledgeSource,
    KnowledgeSyncRun,
    Requirement,
    RequirementSource,
    RequirementVersion,
    SourceRevision,
)

NOW = datetime(2026, 9, 17, tzinfo=UTC)


@pytest.fixture
def session(test_database_url: str) -> Iterator[Session]:
    engine: Engine = create_engine(test_database_url)
    tables = (
        "requirement_source, requirement_version, requirement, source_revision, "
        "knowledge_source, knowledge_sync_run CASCADE"
    )
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {tables}"))
    database_session = Session(engine)
    try:
        yield database_session
    finally:
        database_session.rollback()
        database_session.close()
        with engine.begin() as connection:
            connection.execute(text(f"TRUNCATE TABLE {tables}"))
        engine.dispose()


def _run() -> KnowledgeSyncRun:
    return KnowledgeSyncRun(
        git_commit_sha="a" * 40,
        status=KnowledgeSyncStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW,
        validation_summary={"synthetic": True},
    )


def _source() -> KnowledgeSource:
    return KnowledgeSource(
        source_code="MY-TEST-SOURCE",
        canonical_url="https://official.example/policy",
        title="Synthetic official policy",
        authority="Synthetic authority",
        jurisdiction="Malaysia",
        language="en",
        topics=["student_pass"],
        source_type="official_guidance",
        status=KnowledgeSourceStatus.REVIEWED,
    )


def _requirement() -> Requirement:
    return Requirement(
        requirement_code="SPV1-REQ-TEST",
        service_type=ServiceType.STUDENT_PASS,
        category="document",
    )


def _seed_complete_version(session: Session) -> tuple[SourceRevision, RequirementVersion]:
    run, source, requirement = _run(), _source(), _requirement()
    session.add_all([run, source, requirement])
    session.flush()
    revision = SourceRevision(
        knowledge_source_id=source.id,
        retrieved_at=NOW,
        reviewed_at=NOW,
        normalized_content_hash="b" * 64,
        repository_snapshot_reference="data/official-sources/reviews/synthetic.md",
        git_commit_sha="a" * 40,
        knowledge_sync_run_id=run.id,
    )
    version = RequirementVersion(
        requirement_id=requirement.id,
        version_number=1,
        stage="pre_submission",
        responsible_actor="applicant",
        level="required",
        statement="Provide a synthetic document.",
        condition_document={"always": True},
        machine_handling="Check presence only.",
        fingerprint="c" * 64,
        git_commit_sha="a" * 40,
        knowledge_sync_run_id=run.id,
    )
    session.add_all([revision, version])
    session.flush()
    session.add(
        RequirementSource(
            requirement_version_id=version.id,
            source_revision_id=revision.id,
            locator="Synthetic section 1",
            support_type=RequirementSupportType.PRIMARY,
        )
    )
    session.commit()
    return revision, version


def test_valid_requirement_version_with_source_provenance_commits(session: Session) -> None:
    _, version = _seed_complete_version(session)
    assert version.id is not None


@pytest.mark.parametrize("model_factory, field", [(_source, "status"), (_run, "status")])
def test_knowledge_enums_reject_unknown_persisted_values(
    session: Session, model_factory: object, field: str
) -> None:
    record = model_factory()  # type: ignore[operator]
    setattr(record, field, "UNKNOWN")
    session.add(record)
    with pytest.raises(IntegrityError):
        session.flush()


def test_requirement_source_rejects_unknown_support_type(session: Session) -> None:
    revision, version = _seed_complete_version(session)
    with (
        session.bind.begin() as connection,  # type: ignore[union-attr]
        pytest.raises(IntegrityError),
    ):
        connection.execute(
            text(
                "INSERT INTO requirement_source "
                "(requirement_version_id, source_revision_id, locator, support_type) "
                "VALUES (:version_id, :revision_id, 'Unknown support', 'UNKNOWN')"
            ),
            {"version_id": version.id, "revision_id": revision.id},
        )


def test_source_code_url_and_successful_sync_sha_are_unique(session: Session) -> None:
    session.add_all([_source(), _run()])
    session.flush()
    session.add(_source())
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
    session.add_all([_run(), _run()])
    with pytest.raises(IntegrityError):
        session.flush()


def test_requirement_version_rejects_invalid_version_or_duplicate_fingerprint(
    session: Session,
) -> None:
    _, version = _seed_complete_version(session)
    sql = text(
        "INSERT INTO requirement_version "
        "(requirement_id, version_number, stage, responsible_actor, level, statement, "
        "condition_document, machine_handling, fingerprint, git_commit_sha, knowledge_sync_run_id) "
        "VALUES (:requirement_id, :version_number, 'pre_submission', 'applicant', 'required', "
        "'Invalid', CAST(:condition_document AS jsonb), 'manual', :fingerprint, :git_sha, :run_id)"
    )
    with (
        session.bind.begin() as connection,  # type: ignore[union-attr]
        pytest.raises(IntegrityError),
    ):
        connection.execute(
            sql,
            {
                "requirement_id": version.requirement_id,
                "version_number": 0,
                "condition_document": '{"always": true}',
                "fingerprint": "d" * 64,
                "git_sha": "a" * 40,
                "run_id": version.knowledge_sync_run_id,
            },
        )
    with (
        session.bind.begin() as connection,  # type: ignore[union-attr]
        pytest.raises(IntegrityError),
    ):
        connection.execute(
            sql,
            {
                "requirement_id": version.requirement_id,
                "version_number": 2,
                "condition_document": '{"always": true}',
                "fingerprint": version.fingerprint,
                "git_sha": "a" * 40,
                "run_id": version.knowledge_sync_run_id,
            },
        )


def test_requirement_version_requires_source_provenance_at_commit(session: Session) -> None:
    run, requirement = _run(), _requirement()
    session.add_all([run, requirement])
    session.flush()
    session.add(
        RequirementVersion(
            requirement_id=requirement.id,
            version_number=1,
            stage="pre_submission",
            responsible_actor="applicant",
            level="required",
            statement="Source-less requirement.",
            condition_document={"always": True},
            machine_handling="Never valid.",
            fingerprint="d" * 64,
            git_commit_sha="a" * 40,
            knowledge_sync_run_id=run.id,
        )
    )
    with pytest.raises(IntegrityError, match="source provenance"):
        session.commit()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE source_revision SET retrieved_at = retrieved_at",
        "DELETE FROM source_revision",
        "UPDATE requirement_version SET statement = 'nope'",
        "DELETE FROM requirement_version",
        "UPDATE requirement_source SET locator = 'nope'",
        "DELETE FROM requirement_source",
    ],
)
def test_knowledge_history_is_append_only(session: Session, statement: str) -> None:
    _seed_complete_version(session)
    with (
        session.bind.begin() as connection,  # type: ignore[union-attr]
        pytest.raises(DBAPIError, match="append-only"),
    ):
        connection.execute(text(statement))


def test_knowledge_history_foreign_keys_are_restrictive(session: Session) -> None:
    revision, version = _seed_complete_version(session)
    with (
        session.bind.begin() as connection,  # type: ignore[union-attr]
        pytest.raises(IntegrityError),
    ):
        connection.execute(
            text("DELETE FROM knowledge_source WHERE id = :source_id"),
            {"source_id": revision.knowledge_source_id},
        )
    with (
        session.bind.begin() as connection,  # type: ignore[union-attr]
        pytest.raises(IntegrityError),
    ):
        connection.execute(
            text("DELETE FROM requirement WHERE id = :requirement_id"),
            {"requirement_id": version.requirement_id},
        )

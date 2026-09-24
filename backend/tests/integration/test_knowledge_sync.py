from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session

from app.database.enums import KnowledgeSyncStatus
from app.database.models import RuleSetVersion, SourceRevision
from app.knowledge.repository import KnowledgeBundle
from app.knowledge.sync import KnowledgeSynchronizer


def test_sync_interface_is_available() -> None:
    assert hasattr(KnowledgeSynchronizer, "sync")


def test_sync_rejects_missing_repository() -> None:
    with pytest.raises(ValueError, match="repository"):
        KnowledgeSynchronizer().sync(Path("/does/not/exist"), "a" * 40)


@pytest.fixture
def clean_sync_database(test_database_url: str) -> Iterator[Session]:
    engine: Engine = create_engine(test_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE approval_event, rule_requirement, rule_version, "
                "rule_definition, rule_set_version, rule_set, requirement_source, "
                "requirement_version, requirement, source_revision, knowledge_source, "
                "knowledge_sync_run CASCADE"
            )
        )
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def _bundle(sha: str) -> KnowledgeBundle:
    return KnowledgeBundle(
        git_commit_sha=sha,
        registry={
            "sources": [
                {
                    "id": "SRC-1",
                    "canonical_url": "https://official.example/source",
                    "title": "Synthetic source",
                    "authority": "Synthetic authority",
                    "jurisdiction": "Malaysia",
                    "language": "en",
                    "topics": ["student_pass"],
                    "source_type": "official_guidance",
                    "retrieved_at": "2026-09-18",
                    "reviewed_at": "2026-09-18",
                    "status": "reviewed",
                }
            ]
        },
        requirements={
            "version": "1.0.0",
            "requirements": [
                {
                    "id": "REQ-1",
                    "category": "document",
                    "stage": "pre_submission",
                    "actor": "applicant",
                    "level": "required",
                    "statement": "Provide a synthetic document.",
                    "condition": "always",
                    "machine_handling": "Check presence.",
                    "sources": [{"source_id": "SRC-1", "locator": "section 1"}],
                }
            ],
        },
        rule_set={
            "rule_set_id": "student-pass-v1",
            "version": "1.0.0",
            "effective_from": "2026-09-18",
            "scope": {"application_type": "new"},
            "outcome_contract": ["pass", "manual_review"],
            "default_outcome": "pass",
            "rules": [
                {
                    "id": "RULE-1",
                    "priority": 10,
                    "description": "Synthetic rule",
                    "when": {"fact": "document.present"},
                    "then": {
                        "outcome": "manual_review",
                        "code": "SYNTHETIC",
                        "message": "Review document.",
                        "create_task": "review_document",
                    },
                    "requirement_ids": ["REQ-1"],
                    "source_ids": ["SRC-1"],
                }
            ],
        },
        datasets=(),
    )


def test_sync_imports_once_and_reuses_successful_commit(
    monkeypatch: pytest.MonkeyPatch,
    clean_sync_database: Session,
    tmp_path: Path,
) -> None:
    sha = "a" * 40
    root = tmp_path
    (root / ".git").write_text("synthetic", encoding="utf-8")
    bundle = _bundle(sha)
    monkeypatch.setattr("app.knowledge.sync.load_knowledge_bundle", lambda *_: bundle)

    def factory() -> Session:
        return Session(clean_sync_database.bind)  # type: ignore[arg-type]

    first = KnowledgeSynchronizer(factory).sync(root, sha)
    second = KnowledgeSynchronizer(factory).sync(root, sha)
    assert first.status is KnowledgeSyncStatus.SUCCEEDED
    assert first.source_count == 1
    assert second.reused is True
    release = clean_sync_database.scalar(select(RuleSetVersion))
    assert release is not None
    assert release.submission_cutoff_at == datetime(2026, 9, 18, tzinfo=UTC)


def test_sync_reuses_identical_source_revision_across_code_only_commits(
    monkeypatch: pytest.MonkeyPatch,
    clean_sync_database: Session,
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").write_text("synthetic", encoding="utf-8")
    current_sha = "a" * 40
    monkeypatch.setattr(
        "app.knowledge.sync.load_knowledge_bundle", lambda *_: _bundle(current_sha)
    )

    def factory() -> Session:
        return Session(clean_sync_database.bind)  # type: ignore[arg-type]

    KnowledgeSynchronizer(factory).sync(tmp_path, current_sha)
    current_sha = "b" * 40
    second = KnowledgeSynchronizer(factory).sync(tmp_path, current_sha)

    assert second.status is KnowledgeSyncStatus.SUCCEEDED
    assert clean_sync_database.scalar(
        select(func.count()).select_from(SourceRevision)
    ) == 1

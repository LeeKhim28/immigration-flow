from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.database.enums import (
    ActorType,
    ApplicabilityBasis,
    ApprovalDecision,
    KnowledgeSourceStatus,
    KnowledgeSyncStatus,
    RequirementSupportType,
    RuleSetVersionStatus,
    ServiceType,
)
from app.database.models import (
    Actor,
    ApprovalEvent,
    KnowledgeSource,
    KnowledgeSyncRun,
    Requirement,
    RequirementSource,
    RequirementVersion,
    RuleDefinition,
    RuleRequirement,
    RuleSet,
    RuleSetVersion,
    RuleVersion,
    SourceRevision,
)

NOW = datetime(2026, 9, 18, tzinfo=UTC)


@pytest.fixture
def session(test_database_url: str) -> Iterator[Session]:
    engine: Engine = create_engine(test_database_url)
    tables = (
        "approval_event, rule_requirement, rule_version, rule_definition, "
        "rule_set_version, rule_set, requirement_source, requirement_version, "
        "requirement, source_revision, knowledge_source, knowledge_sync_run, "
        "audit_event, actor CASCADE"
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


def _seed_requirement(session: Session) -> tuple[KnowledgeSyncRun, RequirementVersion]:
    run = KnowledgeSyncRun(
        git_commit_sha="a" * 40,
        status=KnowledgeSyncStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW,
    )
    source = KnowledgeSource(
        source_code="MY-RULE-SOURCE",
        canonical_url="https://official.example/rules",
        title="Synthetic source",
        authority="Synthetic authority",
        jurisdiction="Malaysia",
        language="en",
        topics=["student_pass"],
        source_type="official_guidance",
        status=KnowledgeSourceStatus.REVIEWED,
    )
    requirement = Requirement(
        requirement_code="SPV1-REQ-RULE",
        service_type=ServiceType.STUDENT_PASS,
        category="document",
    )
    session.add_all([run, source, requirement])
    session.flush()
    revision = SourceRevision(
        knowledge_source_id=source.id,
        retrieved_at=NOW,
        reviewed_at=NOW,
        normalized_content_hash="b" * 64,
        repository_snapshot_reference="data/official-sources/synthetic.md",
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
        machine_handling="Check presence.",
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
            locator="Synthetic section",
            support_type=RequirementSupportType.PRIMARY,
        )
    )
    session.flush()
    return run, version


def _governed_rows(session: Session) -> tuple[RuleSetVersion, RuleVersion, RuleRequirement]:
    run, requirement_version = _seed_requirement(session)
    rule_set = RuleSet(
        rule_set_code="STUDENT-PASS-V1",
        service_type=ServiceType.STUDENT_PASS,
        name="Student Pass V1",
    )
    session.add(rule_set)
    session.flush()
    release = RuleSetVersion(
        rule_set_id=rule_set.id,
        semantic_version="1.0.0",
        scope_document={"application_type": "NEW"},
        outcome_contract=["pass", "manual_review", "action_required"],
        default_outcome="manual_review",
        dataset_snapshots={"official": ["MY-RULE-SOURCE"]},
        published_at=NOW,
        effective_at=NOW,
        applicability_basis=ApplicabilityBasis.IMMIGRATION_SUBMISSION_DATE,
        submission_cutoff_at=NOW,
        transition_policy={"re_evaluate_after_effective": True},
        status=RuleSetVersionStatus.REVIEW,
        knowledge_sync_run_id=run.id,
        fingerprint="d" * 64,
        git_commit_sha="a" * 40,
    )
    definition = RuleDefinition(rule_code="SPV1-RULE-001", name="Synthetic rule")
    session.add_all([release, definition])
    session.flush()
    rule = RuleVersion(
        rule_definition_id=definition.id,
        rule_set_version_id=release.id,
        description="Synthetic rule",
        priority=10,
        condition_document={"fact": "document_present"},
        outcome="manual_review",
        finding_code="SYNTHETIC",
        message="Review synthetic evidence.",
        task_type="verify",
        supplemental_source_codes=["MY-RULE-SOURCE"],
        fingerprint="e" * 64,
        git_commit_sha="a" * 40,
        knowledge_sync_run_id=run.id,
    )
    session.add(rule)
    session.flush()
    link = RuleRequirement(rule_version_id=rule.id, requirement_version_id=requirement_version.id)
    session.add(link)
    session.commit()
    return release, rule, link


def test_complete_rule_release_commits(session: Session) -> None:
    release, rule, link = _governed_rows(session)
    assert release.id and rule.id and link.rule_version_id == rule.id


def test_rule_version_requires_requirement_provenance(session: Session) -> None:
    release, _, _ = _governed_rows(session)
    definition = RuleDefinition(rule_code="SPV1-RULE-002", name="Orphan rule")
    session.add(definition)
    session.flush()
    session.add(
        RuleVersion(
            rule_definition_id=definition.id,
            rule_set_version_id=release.id,
            description="Orphan",
            priority=1,
            condition_document={"always": True},
            outcome="manual_review",
            finding_code="ORPHAN",
            message="Orphan",
            supplemental_source_codes=[],
            fingerprint="f" * 64,
            git_commit_sha="a" * 40,
            knowledge_sync_run_id=release.knowledge_sync_run_id,
        )
    )
    with pytest.raises(ProgrammingError, match="requirement provenance"):
        session.commit()


def test_rule_history_is_append_only(session: Session) -> None:
    _, rule, link = _governed_rows(session)
    with (
        session.bind.begin() as connection,  # type: ignore[union-attr]
        pytest.raises(DBAPIError, match="append-only"),
    ):
        connection.execute(  # type: ignore[union-attr]
            text("UPDATE rule_version SET message = 'changed' WHERE id = :id"), {"id": rule.id}
        )
    with (
        session.bind.begin() as connection,  # type: ignore[union-attr]
        pytest.raises(DBAPIError, match="append-only"),
    ):
        connection.execute(  # type: ignore[union-attr]
            text("DELETE FROM rule_requirement WHERE rule_version_id = :id"),
            {"id": link.rule_version_id},
        )


def test_approval_requires_administrator_actor(session: Session) -> None:
    release, _, _ = _governed_rows(session)
    applicant = Actor(
        actor_type=ActorType.APPLICANT, display_name="Applicant", external_reference="APP-1"
    )
    session.add(applicant)
    session.flush()
    session.add(
        ApprovalEvent(
            rule_set_version_id=release.id,
            decision=ApprovalDecision.APPROVED,
            decided_by_actor_id=applicant.id,
            decided_at=NOW,
            notes="not allowed",
        )
    )
    with pytest.raises(ProgrammingError, match="administrator"):
        session.commit()


def test_audit_event_allows_governance_entity_without_case(session: Session) -> None:
    release, _, _ = _governed_rows(session)
    session.execute(
        text(
            "INSERT INTO audit_event (case_id, actor_id, action, entity_type, entity_id, "
            "occurred_at) "
            "VALUES (NULL, NULL, 'RULE_REVIEWED', 'RULE_SET_VERSION', :id, :occurred_at)"
        ),
        {"id": release.id, "occurred_at": NOW},
    )
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO audit_event (case_id, actor_id, action, entity_type, entity_id, "
                "occurred_at) "
                "VALUES (NULL, NULL, 'CASE_UPDATE', 'CASE', :id, :occurred_at)"
            ),
            {"id": release.id, "occurred_at": NOW},
        )

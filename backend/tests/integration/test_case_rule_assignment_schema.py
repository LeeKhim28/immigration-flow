from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.database.enums import (
    ActorType,
    ApplicabilityBasis,
    KnowledgeSourceStatus,
    KnowledgeSyncStatus,
    RequirementSupportType,
    RuleSetVersionStatus,
    ServiceType,
)
from app.database.models import (
    Actor,
    ApplicantProfile,
    CaseRequirement,
    CaseRuleAssignment,
    EvaluationFinding,
    ImmigrationCase,
    Institution,
    KnowledgeSource,
    KnowledgeSyncRun,
    Programme,
    Requirement,
    RequirementSource,
    RequirementVersion,
    RuleDefinition,
    RuleEvaluation,
    RuleRequirement,
    RuleSet,
    RuleSetVersion,
    RuleVersion,
    SourceRevision,
    StudentPassCaseProfile,
)

NOW = datetime(2026, 9, 18, tzinfo=UTC)


@pytest.fixture
def session(test_database_url: str) -> Iterator[Session]:
    engine: Engine = create_engine(test_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE actor, institution, knowledge_sync_run, "
                "knowledge_source, requirement, rule_set, rule_definition CASCADE"
            )
        )
    database_session = Session(engine)
    try:
        yield database_session
    finally:
        database_session.rollback()
        database_session.close()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE TABLE actor, institution, knowledge_sync_run, "
                    "knowledge_source, requirement, rule_set, rule_definition CASCADE"
                )
            )
        engine.dispose()


def _seed_assignment(session: Session) -> tuple[CaseRuleAssignment, CaseRequirement]:
    applicant = Actor(actor_type=ActorType.APPLICANT, display_name="Checklist applicant")
    institution = Institution(
        institution_code="CHECKLIST-INST",
        name="Checklist institution",
        institution_type="IPTS",
        region_code="MY-10",
        active=True,
    )
    session.add_all([applicant, institution])
    session.flush()
    profile = ApplicantProfile(actor_id=applicant.id, synthetic_reference="CHECKLIST-APPLICANT")
    programme = Programme(
        institution_id=institution.id,
        programme_code="CHECKLIST-PROG",
        name="Checklist programme",
        level="BACHELOR",
        active=True,
    )
    session.add_all([profile, programme])
    session.flush()
    case = ImmigrationCase(
        case_number="CASE-CHECKLIST-SCHEMA",
        applicant_profile_id=profile.id,
        service_type=ServiceType.STUDENT_PASS,
        status="DRAFT",
        stage="PRE_SUBMISSION",
        created_by_actor_id=applicant.id,
    )
    run = KnowledgeSyncRun(
        git_commit_sha="a" * 40,
        status=KnowledgeSyncStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW,
    )
    source = KnowledgeSource(
        source_code="CHECKLIST-SOURCE",
        canonical_url="https://official.example/checklist",
        title="Checklist source",
        authority="Synthetic authority",
        jurisdiction="Malaysia",
        language="en",
        topics=["student_pass"],
        source_type="official_guidance",
        status=KnowledgeSourceStatus.REVIEWED,
    )
    requirement = Requirement(
        requirement_code="SPV1-REQ-CHECKLIST",
        service_type=ServiceType.STUDENT_PASS,
        category="document",
    )
    rule_set = RuleSet(
        rule_set_code="STUDENT-PASS-CHECKLIST",
        service_type=ServiceType.STUDENT_PASS,
        name="Student Pass checklist",
    )
    session.add_all([case, run, source, requirement, rule_set])
    session.flush()
    session.add(
        StudentPassCaseProfile(
            case_id=case.id,
            application_type="NEW",
            institution_id=institution.id,
            programme_id=programme.id,
            institution_type="IPTS",
            region_code="MY-10",
            applicant_location="OUTSIDE_MALAYSIA",
            nationality_code="CN",
            passport_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
    )
    source_revision = SourceRevision(
        knowledge_source_id=source.id,
        retrieved_at=NOW,
        reviewed_at=NOW,
        normalized_content_hash="b" * 64,
        repository_snapshot_reference="synthetic",
        git_commit_sha="a" * 40,
        knowledge_sync_run_id=run.id,
    )
    requirement_version = RequirementVersion(
        requirement_id=requirement.id,
        version_number=1,
        stage="pre_submission",
        responsible_actor="applicant",
        level="required",
        statement="Provide the synthetic checklist document.",
        condition_document={"always": True},
        machine_handling="Check presence.",
        fingerprint="c" * 64,
        git_commit_sha="a" * 40,
        knowledge_sync_run_id=run.id,
    )
    release = RuleSetVersion(
        rule_set_id=rule_set.id,
        semantic_version="1.0.0",
        scope_document={"application_type": "NEW"},
        outcome_contract=["pass", "manual_review", "action_required"],
        default_outcome="manual_review",
        dataset_snapshots={},
        effective_at=NOW,
        applicability_basis=ApplicabilityBasis.IMMIGRATION_SUBMISSION_DATE,
        submission_cutoff_at=NOW,
        transition_policy={"re_evaluate_after_effective": True},
        status=RuleSetVersionStatus.REVIEW,
        knowledge_sync_run_id=run.id,
        fingerprint="d" * 64,
        git_commit_sha="a" * 40,
    )
    definition = RuleDefinition(rule_code="CHECKLIST-RULE", name="Checklist rule")
    session.add_all([source_revision, requirement_version, release, definition])
    session.flush()
    rule = RuleVersion(
        rule_definition_id=definition.id,
        rule_set_version_id=release.id,
        description="Checklist rule",
        priority=1,
        condition_document={"always": True},
        outcome="manual_review",
        finding_code="CHECKLIST",
        message="Check checklist evidence.",
        task_type="verify",
        supplemental_source_codes=[],
        fingerprint="e" * 64,
        git_commit_sha="a" * 40,
        knowledge_sync_run_id=run.id,
    )
    session.add_all(
        [
            rule,
            RequirementSource(
                requirement_version_id=requirement_version.id,
                source_revision_id=source_revision.id,
                locator="Synthetic section",
                support_type=RequirementSupportType.PRIMARY,
            ),
        ]
    )
    session.flush()
    session.add(
        RuleRequirement(rule_version_id=rule.id, requirement_version_id=requirement_version.id)
    )
    session.flush()
    assignment = CaseRuleAssignment(
        case_id=case.id,
        rule_set_version_id=release.id,
        assignment_reason="INITIAL_SUBMISSION",
        assigned_at=NOW,
        assigned_by_actor_id=applicant.id,
    )
    session.add(assignment)
    session.flush()
    checklist = CaseRequirement(
        case_id=case.id,
        requirement_version_id=requirement_version.id,
        status="PENDING",
    )
    session.add(checklist)
    session.commit()
    return assignment, checklist


def test_assignment_and_checklist_history_are_immutable(session: Session) -> None:
    assignment, checklist = _seed_assignment(session)

    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(
            text("DELETE FROM case_rule_assignment WHERE id = :id"),
            {"id": assignment.id},
        )
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(
            text("DELETE FROM case_requirement WHERE id = :id"),
            {"id": checklist.id},
        )
        session.commit()


def test_evaluation_and_finding_history_are_immutable(session: Session) -> None:
    assignment, _ = _seed_assignment(session)
    rule = session.scalar(
        select(RuleVersion).where(RuleVersion.rule_set_version_id == assignment.rule_set_version_id)
    )
    assert rule is not None
    evaluation = RuleEvaluation(
        case_id=assignment.case_id,
        rule_set_version_id=assignment.rule_set_version_id,
        trigger="INITIAL_SUBMISSION",
        input_snapshot={"synthetic": True},
        outcome="manual_review",
        evaluated_at=NOW,
        engine_version="v1",
    )
    session.add(evaluation)
    session.flush()
    finding = EvaluationFinding(
        rule_evaluation_id=evaluation.id,
        rule_version_id=rule.id,
        outcome="manual_review",
        code="SYNTHETIC",
        message="Review synthetic evidence.",
        details={"synthetic": True},
    )
    session.add(finding)
    session.commit()

    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(
            text("UPDATE rule_evaluation SET outcome = 'pass' WHERE id = :id"),
            {"id": evaluation.id},
        )
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(
            text("DELETE FROM evaluation_finding WHERE id = :id"),
            {"id": finding.id},
        )
        session.commit()

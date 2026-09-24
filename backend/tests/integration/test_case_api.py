from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select, text
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
    ApplicantProfile,
    ApprovalEvent,
    AuditEvent,
    CaseEvent,
    CaseRequirement,
    CaseRuleAssignment,
    CaseStatusHistory,
    CaseSubmission,
    Document,
    DocumentVersion,
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
)
from app.knowledge.activation import ActivationCoordinator


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
        _seed_active_student_pass_release(database_session)
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


def _seed_applicant_context(
    session: Session,
    suffix: str,
) -> tuple[Actor, ApplicantProfile, Institution, Programme]:
    applicant = Actor(
        actor_type=ActorType.APPLICANT,
        display_name=f"Applicant {suffix}",
    )
    institution = Institution(
        institution_code=f"INST-{suffix}",
        name=f"Institution {suffix}",
        institution_type="IPTS",
        region_code="MY-10",
        active=True,
    )
    session.add_all([applicant, institution])
    session.flush()
    profile = ApplicantProfile(
        actor_id=applicant.id,
        synthetic_reference=f"SYN-{suffix}",
    )
    programme = Programme(
        institution_id=institution.id,
        programme_code=f"PROG-{suffix}",
        name=f"Programme {suffix}",
        level="BACHELOR",
        active=True,
    )
    session.add_all([profile, programme])
    session.commit()
    return applicant, profile, institution, programme


def _draft_payload(
    applicant_profile_id: UUID,
    institution_id: UUID,
    programme_id: UUID,
    *,
    case_number: str = "CASE-API-001",
) -> dict[str, str]:
    return {
        "case_number": case_number,
        "applicant_profile_id": str(applicant_profile_id),
        "application_type": "NEW",
        "institution_id": str(institution_id),
        "programme_id": str(programme_id),
        "institution_type": "IPTS",
        "region_code": "MY-10",
        "applicant_location": "OUTSIDE_MALAYSIA",
        "nationality_code": "CN",
        "passport_expires_at": datetime(2030, 1, 1, tzinfo=UTC).isoformat(),
    }


def _create_draft(
    client: TestClient,
    applicant: Actor,
    profile: ApplicantProfile,
    institution: Institution,
    programme: Programme,
    *,
    case_number: str,
) -> UUID:
    response = client.post(
        "/api/v1/applicant/cases",
        headers={"X-Actor-Id": str(applicant.id)},
        json=_draft_payload(
            profile.id,
            institution.id,
            programme.id,
            case_number=case_number,
        ),
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _seed_officer(session: Session, suffix: str) -> Actor:
    officer = Actor(
        actor_type=ActorType.OFFICER,
        display_name=f"Officer {suffix}",
    )
    session.add(officer)
    session.commit()
    return officer


def _seed_active_student_pass_release(session: Session) -> RuleSetVersion:
    released_at = datetime(2020, 1, 1, tzinfo=UTC)
    run = KnowledgeSyncRun(
        git_commit_sha="a" * 40,
        status=KnowledgeSyncStatus.SUCCEEDED,
        started_at=released_at,
        completed_at=released_at,
    )
    source = KnowledgeSource(
        source_code="CASE-API-SOURCE",
        canonical_url="https://official.example/case-api",
        title="Case API source",
        authority="Synthetic authority",
        jurisdiction="Malaysia",
        language="en",
        topics=["student_pass"],
        source_type="official_guidance",
        status=KnowledgeSourceStatus.REVIEWED,
    )
    requirement = Requirement(
        requirement_code="SPV1-REQ-CASE-API",
        service_type=ServiceType.STUDENT_PASS,
        category="document",
    )
    rule_set = RuleSet(
        rule_set_code="STUDENT-PASS-CASE-API",
        service_type=ServiceType.STUDENT_PASS,
        name="Student Pass Case API",
    )
    session.add_all([run, source, requirement, rule_set])
    session.flush()
    revision = SourceRevision(
        knowledge_source_id=source.id,
        retrieved_at=released_at,
        reviewed_at=released_at,
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
        statement="Provide the synthetic Student Pass document.",
        condition_document={"always": True},
        machine_handling="Check document metadata.",
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
        published_at=released_at,
        effective_at=released_at,
        activated_at=released_at,
        applicability_basis=ApplicabilityBasis.IMMIGRATION_SUBMISSION_DATE,
        submission_cutoff_at=released_at,
        transition_policy={"re_evaluate_after_effective": True},
        status=RuleSetVersionStatus.ACTIVE,
        knowledge_sync_run_id=run.id,
        fingerprint="d" * 64,
        git_commit_sha="a" * 40,
    )
    definition = RuleDefinition(rule_code="CASE-API-RULE", name="Case API rule")
    session.add_all([revision, requirement_version, release, definition])
    session.flush()
    rule = RuleVersion(
        rule_definition_id=definition.id,
        rule_set_version_id=release.id,
        description="Case API rule",
        priority=1,
        condition_document={"always": True},
        outcome="manual_review",
        finding_code="CASE_API",
        message="Review synthetic evidence.",
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
                source_revision_id=revision.id,
                locator="Synthetic section",
                support_type=RequirementSupportType.PRIMARY,
            ),
        ]
    )
    session.flush()
    session.add(
        RuleRequirement(
            rule_version_id=rule.id,
            requirement_version_id=requirement_version.id,
        )
    )
    session.commit()
    return release


def _submit_draft(client: TestClient, applicant: Actor, case_id: UUID) -> None:
    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/submit",
        headers={"X-Actor-Id": str(applicant.id)},
        json={"channel": "ONLINE_PORTAL"},
    )
    assert response.status_code == 201


def test_applicant_creates_student_pass_draft(client: TestClient, session: Session) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "DRAFT")

    response = client.post(
        "/api/v1/applicant/cases",
        headers={"X-Actor-Id": str(applicant.id)},
        json=_draft_payload(profile.id, institution.id, programme.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["case_number"] == "CASE-API-001"
    assert body["status"] == "DRAFT"
    assert body["stage"] == "PRE_SUBMISSION"
    assert body["applicant_profile_id"] == str(profile.id)


def test_applicant_records_document_metadata_for_owned_draft_case(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "DOCUMENT")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-DOCUMENT",
    )

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/documents",
        headers={"X-Actor-Id": str(applicant.id)},
        json={
            "document_type": "PASSPORT_BIODATA",
            "storage_reference": "metadata-only://case/passport-biodata-v1",
            "content_hash": "a" * 64,
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "captured_at": "2026-09-18T10:00:00Z",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["case_id"] == str(case_id)
    assert body["document_type"] == "PASSPORT_BIODATA"
    assert body["version_number"] == 1
    assert body["storage_reference"] == "metadata-only://case/passport-biodata-v1"
    assert session.scalar(select(func.count()).select_from(Document)) == 1
    assert session.scalar(select(func.count()).select_from(DocumentVersion)) == 1


def test_applicant_cannot_record_document_metadata_for_another_case(
    client: TestClient,
    session: Session,
) -> None:
    owner, profile, institution, programme = _seed_applicant_context(session, "DOCUMENT-OWNER")
    other, _other_profile, _other_institution, _other_programme = _seed_applicant_context(
        session,
        "DOCUMENT-OTHER",
    )
    case_id = _create_draft(
        client,
        owner,
        profile,
        institution,
        programme,
        case_number="CASE-API-DOCUMENT-OWNER",
    )

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/documents",
        headers={"X-Actor-Id": str(other.id)},
        json={
            "document_type": "PASSPORT_BIODATA",
            "storage_reference": "metadata-only://case/passport-biodata-v1",
            "content_hash": "b" * 64,
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "captured_at": "2026-09-18T10:00:00Z",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "actor does not own the case"}
    assert session.scalar(select(func.count()).select_from(Document)) == 0


def test_applicant_cannot_record_document_metadata_after_submission(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(
        session,
        "DOCUMENT-SUBMITTED",
    )
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-DOCUMENT-SUBMITTED",
    )
    _submit_draft(client, applicant, case_id)

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/documents",
        headers={"X-Actor-Id": str(applicant.id)},
        json={
            "document_type": "PASSPORT_BIODATA",
            "storage_reference": "metadata-only://case/passport-biodata-v1",
            "content_hash": "c" * 64,
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "captured_at": "2026-09-18T10:00:00Z",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "documents can only be recorded for a draft case"}
    assert session.scalar(select(func.count()).select_from(Document)) == 0


def test_applicant_submission_records_handover_and_moves_case_to_submitted(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "SUBMIT")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-SUBMIT",
    )
    release = session.scalar(select(RuleSetVersion))
    assert release is not None

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/submit",
        headers={"X-Actor-Id": str(applicant.id)},
        json={"channel": "ONLINE_PORTAL"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["case_id"] == str(case_id)
    assert body["status"] == "SUBMITTED"
    assert body["submitted_at"] is not None
    assert body["accepted_at"] is None
    case = session.get(ImmigrationCase, case_id)
    assert case is not None
    assert case.current_rule_set_version_id == release.id
    assert (
        session.scalar(
            select(CaseSubmission.applicable_rule_set_version_id).where(
                CaseSubmission.case_id == case_id
            )
        )
        == release.id
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(CaseRuleAssignment)
            .where(CaseRuleAssignment.case_id == case_id)
        )
        == 1
    )
    assert (
        session.scalar(select(CaseRequirement.status).where(CaseRequirement.case_id == case_id))
        == "PENDING"
    )
    from app.database.models import EvaluationFinding, RuleEvaluation

    evaluation = session.scalar(select(RuleEvaluation).where(RuleEvaluation.case_id == case_id))
    assert evaluation is not None
    assert evaluation.rule_set_version_id == release.id
    assert evaluation.outcome == "manual_review"
    assert evaluation.input_snapshot["facts"]["application.service_region"] == "peninsular_malaysia"
    assert (
        session.scalar(
            select(func.count())
            .select_from(EvaluationFinding)
            .where(EvaluationFinding.rule_evaluation_id == evaluation.id)
        )
        == 1
    )


def test_submission_without_an_active_release_keeps_case_as_draft(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "NO-RELEASE")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-NO-RELEASE",
    )
    release = session.scalar(select(RuleSetVersion))
    assert release is not None
    release.status = RuleSetVersionStatus.RETIRED
    session.commit()

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/submit",
        headers={"X-Actor-Id": str(applicant.id)},
        json={"channel": "ONLINE_PORTAL"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "no active rule set applies to the submission date"}
    case = session.get(ImmigrationCase, case_id)
    assert case is not None
    assert case.status.value == "DRAFT"
    assert case.current_rule_set_version_id is None
    assert (
        session.scalar(
            select(func.count())
            .select_from(CaseSubmission)
            .where(CaseSubmission.case_id == case_id)
        )
        == 0
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(CaseRuleAssignment)
            .where(CaseRuleAssignment.case_id == case_id)
        )
        == 0
    )


def test_case_owner_reads_materialized_requirement_checklist(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "CHECKLIST")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-CHECKLIST",
    )
    _submit_draft(client, applicant, case_id)

    response = client.get(
        f"/api/v1/applicant/cases/{case_id}/checklist",
        headers={"X-Actor-Id": str(applicant.id)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "rule_set_version": "1.0.0",
        "requirements": [
            {
                "requirement_code": "SPV1-REQ-CASE-API",
                "statement": "Provide the synthetic Student Pass document.",
                "machine_handling": "Check document metadata.",
                "status": "PENDING",
                "sources": [{
                    "title": "Case API source",
                    "canonical_url": "https://official.example/case-api",
                    "locator": "Synthetic section",
                    "reviewed_at": "2020-01-01T00:00:00Z",
                }],
            }
        ],
    }


def test_draft_checklist_previews_current_rules_without_assigning_them(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "PREVIEW")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-PREVIEW",
    )

    response = client.get(
        f"/api/v1/applicant/cases/{case_id}/checklist",
        headers={"X-Actor-Id": str(applicant.id)},
    )

    assert response.status_code == 200
    assert response.json()["rule_set_version"] == "1.0.0"
    assert response.json()["requirements"][0]["status"] == "PENDING"
    session.expire_all()
    case = session.get(ImmigrationCase, case_id)
    assert case is not None and case.current_rule_set_version_id is None
    assert session.scalar(
        select(func.count()).select_from(CaseRuleAssignment).where(
            CaseRuleAssignment.case_id == case_id
        )
    ) == 0


def test_other_applicant_cannot_read_case_requirement_checklist(
    client: TestClient,
    session: Session,
) -> None:
    owner, profile, institution, programme = _seed_applicant_context(session, "CHECKLIST-OWNER")
    other, _other_profile, _other_institution, _other_programme = _seed_applicant_context(
        session,
        "CHECKLIST-OTHER",
    )
    case_id = _create_draft(
        client,
        owner,
        profile,
        institution,
        programme,
        case_number="CASE-API-CHECKLIST-OWNER",
    )
    _submit_draft(client, owner, case_id)

    response = client.get(
        f"/api/v1/applicant/cases/{case_id}/checklist",
        headers={"X-Actor-Id": str(other.id)},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "actor does not own the case"}


def test_officer_lists_submitted_cases(client: TestClient, session: Session) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "QUEUE")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-QUEUE",
    )
    _submit_draft(client, applicant, case_id)
    officer = _seed_officer(session, "QUEUE")

    response = client.get(
        "/api/v1/officer/cases",
        headers={"X-Actor-Id": str(officer.id)},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(case_id)]
    item = response.json()[0]
    assert item["status"] == "SUBMITTED"
    assert item["submitted_at"] is not None
    assert item["institution"] == {
        "id": str(institution.id), "name": "Institution QUEUE", "code": "INST-QUEUE"
    }
    assert item["readiness"] == {"outcome": "manual_review", "finding_count": 1}
    assert "applicant_profile_id" not in item


def test_officer_starts_processing_and_records_transition_evidence(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "PROCESS")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-PROCESS",
    )
    _submit_draft(client, applicant, case_id)
    officer = _seed_officer(session, "PROCESS")

    response = client.post(
        f"/api/v1/officer/cases/{case_id}/start-processing",
        headers={"X-Actor-Id": str(officer.id)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROCESS"
    session.expire_all()
    case = session.get(ImmigrationCase, case_id)
    assert case is not None
    assert case.assigned_to_actor_id == officer.id
    assert (
        session.scalar(
            select(CaseStatusHistory.id).where(
                CaseStatusHistory.case_id == case_id,
                CaseStatusHistory.reason_code == "OFFICER_STARTED_PROCESSING",
            )
        )
        is not None
    )
    assert (
        session.scalar(
            select(CaseEvent.id).where(
                CaseEvent.case_id == case_id,
                CaseEvent.event_type == "CASE_PROCESSING_STARTED",
            )
        )
        is not None
    )
    assert (
        session.scalar(
            select(AuditEvent.id).where(
                AuditEvent.case_id == case_id,
                AuditEvent.action == "CASE_PROCESSING_STARTED",
            )
        )
        is not None
    )


def test_applicant_cannot_create_case_for_another_profile(
    client: TestClient,
    session: Session,
) -> None:
    applicant, _profile, institution, programme = _seed_applicant_context(session, "OWNER-A")
    _other, other_profile, _other_institution, _other_programme = _seed_applicant_context(
        session,
        "OWNER-B",
    )

    response = client.post(
        "/api/v1/applicant/cases",
        headers={"X-Actor-Id": str(applicant.id)},
        json=_draft_payload(
            other_profile.id,
            institution.id,
            programme.id,
            case_number="CASE-API-FOREIGN-PROFILE",
        ),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "actor does not own the applicant profile"}


def test_repeated_submission_returns_conflict_without_second_initial_submission(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "REPEAT")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-REPEAT",
    )
    _submit_draft(client, applicant, case_id)

    response = client.post(
        f"/api/v1/applicant/cases/{case_id}/submit",
        headers={"X-Actor-Id": str(applicant.id)},
        json={"channel": "ONLINE_PORTAL"},
    )

    assert response.status_code == 409
    assert (
        session.scalar(
            select(func.count())
            .select_from(CaseSubmission)
            .where(CaseSubmission.case_id == case_id)
        )
        == 1
    )


def test_applicant_cannot_access_officer_queue(client: TestClient, session: Session) -> None:
    applicant, _profile, _institution, _programme = _seed_applicant_context(session, "ROLE")

    response = client.get(
        "/api/v1/officer/cases",
        headers={"X-Actor-Id": str(applicant.id)},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "actor is not permitted for this action"}


def test_officer_cannot_start_processing_twice(client: TestClient, session: Session) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "TWICE")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-TWICE",
    )
    _submit_draft(client, applicant, case_id)
    officer = _seed_officer(session, "TWICE")
    first = client.post(
        f"/api/v1/officer/cases/{case_id}/start-processing",
        headers={"X-Actor-Id": str(officer.id)},
    )
    assert first.status_code == 200

    response = client.post(
        f"/api/v1/officer/cases/{case_id}/start-processing",
        headers={"X-Actor-Id": str(officer.id)},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "case is not in the required state"}


def test_concurrent_officers_start_processing_exactly_once(
    client: TestClient,
    session: Session,
) -> None:
    applicant, profile, institution, programme = _seed_applicant_context(session, "CONCURRENT")
    case_id = _create_draft(
        client,
        applicant,
        profile,
        institution,
        programme,
        case_number="CASE-API-CONCURRENT",
    )
    _submit_draft(client, applicant, case_id)
    officer = _seed_officer(session, "CONCURRENT")
    barrier = Barrier(2)

    def start_processing() -> int:
        barrier.wait()
        response = client.post(
            f"/api/v1/officer/cases/{case_id}/start-processing",
            headers={"X-Actor-Id": str(officer.id)},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: start_processing(), range(2)))

    assert sorted(statuses) == [200, 409]
    session.expire_all()
    assert (
        session.scalar(
            select(func.count())
            .select_from(CaseStatusHistory)
            .where(
                CaseStatusHistory.case_id == case_id,
                CaseStatusHistory.reason_code == "OFFICER_STARTED_PROCESSING",
            )
        )
        == 1
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(CaseEvent)
            .where(
                CaseEvent.case_id == case_id,
                CaseEvent.event_type == "CASE_PROCESSING_STARTED",
            )
        )
        == 1
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.case_id == case_id,
                AuditEvent.action == "CASE_PROCESSING_STARTED",
            )
        )
        == 1
    )


@pytest.mark.parametrize(
    ("cutoff_offset", "final_status", "simulate_failure", "expected"),
    [
        (timedelta(days=-1), False, False, 2),
        (timedelta(0), False, False, 2),
        (timedelta(hours=1), False, False, 1),
        (timedelta(days=-1), True, False, 1),
        (timedelta(days=-1), False, True, 1),
    ],
)
def test_activation_reassesses_only_eligible_cases(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    cutoff_offset: timedelta,
    final_status: bool,
    simulate_failure: bool,
    expected: int,
) -> None:
    suffix = f"ACT-{cutoff_offset.total_seconds()}-{final_status}-{simulate_failure}"
    applicant, profile, institution, programme = _seed_applicant_context(session, suffix)
    case_id = _create_draft(
        client, applicant, profile, institution, programme, case_number=f"CASE-{suffix}"
    )
    _submit_draft(client, applicant, case_id)
    submitted_at = session.scalar(
        select(CaseSubmission.submitted_at).where(CaseSubmission.case_id == case_id)
    )
    assert submitted_at is not None
    case = session.get(ImmigrationCase, case_id)
    assert case is not None
    if final_status:
        case.status = "COMPLETED"
        case.stage = "CLOSED"
        session.commit()
    original = session.scalar(
        select(CaseRuleAssignment).where(CaseRuleAssignment.case_id == case_id)
    )
    original_evaluation = session.scalar(
        select(RuleEvaluation).where(RuleEvaluation.case_id == case_id)
    )
    assert original is not None and original_evaluation is not None
    old_release = session.get(RuleSetVersion, original.rule_set_version_id)
    assert old_release is not None
    current = datetime.now(UTC)
    administrator = Actor(actor_type=ActorType.ADMINISTRATOR, display_name="Activation admin")
    session.add(administrator)
    session.flush()
    next_release = RuleSetVersion(
        rule_set_id=old_release.rule_set_id,
        semantic_version="2.0.0",
        scope_document=old_release.scope_document,
        outcome_contract=old_release.outcome_contract,
        default_outcome="pass",
        dataset_snapshots={},
        published_at=current,
        effective_at=current + timedelta(days=1),
        applicability_basis=ApplicabilityBasis.IMMIGRATION_SUBMISSION_DATE,
        submission_cutoff_at=submitted_at + cutoff_offset,
        transition_policy={"re_evaluate_after_effective": True},
        status=RuleSetVersionStatus.REVIEW,
        supersedes_rule_set_version_id=old_release.id,
        knowledge_sync_run_id=old_release.knowledge_sync_run_id,
        fingerprint="f" * 64,
        git_commit_sha="a" * 40,
    )
    session.add(next_release)
    session.flush()
    session.add(
        ApprovalEvent(
            rule_set_version_id=next_release.id,
            decision=ApprovalDecision.APPROVED,
            decided_by_actor_id=administrator.id,
            decided_at=current,
            notes="Synthetic transition",
        )
    )
    old_rule = session.scalar(
        select(RuleVersion).where(RuleVersion.rule_set_version_id == old_release.id)
    )
    assert old_rule is not None
    new_rule = RuleVersion(
        rule_definition_id=old_rule.rule_definition_id,
        rule_set_version_id=next_release.id,
        description="New synthetic review",
        priority=1,
        condition_document={"always": True},
        outcome="manual_review",
        finding_code="NEW_REVIEW",
        message="Review under new release.",
        task_type="verify",
        supplemental_source_codes=[],
        fingerprint="f" * 64,
        git_commit_sha="a" * 40,
        knowledge_sync_run_id=old_release.knowledge_sync_run_id,
    )
    session.add(new_rule)
    session.flush()
    old_link = session.scalar(
        select(RuleRequirement).where(RuleRequirement.rule_version_id == old_rule.id)
    )
    assert old_link is not None
    session.add(
        RuleRequirement(
            rule_version_id=new_rule.id,
            requirement_version_id=old_link.requirement_version_id,
        )
    )
    session.commit()

    if simulate_failure:

        def _fail_case(*args: object, **kwargs: object) -> None:
            raise ValueError("synthetic invalid case")

        monkeypatch.setattr("app.knowledge.activation._reassess_case", _fail_case)

    summary = ActivationCoordinator().activate_due(session, current + timedelta(days=2))

    assert summary.activated == 1
    assignments = list(
        session.scalars(select(CaseRuleAssignment).where(CaseRuleAssignment.case_id == case_id))
    )
    evaluations = list(
        session.scalars(select(RuleEvaluation).where(RuleEvaluation.case_id == case_id))
    )
    assert len(assignments) == expected
    assert len(evaluations) == expected
    session.refresh(case)
    assert case.current_rule_set_version_id == (
        next_release.id if expected == 2 else old_release.id
    )
    if expected == 2:
        assert assignments[-1].supersedes_assignment_id == original.id
        assert evaluations[-1].supersedes_evaluation_id == original_evaluation.id
    if simulate_failure:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.case_id == case_id,
                    AuditEvent.action == "CASE_POLICY_REASSESSMENT_FAILED",
                )
            )
            == 1
        )

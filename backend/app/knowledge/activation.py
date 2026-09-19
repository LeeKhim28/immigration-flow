from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import (
    ApplicabilityBasis,
    ApprovalDecision,
    CaseStatus,
    KnowledgeSyncStatus,
    RuleSetVersionStatus,
    SubmissionType,
)
from app.database.models import (
    ApprovalEvent,
    AuditEvent,
    CaseEvent,
    CaseRequirement,
    CaseRuleAssignment,
    CaseSubmission,
    ImmigrationCase,
    KnowledgeSyncRun,
    RequirementVersion,
    RuleEvaluation,
    RuleRequirement,
    RuleSet,
    RuleSetVersion,
    RuleVersion,
)
from app.domains.evaluations.service import evaluate_case


@dataclass(frozen=True, slots=True)
class ActivationSummary:
    activated: int = 0
    skipped: int = 0
    failed: int = 0


class ActivationCoordinator:
    def activate_due(self, session: Session, now: datetime) -> ActivationSummary:
        _require_aware(now)
        activated = skipped = failed = 0
        releases = session.scalars(
            select(RuleSetVersion)
            .where(
                RuleSetVersion.status == RuleSetVersionStatus.REVIEW,
                RuleSetVersion.effective_at <= now,
            )
            .order_by(RuleSetVersion.effective_at, RuleSetVersion.id)
            .with_for_update()
        ).all()
        for release in releases:
            approval = session.scalar(
                select(ApprovalEvent).where(
                    ApprovalEvent.rule_set_version_id == release.id,
                    ApprovalEvent.decision == ApprovalDecision.APPROVED,
                )
            )
            sync = session.get(KnowledgeSyncRun, release.knowledge_sync_run_id)
            if approval is None or sync is None or sync.status != KnowledgeSyncStatus.SUCCEEDED:
                skipped += 1
                continue
            try:
                with session.begin_nested():
                    active = session.scalar(
                        select(RuleSetVersion)
                        .where(
                            RuleSetVersion.rule_set_id == release.rule_set_id,
                            RuleSetVersion.status == RuleSetVersionStatus.ACTIVE,
                        )
                        .with_for_update()
                    )
                    if active is not None:
                        active.status = RuleSetVersionStatus.RETIRED
                        session.flush()
                    release.status = RuleSetVersionStatus.ACTIVE
                    release.activated_at = now
                    session.add(
                        AuditEvent(
                            case_id=None,
                            actor_id=None,
                            action="RULE_SET_ACTIVATED",
                            entity_type="RULE_SET_VERSION",
                            entity_id=release.id,
                            after_summary={
                                "status": "ACTIVE",
                                "retired_version_id": str(active.id) if active else None,
                            },
                            occurred_at=now,
                        )
                    )
                    session.flush()
                    _reassess_eligible_cases(session, release, now)
                activated += 1
            except Exception:
                failed += 1
        session.commit()
        return ActivationSummary(activated=activated, skipped=skipped, failed=failed)


def _reassess_eligible_cases(session: Session, release: RuleSetVersion, now: datetime) -> None:
    cutoff = release.submission_cutoff_at
    if (
        release.applicability_basis != ApplicabilityBasis.IMMIGRATION_SUBMISSION_DATE
        or cutoff is None
        or release.transition_policy.get("re_evaluate_after_effective") is not True
    ):
        return
    rule_set = session.get(RuleSet, release.rule_set_id)
    if rule_set is None:
        raise ValueError("rule set is missing")
    cases = list(
        session.scalars(
            select(ImmigrationCase)
            .join(CaseSubmission, CaseSubmission.case_id == ImmigrationCase.id)
            .where(
                CaseSubmission.submission_type == SubmissionType.INITIAL,
                CaseSubmission.submitted_at >= cutoff,
                ImmigrationCase.service_type == rule_set.service_type,
                ImmigrationCase.status.not_in(
                    [CaseStatus.DRAFT, CaseStatus.COMPLETED, CaseStatus.WITHDRAWN]
                ),
                ImmigrationCase.current_rule_set_version_id != release.id,
            )
            .with_for_update(of=ImmigrationCase)
        )
    )
    requirement_ids = list(
        session.scalars(
            select(RequirementVersion.id)
            .join(RuleRequirement, RuleRequirement.requirement_version_id == RequirementVersion.id)
            .join(RuleVersion, RuleVersion.id == RuleRequirement.rule_version_id)
            .where(RuleVersion.rule_set_version_id == release.id)
            .distinct()
        )
    )
    if cases and not requirement_ids:
        raise ValueError("approved release has no material requirements")
    for case in cases:
        case_id = case.id
        try:
            with session.begin_nested():
                _reassess_case(session, case, release, requirement_ids, now)
                session.flush()
        except Exception:
            session.add_all(
                [
                    CaseEvent(
                        case_id=case_id,
                        event_type="CASE_POLICY_REASSESSMENT_FAILED",
                        event_payload={"rule_set_version_id": str(release.id)},
                        occurred_at=now,
                        actor_id=None,
                    ),
                    AuditEvent(
                        case_id=case_id,
                        actor_id=None,
                        action="CASE_POLICY_REASSESSMENT_FAILED",
                        entity_type="CASE",
                        entity_id=case_id,
                        after_summary={"rule_set_version_id": str(release.id)},
                        occurred_at=now,
                    ),
                ]
            )


def _reassess_case(
    session: Session,
    case: ImmigrationCase,
    release: RuleSetVersion,
    requirement_ids: list[UUID],
    now: datetime,
) -> None:
    previous_assignment = session.scalar(
        select(CaseRuleAssignment)
        .where(CaseRuleAssignment.case_id == case.id)
        .order_by(CaseRuleAssignment.assigned_at.desc(), CaseRuleAssignment.id.desc())
        .limit(1)
    )
    previous_evaluation = session.scalar(
        select(RuleEvaluation)
        .where(RuleEvaluation.case_id == case.id)
        .order_by(RuleEvaluation.evaluated_at.desc(), RuleEvaluation.id.desc())
        .limit(1)
    )
    assignment = CaseRuleAssignment(
        case_id=case.id,
        rule_set_version_id=release.id,
        assignment_reason="POLICY_ACTIVATION_REASSESSMENT",
        assigned_at=now,
        assigned_by_actor_id=None,
        supersedes_assignment_id=previous_assignment.id if previous_assignment else None,
    )
    session.add(assignment)
    session.flush()
    present_ids = set(
        session.scalars(
            select(CaseRequirement.requirement_version_id).where(CaseRequirement.case_id == case.id)
        )
    )
    session.add_all(
        CaseRequirement(case_id=case.id, requirement_version_id=version_id, status="PENDING")
        for version_id in requirement_ids
        if version_id not in present_ids
    )
    case.current_rule_set_version_id = release.id
    evaluation = evaluate_case(
        session,
        case,
        release,
        trigger="POLICY_ACTIVATION_REASSESSMENT",
        at=now,
        supersedes_evaluation_id=previous_evaluation.id if previous_evaluation else None,
    )
    session.add_all(
        [
            CaseEvent(
                case_id=case.id,
                event_type="CASE_POLICY_REASSESSED",
                event_payload={
                    "rule_set_version_id": str(release.id),
                    "evaluation_id": str(evaluation.id),
                },
                occurred_at=now,
                actor_id=None,
            ),
            AuditEvent(
                case_id=case.id,
                actor_id=None,
                action="CASE_POLICY_REASSESSED",
                entity_type="CASE_RULE_ASSIGNMENT",
                entity_id=assignment.id,
                before_summary={
                    "rule_set_version_id": str(previous_assignment.rule_set_version_id)
                    if previous_assignment
                    else None
                },
                after_summary={
                    "rule_set_version_id": str(release.id),
                    "evaluation_id": str(evaluation.id),
                },
                occurred_at=now,
            ),
        ]
    )


def display_release_status(
    version: RuleSetVersion, decision: ApprovalEvent | None, now: datetime
) -> str:
    _require_aware(now)
    if version.status == RuleSetVersionStatus.ACTIVE:
        return "ACTIVE"
    if version.status == RuleSetVersionStatus.RETIRED:
        return "RETIRED"
    if decision is None:
        return version.status.value
    if decision.decision == ApprovalDecision.REJECTED:
        return "REJECTED"
    if version.effective_at > now:
        return "SCHEDULED"
    return "DUE"


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")

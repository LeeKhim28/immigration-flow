from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.enums import ActorType, CaseStage, CaseStatus, SubmissionType
from app.database.models import (
    Actor,
    ApplicantProfile,
    CaseEvent,
    CaseSubmission,
    EvaluationFinding,
    ImmigrationCase,
    Institution,
    Programme,
    RuleEvaluation,
    RuleSetVersion,
    StudentPassCaseProfile,
)
from app.domains.cases.service import CaseWorkflowError
from app.domains.demo.service import DEMO_PREFIX


@dataclass(frozen=True)
class NamedReference:
    id: UUID
    name: str
    code: str


@dataclass(frozen=True)
class CaseDetail:
    id: UUID
    case_number: str
    applicant_profile_id: UUID
    status: CaseStatus
    stage: CaseStage
    synthetic: bool
    institution: NamedReference
    programme: NamedReference
    nationality_code: str
    passport_expires_at: datetime
    rule_set_version: str | None


@dataclass(frozen=True)
class TimelineEntry:
    id: UUID
    event_type: str
    occurred_at: datetime


@dataclass(frozen=True)
class FindingProjection:
    id: UUID
    outcome: str
    code: str
    message: str


@dataclass(frozen=True)
class EvaluationProjection:
    id: UUID
    outcome: str
    trigger: str
    evaluated_at: datetime
    supersedes_evaluation_id: UUID | None
    rule_set_version: str
    findings: tuple[FindingProjection, ...]


@dataclass(frozen=True)
class ReadinessSummary:
    outcome: str
    finding_count: int


@dataclass(frozen=True)
class OfficerQueueItem:
    id: UUID
    case_number: str
    status: CaseStatus
    stage: CaseStage
    submitted_at: datetime
    institution: NamedReference
    readiness: ReadinessSummary


def list_officer_case_summaries(
    session: Session, actor: Actor, status: CaseStatus
) -> tuple[OfficerQueueItem, ...]:
    _require_actor(actor, ActorType.OFFICER)
    if status not in {CaseStatus.SUBMITTED, CaseStatus.IN_PROCESS}:
        raise CaseWorkflowError(422, "status filter is not supported")
    rows = session.execute(
        select(ImmigrationCase, CaseSubmission, Institution)
        .join(StudentPassCaseProfile, StudentPassCaseProfile.case_id == ImmigrationCase.id)
        .join(Institution, Institution.id == StudentPassCaseProfile.institution_id)
        .join(CaseSubmission, CaseSubmission.case_id == ImmigrationCase.id)
        .where(
            ImmigrationCase.status == status,
            CaseSubmission.submission_type == SubmissionType.INITIAL,
        )
        .order_by(CaseSubmission.submitted_at, ImmigrationCase.id)
    )
    items = []
    for case, submission, institution in rows:
        evaluation = session.scalar(
            select(RuleEvaluation)
            .where(RuleEvaluation.case_id == case.id)
            .order_by(RuleEvaluation.evaluated_at.desc(), RuleEvaluation.id.desc())
            .limit(1)
        )
        if evaluation is None:
            readiness = ReadinessSummary("not_evaluated", 0)
        else:
            count = session.scalar(
                select(func.count())
                .select_from(EvaluationFinding)
                .where(EvaluationFinding.rule_evaluation_id == evaluation.id)
            )
            readiness = ReadinessSummary(evaluation.outcome, int(count or 0))
        items.append(
            OfficerQueueItem(
                case.id,
                case.case_number,
                case.status,
                case.stage,
                submission.submitted_at,
                NamedReference(institution.id, institution.name, institution.institution_code),
                readiness,
            )
        )
    return tuple(items)


def get_applicant_case_detail(
    session: Session,
    actor: Actor,
    case_id: UUID,
) -> CaseDetail:
    _require_actor(actor, ActorType.APPLICANT)
    detail, owner_actor_id = _get_case_detail(session, case_id)
    if owner_actor_id != actor.id:
        raise CaseWorkflowError(403, "actor does not own the case")
    return detail


def get_officer_case_detail(
    session: Session,
    actor: Actor,
    case_id: UUID,
) -> CaseDetail:
    _require_actor(actor, ActorType.OFFICER)
    detail, _ = _get_case_detail(session, case_id)
    return detail


def get_applicant_timeline(
    session: Session,
    actor: Actor,
    case_id: UUID,
) -> tuple[TimelineEntry, ...]:
    get_applicant_case_detail(session, actor, case_id)
    return tuple(
        TimelineEntry(event.id, event.event_type, event.occurred_at)
        for event in session.scalars(
            select(CaseEvent)
            .where(CaseEvent.case_id == case_id)
            .order_by(CaseEvent.occurred_at, CaseEvent.id)
        )
    )


def get_officer_timeline(
    session: Session,
    actor: Actor,
    case_id: UUID,
) -> tuple[TimelineEntry, ...]:
    get_officer_case_detail(session, actor, case_id)
    return tuple(
        TimelineEntry(event.id, event.event_type, event.occurred_at)
        for event in session.scalars(
            select(CaseEvent)
            .where(CaseEvent.case_id == case_id)
            .order_by(CaseEvent.occurred_at, CaseEvent.id)
        )
    )


def get_case_evaluations(
    session: Session,
    actor: Actor,
    case_id: UUID,
    *,
    officer: bool = False,
) -> tuple[EvaluationProjection, ...]:
    if officer:
        get_officer_case_detail(session, actor, case_id)
    else:
        get_applicant_case_detail(session, actor, case_id)
    projections = []
    for evaluation in session.scalars(
        select(RuleEvaluation)
        .where(RuleEvaluation.case_id == case_id)
        .order_by(RuleEvaluation.evaluated_at, RuleEvaluation.id)
    ):
        release = session.get(RuleSetVersion, evaluation.rule_set_version_id)
        if release is None:
            raise CaseWorkflowError(409, "evaluation rule set version was not found")
        findings = tuple(
            FindingProjection(item.id, item.outcome, item.code, item.message)
            for item in session.scalars(
                select(EvaluationFinding)
                .where(EvaluationFinding.rule_evaluation_id == evaluation.id)
                .order_by(EvaluationFinding.id)
            )
        )
        projections.append(
            EvaluationProjection(
                evaluation.id,
                evaluation.outcome,
                evaluation.trigger,
                evaluation.evaluated_at,
                evaluation.supersedes_evaluation_id,
                release.semantic_version,
                findings,
            )
        )
    return tuple(projections)


def _get_case_detail(session: Session, case_id: UUID) -> tuple[CaseDetail, UUID]:
    case = session.get(ImmigrationCase, case_id)
    if case is None:
        raise CaseWorkflowError(404, "case was not found")
    profile = session.get(ApplicantProfile, case.applicant_profile_id)
    student = session.get(StudentPassCaseProfile, case.id)
    if profile is None or student is None:
        raise CaseWorkflowError(409, "case profile is incomplete")
    institution = session.get(Institution, student.institution_id)
    programme = session.get(Programme, student.programme_id)
    if institution is None or programme is None:
        raise CaseWorkflowError(409, "case reference data is incomplete")
    release = (
        session.get(RuleSetVersion, case.current_rule_set_version_id)
        if case.current_rule_set_version_id is not None
        else None
    )
    owner = session.get(Actor, profile.actor_id)
    synthetic = bool(owner and (owner.external_reference or "").startswith(DEMO_PREFIX))
    return (
        CaseDetail(
            id=case.id,
            case_number=case.case_number,
            applicant_profile_id=case.applicant_profile_id,
            status=case.status,
            stage=case.stage,
            synthetic=synthetic,
            institution=NamedReference(
                institution.id,
                institution.name,
                institution.institution_code,
            ),
            programme=NamedReference(programme.id, programme.name, programme.programme_code),
            nationality_code=student.nationality_code,
            passport_expires_at=student.passport_expires_at,
            rule_set_version=release.semantic_version if release else None,
        ),
        profile.actor_id,
    )


def _require_actor(actor: Actor, expected: ActorType) -> None:
    if actor.actor_type != expected:
        raise CaseWorkflowError(403, "actor is not permitted for this action")

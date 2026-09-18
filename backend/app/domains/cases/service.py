from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import (
    ActorType,
    ApplicantLocation,
    ApplicationType,
    CaseStage,
    CaseStatus,
    InstitutionType,
    ServiceType,
    SubmissionChannel,
    SubmissionType,
)
from app.database.models import (
    Actor,
    ApplicantProfile,
    AuditEvent,
    CaseEvent,
    CaseStatusHistory,
    CaseSubmission,
    ImmigrationCase,
    Institution,
    Programme,
    StudentPassCaseProfile,
)


class CaseWorkflowError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class DraftStudentPassCaseCommand:
    case_number: str
    applicant_profile_id: UUID
    application_type: ApplicationType
    institution_id: UUID
    programme_id: UUID
    institution_type: InstitutionType
    region_code: str
    applicant_location: ApplicantLocation
    nationality_code: str
    passport_expires_at: datetime


def create_student_pass_draft(
    session: Session,
    actor: Actor,
    command: DraftStudentPassCaseCommand,
) -> ImmigrationCase:
    _require_actor_type(actor, ActorType.APPLICANT)
    profile = _require_record(
        session.get(ApplicantProfile, command.applicant_profile_id),
        "applicant profile",
    )
    if profile.actor_id != actor.id:
        raise CaseWorkflowError(403, "actor does not own the applicant profile")

    institution = _require_record(session.get(Institution, command.institution_id), "institution")
    programme = _require_record(session.get(Programme, command.programme_id), "programme")
    if programme.institution_id != institution.id:
        raise CaseWorkflowError(422, "programme does not belong to the institution")
    if not institution.active or not programme.active:
        raise CaseWorkflowError(409, "institution and programme must be active")
    if (
        session.scalar(
            select(ImmigrationCase.id).where(ImmigrationCase.case_number == command.case_number)
        )
        is not None
    ):
        raise CaseWorkflowError(409, "case number already exists")

    case = ImmigrationCase(
        case_number=command.case_number,
        applicant_profile_id=profile.id,
        service_type=ServiceType.STUDENT_PASS,
        status=CaseStatus.DRAFT,
        stage=CaseStage.PRE_SUBMISSION,
        created_by_actor_id=actor.id,
    )
    session.add(case)
    session.flush()
    session.add(
        StudentPassCaseProfile(
            case_id=case.id,
            application_type=command.application_type,
            institution_id=institution.id,
            programme_id=programme.id,
            institution_type=command.institution_type,
            region_code=command.region_code,
            applicant_location=command.applicant_location,
            nationality_code=command.nationality_code,
            passport_expires_at=command.passport_expires_at,
        )
    )
    _record_case_created(session, case, actor)
    session.commit()
    session.refresh(case)
    return case


def submit_case_to_immigration(
    session: Session,
    actor: Actor,
    case_id: UUID,
    channel: SubmissionChannel,
) -> tuple[ImmigrationCase, CaseSubmission]:
    _require_actor_type(actor, ActorType.APPLICANT)
    case = _require_owned_case(session, case_id, actor)
    _require_status(case, CaseStatus.DRAFT)
    occurred_at = datetime.now(UTC)
    submission = CaseSubmission(
        case_id=case.id,
        submission_type=SubmissionType.INITIAL,
        channel=channel,
        submitted_by_actor_id=actor.id,
        submitted_at=occurred_at,
    )
    session.add(submission)
    _transition_case(
        session,
        case,
        to_status=CaseStatus.SUBMITTED,
        to_stage=CaseStage.IMMIGRATION_PROCESSING,
        reason_code="APPLICANT_SUBMITTED",
        event_type="CASE_SUBMITTED_TO_IMMIGRATION",
        actor=actor,
        occurred_at=occurred_at,
    )
    session.commit()
    session.refresh(case)
    session.refresh(submission)
    return case, submission


def list_officer_cases(
    session: Session,
    officer: Actor,
    status: CaseStatus,
) -> list[ImmigrationCase]:
    _require_actor_type(officer, ActorType.OFFICER)
    if status not in {CaseStatus.SUBMITTED, CaseStatus.IN_PROCESS}:
        raise CaseWorkflowError(422, "status filter is not supported")
    return list(
        session.scalars(
            select(ImmigrationCase)
            .where(ImmigrationCase.status == status)
            .order_by(ImmigrationCase.created_at, ImmigrationCase.id)
        )
    )


def start_case_processing(
    session: Session,
    officer: Actor,
    case_id: UUID,
) -> ImmigrationCase:
    _require_actor_type(officer, ActorType.OFFICER)
    case = _require_record(session.get(ImmigrationCase, case_id), "case")
    _require_status(case, CaseStatus.SUBMITTED)
    occurred_at = datetime.now(UTC)
    case.assigned_to_actor_id = officer.id
    _transition_case(
        session,
        case,
        to_status=CaseStatus.IN_PROCESS,
        to_stage=CaseStage.IMMIGRATION_PROCESSING,
        reason_code="OFFICER_STARTED_PROCESSING",
        event_type="CASE_PROCESSING_STARTED",
        actor=officer,
        occurred_at=occurred_at,
    )
    session.commit()
    session.refresh(case)
    return case


def _require_actor_type(actor: Actor, expected: ActorType) -> None:
    if actor.actor_type is not expected:
        raise CaseWorkflowError(403, "actor is not permitted for this action")


def _require_owned_case(session: Session, case_id: UUID, actor: Actor) -> ImmigrationCase:
    case = _require_record(session.get(ImmigrationCase, case_id), "case")
    profile = _require_record(
        session.get(ApplicantProfile, case.applicant_profile_id),
        "applicant profile",
    )
    if profile.actor_id != actor.id:
        raise CaseWorkflowError(403, "actor does not own the case")
    return case


def _require_status(case: ImmigrationCase, expected: CaseStatus) -> None:
    if case.status is not expected:
        raise CaseWorkflowError(409, "case is not in the required state")


def _require_record[T](record: T | None, label: str) -> T:
    if record is None:
        raise CaseWorkflowError(404, f"{label} was not found")
    return record


def _record_case_created(session: Session, case: ImmigrationCase, actor: Actor) -> None:
    occurred_at = datetime.now(UTC)
    session.add_all(
        [
            CaseStatusHistory(
                case_id=case.id,
                from_status=None,
                to_status=CaseStatus.DRAFT,
                reason_code="CASE_CREATED",
                changed_by_actor_id=actor.id,
                changed_at=occurred_at,
            ),
            CaseEvent(
                case_id=case.id,
                event_type="CASE_CREATED",
                event_payload={"status": CaseStatus.DRAFT.value},
                occurred_at=occurred_at,
                actor_id=actor.id,
            ),
            AuditEvent(
                case_id=case.id,
                actor_id=actor.id,
                action="CASE_CREATED",
                entity_type="CASE",
                entity_id=case.id,
                after_summary={"status": CaseStatus.DRAFT.value},
                occurred_at=occurred_at,
            ),
        ]
    )


def _transition_case(
    session: Session,
    case: ImmigrationCase,
    *,
    to_status: CaseStatus,
    to_stage: CaseStage,
    reason_code: str,
    event_type: str,
    actor: Actor,
    occurred_at: datetime,
) -> None:
    from_status = case.status
    case.status = to_status
    case.stage = to_stage
    case.updated_at = occurred_at
    case.row_version += 1
    session.add_all(
        [
            CaseStatusHistory(
                case_id=case.id,
                from_status=from_status,
                to_status=to_status,
                reason_code=reason_code,
                changed_by_actor_id=actor.id,
                changed_at=occurred_at,
            ),
            CaseEvent(
                case_id=case.id,
                event_type=event_type,
                event_payload={
                    "from_status": from_status.value,
                    "to_status": to_status.value,
                    "reason_code": reason_code,
                },
                occurred_at=occurred_at,
                actor_id=actor.id,
            ),
            AuditEvent(
                case_id=case.id,
                actor_id=actor.id,
                action=event_type,
                entity_type="CASE",
                entity_id=case.id,
                before_summary={"status": from_status.value},
                after_summary={"status": to_status.value},
                occurred_at=occurred_at,
            ),
        ]
    )

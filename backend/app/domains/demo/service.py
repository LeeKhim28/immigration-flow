from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database.enums import (
    ActorType,
    ApplicantLocation,
    ApplicationType,
    CaseStage,
    CaseStatus,
    InstitutionType,
    ServiceType,
)
from app.database.models import (
    Actor,
    ApplicantProfile,
    AuditEvent,
    CaseEvent,
    CaseStatusHistory,
    ImmigrationCase,
    Institution,
    Programme,
    StudentPassCaseProfile,
)

DEMO_PREFIX = "IMMIGRATIONFLOW-DEMO-V1:"
APPLICANT_REFERENCE = f"{DEMO_PREFIX}APPLICANT"
OFFICER_REFERENCE = f"{DEMO_PREFIX}OFFICER"
PROFILE_REFERENCE = f"{DEMO_PREFIX}PROFILE"
INSTITUTION_CODE = "IF-DEMO-UNIVERSITY"
CASE_NUMBER_PREFIX = "IF-DEMO-STUDENT-PASS-"
ADVISORY_LOCK_KEY = 4_938_212_026


@dataclass(frozen=True)
class DemoSession:
    applicant_actor_id: UUID
    officer_actor_id: UUID
    case_id: UUID
    case_number: str


class DemoSessionService:
    @staticmethod
    def get_or_create(session: Session) -> DemoSession:
        DemoSessionService._lock(session)
        applicant, profile, officer, institution, programme = (
            DemoSessionService._get_or_create_reference_data(session)
        )
        current = session.scalar(
            select(ImmigrationCase)
            .where(ImmigrationCase.created_by_actor_id == applicant.id)
            .order_by(ImmigrationCase.created_at.desc(), ImmigrationCase.id.desc())
            .limit(1)
        )
        if current is None or current.status != CaseStatus.DRAFT:
            current = DemoSessionService._create_case(
                session,
                applicant,
                profile,
                institution,
                programme,
            )
        session.commit()
        return DemoSession(applicant.id, officer.id, current.id, current.case_number)

    @staticmethod
    def reset(session: Session) -> None:
        DemoSessionService._lock(session)
        applicant = session.scalar(
            select(Actor).where(Actor.external_reference == APPLICANT_REFERENCE)
        )
        if applicant is None:
            session.commit()
            return
        current = session.scalar(
            select(ImmigrationCase)
            .where(ImmigrationCase.created_by_actor_id == applicant.id)
            .order_by(ImmigrationCase.created_at.desc(), ImmigrationCase.id.desc())
            .limit(1)
        )
        if current is not None and current.status not in {
            CaseStatus.COMPLETED,
            CaseStatus.WITHDRAWN,
        }:
            DemoSessionService._withdraw_case(session, current, applicant)
        session.commit()

    @staticmethod
    def _lock(session: Session) -> None:
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": ADVISORY_LOCK_KEY},
        )

    @staticmethod
    def _get_or_create_reference_data(
        session: Session,
    ) -> tuple[Actor, ApplicantProfile, Actor, Institution, Programme]:
        applicant = session.scalar(
            select(Actor).where(Actor.external_reference == APPLICANT_REFERENCE)
        )
        if applicant is None:
            applicant = Actor(
                actor_type=ActorType.APPLICANT,
                display_name="Aisha Rahman (Synthetic)",
                external_reference=APPLICANT_REFERENCE,
            )
            session.add(applicant)
            session.flush()
        profile = session.scalar(
            select(ApplicantProfile).where(
                ApplicantProfile.synthetic_reference == PROFILE_REFERENCE
            )
        )
        if profile is None:
            profile = ApplicantProfile(actor_id=applicant.id, synthetic_reference=PROFILE_REFERENCE)
            session.add(profile)

        officer = session.scalar(select(Actor).where(Actor.external_reference == OFFICER_REFERENCE))
        if officer is None:
            officer = Actor(
                actor_type=ActorType.OFFICER,
                display_name="Demo Reviewing Officer (Synthetic)",
                external_reference=OFFICER_REFERENCE,
            )
            session.add(officer)

        institution = session.scalar(
            select(Institution).where(Institution.institution_code == INSTITUTION_CODE)
        )
        if institution is None:
            institution = Institution(
                institution_code=INSTITUTION_CODE,
                name="Northstar International University (Synthetic)",
                institution_type=InstitutionType.IPTS.value,
                region_code="MY-10",
                active=True,
            )
            session.add(institution)
            session.flush()
        programme = session.scalar(
            select(Programme).where(
                Programme.institution_id == institution.id,
                Programme.programme_code == "IF-DEMO-BSC-CS",
            )
        )
        if programme is None:
            programme = Programme(
                institution_id=institution.id,
                programme_code="IF-DEMO-BSC-CS",
                name="Bachelor of Computer Science (Synthetic)",
                level="BACHELOR",
                active=True,
            )
            session.add(programme)
        session.flush()
        return applicant, profile, officer, institution, programme

    @staticmethod
    def _create_case(
        session: Session,
        applicant: Actor,
        profile: ApplicantProfile,
        institution: Institution,
        programme: Programme,
    ) -> ImmigrationCase:
        sequence = int(
            session.scalar(
                select(func.count())
                .select_from(ImmigrationCase)
                .where(ImmigrationCase.created_by_actor_id == applicant.id)
            )
            or 0
        ) + 1
        case = ImmigrationCase(
            case_number=f"{CASE_NUMBER_PREFIX}{sequence:03d}",
            applicant_profile_id=profile.id,
            service_type=ServiceType.STUDENT_PASS,
            status=CaseStatus.DRAFT,
            stage=CaseStage.PRE_SUBMISSION,
            created_by_actor_id=applicant.id,
        )
        session.add(case)
        session.flush()
        session.add(
            StudentPassCaseProfile(
                case_id=case.id,
                application_type=ApplicationType.NEW,
                institution_id=institution.id,
                programme_id=programme.id,
                institution_type=InstitutionType.IPTS,
                region_code="MY-10",
                applicant_location=ApplicantLocation.OUTSIDE_MALAYSIA,
                nationality_code="IDN",
                passport_expires_at=datetime(2031, 12, 31, tzinfo=UTC),
            )
        )
        DemoSessionService._record_transition(
            session,
            case,
            applicant,
            from_status=None,
            to_status=CaseStatus.DRAFT,
            reason="CASE_CREATED",
            action="CASE_CREATED",
        )
        return case

    @staticmethod
    def _withdraw_case(session: Session, case: ImmigrationCase, actor: Actor) -> None:
        previous = case.status
        case.status = CaseStatus.WITHDRAWN
        case.stage = CaseStage.CLOSED
        case.row_version += 1
        case.updated_at = datetime.now(UTC)
        DemoSessionService._record_transition(
            session,
            case,
            actor,
            from_status=previous,
            to_status=CaseStatus.WITHDRAWN,
            reason="DEMO_RESET",
            action="CASE_WITHDRAWN_FOR_DEMO_RESET",
        )

    @staticmethod
    def _record_transition(
        session: Session,
        case: ImmigrationCase,
        actor: Actor,
        *,
        from_status: CaseStatus | None,
        to_status: CaseStatus,
        reason: str,
        action: str,
    ) -> None:
        occurred_at = datetime.now(UTC)
        session.add_all(
            [
                CaseStatusHistory(
                    case_id=case.id,
                    from_status=from_status,
                    to_status=to_status,
                    reason_code=reason,
                    changed_by_actor_id=actor.id,
                    changed_at=occurred_at,
                ),
                CaseEvent(
                    case_id=case.id,
                    event_type=action,
                    event_payload={"status": to_status.value, "reason_code": reason},
                    occurred_at=occurred_at,
                    actor_id=actor.id,
                ),
                AuditEvent(
                    case_id=case.id,
                    actor_id=actor.id,
                    action=action,
                    entity_type="CASE",
                    entity_id=case.id,
                    before_summary=(
                        {"status": from_status.value} if from_status is not None else None
                    ),
                    after_summary={"status": to_status.value},
                    occurred_at=occurred_at,
                ),
            ]
        )

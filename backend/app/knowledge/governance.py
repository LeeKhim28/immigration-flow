from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import (
    ActorType,
    ApprovalDecision,
    KnowledgeSyncStatus,
    RuleSetVersionStatus,
)
from app.database.models import Actor, ApprovalEvent, AuditEvent, KnowledgeSyncRun, RuleSetVersion


def submit_for_review(
    session: Session, version_id: UUID, actor_id: UUID, now: datetime
) -> RuleSetVersion:
    _require_aware(now)
    version = session.scalar(
        select(RuleSetVersion).where(RuleSetVersion.id == version_id).with_for_update()
    )
    if version is None:
        raise ValueError("rule-set version not found")
    if version.status != RuleSetVersionStatus.DRAFT:
        raise ValueError("only draft releases can enter review")
    sync = session.get(KnowledgeSyncRun, version.knowledge_sync_run_id)
    if sync is None or sync.status != KnowledgeSyncStatus.SUCCEEDED:
        raise ValueError("release requires a successful knowledge synchronization")
    if session.get(Actor, actor_id) is None:
        raise ValueError("review actor not found")
    version.status = RuleSetVersionStatus.REVIEW
    session.add(
        AuditEvent(
            case_id=None,
            actor_id=actor_id,
            action="RULE_SET_SUBMITTED_FOR_REVIEW",
            entity_type="RULE_SET_VERSION",
            entity_id=version.id,
            after_summary={"status": "REVIEW"},
            occurred_at=now,
        )
    )
    session.flush()
    return version


def decide_release(
    session: Session,
    version_id: UUID,
    administrator_id: UUID,
    decision: ApprovalDecision,
    notes: str | None,
    now: datetime,
) -> ApprovalEvent:
    _require_aware(now)
    if notes is not None and len(notes) > 2000:
        raise ValueError("approval notes are limited to 2000 characters")
    admin = session.scalar(
        select(Actor).where(
            Actor.id == administrator_id, Actor.actor_type == ActorType.ADMINISTRATOR
        )
    )
    if admin is None:
        raise ValueError("administrator actor is required")
    version = session.scalar(
        select(RuleSetVersion).where(RuleSetVersion.id == version_id).with_for_update()
    )
    if version is None:
        raise ValueError("rule-set version not found")
    if version.status != RuleSetVersionStatus.REVIEW:
        raise ValueError("only releases in review can receive a decision")
    if (
        session.scalar(select(ApprovalEvent).where(ApprovalEvent.rule_set_version_id == version_id))
        is not None
    ):
        raise ValueError("release already has a final decision")
    event = ApprovalEvent(
        rule_set_version_id=version_id,
        decision=decision,
        decided_by_actor_id=administrator_id,
        decided_at=now,
        notes=notes,
    )
    session.add(event)
    session.add(
        AuditEvent(
            case_id=None,
            actor_id=administrator_id,
            action=f"RULE_SET_{decision.value}",
            entity_type="APPROVAL_EVENT",
            entity_id=version_id,
            after_summary={"decision": decision.value},
            occurred_at=now,
        )
    )
    session.flush()
    return event


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")

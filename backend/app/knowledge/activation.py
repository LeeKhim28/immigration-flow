from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import ApprovalDecision, KnowledgeSyncStatus, RuleSetVersionStatus
from app.database.models import ApprovalEvent, AuditEvent, KnowledgeSyncRun, RuleSetVersion


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
                activated += 1
            except Exception:
                failed += 1
        session.commit()
        return ActivationSummary(activated=activated, skipped=skipped, failed=failed)


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

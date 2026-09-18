from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.database.enums import ApprovalDecision, RuleSetVersionStatus
from app.knowledge.activation import display_release_status

NOW = datetime(2026, 9, 18, tzinfo=UTC)


def test_future_approved_release_is_derived_as_scheduled() -> None:
    version = SimpleNamespace(status=RuleSetVersionStatus.REVIEW, effective_at=NOW.replace(day=20))
    decision = SimpleNamespace(decision=ApprovalDecision.APPROVED)
    assert display_release_status(version, decision, NOW) == "SCHEDULED"


def test_rejected_release_is_not_scheduled() -> None:
    version = SimpleNamespace(status=RuleSetVersionStatus.REVIEW, effective_at=NOW)
    decision = SimpleNamespace(decision=ApprovalDecision.REJECTED)
    assert display_release_status(version, decision, NOW) == "REJECTED"


def test_activation_status_requires_timezone_aware_clock() -> None:
    version = SimpleNamespace(status=RuleSetVersionStatus.REVIEW, effective_at=NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        display_release_status(version, None, datetime(2026, 9, 18))

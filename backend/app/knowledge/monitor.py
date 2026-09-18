import difflib
from collections.abc import Callable
from datetime import datetime

from app.knowledge.contracts import (
    CheckError,
    MonitorBaseline,
    MonitorOutcome,
    MonitorResult,
    MonitorState,
    MonitorTrigger,
    RetrievedSource,
)
from app.knowledge.normalization import NormalizationError
from app.knowledge.url_safety import SourceRetrievalError, UnsafeSourceUrl

_MAX_CHANGE_SUMMARY_CHARS = 2000


def build_change_summary(
    previous: bytes, current: bytes, max_chars: int = _MAX_CHANGE_SUMMARY_CHARS
) -> str:
    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    previous_lines = previous.decode("utf-8", errors="replace").splitlines()
    current_lines = current.decode("utf-8", errors="replace").splitlines()
    changes = [
        line
        for line in difflib.unified_diff(previous_lines, current_lines, lineterm="")
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    summary = "\n".join(changes)
    return summary[:max_chars]


def check_source(
    baseline: MonitorBaseline,
    prior_state: MonitorState,
    trigger: MonitorTrigger,
    retrieve: Callable[[], RetrievedSource],
    now: datetime,
) -> MonitorResult:
    if prior_state.source_id != baseline.source_id:
        raise ValueError("prior_state source_id must match baseline source_id")

    try:
        retrieved = retrieve()
    except (UnsafeSourceUrl, SourceRetrievalError, NormalizationError) as error:
        return _failure_result(baseline, prior_state, trigger, error, now)

    comparison_hash = prior_state.last_comparable_hash or baseline.approved_hash
    outcome = (
        MonitorOutcome.UNCHANGED
        if retrieved.content_hash == comparison_hash
        else MonitorOutcome.CHANGED
    )
    next_state = MonitorState(
        source_id=baseline.source_id,
        last_outcome=outcome,
        consecutive_failures=0,
        last_comparable_hash=retrieved.content_hash,
    )
    summary = None
    if outcome is MonitorOutcome.CHANGED:
        summary = (
            f"Normalized content hash changed from {comparison_hash} to {retrieved.content_hash}."
        )
    return MonitorResult(
        source_id=baseline.source_id,
        outcome=outcome,
        previous_hash=comparison_hash,
        current_hash=retrieved.content_hash,
        change_summary=summary,
        error=None,
        next_state=next_state,
        should_notify=outcome is MonitorOutcome.CHANGED,
    )


def _failure_result(
    baseline: MonitorBaseline,
    prior_state: MonitorState,
    trigger: MonitorTrigger,
    error: UnsafeSourceUrl | SourceRetrievalError | NormalizationError,
    now: datetime,
) -> MonitorResult:
    failure_count = prior_state.consecutive_failures
    if trigger is MonitorTrigger.SCHEDULED:
        failure_count += 1

    outcome = prior_state.last_outcome
    if trigger is MonitorTrigger.SCHEDULED and failure_count >= 3:
        outcome = MonitorOutcome.BLOCKED

    next_state = MonitorState(
        source_id=baseline.source_id,
        last_outcome=outcome,
        consecutive_failures=failure_count,
        last_comparable_hash=prior_state.last_comparable_hash,
    )
    return MonitorResult(
        source_id=baseline.source_id,
        outcome=outcome,
        previous_hash=prior_state.last_comparable_hash,
        current_hash=None,
        change_summary=None,
        error=CheckError(
            code=_error_code(error),
            public_message="Official source retrieval could not be completed.",
            checked_at=now,
        ),
        next_state=next_state,
        should_notify=outcome is MonitorOutcome.BLOCKED,
    )


def _error_code(error: UnsafeSourceUrl | SourceRetrievalError | NormalizationError) -> str:
    if isinstance(error, UnsafeSourceUrl):
        return "UNSAFE_SOURCE_URL"
    if isinstance(error, NormalizationError):
        return "SOURCE_NORMALIZATION_FAILED"
    return "SOURCE_RETRIEVAL_FAILED"

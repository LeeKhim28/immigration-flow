from datetime import UTC, datetime

import pytest

from app.knowledge.contracts import (
    MonitorBaseline,
    MonitorOutcome,
    MonitorState,
    MonitorTrigger,
    RetrievedSource,
)
from app.knowledge.monitor import build_change_summary, check_source
from app.knowledge.normalization import normalize_html
from app.knowledge.url_safety import SourceRetrievalError

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _baseline() -> MonitorBaseline:
    return MonitorBaseline(
        source_id="MY-TEST-SOURCE",
        canonical_url="https://official.example/policy",
        allowed_hosts=("official.example",),
        selector=None,
        strategy_version=1,
        approved_hash="a" * 64,
        captured_at=NOW,
        git_commit_sha="b" * 40,
    )


def _state(
    outcome: MonitorOutcome, failures: int, content_hash: str | None = "a" * 64
) -> MonitorState:
    return MonitorState(
        source_id="MY-TEST-SOURCE",
        last_outcome=outcome,
        consecutive_failures=failures,
        last_comparable_hash=content_hash,
    )


def _source(content_hash: str) -> RetrievedSource:
    return RetrievedSource(
        final_url="https://official.example/policy",
        retrieved_at=NOW,
        normalized_content="Public policy text",
        content_hash=content_hash,
    )


@pytest.mark.parametrize(
    ("prior", "trigger", "result_hash", "expected_outcome", "expected_failures", "notify"),
    [
        (
            _state(MonitorOutcome.CHANGED, 2),
            MonitorTrigger.SCHEDULED,
            "a" * 64,
            MonitorOutcome.UNCHANGED,
            0,
            False,
        ),
        (
            _state(MonitorOutcome.UNCHANGED, 2),
            MonitorTrigger.SCHEDULED,
            "c" * 64,
            MonitorOutcome.CHANGED,
            0,
            True,
        ),
        (
            _state(MonitorOutcome.UNCHANGED, 0),
            MonitorTrigger.SCHEDULED,
            "a" * 64,
            MonitorOutcome.UNCHANGED,
            0,
            False,
        ),
    ],
)
def test_successful_check_classifies_hash_and_resets_failure_streak(
    prior: MonitorState,
    trigger: MonitorTrigger,
    result_hash: str,
    expected_outcome: MonitorOutcome,
    expected_failures: int,
    notify: bool,
) -> None:
    result = check_source(_baseline(), prior, trigger, lambda: _source(result_hash), NOW)

    assert result.outcome is expected_outcome
    assert result.next_state.consecutive_failures == expected_failures
    assert result.should_notify is notify
    assert result.error is None


@pytest.mark.parametrize(
    ("prior_failures", "trigger", "expected_outcome", "expected_failures", "notify"),
    [
        (0, MonitorTrigger.SCHEDULED, MonitorOutcome.UNCHANGED, 1, False),
        (1, MonitorTrigger.SCHEDULED, MonitorOutcome.UNCHANGED, 2, False),
        (2, MonitorTrigger.SCHEDULED, MonitorOutcome.BLOCKED, 3, True),
        (2, MonitorTrigger.MANUAL, MonitorOutcome.UNCHANGED, 2, False),
    ],
)
def test_typed_retrieval_failure_only_blocks_after_third_scheduled_failure(
    prior_failures: int,
    trigger: MonitorTrigger,
    expected_outcome: MonitorOutcome,
    expected_failures: int,
    notify: bool,
) -> None:
    def fail() -> RetrievedSource:
        raise SourceRetrievalError("request failed")

    result = check_source(
        _baseline(),
        _state(MonitorOutcome.UNCHANGED, prior_failures),
        trigger,
        fail,
        NOW,
    )

    assert result.outcome is expected_outcome
    assert result.next_state.consecutive_failures == expected_failures
    assert result.should_notify is notify
    assert result.error is not None
    assert result.error.code == "SOURCE_RETRIEVAL_FAILED"


def test_unexpected_retrieval_error_is_not_converted_into_monitor_state() -> None:
    def fail() -> RetrievedSource:
        raise RuntimeError("programming defect")

    with pytest.raises(RuntimeError, match="programming defect"):
        check_source(
            _baseline(), _state(MonitorOutcome.UNCHANGED, 0), MonitorTrigger.SCHEDULED, fail, NOW
        )


def test_change_summary_includes_only_normalized_public_policy_text() -> None:
    previous = normalize_html(
        b"<main id='policy'>Old public policy</main><script>removed script</script>",
        "#policy",
        1,
    )
    current = normalize_html(
        b"<main id='policy'>New public policy</main><div class='cookie-banner'>cookie text</div>",
        "#policy",
        1,
    )

    summary = build_change_summary(previous, current)

    assert "Old public policy" in summary
    assert "New public policy" in summary
    assert "removed script" not in summary
    assert "cookie text" not in summary


def test_change_summary_is_limited_to_requested_length() -> None:
    summary = build_change_summary(b"old " * 1000, b"new " * 1000, max_chars=2000)

    assert len(summary) <= 2000

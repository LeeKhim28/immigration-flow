import pytest

from app.knowledge.contracts import MonitorOutcome, MonitorState


def test_monitor_outcomes_exclude_fetch_failed() -> None:
    assert {item.value for item in MonitorOutcome} == {
        "UNCHANGED",
        "CHANGED",
        "BLOCKED",
    }


def test_monitor_state_round_trips_json_data() -> None:
    state = MonitorState(
        source_id="MY-TEST-SOURCE",
        last_outcome=MonitorOutcome.UNCHANGED,
        consecutive_failures=2,
        last_comparable_hash="a" * 64,
    )

    assert MonitorState.from_dict(state.to_dict()) == state


@pytest.mark.parametrize(
    "value",
    [
        {
            "source_id": "MY-TEST-SOURCE",
            "last_outcome": "UNCHANGED",
            "consecutive_failures": -1,
            "last_comparable_hash": None,
        },
        {
            "source_id": "MY-TEST-SOURCE",
            "last_outcome": "FETCH_FAILED",
            "consecutive_failures": 0,
            "last_comparable_hash": None,
        },
        {
            "source_id": 17,
            "last_outcome": "UNCHANGED",
            "consecutive_failures": 0,
            "last_comparable_hash": None,
        },
        {
            "source_id": "MY-TEST-SOURCE",
            "last_outcome": "UNCHANGED",
            "consecutive_failures": 0,
            "last_comparable_hash": "A" * 64,
        },
    ],
)
def test_monitor_state_rejects_invalid_persisted_data(value: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        MonitorState.from_dict(value)

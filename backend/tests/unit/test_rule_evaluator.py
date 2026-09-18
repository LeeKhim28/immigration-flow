import pytest

from app.domains.evaluations.service import condition_matches


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ({"fact": "x", "operator": "eq", "value": 3}, True),
        ({"fact": "x", "operator": "in", "value": [2, 3]}, True),
        ({"fact": "x", "operator": "present", "value": None}, True),
        ({"fact": "missing", "operator": "absent", "value": None}, True),
        ({"fact": "missing", "operator": "neq", "value": True}, True),
        ({"all": [{"fact": "x", "operator": "eq", "value": 3}]}, True),
        ({"any": [{"fact": "x", "operator": "eq", "value": 4}]}, False),
        ({"fact": "x", "operator": "dataset_contains", "value": "demo"}, True),
    ],
)
def test_condition_matches(condition: dict[str, object], expected: bool) -> None:
    facts = {"x": 3}
    datasets = {"demo": [3]}
    assert condition_matches(condition, facts, datasets) is expected


def test_unavailable_numeric_fact_does_not_match_threshold() -> None:
    assert not condition_matches({"fact": "missing", "operator": "gte", "value": 31}, {}, {})

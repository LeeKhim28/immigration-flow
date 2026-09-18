import pytest

from app.knowledge.dsl import validate_requirement_condition, validate_rule_condition


def test_requirement_condition_accepts_allowlisted_forms() -> None:
    assert validate_requirement_condition("always") == "always"
    assert (
        validate_requirement_condition(
            {"field": "applicant.nationality_code", "operator": "in", "value": ["IR"]}
        )["operator"]
        == "in"
    )


@pytest.mark.parametrize(
    "condition",
    [
        {"field": "a", "operator": "eval", "value": "x"},
        {"field": "a", "operator": "eq", "value": object()},
        {"field": "a", "operator": "eq"},
        {"all": [], "field": "a", "operator": "eq", "value": True},
    ],
)
def test_requirement_condition_rejects_unsafe_or_malformed_forms(condition: object) -> None:
    with pytest.raises(ValueError):
        validate_requirement_condition(condition)


def test_rule_condition_accepts_nested_allowlisted_logic() -> None:
    condition = {
        "all": [
            {"fact": "applicant.nationality_code", "operator": "eq", "value": "SD"},
            {"fact": "documents.passport_all_pages.present", "operator": "neq", "value": True},
        ]
    }
    assert validate_rule_condition(condition)["all"][0]["operator"] == "eq"


@pytest.mark.parametrize(
    "condition",
    [
        {"any": [{"fact": "a", "operator": "shell", "value": "x"}]},
        {"all": [{"fact": "a", "operator": "eq", "value": object()}]},
        {"fact": "a", "operator": "eq", "value": True, "extra": 1},
    ],
)
def test_rule_condition_rejects_unknown_operator_or_non_json_value(condition: object) -> None:
    with pytest.raises(ValueError):
        validate_rule_condition(condition)


def test_rule_condition_rejects_excessive_depth() -> None:
    condition: object = {"fact": "a", "operator": "eq", "value": True}
    for _ in range(9):
        condition = {"all": [condition]}
    with pytest.raises(ValueError, match="depth"):
        validate_rule_condition(condition, max_depth=8)

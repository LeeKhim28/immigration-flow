from collections.abc import Mapping

REQUIREMENT_OPERATORS = frozenset({"eq", "in", "in_dataset"})
RULE_OPERATORS = frozenset(
    {"eq", "neq", "in", "not_in", "gte", "lte", "present", "absent", "dataset_contains"}
)


def validate_requirement_condition(value: object) -> str | dict[str, object]:
    if value == "always":
        return "always"
    if not isinstance(value, Mapping):
        raise ValueError("requirement condition must be 'always' or an object")
    if set(value) != {"field", "operator", "value"}:
        raise ValueError("requirement condition has unknown or missing keys")
    field, operator = value["field"], value["operator"]
    if not isinstance(field, str) or not field:
        raise ValueError("requirement condition field must be non-empty text")
    if operator not in REQUIREMENT_OPERATORS:
        raise ValueError("unsupported requirement condition operator")
    _require_json(value["value"])
    return dict(value)


def validate_rule_condition(value: object, *, max_depth: int = 8) -> dict[str, object]:
    _validate_rule_node(value, depth=0, max_depth=max_depth)
    if not isinstance(value, Mapping):
        raise ValueError("rule condition node must be an object")
    return {str(key): item for key, item in value.items()}


def _validate_rule_node(value: object, *, depth: int, max_depth: int) -> None:
    if depth > max_depth:
        raise ValueError("rule condition exceeds maximum depth")
    if not isinstance(value, Mapping):
        raise ValueError("rule condition node must be an object")
    keys = set(value)
    if keys == {"all"} or keys == {"any"}:
        children = value[next(iter(keys))]
        if not isinstance(children, list) or not children:
            raise ValueError("logical condition must contain a non-empty list")
        for child in children:
            _validate_rule_node(child, depth=depth + 1, max_depth=max_depth)
        return
    if keys not in ({"fact", "operator"}, {"fact", "operator", "value"}):
        raise ValueError("rule condition has unknown or missing keys")
    fact, operator = value["fact"], value["operator"]
    if not isinstance(fact, str) or not fact:
        raise ValueError("rule condition fact must be non-empty text")
    if operator not in RULE_OPERATORS:
        raise ValueError("unsupported rule condition operator")
    if operator in {"present", "absent"}:
        if "value" in value and value["value"] is not None:
            raise ValueError("presence operators do not accept a non-null value")
        return
    if "value" not in value:
        raise ValueError("binary rule condition requires a value")
    _require_json(value["value"])


def _require_json(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for item in value:
            _require_json(item)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be text")
            _require_json(item)
        return
    raise ValueError(f"value of type {type(value).__name__} is not JSON-safe")

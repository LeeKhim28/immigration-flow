from app.knowledge.fingerprints import (
    canonical_fingerprint,
    requirement_fingerprint,
    rule_fingerprint,
    rule_set_fingerprint,
)


def test_mapping_order_does_not_change_canonical_fingerprint() -> None:
    assert canonical_fingerprint({"b": 2, "a": 1}) == canonical_fingerprint({"a": 1, "b": 2})


def test_requirement_provenance_order_does_not_change_fingerprint() -> None:
    requirement = {"id": "REQ", "statement": "Provide a document.", "stage": "pre_submission"}
    first = [{"source_id": "B", "locator": "2"}, {"source_id": "A", "locator": "1"}]
    second = list(reversed(first))
    assert requirement_fingerprint(requirement, first) == requirement_fingerprint(
        requirement, second
    )


def test_requirement_semantic_fields_change_fingerprint() -> None:
    base = {"id": "REQ", "statement": "Provide a document.", "stage": "pre_submission"}
    changed = {**base, "stage": "endorsement"}
    assert requirement_fingerprint(base, []) != requirement_fingerprint(changed, [])


def test_rule_and_release_fingerprints_include_dependencies() -> None:
    rule = {"id": "RULE", "description": "Check documents.", "priority": 1}
    assert rule_fingerprint(rule, [{"id": "REQ", "fingerprint": "a"}]) != rule_fingerprint(
        rule, [{"id": "REQ", "fingerprint": "b"}]
    )
    release = {"id": "RELEASE", "default_outcome": "pass"}
    assert rule_set_fingerprint(release, ["a"]) != rule_set_fingerprint(release, ["b"])

import hashlib
import json
from collections.abc import Mapping, Sequence


def canonical_fingerprint(value: Mapping[str, object]) -> str:
    payload = json.dumps(
        _canonical(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def requirement_fingerprint(
    requirement: Mapping[str, object], provenance: Sequence[Mapping[str, object]]
) -> str:
    return canonical_fingerprint(
        {"requirement": requirement, "provenance": sorted(provenance, key=_sort_key)}
    )


def rule_fingerprint(
    rule: Mapping[str, object], requirement_versions: Sequence[Mapping[str, object]]
) -> str:
    return canonical_fingerprint(
        {
            "rule": rule,
            "requirement_versions": sorted(requirement_versions, key=_sort_key),
        }
    )


def rule_set_fingerprint(release: Mapping[str, object], rule_fingerprints: Sequence[str]) -> str:
    return canonical_fingerprint(
        {"release": release, "rule_fingerprints": sorted(rule_fingerprints)}
    )


def _sort_key(value: Mapping[str, object]) -> str:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key).strip(): _canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError(f"cannot fingerprint value of type {type(value).__name__}")

import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from app.knowledge.contracts import MonitorBaseline

_OFFICIAL_SOURCES_DIRECTORY = Path("data/official-sources")
_REGISTRY_FILE = "registry.yaml"
_BASELINES_FILE = "monitoring-baselines.yaml"
_SCHEMA_FILE = "monitoring-baseline.schema.json"
_REQUIREMENT_FILE = Path("data/official-sources/extracts/student-pass-v1.requirements.yaml")
_RULE_FILE = Path("data/rules/student-pass-v1.yaml")
_REQUIREMENT_SCHEMA_FILE = Path("data/official-sources/extracts/requirement-set.schema.json")
_RULE_SCHEMA_FILE = Path("data/rules/rule-set.schema.json")
_DATASET_FILE = Path("data/official-sources/extracts/sev-required-countries.yaml")
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True, slots=True)
class KnowledgeBundle:
    git_commit_sha: str
    registry: Mapping[str, object]
    requirements: Mapping[str, object]
    rule_set: Mapping[str, object]
    datasets: tuple[Mapping[str, object], ...]


def load_monitor_baselines(root: Path) -> Sequence[MonitorBaseline]:
    """Load reviewed, schema-valid monitor baselines from a repository checkout."""
    directory = root / _OFFICIAL_SOURCES_DIRECTORY
    registry = _load_mapping(directory / _REGISTRY_FILE)
    baseline_document = _load_mapping(directory / _BASELINES_FILE)
    schema = _load_mapping(directory / _SCHEMA_FILE)
    _validate_schema(baseline_document, schema)

    reviewed_sources = _reviewed_source_urls(registry)
    records = baseline_document["baselines"]
    if not isinstance(records, list):
        raise ValueError("monitoring baselines must be a list")

    baselines: list[MonitorBaseline] = []
    seen_ids: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("monitoring baseline must be an object")
        source_id = _required_text(record, "source_id")
        if source_id in seen_ids:
            raise ValueError(f"duplicate source_id in monitoring baselines: {source_id}")
        seen_ids.add(source_id)
        registered_url = reviewed_sources.get(source_id)
        if registered_url is None:
            if _registry_contains_source(registry, source_id):
                raise ValueError(f"monitoring source_id must be reviewed: {source_id}")
            raise ValueError(f"unknown source_id in monitoring baselines: {source_id}")

        canonical_url = _required_text(record, "canonical_url")
        if canonical_url != registered_url:
            raise ValueError(f"canonical_url must match registry for source_id: {source_id}")
        parsed_url = urlparse(canonical_url)
        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise ValueError(f"canonical_url must be HTTPS for source_id: {source_id}")

        allowed_hosts = _hostnames(record.get("allowed_hosts"))
        if parsed_url.hostname.lower() not in allowed_hosts:
            raise ValueError(
                f"allowed_hosts must include canonical URL host for source_id: {source_id}"
            )
        selector = record.get("selector")
        if selector is not None and not isinstance(selector, str):
            raise ValueError(f"selector must be text or null for source_id: {source_id}")

        baselines.append(
            MonitorBaseline(
                source_id=source_id,
                canonical_url=canonical_url,
                allowed_hosts=allowed_hosts,
                selector=selector,
                strategy_version=_required_int(record, "strategy_version"),
                approved_hash=_required_text(record, "approved_hash"),
                captured_at=_parse_datetime(_required_text(record, "captured_at"), "captured_at"),
                git_commit_sha=_required_text(record, "git_commit_sha"),
            )
        )
    return tuple(baselines)


def load_knowledge_bundle(root: Path, git_sha: str) -> KnowledgeBundle:
    if _SHA_PATTERN.fullmatch(git_sha) is None:
        raise ValueError("git SHA must be lowercase hexadecimal with 40 to 64 characters")
    head, dirty_files = _git_state(root)
    if dirty_files:
        raise ValueError("repository checkout is dirty")
    if head != git_sha:
        raise ValueError("provided git SHA does not match repository HEAD")

    sources = _load_mapping(root / _OFFICIAL_SOURCES_DIRECTORY / _REGISTRY_FILE)
    requirements = _load_mapping(root / _REQUIREMENT_FILE)
    rule_set = _load_mapping(root / _RULE_FILE)
    requirement_schema = _load_mapping(root / _REQUIREMENT_SCHEMA_FILE)
    rule_schema = _load_mapping(root / _RULE_SCHEMA_FILE)
    _validate_schema(requirements, requirement_schema)
    _validate_schema(rule_set, rule_schema)
    _validate_bundle_references(sources, requirements, rule_set)
    datasets = (_load_mapping(root / _DATASET_FILE),)
    return KnowledgeBundle(
        git_commit_sha=git_sha,
        registry=sources,
        requirements=requirements,
        rule_set=rule_set,
        datasets=datasets,
    )


def _git_state(root: Path) -> tuple[str, str]:
    try:
        head_result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        status_result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("could not inspect repository Git state") from error
    return head_result.stdout.strip(), status_result.stdout


def _validate_bundle_references(
    registry: Mapping[str, object],
    requirements: Mapping[str, object],
    rule_set: Mapping[str, object],
) -> None:
    source_records = registry.get("sources")
    requirement_records = requirements.get("requirements")
    rule_records = rule_set.get("rules")
    if not isinstance(source_records, list) or not isinstance(requirement_records, list):
        raise ValueError("knowledge bundle records must be lists")
    if not isinstance(rule_records, list):
        raise ValueError("rule set records must be a list")

    sources: dict[str, Mapping[str, object]] = {}
    for source in source_records:
        if not isinstance(source, Mapping):
            raise ValueError("source registry entry must be an object")
        source_id = _required_text(source, "id")
        if source_id in sources:
            raise ValueError(f"duplicate source ID: {source_id}")
        sources[source_id] = source

    requirements_by_id: dict[str, Mapping[str, object]] = {}
    for requirement in requirement_records:
        if not isinstance(requirement, Mapping):
            raise ValueError("requirement entry must be an object")
        requirement_id = _required_text(requirement, "id")
        if requirement_id in requirements_by_id:
            raise ValueError(f"duplicate requirement ID: {requirement_id}")
        requirements_by_id[requirement_id] = requirement
        for citation in _required_list(requirement, "sources"):
            if not isinstance(citation, Mapping):
                raise ValueError(f"invalid source citation in {requirement_id}")
            source_id = _required_text(citation, "source_id")
            if source_id not in sources:
                raise ValueError(f"unknown source ID {source_id} in {requirement_id}")

    if requirements.get("version") != rule_set.get("version"):
        raise ValueError("requirement and rule versions differ")
    seen_priorities: set[int] = set()
    rule_ids: set[str] = set()
    for rule in rule_records:
        if not isinstance(rule, Mapping):
            raise ValueError("rule entry must be an object")
        rule_id = _required_text(rule, "id")
        if rule_id in rule_ids:
            raise ValueError(f"duplicate rule ID: {rule_id}")
        rule_ids.add(rule_id)
        priority = rule.get("priority")
        if not isinstance(priority, int) or priority in seen_priorities:
            raise ValueError(f"duplicate or invalid rule priority in {rule_id}")
        seen_priorities.add(priority)
        for requirement_id in _required_text_list(rule, "requirement_ids"):
            if requirement_id not in requirements_by_id:
                raise ValueError(f"unknown requirement ID {requirement_id} in {rule_id}")
        for source_id in _required_text_list(rule, "source_ids"):
            if source_id not in sources:
                raise ValueError(f"unknown source ID {source_id} in {rule_id}")


def _required_list(record: Mapping[str, object], field_name: str) -> list[object]:
    value = record.get(field_name)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list")
    return value


def _required_text_list(record: Mapping[str, object], field_name: str) -> list[str]:
    values = _required_list(record, field_name)
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"{field_name} must contain only non-empty text")
    return [value for value in values if isinstance(value, str)]


def _load_mapping(path: Path) -> Mapping[str, object]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"could not read {path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"could not parse YAML at {path}") from error
    if not isinstance(document, Mapping):
        raise ValueError(f"{path} must contain an object")
    return document


def _validate_schema(document: Mapping[str, object], schema: Mapping[str, object]) -> None:
    try:
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        validator.validate(document)
    except Exception as error:  # jsonschema has several public validation error types.
        raise ValueError("monitoring baselines do not satisfy their schema") from error


def _reviewed_source_urls(registry: Mapping[str, object]) -> dict[str, str]:
    sources = registry.get("sources")
    if not isinstance(sources, list):
        raise ValueError("source registry must contain sources")
    result: dict[str, str] = {}
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("source registry entry must be an object")
        if source.get("status") == "reviewed":
            result[_required_text(source, "id")] = _required_text(source, "canonical_url")
    return result


def _registry_contains_source(registry: Mapping[str, object], source_id: str) -> bool:
    sources = registry.get("sources")
    return isinstance(sources, list) and any(
        isinstance(source, Mapping) and source.get("id") == source_id for source in sources
    )


def _hostnames(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(host, str) for host in value):
        raise ValueError("allowed_hosts must be a non-empty list of host names")
    return tuple(host.lower() for host in value)


def _required_text(record: Mapping[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_int(record: Mapping[str, object], field_name: str) -> int:
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO 8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def load_repository_document(root: Path, relative_path: Path) -> Mapping[str, object]:
    """Read a YAML document from a repository path for later sync stages."""
    return _load_mapping(root / relative_path)


def load_json_document(root: Path, relative_path: Path) -> Mapping[str, object]:
    try:
        document = json.loads((root / relative_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read JSON document at {relative_path}") from error
    if not isinstance(document, Mapping):
        raise ValueError(f"JSON document at {relative_path} must be an object")
    return document

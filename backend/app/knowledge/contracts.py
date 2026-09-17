import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_GIT_SHA_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_MAX_PUBLIC_ERROR_MESSAGE_LENGTH = 500


class MonitorOutcome(StrEnum):
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    BLOCKED = "BLOCKED"


class MonitorTrigger(StrEnum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


def _require_non_empty_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class CheckError:
    code: str
    public_message: str
    checked_at: datetime

    def __post_init__(self) -> None:
        _require_non_empty_text(self.code, "code")
        _require_non_empty_text(self.public_message, "public_message")
        if len(self.public_message) > _MAX_PUBLIC_ERROR_MESSAGE_LENGTH:
            raise ValueError("public_message must be at most 500 characters")
        _require_aware_datetime(self.checked_at, "checked_at")


@dataclass(frozen=True, slots=True)
class MonitorBaseline:
    source_id: str
    canonical_url: str
    allowed_hosts: tuple[str, ...]
    selector: str | None
    strategy_version: int
    approved_hash: str
    captured_at: datetime
    git_commit_sha: str

    def __post_init__(self) -> None:
        _require_non_empty_text(self.source_id, "source_id")
        _require_non_empty_text(self.canonical_url, "canonical_url")
        if not self.allowed_hosts or any(not host.strip() for host in self.allowed_hosts):
            raise ValueError("allowed_hosts must contain non-empty host names")
        if self.selector is not None:
            _require_non_empty_text(self.selector, "selector")
        if self.strategy_version < 1:
            raise ValueError("strategy_version must be positive")
        _require_sha256(self.approved_hash, "approved_hash")
        _require_aware_datetime(self.captured_at, "captured_at")
        if _GIT_SHA_PATTERN.fullmatch(self.git_commit_sha) is None:
            raise ValueError("git_commit_sha must be a lowercase 40- or 64-character Git SHA")


@dataclass(frozen=True, slots=True)
class MonitorState:
    source_id: str
    last_outcome: MonitorOutcome
    consecutive_failures: int
    last_comparable_hash: str | None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.source_id, "source_id")
        if self.consecutive_failures < 0:
            raise ValueError("consecutive_failures must be a non-negative integer")
        if self.last_comparable_hash is not None:
            _require_sha256(self.last_comparable_hash, "last_comparable_hash")

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "last_outcome": self.last_outcome.value,
            "consecutive_failures": self.consecutive_failures,
            "last_comparable_hash": self.last_comparable_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> MonitorState:
        source_id = value.get("source_id")
        failures = value.get("consecutive_failures")
        content_hash = value.get("last_comparable_hash")
        outcome = value.get("last_outcome")

        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_id must be a non-empty string")
        if not isinstance(failures, int) or isinstance(failures, bool) or failures < 0:
            raise ValueError("consecutive_failures must be a non-negative integer")
        if content_hash is not None and not isinstance(content_hash, str):
            raise ValueError("last_comparable_hash must be lowercase SHA-256")
        if not isinstance(outcome, str):
            raise ValueError("last_outcome must be a known monitor outcome")

        try:
            parsed_outcome = MonitorOutcome(outcome)
        except ValueError as error:
            raise ValueError("last_outcome must be a known monitor outcome") from error

        return cls(
            source_id=source_id,
            last_outcome=parsed_outcome,
            consecutive_failures=failures,
            last_comparable_hash=content_hash,
        )


@dataclass(frozen=True, slots=True)
class RetrievedSource:
    final_url: str
    retrieved_at: datetime
    normalized_content: str
    content_hash: str

    def __post_init__(self) -> None:
        _require_non_empty_text(self.final_url, "final_url")
        _require_aware_datetime(self.retrieved_at, "retrieved_at")
        _require_sha256(self.content_hash, "content_hash")


@dataclass(frozen=True, slots=True)
class MonitorResult:
    source_id: str
    outcome: MonitorOutcome
    previous_hash: str | None
    current_hash: str | None
    change_summary: str | None
    error: CheckError | None
    next_state: MonitorState
    should_notify: bool

    def __post_init__(self) -> None:
        _require_non_empty_text(self.source_id, "source_id")
        if self.previous_hash is not None:
            _require_sha256(self.previous_hash, "previous_hash")
        if self.current_hash is not None:
            _require_sha256(self.current_hash, "current_hash")
        if self.next_state.source_id != self.source_id:
            raise ValueError("next_state source_id must match source_id")


@dataclass(frozen=True, slots=True)
class IssueDraft:
    title: str
    body: str
    labels: tuple[str, ...]
    dedupe_marker: str

    def __post_init__(self) -> None:
        _require_non_empty_text(self.title, "title")
        _require_non_empty_text(self.body, "body")
        _require_non_empty_text(self.dedupe_marker, "dedupe_marker")
        if not self.labels or any(not label.strip() for label in self.labels):
            raise ValueError("labels must contain non-empty labels")

from collections.abc import Mapping
from typing import Protocol

import httpx

from app.knowledge.contracts import IssueDraft, MonitorOutcome, MonitorResult

_API_ROOT = "https://api.github.com"
_MONITOR_LABEL = "source-monitor"
_OUTCOME_LABELS = {
    MonitorOutcome.CHANGED: "source-changed",
    MonitorOutcome.BLOCKED: "source-blocked",
}


class ReviewIssueGateway(Protocol):
    def ensure_labels(self) -> None: ...

    def upsert(self, result: MonitorResult) -> None: ...


class GitHubIssueGateway:
    LABELS = (_MONITOR_LABEL, "source-changed", "source-blocked")

    def __init__(self, repo: str, token: str, client: httpx.Client) -> None:
        owner, separator, name = repo.partition("/")
        if not separator or not owner or not name or "/" in name:
            raise ValueError("repo must be formatted as owner/repository")
        if not token:
            raise ValueError("token must be non-empty")
        self._base_url = f"{_API_ROOT}/repos/{owner}/{name}"
        self._client = client
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def ensure_labels(self) -> None:
        existing = {
            item.get("name")
            for item in self._get_json("/labels", params={"per_page": "100"})
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        for label in self.LABELS:
            if label not in existing:
                self._request("POST", "/labels", json={"name": label})

    def upsert(self, result: MonitorResult) -> None:
        draft = _issue_draft(result)
        open_issues = self._get_json("/issues", params={"state": "open", "per_page": "100"})
        issue_number = next(
            (
                item.get("number")
                for item in open_issues
                if isinstance(item, dict)
                and isinstance(item.get("number"), int)
                and isinstance(item.get("body"), str)
                and draft.dedupe_marker in item["body"]
            ),
            None,
        )
        payload = {"title": draft.title, "body": draft.body, "labels": list(draft.labels)}
        if issue_number is None:
            self._request("POST", "/issues", json=payload)
        else:
            self._request("PATCH", f"/issues/{issue_number}", json=payload)

    def _get_json(self, path: str, *, params: dict[str, str]) -> list[object]:
        response = self._request("GET", path, params=params)
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("GitHub API returned an unexpected response")
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        response = self._client.request(
            method,
            f"{self._base_url}{path}",
            headers=self._headers,
            params=params,
            json=json,
            follow_redirects=False,
        )
        response.raise_for_status()
        return response


class CollectingIssueGateway:
    """No-network gateway used by local dry-runs and unit tests."""

    def __init__(self) -> None:
        self.operations: tuple[str, ...] = ()

    def ensure_labels(self) -> None:
        self.operations += ("ensure_labels",)

    def upsert(self, result: MonitorResult) -> None:
        self.operations += (f"upsert:{result.source_id}:{result.outcome.value}",)


def _issue_draft(result: MonitorResult) -> IssueDraft:
    try:
        outcome_label = _OUTCOME_LABELS[result.outcome]
    except KeyError as error:
        raise ValueError(
            "only changed or blocked monitor results can create review issues"
        ) from error

    marker = f"<!-- immigration-flow-source:{result.source_id} -->"
    lines = [
        marker,
        f"## Official source monitoring: {result.source_id}",
        "",
        f"Outcome: `{result.outcome.value}`",
        f"Previous normalized hash: `{result.previous_hash or 'unavailable'}`",
        f"Observed normalized hash: `{result.current_hash or 'unavailable'}`",
    ]
    if result.change_summary:
        lines.extend(["", "### Sanitized change summary", "", result.change_summary])
    if result.error:
        lines.extend(
            [
                "",
                f"Check error: `{result.error.code}` at `{result.error.checked_at.isoformat()}`",
                result.error.public_message,
            ]
        )
    lines.extend(
        [
            "",
            "Review the official source and submit a reviewed repository change if requirements, "
            "rules, or the monitoring baseline need updating.",
        ]
    )
    return IssueDraft(
        title=f"Review official source: {result.source_id}",
        body="\n".join(lines),
        labels=(_MONITOR_LABEL, outcome_label),
        dedupe_marker=marker,
    )

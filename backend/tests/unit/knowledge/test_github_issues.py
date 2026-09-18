import json
from datetime import UTC, datetime

import httpx

from app.knowledge.contracts import MonitorOutcome, MonitorResult, MonitorState
from app.knowledge.github_issues import CollectingIssueGateway, GitHubIssueGateway

NOW = datetime(2026, 9, 17, tzinfo=UTC)
TOKEN = "test-token-that-must-not-enter-an-issue"
MARKER = "<!-- immigration-flow-source:MY-TEST-SOURCE -->"


def _result(outcome: MonitorOutcome = MonitorOutcome.CHANGED) -> MonitorResult:
    return MonitorResult(
        source_id="MY-TEST-SOURCE",
        outcome=outcome,
        previous_hash="a" * 64,
        current_hash="b" * 64 if outcome is MonitorOutcome.CHANGED else None,
        change_summary="- Previous public policy\n+ Current public policy",
        error=None,
        next_state=MonitorState(
            source_id="MY-TEST-SOURCE",
            last_outcome=outcome,
            consecutive_failures=0,
            last_comparable_hash="b" * 64,
        ),
        should_notify=True,
    )


def test_gateway_creates_only_missing_required_labels() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[{"name": "source-monitor"}])
        return httpx.Response(201, json={"name": json.loads(request.content)["name"]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    GitHubIssueGateway("acme/flow", TOKEN, client).ensure_labels()

    created = [
        json.loads(request.content)["name"] for request in requests if request.method == "POST"
    ]
    assert created == ["source-changed", "source-blocked"]


def test_gateway_updates_one_open_issue_matched_by_hidden_source_marker() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET" and request.url.path.endswith("/labels"):
            return httpx.Response(200, json=[{"name": name} for name in GitHubIssueGateway.LABELS])
        if request.method == "GET" and request.url.path.endswith("/issues"):
            return httpx.Response(200, json=[{"number": 7, "body": f"Existing issue\n{MARKER}"}])
        if request.method == "PATCH" and request.url.path.endswith("/issues/7"):
            return httpx.Response(200, json={"number": 7})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    GitHubIssueGateway("acme/flow", TOKEN, client).upsert(_result())

    patch_request = next(request for request in requests if request.method == "PATCH")
    payload = json.loads(patch_request.content)
    assert payload["labels"] == ["source-monitor", "source-changed"]
    assert MARKER in payload["body"]
    assert TOKEN not in patch_request.url.raw_path.decode()
    assert TOKEN not in patch_request.content.decode()
    assert "cookie" not in {name.lower() for name in patch_request.headers}
    assert not any(
        request.method == "POST" and request.url.path.endswith("/issues") for request in requests
    )


def test_gateway_creates_issue_when_no_open_issue_has_marker() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET" and request.url.path.endswith("/labels"):
            return httpx.Response(200, json=[{"name": name} for name in GitHubIssueGateway.LABELS])
        if request.method == "GET" and request.url.path.endswith("/issues"):
            return httpx.Response(200, json=[])
        if request.method == "POST" and request.url.path.endswith("/issues"):
            return httpx.Response(201, json={"number": 8})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    GitHubIssueGateway("acme/flow", TOKEN, client).upsert(_result(MonitorOutcome.BLOCKED))

    create_request = next(request for request in requests if request.method == "POST")
    payload = json.loads(create_request.content)
    assert payload["labels"] == ["source-monitor", "source-blocked"]
    assert MARKER in payload["body"]


def test_collecting_gateway_records_dry_run_operation_without_network() -> None:
    gateway = CollectingIssueGateway()

    gateway.ensure_labels()
    gateway.upsert(_result())

    assert gateway.operations == (
        "ensure_labels",
        "upsert:MY-TEST-SOURCE:CHANGED",
    )

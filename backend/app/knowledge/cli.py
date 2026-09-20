import argparse
import json
import os
import socket
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.enums import ActorType
from app.database.models import Actor
from app.knowledge.activation import ActivationCoordinator
from app.knowledge.contracts import (
    MonitorBaseline,
    MonitorOutcome,
    MonitorState,
    MonitorTrigger,
    RetrievedSource,
)
from app.knowledge.github_issues import (
    CollectingIssueGateway,
    GitHubIssueGateway,
    ReviewIssueGateway,
)
from app.knowledge.governance import decide_release, submit_for_review
from app.knowledge.monitor import check_source
from app.knowledge.repository import load_monitor_baselines, load_repository_document
from app.knowledge.sync import KnowledgeSynchronizer
from app.knowledge.url_safety import retrieve_source


class SocketHostResolver:
    def resolve(self, hostname: str) -> tuple[str, ...]:
        results = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        addresses = {result[4][0] for result in results if isinstance(result[4][0], str)}
        return tuple(sorted(addresses))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor reviewed ImmigrationFlow official sources."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    monitor = subparsers.add_parser(
        "monitor", help="Retrieve monitored sources and record outcomes."
    )
    monitor.add_argument("--root", type=Path, required=True, help="Repository root directory.")
    monitor.add_argument("--state", type=Path, required=True, help="Prior monitor state JSON file.")
    monitor.add_argument(
        "--output-state", type=Path, required=True, help="Next monitor state JSON file."
    )
    monitor.add_argument(
        "--trigger", choices=tuple(item.value.lower() for item in MonitorTrigger), required=True
    )
    monitor.add_argument("--dry-run", action="store_true", help="Do not call the GitHub API.")

    bootstrap = subparsers.add_parser(
        "bootstrap-baselines", help="Generate a review-only candidate monitoring baseline file."
    )
    bootstrap.add_argument("--root", type=Path, required=True, help="Repository root directory.")
    bootstrap.add_argument("--output", type=Path, required=True, help="Candidate YAML output file.")

    sync = subparsers.add_parser("sync", help="Import a reviewed knowledge bundle into PostgreSQL.")
    sync.add_argument("--root", type=Path, required=True)
    sync.add_argument("--git-sha", required=True)

    review = subparsers.add_parser("review", help="Submit a synchronized release for review.")
    review.add_argument("--version-id", required=True)
    review.add_argument("--actor-id", required=True)

    decide = subparsers.add_parser("decide", help="Record an administrator release decision.")
    decide.add_argument("--version-id", required=True)
    decide.add_argument("--administrator-id", required=True)
    decide.add_argument("--decision", choices=("APPROVED", "REJECTED"), required=True)
    decide.add_argument("--notes")

    activate = subparsers.add_parser(
        "activate-due", help="Activate approved releases whose effective time has arrived."
    )
    activate.add_argument("--at")

    demo = subparsers.add_parser(
        "prepare-demo",
        help="Synchronize and activate the reviewed bundle for a protected local demo.",
    )
    demo.add_argument("--root", type=Path, required=True)
    demo.add_argument("--git-sha", required=True)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(arguments)
    try:
        if parsed.command == "monitor":
            return _monitor(parsed)
        if parsed.command == "bootstrap-baselines":
            return _bootstrap_baselines(parsed)
        if parsed.command == "sync":
            result = KnowledgeSynchronizer().sync(parsed.root, parsed.git_sha)
            print(
                json.dumps(
                    {
                        "run_id": str(result.run_id),
                        "status": result.status.value,
                        "reused": result.reused,
                    }
                )
            )
            return 0
        if parsed.command == "review":
            from uuid import UUID

            from app.database.session import get_db_session

            session = next(get_db_session())
            try:
                submit_for_review(
                    session, UUID(parsed.version_id), UUID(parsed.actor_id), datetime.now(UTC)
                )
                session.commit()
            finally:
                session.close()
            print("review submitted")
            return 0
        if parsed.command == "decide":
            from uuid import UUID

            from app.database.enums import ApprovalDecision
            from app.database.session import get_db_session

            session = next(get_db_session())
            try:
                decide_release(
                    session,
                    UUID(parsed.version_id),
                    UUID(parsed.administrator_id),
                    ApprovalDecision(parsed.decision),
                    parsed.notes,
                    datetime.now(UTC),
                )
                session.commit()
            finally:
                session.close()
            print("decision recorded")
            return 0
        if parsed.command == "prepare-demo":
            return _prepare_demo(parsed.root, parsed.git_sha)
        from app.database.session import get_db_session

        session = next(get_db_session())
        try:
            when = (
                datetime.fromisoformat(parsed.at.replace("Z", "+00:00"))
                if parsed.at
                else datetime.now(UTC)
            )
            summary = ActivationCoordinator().activate_due(session, when)
        finally:
            session.close()
        print(
            json.dumps(
                {
                    "activated": summary.activated,
                    "skipped": summary.skipped,
                    "failed": summary.failed,
                }
            )
        )
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print("error: database operation failed", file=sys.stderr)
        return 3


def _prepare_demo(root: Path, git_sha: str) -> int:
    from app.core.config import get_settings
    from app.database.enums import ApprovalDecision, RuleSetVersionStatus, ServiceType
    from app.database.models import ApprovalEvent, RuleSet, RuleSetVersion
    from app.database.session import get_db_session

    if not get_settings().demo_mode:
        raise ValueError("prepare-demo requires DEMO_MODE=true")

    result = KnowledgeSynchronizer().sync(root, git_sha)
    now = datetime.now(UTC)
    session = next(get_db_session())
    try:
        release = session.scalar(
            select(RuleSetVersion).where(RuleSetVersion.knowledge_sync_run_id == result.run_id)
        )
        if release is None:
            release = session.scalar(
                select(RuleSetVersion)
                .join(RuleSet, RuleSet.id == RuleSetVersion.rule_set_id)
                .where(
                    RuleSet.service_type == ServiceType.STUDENT_PASS,
                    RuleSetVersion.status == RuleSetVersionStatus.ACTIVE,
                )
                .order_by(RuleSetVersion.activated_at.desc(), RuleSetVersion.id.desc())
                .limit(1)
            )
        if release is None:
            raise RuntimeError("synchronized demo release was not found")
        if release.status == RuleSetVersionStatus.DRAFT:
            reviewer = _demo_actor(
                session,
                ActorType.SYSTEM,
                "IMMIGRATIONFLOW-DEMO-V1:KNOWLEDGE-REVIEWER",
                "Demo Knowledge Reviewer (Synthetic)",
            )
            administrator = _demo_actor(
                session,
                ActorType.ADMINISTRATOR,
                "IMMIGRATIONFLOW-DEMO-V1:ADMINISTRATOR",
                "Demo Rule Administrator (Synthetic)",
            )
            submit_for_review(session, release.id, reviewer.id, now)
            decide_release(
                session,
                release.id,
                administrator.id,
                ApprovalDecision.APPROVED,
                "Synthetic local demo activation of the reviewed repository bundle.",
                now,
            )
            session.commit()
        elif release.status == RuleSetVersionStatus.REVIEW:
            approval = session.scalar(
                select(ApprovalEvent).where(ApprovalEvent.rule_set_version_id == release.id)
            )
            if approval is None or approval.decision != ApprovalDecision.APPROVED:
                raise ValueError("demo release is in review without an approval")
        summary = ActivationCoordinator().activate_due(session, now)
        session.refresh(release)
        if release.status != RuleSetVersionStatus.ACTIVE:
            raise RuntimeError("demo rule release did not become active")
    finally:
        session.close()
    print(json.dumps({"status": "ready", "activated": summary.activated}))
    return 0


def _demo_actor(
    session: Session,
    actor_type: ActorType,
    external_reference: str,
    display_name: str,
) -> Actor:
    actor = session.scalar(
        select(Actor).where(Actor.external_reference == external_reference)
    )
    if actor is None:
        actor = Actor(
            actor_type=actor_type,
            display_name=display_name,
            external_reference=external_reference,
        )
        session.add(actor)
        session.flush()
    return actor


def _monitor(arguments: argparse.Namespace) -> int:
    baselines = load_monitor_baselines(arguments.root)
    prior_states = _load_states(arguments.state)
    trigger = MonitorTrigger(arguments.trigger.upper())
    next_states: dict[str, MonitorState] = {}
    resolver = SocketHostResolver()
    with httpx.Client(timeout=15.0, trust_env=False) as client:
        gateway = _issue_gateway(arguments.dry_run, client)
        gateway.ensure_labels()
        for baseline in baselines:
            prior_state = prior_states.get(baseline.source_id, _initial_state(baseline))

            def retrieve(baseline: MonitorBaseline = baseline) -> RetrievedSource:
                return retrieve_source(baseline, client, resolver)

            result = check_source(
                baseline,
                prior_state,
                trigger,
                retrieve,
                datetime.now(UTC),
            )
            next_states[baseline.source_id] = result.next_state
            if result.should_notify:
                gateway.upsert(result)

    _write_states(arguments.output_state, next_states)
    if isinstance(gateway, CollectingIssueGateway):
        for operation in gateway.operations:
            print(operation)
    return 0


def _bootstrap_baselines(arguments: argparse.Namespace) -> int:
    registry = load_repository_document(arguments.root, Path("data/official-sources/registry.yaml"))
    sources = registry.get("sources")
    if not isinstance(sources, list):
        raise ValueError("source registry must contain sources")
    git_commit_sha = _head_commit(arguments.root)
    resolver = SocketHostResolver()
    candidates: list[dict[str, object]] = []
    with httpx.Client(trust_env=False) as client:
        for source in sources:
            if not isinstance(source, Mapping) or source.get("status") != "reviewed":
                continue
            source_id = _source_text(source, "id")
            canonical_url = _source_text(source, "canonical_url")
            hostname = httpx.URL(canonical_url).host
            if hostname is None:
                raise ValueError(f"source has no hostname: {source_id}")
            baseline = MonitorBaseline(
                source_id=source_id,
                canonical_url=canonical_url,
                allowed_hosts=(hostname,),
                selector=None,
                strategy_version=1,
                approved_hash="0" * 64,
                captured_at=datetime.now(UTC),
                git_commit_sha=git_commit_sha,
            )
            retrieved = retrieve_source(baseline, client, resolver)
            candidates.append(
                {
                    "source_id": source_id,
                    "canonical_url": canonical_url,
                    "allowed_hosts": [hostname],
                    "selector": None,
                    "strategy_version": 1,
                    "approved_hash": retrieved.content_hash,
                    "captured_at": retrieved.retrieved_at.isoformat(),
                    "git_commit_sha": git_commit_sha,
                }
            )
    _atomic_write_yaml(arguments.output, {"schema_version": 1, "baselines": candidates})
    print(f"Generated {len(candidates)} candidate baseline records.")
    return 0


def _issue_gateway(dry_run: bool, client: httpx.Client) -> ReviewIssueGateway:
    if dry_run:
        return CollectingIssueGateway()
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise ValueError("GITHUB_TOKEN and GITHUB_REPOSITORY are required unless --dry-run is used")
    return GitHubIssueGateway(repo, token, client)


def _load_states(path: Path) -> dict[str, MonitorState]:
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read monitor state from {path}") from error
    if not isinstance(document, Mapping) or not isinstance(document.get("sources"), Mapping):
        raise ValueError("monitor state must contain a sources object")
    states: dict[str, MonitorState] = {}
    for source_id, state in document["sources"].items():
        if not isinstance(source_id, str) or not isinstance(state, Mapping):
            raise ValueError("monitor state source entries must be objects keyed by source ID")
        parsed = MonitorState.from_dict(state)
        if parsed.source_id != source_id:
            raise ValueError("monitor state source key must match its source_id")
        states[source_id] = parsed
    return states


def _write_states(path: Path, states: Mapping[str, MonitorState]) -> None:
    payload = {
        "sources": {source_id: states[source_id].to_dict() for source_id in sorted(states)},
    }
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _atomic_write_yaml(path: Path, document: Mapping[str, object]) -> None:
    _atomic_write_text(path, yaml.safe_dump(dict(document), sort_keys=False, allow_unicode=True))


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temporary.write(text)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def _initial_state(baseline: MonitorBaseline) -> MonitorState:
    return MonitorState(
        source_id=baseline.source_id,
        last_outcome=MonitorOutcome.UNCHANGED,
        consecutive_failures=0,
        last_comparable_hash=None,
    )


def _head_commit(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _source_text(source: Mapping[str, object], field_name: str) -> str:
    value = source.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"source {field_name} must be non-empty text")
    return value


if __name__ == "__main__":
    raise SystemExit(main())

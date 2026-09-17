import json
from datetime import UTC, datetime
from pathlib import Path
from shutil import copyfile

from app.knowledge.cli import main
from app.knowledge.contracts import RetrievedSource

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _write_repository(root: Path) -> None:
    source_directory = root / "data" / "official-sources"
    source_directory.mkdir(parents=True)
    (source_directory / "registry.yaml").write_text(
        """schema_version: 1
sources:
  - id: MY-TEST-SOURCE
    canonical_url: https://official.example/policy
    status: reviewed
""",
        encoding="utf-8",
    )
    (source_directory / "monitoring-baselines.yaml").write_text(
        """schema_version: 1
baselines:
  - source_id: MY-TEST-SOURCE
    canonical_url: https://official.example/policy
    allowed_hosts: [official.example]
    strategy_version: 1
    approved_hash: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    captured_at: "2026-09-17T00:00:00+00:00"
    git_commit_sha: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
""",
        encoding="utf-8",
    )
    project_root = Path(__file__).resolve().parents[4]
    copyfile(
        project_root / "data" / "official-sources" / "monitoring-baseline.schema.json",
        source_directory / "monitoring-baseline.schema.json",
    )


def test_monitor_dry_run_writes_sanitized_state_without_github_token(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _write_repository(tmp_path)
    state_path = tmp_path / "prior.json"
    output_path = tmp_path / "next.json"

    def retrieved_source(*_: object) -> RetrievedSource:
        return RetrievedSource(
            final_url="https://official.example/policy",
            retrieved_at=NOW,
            normalized_content="Changed public policy",
            content_hash="c" * 64,
        )

    monkeypatch.setattr("app.knowledge.cli.retrieve_source", retrieved_source)

    exit_code = main(
        [
            "monitor",
            "--root",
            str(tmp_path),
            "--state",
            str(state_path),
            "--output-state",
            str(output_path),
            "--trigger",
            "manual",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "sources": {
            "MY-TEST-SOURCE": {
                "consecutive_failures": 0,
                "last_comparable_hash": "c" * 64,
                "last_outcome": "CHANGED",
                "source_id": "MY-TEST-SOURCE",
            }
        }
    }
    assert "upsert:MY-TEST-SOURCE:CHANGED" in capsys.readouterr().out

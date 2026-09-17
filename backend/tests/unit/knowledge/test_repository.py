from datetime import UTC, datetime
from pathlib import Path
from shutil import copyfile

import pytest

from app.knowledge.repository import load_monitor_baselines

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _write_repository(
    root: Path, *, source_status: str = "reviewed", source_id: str = "MY-TEST-SOURCE"
) -> None:
    source_directory = root / "data" / "official-sources"
    source_directory.mkdir(parents=True)
    (source_directory / "registry.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "sources:",
                f"  - id: {source_id}",
                "    canonical_url: https://official.example/policy",
                f"    status: {source_status}",
            ]
        ),
        encoding="utf-8",
    )
    (source_directory / "monitoring-baselines.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "baselines:",
                "  - source_id: MY-TEST-SOURCE",
                "    canonical_url: https://official.example/policy",
                "    allowed_hosts:",
                "      - official.example",
                "    selector: '#policy'",
                "    strategy_version: 1",
                f"    approved_hash: {'a' * 64}",
                f'    captured_at: "{NOW.isoformat()}"',
                f"    git_commit_sha: {'b' * 40}",
            ]
        ),
        encoding="utf-8",
    )
    project_root = Path(__file__).resolve().parents[4]
    copyfile(
        project_root / "data" / "official-sources" / "monitoring-baseline.schema.json",
        source_directory / "monitoring-baseline.schema.json",
    )


def test_load_monitor_baselines_returns_reviewed_registered_source(tmp_path: Path) -> None:
    _write_repository(tmp_path)

    baselines = load_monitor_baselines(tmp_path)

    assert len(baselines) == 1
    assert baselines[0].source_id == "MY-TEST-SOURCE"
    assert baselines[0].canonical_url == "https://official.example/policy"
    assert baselines[0].allowed_hosts == ("official.example",)
    assert baselines[0].selector == "#policy"


def test_load_monitor_baselines_rejects_candidate_registry_source(tmp_path: Path) -> None:
    _write_repository(tmp_path, source_status="candidate")

    with pytest.raises(ValueError, match="must be reviewed"):
        load_monitor_baselines(tmp_path)


def test_load_monitor_baselines_rejects_unregistered_source(tmp_path: Path) -> None:
    _write_repository(tmp_path, source_id="MY-OTHER-SOURCE")

    with pytest.raises(ValueError, match="unknown source_id"):
        load_monitor_baselines(tmp_path)


def test_load_monitor_baselines_rejects_duplicate_source_ids(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    baseline_path = tmp_path / "data" / "official-sources" / "monitoring-baselines.yaml"
    with baseline_path.open("a", encoding="utf-8") as output:
        output.write(
            "\n".join(
                [
                    "",
                    "  - source_id: MY-TEST-SOURCE",
                    "    canonical_url: https://official.example/policy",
                    "    allowed_hosts: [official.example]",
                    "    strategy_version: 1",
                    f"    approved_hash: {'c' * 64}",
                    f'    captured_at: "{NOW.isoformat()}"',
                    f"    git_commit_sha: {'d' * 40}",
                ]
            )
        )

    with pytest.raises(ValueError, match="duplicate source_id"):
        load_monitor_baselines(tmp_path)

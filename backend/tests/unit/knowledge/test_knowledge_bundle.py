from pathlib import Path

import pytest

from app.knowledge.repository import load_knowledge_bundle

ROOT = Path(__file__).parents[4]


def test_load_knowledge_bundle_rejects_malformed_git_sha() -> None:
    with pytest.raises(ValueError, match="git SHA"):
        load_knowledge_bundle(ROOT, "not-a-sha")


def test_load_knowledge_bundle_rejects_sha_different_from_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.knowledge.repository._git_state",
        lambda root: ("b" * 40, ""),
    )
    with pytest.raises(ValueError, match="does not match repository HEAD"):
        load_knowledge_bundle(ROOT, "a" * 40)


def test_load_knowledge_bundle_rejects_dirty_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.knowledge.repository._git_state",
        lambda root: ("a" * 40, " M data/rules/student-pass-v1.yaml"),
    )
    with pytest.raises(ValueError, match="dirty"):
        load_knowledge_bundle(ROOT, "a" * 40)


def test_load_knowledge_bundle_loads_reviewed_student_pass_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.knowledge.repository._git_state", lambda root: ("a" * 40, ""))
    bundle = load_knowledge_bundle(ROOT, "a" * 40)
    assert len(bundle.requirements["requirements"]) == 17  # type: ignore[arg-type]
    assert len(bundle.rule_set["rules"]) == 16  # type: ignore[arg-type]

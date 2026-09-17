from pathlib import Path

import pytest

from app.knowledge.normalization import NormalizationError, content_sha256, normalize_html

FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "knowledge"


def _fixture(name: str) -> bytes:
    return (FIXTURE_ROOT / name).read_bytes()


def test_layout_only_html_change_keeps_normalized_bytes_and_hash() -> None:
    original = normalize_html(_fixture("original.html"), "#policy-content", strategy_version=1)
    layout_only = normalize_html(
        _fixture("layout-only-change.html"),
        "#policy-content",
        strategy_version=1,
    )

    assert original == layout_only
    assert content_sha256(original) == content_sha256(layout_only)


def test_material_policy_text_change_changes_normalized_hash() -> None:
    original = normalize_html(_fixture("original.html"), "#policy-content", strategy_version=1)
    changed = normalize_html(_fixture("changed.html"), "#policy-content", strategy_version=1)

    assert content_sha256(original) != content_sha256(changed)


def test_missing_configured_selector_fails_closed() -> None:
    with pytest.raises(NormalizationError, match="selector"):
        normalize_html(_fixture("original.html"), "#not-present", strategy_version=1)


def test_unknown_normalization_strategy_is_rejected() -> None:
    with pytest.raises(NormalizationError, match="strategy"):
        normalize_html(_fixture("original.html"), "#policy-content", strategy_version=2)


def test_nested_cookie_banner_is_removed_without_processing_detached_children() -> None:
    normalized = normalize_html(
        b"""
        <main><p>Public Student Pass requirement</p></main>
        <section class="cookie-banner"><div><span>Accept cookies</span></div></section>
        """,
        selector=None,
        strategy_version=1,
    )

    assert normalized == b"Public Student Pass requirement"

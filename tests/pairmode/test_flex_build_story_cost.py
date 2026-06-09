"""Tests for ``_read_story_frontmatter`` flex_factor field (INFRA-160).

Verifies that ``_read_story_frontmatter`` always returns a ``flex_factor``
float key: defaulting to 1.0 when absent, using the numeric value when
present, and defaulting to 1.0 on non-numeric values.

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_flex_build_story_cost.py -x -q
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the pairmode scripts directory is on the path.
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts")
)

from flex_build import _read_story_frontmatter  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_story(tmp_path: Path, frontmatter_extra: str = "") -> Path:
    """Write a minimal story file with optional extra frontmatter lines."""
    story_dir = tmp_path / "docs" / "stories" / "INFRA"
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / "INFRA-160.md"
    story_path.write_text(
        "---\n"
        "id: INFRA-160\n"
        "rail: INFRA\n"
        "status: planned\n"
        "phase: '63'\n"
        "primary_files: []\n"
        f"{frontmatter_extra}"
        "---\n\n## Ensures\n\n- OK\n",
        encoding="utf-8",
    )
    return story_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_flex_factor_absent_defaults_to_1(tmp_path: Path) -> None:
    """Story without flex_factor field returns flex_factor=1.0."""
    story_path = _write_story(tmp_path)
    fm = _read_story_frontmatter(story_path)
    assert "flex_factor" in fm
    assert fm["flex_factor"] == 1.0


def test_flex_factor_present_numeric_returned(tmp_path: Path) -> None:
    """Story with flex_factor: 1.3 returns flex_factor=1.3."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: 1.3\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["flex_factor"] == 1.3


def test_flex_factor_present_integer_coerced(tmp_path: Path) -> None:
    """Story with flex_factor: 2 (integer) returns flex_factor=2.0."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: 2\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["flex_factor"] == 2.0


def test_flex_factor_non_numeric_defaults_to_1(tmp_path: Path) -> None:
    """Non-numeric flex_factor value is treated as absent → 1.0."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: 'large'\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["flex_factor"] == 1.0


def test_flex_factor_null_defaults_to_1(tmp_path: Path) -> None:
    """Null flex_factor value defaults to 1.0."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: null\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["flex_factor"] == 1.0


def test_other_frontmatter_keys_preserved(tmp_path: Path) -> None:
    """Existing frontmatter keys are not disturbed by adding flex_factor."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: 0.8\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["id"] == "INFRA-160"
    assert fm["rail"] == "INFRA"
    assert fm["flex_factor"] == 0.8

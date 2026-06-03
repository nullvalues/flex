"""Tests for flex_build.py permissions-create subcommand (INFRA-137)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

# Make sibling scripts importable via direct path insertion.
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from flex_build import flex_build  # type: ignore[import]  # noqa: E402


def _make_story(tmp_path: Path, story_id: str, primary_files=None, touches=None) -> Path:
    """Write a minimal story spec file with YAML frontmatter."""
    rail = story_id.split("-")[0]
    story_dir = tmp_path / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_file = story_dir / f"{story_id}.md"

    pf_yaml = ""
    if primary_files is not None:
        items = "\n".join(f"  - {p}" for p in primary_files)
        pf_yaml = f"primary_files:\n{items}\n"

    touches_yaml = ""
    if touches is not None:
        items = "\n".join(f"  - {p}" for p in touches)
        touches_yaml = f"touches:\n{items}\n"

    content = (
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        "title: Test story\n"
        "status: planned\n"
        'phase: "99"\n'
        f"{pf_yaml}"
        f"{touches_yaml}"
        "---\n\n"
        "## Requires\n\nNothing.\n\n"
        "## Ensures\n\n- Always true.\n"
    )
    story_file.write_text(content, encoding="utf-8")
    return story_file


def test_permissions_create_writes_json_with_correct_structure(tmp_path):
    runner = CliRunner()
    _make_story(tmp_path, "INFRA-999", primary_files=["a.py"], touches=["b.py"])
    result = runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output + (result.exception or "")
    out_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-999.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert "story_id" in data
    assert "story_spec" in data
    assert "allowed_paths" in data
    assert "generated_at" in data


def test_permissions_create_includes_story_spec_in_allowed_paths(tmp_path):
    runner = CliRunner()
    _make_story(tmp_path, "INFRA-999", primary_files=["a.py"], touches=["b.py"])
    runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    out_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-999.json"
    data = json.loads(out_path.read_text())
    assert "docs/stories/INFRA/INFRA-999.md" in data["allowed_paths"]


def test_permissions_create_deduplicates_paths(tmp_path):
    runner = CliRunner()
    # Same path in both primary_files and touches
    _make_story(
        tmp_path, "INFRA-999", primary_files=["shared.py"], touches=["shared.py"]
    )
    runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    out_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-999.json"
    data = json.loads(out_path.read_text())
    assert data["allowed_paths"].count("shared.py") == 1


def test_permissions_create_handles_missing_primary_files(tmp_path):
    runner = CliRunner()
    # No primary_files key in frontmatter
    _make_story(tmp_path, "INFRA-999", primary_files=None, touches=None)
    result = runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    out_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-999.json"
    data = json.loads(out_path.read_text())
    assert data["allowed_paths"] == ["docs/stories/INFRA/INFRA-999.md"]


def test_permissions_create_handles_missing_touches(tmp_path):
    runner = CliRunner()
    # Has primary_files but no touches key
    _make_story(tmp_path, "INFRA-999", primary_files=["x.py"], touches=None)
    result = runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    out_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-999.json"
    data = json.loads(out_path.read_text())
    assert "x.py" in data["allowed_paths"]
    assert "docs/stories/INFRA/INFRA-999.md" in data["allowed_paths"]


def test_permissions_create_exits_nonzero_when_story_not_found(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-000", "--project-dir", str(tmp_path)],
    )
    assert result.exit_code != 0
    # CliRunner mixes stdout and stderr by default; "not found" must appear somewhere
    assert "not found" in result.output


def test_permissions_create_idempotent(tmp_path):
    runner = CliRunner()
    _make_story(tmp_path, "INFRA-999", primary_files=["a.py"], touches=["b.py"])
    # First run
    r1 = runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    assert r1.exit_code == 0
    out_path = tmp_path / "docs" / "phases" / "permissions" / "INFRA-999.json"
    data1 = json.loads(out_path.read_text())

    # Second run
    r2 = runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    assert r2.exit_code == 0
    data2 = json.loads(out_path.read_text())

    # Both runs produce the same structure
    assert data1["story_id"] == data2["story_id"]
    assert data1["allowed_paths"] == data2["allowed_paths"]
    assert data1["story_spec"] == data2["story_spec"]


def test_permissions_create_registered_on_flex_build_cli():
    assert "permissions-create" in flex_build.commands


def test_permissions_create_stdout_reports_path_and_count(tmp_path):
    runner = CliRunner()
    _make_story(tmp_path, "INFRA-999", primary_files=["a.py"], touches=["b.py"])
    result = runner.invoke(
        flex_build,
        ["permissions-create", "INFRA-999", "--project-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    # stdout should contain the wrote line
    assert "permissions: wrote docs/phases/permissions/INFRA-999.json" in result.output
    # Count should be 3: a.py, b.py, story spec
    assert "(3 paths)" in result.output

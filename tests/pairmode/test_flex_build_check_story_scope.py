"""Tests for ``flex_build.py check-story-scope`` subcommand (Story INFRA-155).

Tests:
1.  test_rule1_fires_when_script_declared_without_test
2.  test_rule1_silent_when_test_declared
3.  test_rule1_silent_when_test_not_on_disk
4.  test_rule1_silent_for_script_in_touches
5.  test_rule1_skips_test_files_and_init
6.  test_rule2_fires_when_template_declared_without_live
7.  test_rule2_silent_when_live_declared
8.  test_rule2_silent_when_no_live_counterpart_exists
9.  test_no_warnings_on_empty_primary_files
10. test_exit_zero_when_warnings_present
11. test_invalid_story_id_exits_one
12. test_missing_story_spec_exits_one
13. test_multiple_warnings_for_multiple_scripts
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str, project_dir: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke flex_build.py with *args*; return the completed process."""
    cmd = [sys.executable, str(_SCRIPT), *args]
    if project_dir is not None:
        cmd += ["--project-dir", str(project_dir)]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(_REPO_ROOT),
        },
    )


def _make_story(
    tmp_path: Path,
    story_id: str,
    primary_files: list[str],
    touches: list[str],
) -> Path:
    """Write a minimal frontmatter-only story file under docs/stories/<RAIL>/<STORY_ID>.md."""
    rail = story_id.split("-", 1)[0]
    story_dir = tmp_path / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"

    pf_lines = "\n".join(f"  - {p}" for p in primary_files)
    touches_lines = "\n".join(f"  - {p}" for p in touches)
    pf_block = f"primary_files:\n{pf_lines}" if primary_files else "primary_files: []"
    touches_block = f"touches:\n{touches_lines}" if touches else "touches: []"

    content = (
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"title: Test story\n"
        f"status: planned\n"
        f"phase: \"99\"\n"
        f"{pf_block}\n"
        f"{touches_block}\n"
        "---\n\n"
        "## Requires\n\nNothing.\n\n"
        "## Ensures\n\n- It works.\n"
    )
    story_path.write_text(content, encoding="utf-8")
    return story_path


def _touch(tmp_path: Path, rel_path: str) -> Path:
    """Create an empty file at tmp_path/rel_path, ensuring parent dirs exist."""
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.touch()
    return full


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_rule1_fires_when_script_declared_without_test(tmp_path: Path) -> None:
    """Script declared, test file exists on disk, test NOT in scope -> warning."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=["skills/pairmode/scripts/foo.py"],
        touches=[],
    )
    _touch(tmp_path, "tests/pairmode/test_foo.py")

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "SCOPE WARNING:" in result.stdout
    assert "test_foo.py" in result.stdout


def test_rule1_silent_when_test_declared(tmp_path: Path) -> None:
    """Both script and test declared; test file on disk -> no SCOPE WARNING."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=[
            "skills/pairmode/scripts/foo.py",
            "tests/pairmode/test_foo.py",
        ],
        touches=[],
    )
    _touch(tmp_path, "tests/pairmode/test_foo.py")

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" not in result.stdout


def test_rule1_silent_when_test_not_on_disk(tmp_path: Path) -> None:
    """Script declared but expected test path does not exist -> no SCOPE WARNING."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=["skills/pairmode/scripts/foo.py"],
        touches=[],
    )
    # Do NOT create tests/pairmode/test_foo.py on disk.

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" not in result.stdout


def test_rule1_silent_for_script_in_touches(tmp_path: Path) -> None:
    """Script in touches, test in primary_files -> scope union covers both, no SCOPE WARNING."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=["tests/pairmode/test_foo.py"],
        touches=["skills/pairmode/scripts/foo.py"],
    )
    _touch(tmp_path, "tests/pairmode/test_foo.py")

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" not in result.stdout


def test_rule1_skips_test_files_and_init(tmp_path: Path) -> None:
    """test_*.py and __init__.py in scripts/ are not subject to rule 1."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=[
            "skills/pairmode/scripts/test_foo.py",
            "skills/pairmode/scripts/__init__.py",
        ],
        touches=[],
    )
    # Even if matching test files existed they should not trigger.
    _touch(tmp_path, "tests/pairmode/test_test_foo.py")
    _touch(tmp_path, "tests/pairmode/test___init__.py")

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" not in result.stdout


def test_rule2_fires_when_template_declared_without_live(tmp_path: Path) -> None:
    """Template declared, live CLAUDE.build.md exists at root, not in scope -> warning."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=["skills/pairmode/templates/CLAUDE.build.md.j2"],
        touches=[],
    )
    _touch(tmp_path, "CLAUDE.build.md")

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" in result.stdout
    assert "CLAUDE.build.md.j2" in result.stdout
    assert "CLAUDE.build.md" in result.stdout


def test_rule2_silent_when_live_declared(tmp_path: Path) -> None:
    """Both template and live file declared -> no SCOPE WARNING."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=[
            "skills/pairmode/templates/CLAUDE.build.md.j2",
            "CLAUDE.build.md",
        ],
        touches=[],
    )
    _touch(tmp_path, "CLAUDE.build.md")

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" not in result.stdout


def test_rule2_silent_when_no_live_counterpart_exists(tmp_path: Path) -> None:
    """Template declared but no live counterpart at any candidate location -> no SCOPE WARNING."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=["skills/pairmode/templates/CLAUDE.build.md.j2"],
        touches=[],
    )
    # Do NOT create CLAUDE.build.md or skills/pairmode/CLAUDE.build.md.

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" not in result.stdout


def test_no_warnings_on_empty_primary_files(tmp_path: Path) -> None:
    """Empty primary_files and touches -> no SCOPE WARNINGs, exit 0."""
    _make_story(tmp_path, "INFRA-001", primary_files=[], touches=[])

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" not in result.stdout


def test_exit_zero_when_warnings_present(tmp_path: Path) -> None:
    """A story that produces warnings must still exit 0 (informational only)."""
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=["skills/pairmode/scripts/bar.py"],
        touches=[],
    )
    _touch(tmp_path, "tests/pairmode/test_bar.py")

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    assert "SCOPE WARNING:" in result.stdout


def test_invalid_story_id_exits_one(tmp_path: Path) -> None:
    """Invalid story_id format -> stderr contains 'invalid story_id format', exit 1."""
    result = _run("check-story-scope", "not-a-story-id", project_dir=tmp_path)
    assert result.returncode == 1
    assert "invalid story_id format" in result.stderr


def test_missing_story_spec_exits_one(tmp_path: Path) -> None:
    """Valid STORY_ID but no story file -> stderr contains 'story spec not found', exit 1."""
    # Do NOT create the story file.
    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 1
    assert "story spec not found" in result.stderr


def test_multiple_warnings_for_multiple_scripts(tmp_path: Path) -> None:
    """Three scripts declared, none with test siblings declared; all test files on disk.

    Assert stdout has exactly three SCOPE WARNING: lines.
    """
    _make_story(
        tmp_path,
        "INFRA-001",
        primary_files=[
            "skills/pairmode/scripts/alpha.py",
            "skills/pairmode/scripts/beta.py",
            "skills/pairmode/scripts/gamma.py",
        ],
        touches=[],
    )
    _touch(tmp_path, "tests/pairmode/test_alpha.py")
    _touch(tmp_path, "tests/pairmode/test_beta.py")
    _touch(tmp_path, "tests/pairmode/test_gamma.py")

    result = _run("check-story-scope", "INFRA-001", project_dir=tmp_path)
    assert result.returncode == 0
    warning_lines = [
        line for line in result.stdout.splitlines() if "SCOPE WARNING:" in line
    ]
    assert len(warning_lines) == 3

"""Tests for next_story.py — find next unbuilt story from a phase file."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

# Insert scripts directory so next_story (and its sibling deps) can be imported.
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from next_story import find_next_story, next_story_cli  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project_layout(tmp_path: Path) -> Path:
    """Create a minimal project layout with docs/phases and docs/stories dirs.

    Returns the project root path.
    """
    project = tmp_path / "myproject"
    (project / "docs" / "phases").mkdir(parents=True)
    (project / "docs" / "stories").mkdir(parents=True)
    # Initialise as a git repo so `git log` calls work cleanly.
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(project),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=str(project), check=True
    )
    # Initial commit so `git log` returns at least one row.
    (project / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(project), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"], cwd=str(project), check=True
    )
    return project


def _write_phase(
    project: Path,
    phase_num: int,
    stories: list[tuple[str, str, str]],
) -> Path:
    """Write a phase file with a ## Stories table.

    `stories` is a list of (story_id, title, status) tuples.
    """
    phase_path = project / "docs" / "phases" / f"phase-{phase_num}.md"
    lines = [
        "---",
        f"id: '{phase_num}'",
        "title: Test Phase",
        "status: active",
        "---",
        "",
        "## Stories",
        "",
        "| ID | Title | Status |",
        "|----|-------|--------|",
    ]
    for sid, title, status in stories:
        lines.append(f"| {sid} | {title} | {status} |")
    lines.append("")
    phase_path.write_text("\n".join(lines), encoding="utf-8")
    return phase_path


def _write_story(project: Path, story_id: str, status: str = "planned") -> Path:
    rail = story_id.split("-", 1)[0]
    story_dir = project / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    path = story_dir / f"{story_id}.md"
    path.write_text(
        "\n".join(
            [
                "---",
                f"id: {story_id}",
                f"rail: {rail}",
                "title: Test",
                f"status: {status}",
                "phase: '45'",
                "primary_files:",
                "  - foo.py",
                "---",
                "",
                "## Requires",
                "",
                "Nothing.",
                "",
                "## Ensures",
                "",
                "Something.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _commit(project: Path, message: str) -> None:
    """Create an empty commit with the given message."""
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", message],
        cwd=str(project),
        check=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_finds_first_planned_story(tmp_path):
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("INFRA-100", "First", "planned"),
            ("INFRA-101", "Second", "planned"),
        ],
    )
    _write_story(project, "INFRA-100")
    _write_story(project, "INFRA-101")

    result = find_next_story(phase, project)

    assert result is not None
    assert result["story_id"] == "INFRA-100"
    assert result["git_verified"] is False
    assert result["story_file"].endswith("INFRA-100.md")


def test_skips_complete_story(tmp_path):
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("INFRA-100", "First", "complete"),
            ("INFRA-101", "Second", "planned"),
        ],
    )
    _write_story(project, "INFRA-100", status="complete")
    _write_story(project, "INFRA-101")
    # Commit the first story so git agrees with the table.
    _commit(project, "feat(story-INFRA-100): done")

    result = find_next_story(phase, project)

    assert result is not None
    assert result["story_id"] == "INFRA-101"
    assert result["git_verified"] is False


def test_git_commit_overrides_table_status(tmp_path):
    """Story with git commit is treated as done even if table says planned.

    Also: a story whose table status is `complete` but has NO matching git
    commit is returned with `git_verified=true` (git overrides the table).
    """
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            # INFRA-100 table says planned, but a commit exists → SKIP it.
            ("INFRA-100", "First", "planned"),
            # INFRA-101 table says complete, but no commit → RETURN with
            # git_verified=true (git overrides the table).
            ("INFRA-101", "Second", "complete"),
        ],
    )
    _write_story(project, "INFRA-100")
    _write_story(project, "INFRA-101", status="complete")
    _commit(project, "feat(story-INFRA-100): done via commit")

    result = find_next_story(phase, project)

    assert result is not None
    assert result["story_id"] == "INFRA-101"
    assert result["git_verified"] is True


def test_all_done_exits_1(tmp_path):
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("INFRA-100", "First", "complete"),
            ("INFRA-101", "Second", "deferred"),
        ],
    )
    _write_story(project, "INFRA-100", status="complete")
    _write_story(project, "INFRA-101", status="planned")
    _commit(project, "feat(story-INFRA-100): done")

    # API-level: find_next_story returns None.
    result = find_next_story(phase, project)
    assert result is None

    # CLI-level: exit code is 1.
    runner = CliRunner()
    cli_result = runner.invoke(
        next_story_cli,
        [str(phase), "--project-dir", str(project)],
    )
    assert cli_result.exit_code == 1
    assert "all stories complete" in cli_result.output


def test_missing_phase_file_exits_2(tmp_path):
    project = _make_project_layout(tmp_path)
    missing_phase = project / "docs" / "phases" / "phase-99.md"

    runner = CliRunner()
    cli_result = runner.invoke(
        next_story_cli,
        [str(missing_phase), "--project-dir", str(project)],
    )
    assert cli_result.exit_code == 2
    assert "not found" in cli_result.output or "error" in cli_result.output


# ---------------------------------------------------------------------------
# Additional sanity coverage
# ---------------------------------------------------------------------------


def test_case_insensitive_commit_match(tmp_path):
    """Commit pattern match is case-insensitive."""
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("INFRA-100", "First", "planned"),
            ("INFRA-101", "Second", "planned"),
        ],
    )
    _write_story(project, "INFRA-100")
    _write_story(project, "INFRA-101")
    # Commit message uses lowercase "story-infra-100".
    _commit(project, "feat(story-infra-100): mixed case")

    result = find_next_story(phase, project)
    assert result is not None
    assert result["story_id"] == "INFRA-101"


def test_bare_mention_commit_match(tmp_path):
    """A commit that mentions the story ID without the `story-` prefix
    (e.g. a merge suffix or status-update chore) counts as done.

    This is the RELEASE-014-style completion: `find_next_story` skips the
    story and advances to the next table row.
    """
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("RELEASE-014", "First", "complete"),
            ("RELEASE-019", "Second", "planned"),
        ],
    )
    _write_story(project, "RELEASE-014", status="complete")
    _write_story(project, "RELEASE-019")
    # Landing commits that never use the `story-RELEASE-014` prefix.
    _commit(project, "merge(fold-prep): fold RELEASE work (RELEASE-014)")
    _commit(project, "chore(orchestrator): RELEASE-014 status update")

    result = find_next_story(phase, project)
    assert result is not None
    assert result["story_id"] == "RELEASE-019"


def test_numeric_prefix_does_not_false_match(tmp_path):
    """A commit mentioning a longer ID (INFRA-1001) must NOT satisfy a
    lookup for INFRA-100 that shares its numeric prefix."""
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("INFRA-100", "First", "planned"),
            ("INFRA-101", "Second", "planned"),
        ],
    )
    _write_story(project, "INFRA-100")
    _write_story(project, "INFRA-101")
    # Only a longer ID sharing INFRA-100's prefix is committed.
    _commit(project, "feat(story-INFRA-1001): unrelated work")

    result = find_next_story(phase, project)
    assert result is not None
    # INFRA-100 must still be next-up — the INFRA-1001 commit is not a match.
    assert result["story_id"] == "INFRA-100"


def test_unresolved_story_file(tmp_path):
    """When the story file doesn't exist, story_file is 'UNRESOLVED'."""
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [("INFRA-100", "First", "planned")],
    )
    # Deliberately do NOT create the story file.

    result = find_next_story(phase, project)
    assert result is not None
    assert result["story_id"] == "INFRA-100"
    assert result["story_file"] == "UNRESOLVED"

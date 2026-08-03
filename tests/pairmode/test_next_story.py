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
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"], cwd=str(project), check=True
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


def test_spec_authoring_commit_does_not_false_match(tmp_path):
    """A `spec(...)` commit that lists several story IDs in prose must NOT
    count as build evidence for any of them (RELEASE-041).

    Reproduces the live false positive: a spec-authoring commit mentioning
    "RELEASE-020/021/022" satisfies a naive word-boundary search for
    RELEASE-020 (the `/` is a valid boundary), even though the commit never
    builds anything — it only adds specs.
    """
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("RELEASE-020", "First", "planned"),
            ("RELEASE-021", "Second", "planned"),
        ],
    )
    _write_story(project, "RELEASE-020")
    _write_story(project, "RELEASE-021")
    _commit(
        project,
        "spec(phase-X): correct status, add RELEASE-020/021/022 specs",
    )

    result = find_next_story(phase, project)
    assert result is not None
    assert result["story_id"] == "RELEASE-020"


def test_genuine_build_commit_still_matches_after_spec_exclusion(tmp_path):
    """A real `feat(story-<ID>):` build commit still counts as done even
    when a `spec(...)` commit for the same story ID also exists in history."""
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("RELEASE-020", "First", "planned"),
            ("RELEASE-021", "Second", "planned"),
        ],
    )
    _write_story(project, "RELEASE-020", status="complete")
    _write_story(project, "RELEASE-021")
    _commit(project, "spec(phase-X): add RELEASE-020 spec")
    _commit(project, "feat(story-RELEASE-020): implement it")

    result = find_next_story(phase, project)
    assert result is not None
    assert result["story_id"] == "RELEASE-021"


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


# ---------------------------------------------------------------------------
# claimed_skipped filter (CER-095.1, INFRA-280) — A3, A4, A5
# ---------------------------------------------------------------------------


def test_no_claimed_argument_is_byte_for_byte_unchanged(tmp_path):
    """A3: calling with no `claimed` argument returns exactly what it did
    before the filter existed — same keys plus an empty `claimed_skipped`."""
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
    assert result["claimed_skipped"] == []


def test_claimed_story_is_skipped_and_reported(tmp_path):
    """A4: claimed={"A"} over table A, B (neither has a commit) returns B,
    and `claimed_skipped` names the skipped story."""
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

    result = find_next_story(phase, project, claimed={"INFRA-100"})

    assert result is not None
    assert result["story_id"] == "INFRA-101"
    assert result["claimed_skipped"] == ["INFRA-100"]


def test_claimed_skipped_empty_when_nothing_skipped(tmp_path):
    """A4: `claimed_skipped` is `[]` when the claim set doesn't intersect
    any story on the walk before the returned one."""
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [("INFRA-100", "First", "planned")],
    )
    _write_story(project, "INFRA-100")

    result = find_next_story(phase, project, claimed={"INFRA-999"})

    assert result is not None
    assert result["story_id"] == "INFRA-100"
    assert result["claimed_skipped"] == []


def test_claim_never_overrides_a_completed_commit(tmp_path):
    """A5: a story with a matching git commit is passed over as complete
    before the claim is consulted — it never lands in `claimed_skipped`."""
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
    _commit(project, "feat(story-INFRA-100): done")

    result = find_next_story(phase, project, claimed={"INFRA-100"})

    assert result is not None
    assert result["story_id"] == "INFRA-101"
    # INFRA-100 is claimed, but it's excluded by the commit check first, so
    # it never reaches (and never appears in) claimed_skipped.
    assert result["claimed_skipped"] == []


def test_claim_never_overrides_deferred_status(tmp_path):
    """A5: a `deferred` story stays excluded regardless of claim state, and
    it does not appear in `claimed_skipped` (the skip status excluded it
    before the claim check ran)."""
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [
            ("INFRA-100", "First", "deferred"),
            ("INFRA-101", "Second", "planned"),
        ],
    )
    _write_story(project, "INFRA-100")
    _write_story(project, "INFRA-101")

    result = find_next_story(
        phase, project, claimed={"INFRA-100", "INFRA-101"}
    )

    assert result is None or result["story_id"] != "INFRA-100"
    # INFRA-101 is claimed, so nothing is returned; INFRA-100 never reaches
    # the claim check because `deferred` excludes it first.
    assert result is None


def test_unknown_claimed_id_is_inert(tmp_path):
    """A5: a claimed story ID absent from the phase's table has no effect
    on the result."""
    project = _make_project_layout(tmp_path)
    phase = _write_phase(
        project,
        45,
        [("INFRA-100", "First", "planned")],
    )
    _write_story(project, "INFRA-100")

    result = find_next_story(phase, project, claimed={"NOPE-999"})

    assert result is not None
    assert result["story_id"] == "INFRA-100"
    assert result["claimed_skipped"] == []


# ---------------------------------------------------------------------------
# INFRA-297 (CER-116) — build evidence is scoped to the commit's own story
# ---------------------------------------------------------------------------

from next_story import _has_story_commit  # noqa: E402

# The subject of commit e83ce900 verbatim. Kept as a literal, not read from
# this repository's git log: RELEASE-067 has since been genuinely built by
# 0978447b, so the real log no longer reproduces the false positive this
# test exists to pin.
_E83CE900 = (
    "e83ce900 story(RELEASE-066): forqsite.help migrated; E6 split verdict — "
    "E4b grammar replacement PROVEN in field, CER-101 content half PROVEN via "
    "reviewer row 14, builder row 13 pending on termination-detection artifact "
    "(new-1); RELEASE-067+ held for operator ruling"
)


def test_e83ce900_does_not_mark_the_mentioned_sibling_built():
    """CER-116 regression pin, both directions.

    Commit e83ce900's subject builds RELEASE-066 and merely *mentions*
    RELEASE-067 ("held for operator ruling"). The old whole-subject search
    read that mention as build evidence, so find_next_story silently skipped
    RELEASE-067 — which was still draft and unbuilt — and offered
    RELEASE-068 instead.

    The log is built here as a literal string on purpose: RELEASE-067 was
    later genuinely built by 0978447b, so this repository's real git log no
    longer reproduces the defect and would make the test vacuous.
    """
    assert _has_story_commit("RELEASE-067", _E83CE900) is False
    assert _has_story_commit("RELEASE-066", _E83CE900) is True


def test_scope_restriction_positive_and_negative():
    """A scope naming a story ID makes that ID — and only that ID — evidence."""
    log = "abc1234 feat(INFRA-100): implement it, unblocks INFRA-101"
    assert _has_story_commit("INFRA-100", log) is True
    assert _has_story_commit("INFRA-101", log) is False


def test_scope_with_multiple_story_ids_counts_all_of_them():
    log = "abc1234 feat(INFRA-100, INFRA-101): implement both"
    assert _has_story_commit("INFRA-100", log) is True
    assert _has_story_commit("INFRA-101", log) is True
    assert _has_story_commit("INFRA-102", log) is False


def test_uppercase_scope_token_matches_case_insensitively():
    """C4: `feat(story-INFRA-100): done` — uppercase scope token path."""
    log = "abc1234 feat(story-INFRA-100): done"
    assert _has_story_commit("INFRA-100", log) is True
    assert _has_story_commit("infra-100", log) is True


def test_lowercase_scope_falls_back_to_whole_subject_search():
    """C2/C4: lowercase scopes never activate the restriction.

    Uppercase-only is the conservative direction: a missed restriction
    re-offers a built story (loud), a wrong restriction skips one (silent).
    """
    assert _has_story_commit("INFRA-100", "abc1234 feat(story-infra-100): mixed case") is True
    assert _has_story_commit(
        "RELEASE-014", "abc1234 merge(fold-prep): fold RELEASE work (RELEASE-014)"
    ) is True
    assert _has_story_commit(
        "RELEASE-014", "abc1234 chore(orchestrator): RELEASE-014 status update"
    ) is True
    assert _has_story_commit(
        "INFRA-100", "abc1234 chore(phase-112): rollup for era-004"
    ) is False


def test_numeric_prefix_does_not_false_match_on_either_path():
    """C4: INFRA-1001 never satisfies a lookup for INFRA-100."""
    # Scope path.
    assert _has_story_commit("INFRA-100", "abc1234 feat(story-INFRA-1001): work") is False
    # Fallback path (no story ID in scope).
    assert _has_story_commit("INFRA-100", "abc1234 chore(rollup): INFRA-1001 landed") is False


def test_spec_skip_still_precedes_the_scope_rule():
    """C3: a `spec(...)` commit is skipped whatever its scope says."""
    assert _has_story_commit("INFRA-100", "abc1234 spec(INFRA-100): write the spec") is False
    assert _has_story_commit(
        "RELEASE-020", "abc1234 spec(phase-X): add RELEASE-020/021/022 specs"
    ) is False


def test_story_id_is_not_matched_out_of_the_sha_field():
    """C6: the fallback searches the message, not the raw --oneline line.

    A story ID whose text appears in the abbreviated SHA field must not
    count. Here the "SHA" column is literally the story ID.
    """
    assert _has_story_commit("ABC-100", "ABC-100 chore(rollup): unrelated work") is False


def test_no_conventional_prefix_uses_the_fallback():
    assert _has_story_commit("INFRA-100", "abc1234 INFRA-100 landed by hand") is True

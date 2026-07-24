"""Tests for skills/pairmode/scripts/scope_guard.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure the scripts directory is on sys.path so the module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))

import scope_guard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STORY_ID = "INFRA-999"


def _write_state(tmp_path: Path, story_id: str | None) -> None:
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    if story_id is not None:
        state = {"current_story": {"id": story_id, "set_at": "2026-01-01T00:00:00+00:00"}}
    else:
        state = {}
    (companion / "state.json").write_text(json.dumps(state))


def _write_permissions(tmp_path: Path, story_id: str, allowed_paths: list[str]) -> None:
    perm_dir = tmp_path / "docs" / "phases" / "permissions"
    perm_dir.mkdir(parents=True, exist_ok=True)
    (perm_dir / f"{story_id}.json").write_text(
        json.dumps({"story_id": story_id, "allowed_paths": allowed_paths})
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_scope_guard_allows_when_no_state_json(tmp_path: Path) -> None:
    """No .companion/state.json — fail open."""
    allowed, reason = scope_guard.check_path("skills/foo.py", tmp_path)
    assert allowed is True
    assert reason  # some reason string is present


def test_scope_guard_allows_when_no_current_story_in_state(tmp_path: Path) -> None:
    """state.json exists but has no current_story key — fail open."""
    _write_state(tmp_path, story_id=None)
    allowed, reason = scope_guard.check_path("skills/foo.py", tmp_path)
    assert allowed is True
    assert "no active story" in reason


def test_scope_guard_allows_when_no_permissions_file(tmp_path: Path) -> None:
    """state.json has current_story but no permissions file — fail open."""
    _write_state(tmp_path, STORY_ID)
    # Do NOT write a permissions file
    allowed, reason = scope_guard.check_path("skills/foo.py", tmp_path)
    assert allowed is True
    assert "no permissions file" in reason
    assert STORY_ID in reason


def test_scope_guard_allows_declared_primary_file(tmp_path: Path) -> None:
    """File is in allowed_paths — allow."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    allowed, reason = scope_guard.check_path("skills/foo.py", tmp_path)
    assert allowed is True
    assert reason == "allowed"


def test_scope_guard_blocks_undeclared_file(tmp_path: Path) -> None:
    """File is NOT in allowed_paths — block."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    allowed, reason = scope_guard.check_path("README.md", tmp_path)
    assert allowed is False
    assert "not in story scope" in reason


def test_scope_guard_normalizes_absolute_path(tmp_path: Path) -> None:
    """Absolute path to a declared file — allow."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    abs_path = tmp_path / "skills" / "foo.py"
    allowed, reason = scope_guard.check_path(abs_path, tmp_path)
    assert allowed is True
    assert reason == "allowed"


def test_scope_guard_normalizes_dotslash_prefix(tmp_path: Path) -> None:
    """Path with leading ./ — should match normalised allowed_paths entry."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    allowed, reason = scope_guard.check_path("./skills/foo.py", tmp_path)
    assert allowed is True
    assert reason == "allowed"


def test_scope_guard_blocks_path_escaping_project_root(tmp_path: Path) -> None:
    """Absolute path outside project root — block."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    allowed, reason = scope_guard.check_path("/etc/passwd", tmp_path)
    assert allowed is False
    assert "escapes project root" in reason


def test_scope_guard_allows_on_malformed_permissions_file(tmp_path: Path) -> None:
    """Permissions file contains invalid JSON — fail open."""
    _write_state(tmp_path, STORY_ID)
    perm_dir = tmp_path / "docs" / "phases" / "permissions"
    perm_dir.mkdir(parents=True, exist_ok=True)
    (perm_dir / f"{STORY_ID}.json").write_text("{ not valid json !!!")
    allowed, reason = scope_guard.check_path("skills/foo.py", tmp_path)
    assert allowed is True


def test_scope_guard_empty_allowed_paths_allows(tmp_path: Path) -> None:
    """Permissions file has empty allowed_paths list — fail open."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, [])
    allowed, reason = scope_guard.check_path("skills/foo.py", tmp_path)
    assert allowed is True
    assert "empty allowed_paths" in reason


# ---------------------------------------------------------------------------
# PROTECTED_GLOBS / fail-closed tests (INFRA-207)
# ---------------------------------------------------------------------------


def test_scope_guard_blocks_protected_path_with_no_active_story(tmp_path: Path) -> None:
    """Write to hooks/pre_tool_use.py with no active story — blocked by PROTECTED_GLOBS."""
    _write_state(tmp_path, story_id=None)
    allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
    assert allowed is False
    assert "protected path" in reason
    assert "primary_files" in reason


def test_scope_guard_allows_protected_path_with_active_story_that_declares_it(tmp_path: Path) -> None:
    """Write to hooks/pre_tool_use.py with an active story that declares it — allowed."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["hooks/pre_tool_use.py"])
    allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
    assert allowed is True
    assert reason == "allowed"


def test_scope_guard_allows_non_protected_path_with_no_active_story(tmp_path: Path) -> None:
    """Write to src/app.py with no active story — allowed (not protected)."""
    _write_state(tmp_path, story_id=None)
    allowed, reason = scope_guard.check_path("src/app.py", tmp_path)
    assert allowed is True
    assert "no active story" in reason


# ---------------------------------------------------------------------------
# Worktree-path normalization (INFRA-238)
# ---------------------------------------------------------------------------


def test_scope_guard_allows_worktree_relative_declared_path(tmp_path: Path) -> None:
    """A declared file addressed via its OWN story's worktree-relative path
    (.pairmode-worktrees/<ID>/<declared-path>) is allowed — the
    .pairmode-worktrees/<ID>/ prefix is stripped before the allowed_paths
    comparison. (Ensures 2.)"""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    worktree_relative = f".pairmode-worktrees/{STORY_ID}/skills/foo.py"
    allowed, reason = scope_guard.check_path(worktree_relative, tmp_path)
    assert allowed is True
    assert reason == "allowed"


def test_scope_guard_allows_worktree_relative_declared_path_absolute(tmp_path: Path) -> None:
    """Same as above, but with an absolute path — the form Claude Code
    actually sends for Edit/Write tool_input.file_path."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    abs_path = tmp_path / ".pairmode-worktrees" / STORY_ID / "skills" / "foo.py"
    allowed, reason = scope_guard.check_path(abs_path, tmp_path)
    assert allowed is True
    assert reason == "allowed"


def test_scope_guard_blocks_foreign_story_worktree_path_bypass(tmp_path: Path) -> None:
    """SECURITY: a path inside a DIFFERENT story's worktree must never be
    misidentified as in-scope just because its trailing segments match an
    allowed_paths entry for the ACTIVE story, after prefix-stripping.

    Active story is STORY_ID (INFRA-999) with allowed_paths=["skills/foo.py"].
    A path under a foreign story's worktree
    (.pairmode-worktrees/INFRA-111/skills/foo.py) has the exact same
    trailing segments as the allowed entry, but lives inside a wholly
    different story's worktree — it must be blocked, not allowed. An
    unconditional prefix-strip (stripping .pairmode-worktrees/<any segment>/
    regardless of whether <segment> is the active story) would incorrectly
    allow this and defeat per-story worktree isolation."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    foreign_worktree_path = ".pairmode-worktrees/INFRA-111/skills/foo.py"
    allowed, reason = scope_guard.check_path(foreign_worktree_path, tmp_path)
    assert allowed is False
    assert "not in story scope" in reason


def test_scope_guard_blocks_foreign_story_worktree_path_bypass_absolute(tmp_path: Path) -> None:
    """Same bypass check as above, with an absolute path."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    abs_path = tmp_path / ".pairmode-worktrees" / "INFRA-111" / "skills" / "foo.py"
    allowed, reason = scope_guard.check_path(abs_path, tmp_path)
    assert allowed is False
    assert "not in story scope" in reason


def test_strip_worktree_prefix_only_strips_matching_active_story() -> None:
    """Unit-level check on the helper directly: matching segment strips,
    non-matching segment (or no active story) leaves the path untouched."""
    matching = f".pairmode-worktrees/{STORY_ID}/skills/foo.py"
    assert scope_guard._strip_worktree_prefix(matching, STORY_ID) == "skills/foo.py"

    foreign = ".pairmode-worktrees/INFRA-111/skills/foo.py"
    assert scope_guard._strip_worktree_prefix(foreign, STORY_ID) == foreign

    assert scope_guard._strip_worktree_prefix(matching, None) == matching

    non_worktree_path = "skills/foo.py"
    assert scope_guard._strip_worktree_prefix(non_worktree_path, STORY_ID) == non_worktree_path


# ---------------------------------------------------------------------------
# Main checkout root resolution from a linked worktree cwd (INFRA-238)
# ---------------------------------------------------------------------------


def _make_linked_worktree(main_root: Path, story_id: str) -> Path:
    """Build a minimal linked-worktree directory structure under *main_root*
    that mimics what `git worktree add` produces: a `.git` *file* in the
    worktree pointing back at `<main>/.git/worktrees/<name>`."""
    worktree_dir = main_root / ".pairmode-worktrees" / story_id
    worktree_dir.mkdir(parents=True)
    git_worktrees_dir = main_root / ".git" / "worktrees" / story_id
    git_worktrees_dir.mkdir(parents=True)
    (worktree_dir / ".git").write_text(f"gitdir: {git_worktrees_dir}\n")
    return worktree_dir


def test_resolve_main_project_root_from_linked_worktree(tmp_path: Path) -> None:
    """cwd = a real linked-worktree directory — resolves back to the main
    checkout root via the .git pointer file."""
    main_root = tmp_path / "main"
    main_root.mkdir()
    worktree_dir = _make_linked_worktree(main_root, STORY_ID)
    resolved = scope_guard._resolve_main_project_root(worktree_dir)
    assert resolved == main_root


def test_resolve_main_project_root_end_to_end_via_check_path(tmp_path: Path) -> None:
    """Full integration: state.json + permissions live only in the main
    checkout; check_path is called with project_dir = the worktree cwd and
    still enforces scope correctly."""
    main_root = tmp_path / "main"
    main_root.mkdir()
    worktree_dir = _make_linked_worktree(main_root, STORY_ID)
    _write_state(main_root, STORY_ID)
    _write_permissions(main_root, STORY_ID, ["skills/foo.py"])

    # A declared file, addressed as an absolute path inside the worktree —
    # exactly what Claude Code would send as Edit tool_input.file_path.
    declared_abs = worktree_dir / "skills" / "foo.py"
    allowed, reason = scope_guard.check_path(declared_abs, worktree_dir)
    assert allowed is True
    assert reason == "allowed"

    # An undeclared file inside the same worktree — still blocked.
    undeclared_abs = worktree_dir / "README.md"
    allowed, reason = scope_guard.check_path(undeclared_abs, worktree_dir)
    assert allowed is False
    assert "not in story scope" in reason


def test_resolve_main_project_root_falls_back_when_not_a_worktree(tmp_path: Path) -> None:
    """No .git file (e.g. a plain directory, or the main checkout itself
    where .git is a directory) — returns project unchanged."""
    assert scope_guard._resolve_main_project_root(tmp_path) == tmp_path

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    assert scope_guard._resolve_main_project_root(tmp_path) == tmp_path

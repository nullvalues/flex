"""Tests for skills/pairmode/scripts/scope_guard.py"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the scripts directory is on sys.path so the module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))

import scope_guard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STORY_ID = "INFRA-999"


def _fresh_iso() -> str:
    """A `set_at` timestamp that is always fresh under
    `scope_guard.entry_is_fresh` regardless of when the suite runs
    (INFRA-271, CER-080)."""
    return datetime.now(timezone.utc).isoformat()


def _stale_iso(days: float) -> str:
    """A `set_at` timestamp *days* old — always stale under
    `scope_guard.STATE_STORY_MAX_AGE_HOURS` (INFRA-271, CER-080). Used only
    in tests that mean to exercise staleness; every other fixture in this
    file stamps a fresh timestamp so pre-INFRA-271 "active story" cases do
    not silently become "no active story" cases."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# Two distinct FRESH timestamps, one second apart, for fixtures that need two
# entries with a defined relative order but both still well within
# STATE_STORY_MAX_AGE_HOURS (the two-builder and ambiguity fixtures below —
# INFRA-271 replaces the old one-day-apart 2026-01-01/2026-01-02 literals,
# which became stale under the new staleness rule).
_FRESH_1 = _fresh_iso()
_FRESH_2 = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()


def _write_state(tmp_path: Path, story_id: str | None) -> None:
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    if story_id is not None:
        state = {"current_story": {"id": story_id, "set_at": _fresh_iso()}}
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
# Mid-story fail-closed protected-path override (INFRA-253)
# ---------------------------------------------------------------------------


def test_scope_guard_blocks_protected_path_mid_story_no_permissions_file(tmp_path: Path) -> None:
    """Active story, but its permissions artifact was never created — a
    protected path must deny, not fail open (INFRA-253 Ensures 1)."""
    _write_state(tmp_path, STORY_ID)
    # Do NOT write a permissions file for STORY_ID.
    allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
    assert allowed is False
    assert STORY_ID in reason
    assert "primary_files" in reason


def test_scope_guard_blocks_protected_path_mid_story_empty_allowed_paths(tmp_path: Path) -> None:
    """Active story, permissions artifact exists but allowed_paths is empty —
    a protected path must deny, not fail open (INFRA-253 Ensures 1)."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, [])
    allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
    assert allowed is False
    assert STORY_ID in reason
    assert "primary_files" in reason


def test_scope_guard_blocks_protected_path_mid_story_malformed_permissions(tmp_path: Path) -> None:
    """Active story, permissions artifact exists but is malformed JSON — a
    protected path must deny, not fail open (INFRA-253 Ensures 1)."""
    _write_state(tmp_path, STORY_ID)
    perm_dir = tmp_path / "docs" / "phases" / "permissions"
    perm_dir.mkdir(parents=True, exist_ok=True)
    (perm_dir / f"{STORY_ID}.json").write_text("{ not valid json !!!")
    allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
    assert allowed is False
    assert STORY_ID in reason
    assert "primary_files" in reason


def test_scope_guard_allows_non_protected_path_mid_story_no_permissions_file(tmp_path: Path) -> None:
    """Active story, no permissions artifact yet, non-protected path — still
    fails open (unchanged non-protected behavior; INFRA-253 Ensures 1)."""
    _write_state(tmp_path, STORY_ID)
    allowed, reason = scope_guard.check_path("src/app.py", tmp_path)
    assert allowed is True
    assert "no permissions file" in reason


def test_scope_guard_allows_declared_protected_path_still_works(tmp_path: Path) -> None:
    """Regression (INFRA-253 Ensures 2): a protected path explicitly present
    in allowed_paths remains allowed."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["hooks/pre_tool_use.py"])
    allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
    assert allowed is True
    assert reason == "allowed"


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


# ---------------------------------------------------------------------------
# INFRA-255: relative-path containment — _normalise() / _norm_str() unit
# tests, plus check_path() traversal-deny regression across every guard
# state.
# ---------------------------------------------------------------------------


def test_normalise_relative_traversal_escapes_root(tmp_path: Path) -> None:
    """A relative path with enough '..' segments to walk above the project
    root must return None — it must NOT be passed through verbatim."""
    assert scope_guard._normalise("../../../etc/passwd", tmp_path) is None


def test_normalise_dotslash_disguised_traversal_escapes_root(tmp_path: Path) -> None:
    """'./../../etc/passwd' must also resolve+contain to None, not be
    laundered into a bare-looking relative string."""
    assert scope_guard._normalise("./../../etc/passwd", tmp_path) is None


def test_normalise_absolute_out_of_root_escapes_root(tmp_path: Path) -> None:
    assert scope_guard._normalise("/etc/passwd", tmp_path) is None


def test_normalise_in_root_relative_path_unchanged(tmp_path: Path) -> None:
    assert scope_guard._normalise("skills/pairmode/scripts/scope_guard.py", tmp_path) == (
        "skills/pairmode/scripts/scope_guard.py"
    )


def test_normalise_in_root_dotslash_prefixed_path_matches_plain(tmp_path: Path) -> None:
    assert scope_guard._normalise("./skills/pairmode/scripts/scope_guard.py", tmp_path) == (
        "skills/pairmode/scripts/scope_guard.py"
    )


def test_normalise_in_root_absolute_path_matches_relative(tmp_path: Path) -> None:
    abs_path = tmp_path / "skills" / "pairmode" / "scripts" / "scope_guard.py"
    assert scope_guard._normalise(abs_path, tmp_path) == "skills/pairmode/scripts/scope_guard.py"


def test_normalise_traversal_that_lands_back_in_root_resolves(tmp_path: Path) -> None:
    """'docs/../hooks/pre_tool_use.py' stays inside the root once resolved —
    it must normalise to its real repo-relative identity, not escape."""
    assert scope_guard._normalise("docs/../hooks/pre_tool_use.py", tmp_path) == (
        "hooks/pre_tool_use.py"
    )


def test_norm_str_does_not_launder_dotslash_disguised_traversal() -> None:
    """Regression for the str.lstrip('./') character-class bug: a path
    starting with './../../' must not be stripped down to a bare-looking
    relative string."""
    result = scope_guard._norm_str("./../../etc/passwd")
    assert result != "etc/passwd"
    assert result == "../../etc/passwd"


def test_norm_str_removes_single_leading_dotslash_prefix_only() -> None:
    assert scope_guard._norm_str("./skills/foo.py") == "skills/foo.py"


def test_norm_str_leaves_path_without_dotslash_prefix_unchanged() -> None:
    assert scope_guard._norm_str("skills/foo.py") == "skills/foo.py"


TRAVERSAL_PATH = "../../../etc/passwd"
DOTSLASH_TRAVERSAL_PATH = "./../../etc/passwd"


def _state_no_active_story(tmp_path: Path) -> None:
    _write_state(tmp_path, story_id=None)


def _state_missing_permissions(tmp_path: Path) -> None:
    _write_state(tmp_path, STORY_ID)
    # Do NOT write a permissions file.


def _state_malformed_permissions(tmp_path: Path) -> None:
    _write_state(tmp_path, STORY_ID)
    perm_dir = tmp_path / "docs" / "phases" / "permissions"
    perm_dir.mkdir(parents=True, exist_ok=True)
    (perm_dir / f"{STORY_ID}.json").write_text("{ not valid json !!!")


def _state_empty_allowed_paths(tmp_path: Path) -> None:
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, [])


def _state_populated_allowed_paths(tmp_path: Path) -> None:
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])


GUARD_STATES = [
    pytest.param(_state_no_active_story, id="no-active-story"),
    pytest.param(_state_missing_permissions, id="missing-permissions"),
    pytest.param(_state_malformed_permissions, id="malformed-permissions"),
    pytest.param(_state_empty_allowed_paths, id="empty-allowed-paths"),
    pytest.param(_state_populated_allowed_paths, id="populated-allowed-paths"),
]


@pytest.mark.parametrize("setup_state", GUARD_STATES)
def test_relative_traversal_denied_in_every_guard_state(
    tmp_path: Path, setup_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures 6/9: a relative traversal path must be denied with
    'path escapes project root' regardless of guard state — it must never
    reach a fail-open return.

    INFRA-271 (CER-087, B7/B8): `home` is faked here (never the developer's
    real one) so this regression proves the allow-list layer added on top of
    `_normalise`'s containment does not weaken it, without this test's
    outcome ever depending on what actually exists under the real `~/.claude`."""
    setup_state(tmp_path)
    fake_home = tmp_path / "fake-home"
    with patch.object(scope_guard.Path, "home", staticmethod(lambda: fake_home)):
        allowed, reason = scope_guard.check_path(TRAVERSAL_PATH, tmp_path)
    assert allowed is False
    assert "escapes project root" in reason


@pytest.mark.parametrize("setup_state", GUARD_STATES)
def test_dotslash_disguised_traversal_denied_in_every_guard_state(
    tmp_path: Path, setup_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_state(tmp_path)
    fake_home = tmp_path / "fake-home"
    with patch.object(scope_guard.Path, "home", staticmethod(lambda: fake_home)):
        allowed, reason = scope_guard.check_path(DOTSLASH_TRAVERSAL_PATH, tmp_path)
    assert allowed is False
    assert "escapes project root" in reason


@pytest.mark.parametrize("setup_state", GUARD_STATES)
def test_absolute_out_of_root_denied_in_every_guard_state(
    tmp_path: Path, setup_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_state(tmp_path)
    fake_home = tmp_path / "fake-home"
    with patch.object(scope_guard.Path, "home", staticmethod(lambda: fake_home)):
        allowed, reason = scope_guard.check_path("/etc/passwd", tmp_path)
    assert allowed is False
    assert "escapes project root" in reason


def test_traversal_back_into_root_protected_path_denied_no_active_story(tmp_path: Path) -> None:
    """Ensures 8: a protected path expressed with traversal segments that
    still land inside the repo resolves to its real identity and is denied
    under the protected-path rule, not laundered past PROTECTED_GLOBS."""
    _write_state(tmp_path, story_id=None)
    allowed, reason = scope_guard.check_path("docs/../hooks/pre_tool_use.py", tmp_path)
    assert allowed is False
    assert "protected path" in reason


def test_traversal_back_into_root_protected_path_denied_mid_story_no_permissions(
    tmp_path: Path,
) -> None:
    _write_state(tmp_path, STORY_ID)
    allowed, reason = scope_guard.check_path("docs/../hooks/pre_tool_use.py", tmp_path)
    assert allowed is False
    assert "protected path" in reason


def test_worktree_prefixed_relative_path_still_matches_allowed_paths(tmp_path: Path) -> None:
    """Regression: the normalisation rewrite must not disturb the existing
    worktree-prefix-stripping behaviour for the active story's own
    worktree-relative paths."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    worktree_relative = f".pairmode-worktrees/{STORY_ID}/skills/foo.py"
    allowed, reason = scope_guard.check_path(worktree_relative, tmp_path)
    assert allowed is True
    assert reason == "allowed"


# ---------------------------------------------------------------------------
# INFRA-320 (CER-128) § A — standing shared surfaces
# ---------------------------------------------------------------------------


def _write_permissions_full(tmp_path: Path, story_id: str, payload: dict) -> None:
    """Write a permissions artifact with an arbitrary payload dict — used
    where a test needs to control `standing_paths`/`story_phase` directly
    rather than the plain `_write_permissions` shape."""
    perm_dir = tmp_path / "docs" / "phases" / "permissions"
    perm_dir.mkdir(parents=True, exist_ok=True)
    (perm_dir / f"{story_id}.json").write_text(json.dumps(payload))


def test_standing_surface_allowed_with_distinct_reason(tmp_path: Path) -> None:
    """A candidate in scope_guard.STANDING_SURFACES is allowed with a reason
    distinguishable from a plain declared-file allow (A3)."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    allowed, reason = scope_guard.check_path("docs/cer/backlog.md", tmp_path)
    assert allowed is True
    assert reason == "allowed (standing shared surface)"


def test_protected_glob_denied_even_when_listed_standing(tmp_path: Path) -> None:
    """A4: the standing allowance never overrides PROTECTED_GLOBS, even for
    a synthetic standing entry pointing straight at a protected glob."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    with patch.object(
        scope_guard, "STANDING_SURFACES", ("hooks/pre_tool_use.py",)
    ):
        allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
    assert allowed is False
    assert reason != "allowed (standing shared surface)"


def test_undeclared_code_file_still_denied_with_unchanged_message(tmp_path: Path) -> None:
    """A8: an undeclared code file outside the standing set is still denied
    with the byte-identical deny string."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    allowed, reason = scope_guard.check_path("README.md", tmp_path)
    assert allowed is False
    assert reason == f"not in story scope for {STORY_ID}: README.md"


def test_legacy_artifact_without_standing_paths_still_grants_them(tmp_path: Path) -> None:
    """A7: an artifact generated before INFRA-320 (no `standing_paths` key)
    still grants the live-computed standing surfaces — a migration-free
    upgrade."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions_full(
        tmp_path, STORY_ID, {"story_id": STORY_ID, "allowed_paths": ["skills/foo.py"]}
    )
    allowed, reason = scope_guard.check_path("docs/architecture.md", tmp_path)
    assert allowed is True
    assert reason == "allowed (standing shared surface)"


def test_malformed_standing_paths_degrades_to_live_computation(tmp_path: Path) -> None:
    """A7: a malformed `standing_paths` value (not a list of strings)
    degrades to the live computation rather than raising."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions_full(
        tmp_path,
        STORY_ID,
        {
            "story_id": STORY_ID,
            "allowed_paths": ["skills/foo.py"],
            "standing_paths": "not-a-list",
        },
    )
    allowed, reason = scope_guard.check_path("docs/cer/backlog.md", tmp_path)
    assert allowed is True
    assert reason == "allowed (standing shared surface)"


def test_standing_paths_for_includes_story_spec_and_phase() -> None:
    result = scope_guard.standing_paths_for("INFRA-999", "113")
    assert "docs/cer/backlog.md" in result
    assert "docs/architecture.md" in result
    assert "docs/stories/INFRA/INFRA-999.md" in result
    assert "docs/phases/phase-113.md" in result


def test_standing_paths_for_no_phase_omits_phase_doc() -> None:
    result = scope_guard.standing_paths_for("INFRA-999", None)
    assert not any(p.startswith("docs/phases/phase-") for p in result)


def test_standing_paths_for_malformed_story_id_returns_static_surfaces_only() -> None:
    result = scope_guard.standing_paths_for("not-a-story-id", "113")
    assert result == scope_guard.STANDING_SURFACES + ("docs/phases/phase-113.md",)


def test_standing_paths_for_never_raises_and_performs_no_io(tmp_path: Path) -> None:
    # Total: no exception for any weird input, and no filesystem access.
    assert scope_guard.standing_paths_for(None, None) == scope_guard.STANDING_SURFACES
    assert scope_guard.standing_paths_for("", "") == scope_guard.STANDING_SURFACES


# ---------------------------------------------------------------------------
# INFRA-281 (CER-095.2): resolve_call_story — per-call story resolution
# ---------------------------------------------------------------------------


def _write_keyed_state(tmp_path: Path, stories: dict[str, str]) -> None:
    """Write a story-keyed ``current_stories`` record (no flat mirror)."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    current_stories = {
        sid: {"id": sid, "set_at": set_at} for sid, set_at in stories.items()
    }
    (companion / "state.json").write_text(json.dumps({"current_stories": current_stories}))


def _make_worktree_dir(main_root: Path, story_id: str) -> Path:
    """Create only the ``.pairmode-worktrees/<story_id>/`` directory — no
    ``.git`` pointer file, so this is NOT a linked-worktree cwd, only a
    worktree-shaped path on disk."""
    worktree_dir = main_root / ".pairmode-worktrees" / story_id
    worktree_dir.mkdir(parents=True)
    return worktree_dir


class TestResolveCallStorySources:
    """B5: one case per RESOLVE_CALL_STORY_SOURCES literal."""

    def test_worktree_cwd(self, tmp_path: Path) -> None:
        main_root = tmp_path / "main"
        main_root.mkdir()
        worktree_dir = _make_linked_worktree(main_root, STORY_ID)
        story_id, source = scope_guard.resolve_call_story(worktree_dir)
        assert (story_id, source) == (STORY_ID, "worktree-cwd")

    def test_worktree_path_nested(self, tmp_path: Path) -> None:
        """A nested path inside the worktree directory still resolves."""
        main_root = tmp_path / "main"
        main_root.mkdir()
        _make_worktree_dir(main_root, STORY_ID)
        file_path = (
            main_root / ".pairmode-worktrees" / STORY_ID / "skills" / "pairmode" / "foo.py"
        )
        story_id, source = scope_guard.resolve_call_story(main_root, file_path)
        assert (story_id, source) == (STORY_ID, "worktree-path")

    def test_worktree_path(self, tmp_path: Path) -> None:
        """cwd is the main checkout (no worktree signal); the target path,
        under a worktree directory that genuinely exists on disk, supplies
        the story ID instead."""
        main_root = tmp_path / "main"
        main_root.mkdir()
        _make_worktree_dir(main_root, STORY_ID)
        file_path = main_root / ".pairmode-worktrees" / STORY_ID / "skills" / "foo.py"
        story_id, source = scope_guard.resolve_call_story(main_root, file_path)
        assert (story_id, source) == (STORY_ID, "worktree-path")

    def test_worktree_path_non_matching_segment_falls_through(self, tmp_path: Path) -> None:
        """A worktree-shaped path segment that does not match _STORY_ID_RE
        must not be treated as a story ID."""
        main_root = tmp_path / "main"
        main_root.mkdir()
        (main_root / ".pairmode-worktrees" / "not-a-story-id").mkdir(parents=True)
        file_path = main_root / ".pairmode-worktrees" / "not-a-story-id" / "skills" / "foo.py"
        story_id, source = scope_guard.resolve_call_story(main_root, file_path)
        assert story_id is None
        assert source == "none"

    def test_worktree_path_requires_directory_to_exist(self, tmp_path: Path) -> None:
        """SECURITY: a worktree-shaped path segment that names a directory
        which does NOT exist on disk must not be trusted as a story
        identity — this is the corroboration that keeps a path-only claim
        from defeating _strip_worktree_prefix's guarantee (see
        test_scope_guard_blocks_foreign_story_worktree_path_bypass)."""
        main_root = tmp_path / "main"
        main_root.mkdir()
        # No .pairmode-worktrees/INFRA-111 directory created.
        file_path = main_root / ".pairmode-worktrees" / "INFRA-111" / "skills" / "foo.py"
        story_id, source = scope_guard.resolve_call_story(main_root, file_path)
        assert story_id is None
        assert source == "none"

    def test_state_single(self, tmp_path: Path) -> None:
        _write_keyed_state(tmp_path, {"A-001": _FRESH_1})
        story_id, source = scope_guard.resolve_call_story(tmp_path)
        assert (story_id, source) == ("A-001", "state-single")

    def test_state_legacy(self, tmp_path: Path) -> None:
        _write_state(tmp_path, STORY_ID)
        story_id, source = scope_guard.resolve_call_story(tmp_path)
        assert (story_id, source) == (STORY_ID, "state-legacy")

    def test_ambiguous(self, tmp_path: Path) -> None:
        _write_keyed_state(
            tmp_path,
            {
                "A-001": _FRESH_1,
                "B-002": _FRESH_2,
            },
        )
        story_id, source = scope_guard.resolve_call_story(tmp_path)
        assert story_id is None
        assert source == "ambiguous"

    def test_none(self, tmp_path: Path) -> None:
        story_id, source = scope_guard.resolve_call_story(tmp_path)
        assert story_id is None
        assert source == "none"

    def test_never_raises_on_garbage_input(self) -> None:
        story_id, source = scope_guard.resolve_call_story(object())  # type: ignore[arg-type]
        assert story_id is None
        assert source == "none"

    def test_sources_enumerable(self) -> None:
        # INFRA-271 (CER-080, A3): "stale" joins the set of resolution
        # sources once the state fallback ages out an untrusted stamp.
        assert scope_guard.RESOLVE_CALL_STORY_SOURCES == {
            "worktree-cwd",
            "worktree-path",
            "state-single",
            "state-legacy",
            "ambiguous",
            "stale",
            "none",
        }


class TestCheckPathAmbiguous:
    """B6: the ambiguous case degrades to no-active-story, never a guess."""

    def test_ambiguous_non_protected_path_allowed(self, tmp_path: Path) -> None:
        _write_keyed_state(
            tmp_path,
            {
                "A-001": _FRESH_1,
                "B-002": _FRESH_2,
            },
        )
        allowed, reason = scope_guard.check_path("src/app.py", tmp_path)
        assert allowed is True
        assert "ambiguous" in reason
        assert "A-001" in reason
        assert "B-002" in reason

    def test_ambiguous_protected_path_denied(self, tmp_path: Path) -> None:
        _write_keyed_state(
            tmp_path,
            {
                "A-001": _FRESH_1,
                "B-002": _FRESH_2,
            },
        )
        allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
        assert allowed is False
        assert "ambiguous" in reason
        assert "A-001" in reason
        assert "B-002" in reason
        assert "protected path" in reason


class TestTwoConcurrentBuildersScopedIndependently:
    """B7: the phase-109 checkpoint-proves scenario — stamping order must
    not affect any of the four results."""

    def _setup(self, tmp_path: Path, stamp_order: list[str]) -> tuple[Path, Path, Path]:
        main_root = tmp_path / "main"
        main_root.mkdir()
        wt_a = _make_linked_worktree(main_root, "A-001")
        wt_b = _make_linked_worktree(main_root, "B-002")
        _write_permissions(main_root, "A-001", ["a.py"])
        _write_permissions(main_root, "B-002", ["b.py"])
        entries = {
            "A-001": {"id": "A-001", "set_at": _FRESH_1},
            "B-002": {"id": "B-002", "set_at": _FRESH_2},
        }
        companion = main_root / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ordered = {sid: entries[sid] for sid in stamp_order}
        (companion / "state.json").write_text(json.dumps({"current_stories": ordered}))
        return main_root, wt_a, wt_b

    def _assert_matrix(self, main_root: Path, wt_a: Path, wt_b: Path) -> None:
        allowed, reason = scope_guard.check_path("a.py", wt_a)
        assert allowed is True

        allowed, reason = scope_guard.check_path("b.py", wt_a)
        assert allowed is False
        assert "A-001" in reason

        allowed, reason = scope_guard.check_path("b.py", wt_b)
        assert allowed is True

        allowed, reason = scope_guard.check_path("a.py", wt_b)
        assert allowed is False
        assert "B-002" in reason

    def test_matrix_stamped_a_then_b(self, tmp_path: Path) -> None:
        main_root, wt_a, wt_b = self._setup(tmp_path, ["A-001", "B-002"])
        self._assert_matrix(main_root, wt_a, wt_b)

    def test_matrix_stamped_b_then_a(self, tmp_path: Path) -> None:
        main_root, wt_a, wt_b = self._setup(tmp_path, ["B-002", "A-001"])
        self._assert_matrix(main_root, wt_a, wt_b)


class TestReadCurrentStoryWrapper:
    """B10: _read_current_story is a thin wrapper over the state-only rules."""

    def test_state_single_returns_id(self, tmp_path: Path) -> None:
        _write_keyed_state(tmp_path, {"A-001": _FRESH_1})
        assert scope_guard._read_current_story(tmp_path) == "A-001"

    def test_state_legacy_returns_id(self, tmp_path: Path) -> None:
        _write_state(tmp_path, STORY_ID)
        assert scope_guard._read_current_story(tmp_path) == STORY_ID

    def test_ambiguous_returns_none(self, tmp_path: Path) -> None:
        _write_keyed_state(
            tmp_path,
            {
                "A-001": _FRESH_1,
                "B-002": _FRESH_2,
            },
        )
        assert scope_guard._read_current_story(tmp_path) is None

    def test_none_returns_none(self, tmp_path: Path) -> None:
        assert scope_guard._read_current_story(tmp_path) is None




# ---------------------------------------------------------------------------
# INFRA-271 (CER-080): idle-checkout tolerance — entry_is_fresh,
# _resolve_story_from_state staleness ordering, and check_path's stale
# no-story branch.
# ---------------------------------------------------------------------------


class TestEntryIsFresh:
    """A2: `entry_is_fresh` predicate — never raises, fails toward
    enforcement on ambiguous input."""

    def test_fresh_entry_is_fresh(self) -> None:
        assert scope_guard.entry_is_fresh({"set_at": _fresh_iso()}) is True

    def test_stale_entry_is_not_fresh(self) -> None:
        assert scope_guard.entry_is_fresh({"set_at": _stale_iso(30)}) is False

    def test_boundary_just_under_cutoff_is_fresh(self) -> None:
        just_under = (
            datetime.now(timezone.utc)
            - timedelta(hours=scope_guard.STATE_STORY_MAX_AGE_HOURS - 0.01)
        ).isoformat()
        assert scope_guard.entry_is_fresh({"set_at": just_under}) is True

    def test_boundary_just_over_cutoff_is_stale(self) -> None:
        just_over = (
            datetime.now(timezone.utc)
            - timedelta(hours=scope_guard.STATE_STORY_MAX_AGE_HOURS + 0.01)
        ).isoformat()
        assert scope_guard.entry_is_fresh({"set_at": just_over}) is False

    def test_non_dict_entry_is_not_fresh(self) -> None:
        assert scope_guard.entry_is_fresh("not-a-dict") is False  # type: ignore[arg-type]
        assert scope_guard.entry_is_fresh(None) is False  # type: ignore[arg-type]

    def test_missing_set_at_is_not_fresh(self) -> None:
        assert scope_guard.entry_is_fresh({}) is False

    def test_empty_set_at_is_not_fresh(self) -> None:
        assert scope_guard.entry_is_fresh({"set_at": ""}) is False

    def test_non_string_set_at_is_not_fresh(self) -> None:
        assert scope_guard.entry_is_fresh({"set_at": 12345}) is False  # type: ignore[dict-item]

    def test_unparseable_set_at_is_not_fresh(self) -> None:
        assert scope_guard.entry_is_fresh({"set_at": "not-a-timestamp"}) is False

    def test_naive_set_at_treated_as_utc(self) -> None:
        naive_fresh = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        assert scope_guard.entry_is_fresh({"set_at": naive_fresh}) is True

    def test_future_set_at_is_fresh(self) -> None:
        """Clock skew must not silently switch enforcement off."""
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        assert scope_guard.entry_is_fresh({"set_at": future}) is True

    def test_custom_max_age_hours_honoured(self) -> None:
        three_hours_old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        assert scope_guard.entry_is_fresh({"set_at": three_hours_old}, max_age_hours=1) is False
        assert scope_guard.entry_is_fresh({"set_at": three_hours_old}, max_age_hours=48) is True

    def test_never_raises_on_garbage(self) -> None:
        assert scope_guard.entry_is_fresh(object()) is False  # type: ignore[arg-type]
        assert scope_guard.entry_is_fresh({"set_at": object()}) is False  # type: ignore[dict-item]


class TestResolveStoryFromStateStaleness:
    """A4/A9: the five-branch resolution order once per-entry staleness is
    applied, including the ambiguity-beats-staleness cases."""

    def test_single_fresh_entry(self, tmp_path: Path) -> None:
        _write_keyed_state(tmp_path, {"A-001": _fresh_iso()})
        assert scope_guard._resolve_story_from_state(tmp_path) == ("A-001", "state-single")

    def test_two_fresh_entries_ambiguous(self, tmp_path: Path) -> None:
        second = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        _write_keyed_state(tmp_path, {"A-001": _fresh_iso(), "B-002": second})
        assert scope_guard._resolve_story_from_state(tmp_path) == (None, "ambiguous")

    def test_no_fresh_entries_but_keyed_non_empty_is_stale(self, tmp_path: Path) -> None:
        _write_keyed_state(tmp_path, {"A-001": _stale_iso(30)})
        assert scope_guard._resolve_story_from_state(tmp_path) == (None, "stale")

    def test_empty_keyed_fresh_legacy_is_state_legacy(self, tmp_path: Path) -> None:
        _write_state(tmp_path, STORY_ID)
        assert scope_guard._resolve_story_from_state(tmp_path) == (STORY_ID, "state-legacy")

    def test_empty_keyed_stale_legacy_is_stale(self, tmp_path: Path) -> None:
        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        state = {"current_story": {"id": STORY_ID, "set_at": _stale_iso(30)}}
        (companion / "state.json").write_text(json.dumps(state))
        assert scope_guard._resolve_story_from_state(tmp_path) == (None, "stale")

    def test_nothing_at_all_is_none(self, tmp_path: Path) -> None:
        assert scope_guard._resolve_story_from_state(tmp_path) == (None, "none")

    def test_one_fresh_one_stale_resolves_state_single_on_fresh(self, tmp_path: Path) -> None:
        """A9: the stale entry is not counted — this is state-single, not
        ambiguous."""
        _write_keyed_state(tmp_path, {"A-001": _fresh_iso(), "B-002": _stale_iso(30)})
        assert scope_guard._resolve_story_from_state(tmp_path) == ("A-001", "state-single")

    def test_two_fresh_is_ambiguous(self, tmp_path: Path) -> None:
        second = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        _write_keyed_state(tmp_path, {"A-001": _fresh_iso(), "B-002": second})
        assert scope_guard._resolve_story_from_state(tmp_path) == (None, "ambiguous")

    def test_two_stale_is_stale(self, tmp_path: Path) -> None:
        _write_keyed_state(tmp_path, {"A-001": _stale_iso(30), "B-002": _stale_iso(45)})
        assert scope_guard._resolve_story_from_state(tmp_path) == (None, "stale")


class TestWorktreeClaimNeverAgesOut:
    """A5: worktree-cwd/worktree-path resolution ignores set_at entirely."""

    def test_worktree_cwd_with_30_day_old_state_entry(self, tmp_path: Path) -> None:
        main_root = tmp_path / "main"
        main_root.mkdir()
        worktree_dir = _make_linked_worktree(main_root, STORY_ID)
        _write_keyed_state(main_root, {STORY_ID: _stale_iso(30)})
        story_id, source = scope_guard.resolve_call_story(worktree_dir)
        assert (story_id, source) == (STORY_ID, "worktree-cwd")


class TestCheckPathStale:
    """A6/A7/A8: a stale-only state fails open for ordinary paths (naming
    the cutoff and remedy) but stays fail-closed for protected paths."""

    def test_stale_state_allows_ordinary_path(self, tmp_path: Path) -> None:
        _write_keyed_state(tmp_path, {STORY_ID: _stale_iso(30)})
        allowed, reason = scope_guard.check_path("src/app.py", tmp_path)
        assert allowed is True
        assert "stale" in reason
        assert str(scope_guard.STATE_STORY_MAX_AGE_HOURS) in reason
        assert "clear-stale-stories" in reason
        assert reason != "no active story — allowing"

    def test_stale_state_denies_protected_path(self, tmp_path: Path) -> None:
        _write_keyed_state(tmp_path, {STORY_ID: _stale_iso(30)})
        allowed, reason = scope_guard.check_path("hooks/pre_tool_use.py", tmp_path)
        assert allowed is False
        assert "is a protected path" in reason

    def test_read_current_story_wrapper_stale_only_returns_none(self, tmp_path: Path) -> None:
        _write_keyed_state(tmp_path, {STORY_ID: _stale_iso(30)})
        assert scope_guard._read_current_story(tmp_path) is None


# ---------------------------------------------------------------------------
# INFRA-271 (CER-087): harness-owned out-of-root write allow-list.
# ---------------------------------------------------------------------------


def _harness_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    return home


class TestHarnessOwnedPrefixes:
    """B1: the allow-list is derived, resolved, narrow, and never raises."""

    def test_memory_and_plans_and_scratchpad_prefixes_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        home = _harness_home(tmp_path)
        tmp_root = tmp_path / "tmproot"
        tmp_root.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_root))
        monkeypatch.setattr(os, "getuid", lambda: 4242, raising=False)

        prefixes = scope_guard.harness_owned_prefixes(project, home=home)
        key = str(project.resolve()).replace("/", "-")

        assert (home / ".claude" / "projects" / key / "memory").resolve() in prefixes
        assert (home / ".claude" / "plans").resolve() in prefixes
        assert (tmp_root / "claude-4242" / key).resolve() in prefixes

    def test_raw_project_dir_key_also_included_when_different(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        raw = tmp_path / "project-harness"
        raw.mkdir()
        home = _harness_home(tmp_path)
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmproot"))
        monkeypatch.setattr(os, "getuid", lambda: 1, raising=False)

        prefixes = scope_guard.harness_owned_prefixes(project, raw_project_dir=raw, home=home)
        raw_key = str(raw.resolve()).replace("/", "-")
        assert (home / ".claude" / "projects" / raw_key / "memory").resolve() in prefixes

    def test_never_raises_when_home_lookup_fails(self, tmp_path: Path) -> None:
        class _BoomHome:
            def resolve(self):
                raise OSError("boom")

        result = scope_guard.harness_owned_prefixes(tmp_path, home=_BoomHome())  # type: ignore[arg-type]
        assert result == []


class TestOutOfRootAllowList:
    """B2/B3/B6/B7/B8: allowed harness prefixes vs. everything else."""

    def _key(self, project: Path) -> str:
        return str(project.resolve()).replace("/", "-")

    def test_harness_memory_write_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        home = _harness_home(tmp_path)
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmproot"))
        monkeypatch.setattr(os, "getuid", lambda: 7, raising=False)
        key = self._key(project)
        memory_dir = home / ".claude" / "projects" / key / "memory"
        memory_dir.mkdir(parents=True)
        target = memory_dir / "note.md"

        with patch.object(scope_guard.Path, "home", staticmethod(lambda: home)):
            allowed, reason = scope_guard._out_of_root_decision(target, project, project)
        assert allowed is True
        assert "harness-owned" in reason

    def test_excluded_paths_still_denied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """B2: the allow-list is narrow — these all still deny."""
        project = tmp_path / "project"
        project.mkdir()
        home = _harness_home(tmp_path)
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmproot"))
        monkeypatch.setattr(os, "getuid", lambda: 7, raising=False)
        key = self._key(project)

        excluded = [
            home / ".claude" / "settings.json",
            home / ".claude" / "CLAUDE.md",
            home / ".claude" / "policies" / "auth-rbac.md",
            home / ".claude" / "plugins" / "x.json",
            home / ".claude" / "skills" / "x" / "SKILL.md",
            home / ".claude" / "projects" / key / "session-uuid.jsonl",
            Path("/etc/passwd"),
        ]

        with patch.object(scope_guard.Path, "home", staticmethod(lambda: home)):
            for path in excluded:
                allowed, reason = scope_guard._out_of_root_decision(path, project, project)
                assert allowed is False, f"{path} unexpectedly allowed: {reason}"
                assert reason == "path escapes project root"

    def test_transcript_jsonl_directory_excluded_memory_subdir_included(
        self, tmp_path: Path
    ) -> None:
        """B2: the transcript exclusion is load-bearing — an agent that
        could write .jsonl transcripts could forge its own effort record."""
        project = tmp_path / "project"
        project.mkdir()
        home = _harness_home(tmp_path)
        key = self._key(project)
        prefixes = scope_guard.harness_owned_prefixes(project, home=home)
        transcript_dir = (home / ".claude" / "projects" / key).resolve()
        assert transcript_dir not in prefixes
        memory_dir = (home / ".claude" / "projects" / key / "memory").resolve()
        assert memory_dir in prefixes

    def test_relative_traversal_that_resolves_into_memory_dir_allowed(
        self, tmp_path: Path
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        home = _harness_home(tmp_path)
        key = self._key(project)
        memory_dir = home / ".claude" / "projects" / key / "memory"
        memory_dir.mkdir(parents=True)

        # A relative traversal string that genuinely resolves into the
        # allow-listed memory directory (nothing to forge — it lands where
        # it lands) is allowed, exactly like any other path that resolves
        # there.
        traversal_into_memory = str(memory_dir / ".." / "memory" / "note.md")
        with patch.object(scope_guard.Path, "home", staticmethod(lambda: home)):
            allowed, reason = scope_guard._out_of_root_decision(traversal_into_memory, project, project)
        assert allowed is True
        assert "harness-owned" in reason

    def test_symlink_under_memory_pointing_elsewhere_denied(self, tmp_path: Path) -> None:
        """A path string that merely *contains* the allow-listed prefix text
        but resolves elsewhere (a symlink under the memory dir pointing at
        an outside target) must be denied — string containment is not the
        comparison; `Path.is_relative_to` on the *resolved* path is."""
        project = tmp_path / "project"
        project.mkdir()
        home = _harness_home(tmp_path)
        key = self._key(project)
        memory_dir = home / ".claude" / "projects" / key / "memory"
        memory_dir.mkdir(parents=True)
        outside_target = tmp_path / "outside" / "secret.txt"
        outside_target.parent.mkdir(parents=True)
        outside_target.write_text("secret")
        link = memory_dir / "escape-link"
        link.symlink_to(outside_target)

        with patch.object(scope_guard.Path, "home", staticmethod(lambda: home)):
            allowed, reason = scope_guard._out_of_root_decision(link, project, project)
        assert allowed is False
        assert reason == "path escapes project root"

    @pytest.mark.parametrize("setup_state", GUARD_STATES)
    def test_harness_owned_write_allowed_in_every_guard_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setup_state
    ) -> None:
        """B6: an out-of-repo harness path is not story scope and is not
        scored against allowed_paths, in any guard state."""
        # `project` must NOT contain `home` — otherwise the memory-dir target
        # would resolve INSIDE the project root and never reach the
        # out-of-root decision this test means to exercise.
        project = tmp_path / "project"
        project.mkdir()
        setup_state(project)
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmproot"))
        monkeypatch.setattr(os, "getuid", lambda: 7, raising=False)
        key = self._key(project)
        memory_dir = home / ".claude" / "projects" / key / "memory"
        memory_dir.mkdir(parents=True)
        target = memory_dir / "note.md"

        with patch.object(scope_guard.Path, "home", staticmethod(lambda: home)):
            allowed, reason = scope_guard.check_path(target, project)
        assert allowed is True
        assert "harness-owned" in reason


# ---------------------------------------------------------------------------
# CER-174 (INFRA-396) — agent_type-scoped write confinement for the
# shadow-reviewer role. `check_path`'s `agent_type` parameter must confine
# agent_type="shadow-reviewer" to exactly `.pairmode-suggestions.md`,
# independent of the active story's own declared scope — even a path that
# IS in that story's `primary_files`/`touches` or a STANDING_SURFACES entry
# must still be denied for the shadow-reviewer.
# ---------------------------------------------------------------------------


def test_shadow_reviewer_denied_on_path_inside_builders_own_scope(tmp_path: Path) -> None:
    """Ensures 5: a shadow-reviewer-attributed write to a path that IS in
    the concurrently-running builder's own declared scope for the same
    story (a primary_files/touches entry) is still denied. The same path
    remains allowed for agent_type="builder" on the same story, proving the
    scopes are genuinely different, not both narrowed."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])

    shadow_allowed, shadow_reason = scope_guard.check_path(
        "skills/foo.py", tmp_path, agent_type="shadow-reviewer"
    )
    assert shadow_allowed is False
    assert shadow_reason

    builder_allowed, builder_reason = scope_guard.check_path(
        "skills/foo.py", tmp_path, agent_type="builder"
    )
    assert builder_allowed is True
    assert builder_reason == "allowed"


def test_shadow_reviewer_denied_on_standing_surface(tmp_path: Path) -> None:
    """Ensures 5: a shadow-reviewer-attributed write to a STANDING_SURFACES
    entry (docs/architecture.md) — normally allowed for the builder as a
    standing shared surface — is denied for the shadow-reviewer."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])

    allowed, reason = scope_guard.check_path(
        "docs/architecture.md", tmp_path, agent_type="shadow-reviewer"
    )
    assert allowed is False
    assert reason


def test_shadow_reviewer_allowed_on_suggestions_file(tmp_path: Path) -> None:
    """Ensures 6: check_path allows a shadow-reviewer-attributed write to
    .pairmode-suggestions.md for the active story."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])

    allowed, reason = scope_guard.check_path(
        ".pairmode-suggestions.md", tmp_path, agent_type="shadow-reviewer"
    )
    assert allowed is True
    assert reason


def test_shadow_reviewer_denied_with_no_active_story(tmp_path: Path) -> None:
    """The shadow-reviewer short-circuit runs before story resolution and
    never falls through to the no-active-story fail-open path either."""
    _write_state(tmp_path, story_id=None)

    allowed, reason = scope_guard.check_path(
        "docs/architecture.md", tmp_path, agent_type="shadow-reviewer"
    )
    assert allowed is False
    assert reason


def test_default_agent_type_unaffected_by_shadow_reviewer_scoping(tmp_path: Path) -> None:
    """Existing callers that never pass agent_type keep today's behavior
    (Ensures 8) — the new parameter defaults to preserving builder/unspecified
    behavior."""
    _write_state(tmp_path, STORY_ID)
    _write_permissions(tmp_path, STORY_ID, ["skills/foo.py"])
    allowed, reason = scope_guard.check_path("skills/foo.py", tmp_path)
    assert allowed is True
    assert reason == "allowed"

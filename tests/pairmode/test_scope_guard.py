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

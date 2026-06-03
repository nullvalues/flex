"""Tests for INFRA-140: sync deny-list merge and prune behaviour."""

from __future__ import annotations

import json
import pathlib

import pytest

from skills.pairmode.scripts.bootstrap import (
    DEFAULT_DENY,
    _SUPERSEDED_DENY_ENTRIES,
    _merge_deny_list,
    _prune_superseded_deny_entries,
)
from skills.pairmode.scripts.sync import sync_project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_project(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a minimal project structure that satisfies sync_project's depth guard."""
    project_dir = tmp_path / "org" / "project"
    project_dir.mkdir(parents=True)

    # .companion/state.json and pairmode_context.json are needed to avoid errors
    companion = project_dir / ".companion"
    companion.mkdir()
    (companion / "state.json").write_text(json.dumps({"pairmode_version": "0.2.0"}), encoding="utf-8")
    (companion / "pairmode_context.json").write_text(
        json.dumps({"project_name": "testproject", "stack": "generic", "test_command": "pytest"}),
        encoding="utf-8",
    )

    return project_dir


def _settings_deny(settings_path: pathlib.Path) -> list[str]:
    """Return the deny list from a settings.json file."""
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    return data.get("permissions", {}).get("deny", [])


# ---------------------------------------------------------------------------
# Tests for _merge_deny_list and _prune_superseded_deny_entries directly
# ---------------------------------------------------------------------------


def test_sync_adds_new_deny_entries_to_empty_settings(tmp_path: pathlib.Path) -> None:
    """Project has no .claude/settings.json; after sync, DEFAULT_DENY is present."""
    project_dir = _make_minimal_project(tmp_path)
    settings_path = project_dir / ".claude" / "settings.json"

    assert not settings_path.exists()

    # Call the functions directly (same path as sync_project uses)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _merge_deny_list(settings_path, DEFAULT_DENY)

    assert settings_path.exists()
    deny = _settings_deny(settings_path)
    for entry in DEFAULT_DENY:
        assert entry in deny, f"Expected '{entry}' in deny list"


def test_sync_adds_missing_new_deny_entries_to_existing_settings(tmp_path: pathlib.Path) -> None:
    """Project settings.json has partial new deny list; after sync all DEFAULT_DENY entries present."""
    project_dir = _make_minimal_project(tmp_path)
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Write only one of the new DEFAULT_DENY entries
    partial = {"permissions": {"deny": [DEFAULT_DENY[0]]}}
    settings_path.write_text(json.dumps(partial, indent=2), encoding="utf-8")

    _merge_deny_list(settings_path, DEFAULT_DENY)

    deny = _settings_deny(settings_path)
    for entry in DEFAULT_DENY:
        assert entry in deny, f"Expected '{entry}' in deny list"


def test_sync_does_not_duplicate_deny_entries(tmp_path: pathlib.Path) -> None:
    """Project already has full DEFAULT_DENY; sync produces no duplicates."""
    project_dir = _make_minimal_project(tmp_path)
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Pre-populate with full DEFAULT_DENY
    existing = {"permissions": {"deny": list(DEFAULT_DENY)}}
    settings_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    _merge_deny_list(settings_path, DEFAULT_DENY)

    deny = _settings_deny(settings_path)
    for entry in DEFAULT_DENY:
        assert deny.count(entry) == 1, f"Entry '{entry}' should appear exactly once"


def test_sync_prunes_superseded_entries(tmp_path: pathlib.Path) -> None:
    """settings.json has old superseded entries; after prune they are gone."""
    project_dir = _make_minimal_project(tmp_path)
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Put some superseded entries in the deny list
    old_entries = [
        "Edit(CLAUDE.md)",
        "Write(CLAUDE.md)",
        "Edit(docs/phases/**)",
        "Write(docs/phases/**)",
    ]
    existing = {"permissions": {"deny": list(old_entries)}}
    settings_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    _prune_superseded_deny_entries(settings_path, _SUPERSEDED_DENY_ENTRIES)

    deny = _settings_deny(settings_path)
    for entry in old_entries:
        assert entry not in deny, f"Superseded entry '{entry}' should have been pruned"


def test_sync_preserves_custom_deny_entries(tmp_path: pathlib.Path) -> None:
    """Custom deny entries (not in DEFAULT_DENY or _SUPERSEDED_DENY_ENTRIES) are preserved."""
    project_dir = _make_minimal_project(tmp_path)
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    custom_entry = "Edit(custom/secret/**)"
    # Mix of superseded + custom entries
    initial = {"permissions": {"deny": ["Edit(CLAUDE.md)", custom_entry]}}
    settings_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    _merge_deny_list(settings_path, DEFAULT_DENY)
    _prune_superseded_deny_entries(settings_path, _SUPERSEDED_DENY_ENTRIES)

    deny = _settings_deny(settings_path)
    assert custom_entry in deny, "Custom entry must not be pruned"
    assert "Edit(CLAUDE.md)" not in deny, "Superseded entry must be pruned"
    for entry in DEFAULT_DENY:
        assert entry in deny, f"DEFAULT_DENY entry '{entry}' must be present"


def test_prune_superseded_is_idempotent(tmp_path: pathlib.Path) -> None:
    """Calling _prune_superseded_deny_entries twice produces the same result."""
    project_dir = _make_minimal_project(tmp_path)
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    initial = {"permissions": {"deny": ["Edit(CLAUDE.md)", "Write(docs/phases/**)", "Edit(custom/path)"]}}
    settings_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    _prune_superseded_deny_entries(settings_path, _SUPERSEDED_DENY_ENTRIES)
    deny_after_first = _settings_deny(settings_path)

    _prune_superseded_deny_entries(settings_path, _SUPERSEDED_DENY_ENTRIES)
    deny_after_second = _settings_deny(settings_path)

    assert deny_after_first == deny_after_second, "Second call must produce identical result"


def test_prune_superseded_no_op_when_file_missing(tmp_path: pathlib.Path) -> None:
    """_prune_superseded_deny_entries does not raise when settings.json does not exist."""
    non_existent = tmp_path / "nonexistent" / ".claude" / "settings.json"

    # Must not raise
    _prune_superseded_deny_entries(non_existent, _SUPERSEDED_DENY_ENTRIES)

"""Tests for skills/pairmode/scripts/session_orphan_notice.py (INFRA-443).

Pure rendering / monkeypatch cases for `orphan_state_notice` — Ensures 4
(status-drift-only rendering names `--sync-status` and never `--apply`) and
Ensures 5 (output derives entirely from `diagnose_state`'s return value, and
the module performs no filesystem scan of its own). Ensures 1/2/3/6 are
hook-level and live in `tests/pairmode/test_session_start_hook.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import flex_build  # noqa: E402
from session_orphan_notice import orphan_state_notice  # noqa: E402


def test_returns_none_when_classification_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        flex_build,
        "diagnose_state",
        lambda *a, **k: {"orphans": [], "in_flight": [], "status_drift": []},
    )
    assert orphan_state_notice(tmp_path) is None


def test_returns_none_even_with_real_orphan_artifacts_on_disk(tmp_path, monkeypatch):
    """Forbidden proxy (Ensures 5): the module must not scan
    `.pairmode-worktrees/` itself. With `diagnose_state` monkeypatched to
    report nothing, a real orphan directory on disk must not leak through."""
    wt = tmp_path / ".pairmode-worktrees" / "DOC-999"
    wt.mkdir(parents=True)
    perm = tmp_path / "docs" / "phases" / "permissions"
    perm.mkdir(parents=True)
    (perm / "DOC-999.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        flex_build,
        "diagnose_state",
        lambda *a, **k: {"orphans": [], "in_flight": [], "status_drift": []},
    )
    assert orphan_state_notice(tmp_path) is None


def test_orphans_only_names_ids_and_apply(tmp_path, monkeypatch):
    monkeypatch.setattr(
        flex_build,
        "diagnose_state",
        lambda *a, **k: {
            "orphans": [
                {"story_id": "DOC-001", "has_worktree": True},
                {"story_id": "DOC-002", "has_worktree": True},
            ],
            "in_flight": [],
            "status_drift": [],
        },
    )
    notice = orphan_state_notice(tmp_path)
    assert notice is not None
    assert "DOC-001" in notice
    assert "DOC-002" in notice
    assert "doctor-state" in notice
    assert "--apply" in notice
    assert "--sync-status" not in notice


def test_status_drift_only_names_ids_and_sync_status_never_apply(tmp_path, monkeypatch):
    """Ensures 4: the only finding is status_drift — the line names the
    story ID and `--sync-status`, and must not instruct `--apply`."""
    monkeypatch.setattr(
        flex_build,
        "diagnose_state",
        lambda *a, **k: {
            "orphans": [],
            "in_flight": [],
            "status_drift": [("DOC-003", "complete", "planned")],
        },
    )
    notice = orphan_state_notice(tmp_path)
    assert notice is not None
    assert "DOC-003" in notice
    assert "doctor-state" in notice
    assert "--sync-status" in notice
    assert "--apply" not in notice


def test_both_findings_present_names_both_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(
        flex_build,
        "diagnose_state",
        lambda *a, **k: {
            "orphans": [{"story_id": "DOC-004", "has_worktree": True}],
            "in_flight": [],
            "status_drift": [("DOC-005", "complete", "planned")],
        },
    )
    notice = orphan_state_notice(tmp_path)
    assert notice is not None
    assert "DOC-004" in notice
    assert "DOC-005" in notice
    assert "--apply" in notice
    assert "--sync-status" in notice


def test_in_flight_only_emits_none(tmp_path, monkeypatch):
    """A story classified `in_flight` (fresh stamp) must stay silent —
    only `orphans`/`status_drift` are ever surfaced."""
    monkeypatch.setattr(
        flex_build,
        "diagnose_state",
        lambda *a, **k: {
            "orphans": [],
            "in_flight": [{"story_id": "DOC-006", "reason": "fresh current_stories entry"}],
            "status_drift": [],
        },
    )
    assert orphan_state_notice(tmp_path) is None


def test_enumerated_ids_capped_at_five_plus_more(tmp_path, monkeypatch):
    ids = [f"DOC-{i:03d}" for i in range(8)]
    monkeypatch.setattr(
        flex_build,
        "diagnose_state",
        lambda *a, **k: {
            "orphans": [{"story_id": sid, "has_worktree": True} for sid in ids],
            "in_flight": [],
            "status_drift": [],
        },
    )
    notice = orphan_state_notice(tmp_path)
    assert notice is not None
    for sid in ids[:5]:
        assert sid in notice
    for sid in ids[5:]:
        assert sid not in notice
    assert "+3 more" in notice


def test_diagnose_state_raising_returns_none(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(flex_build, "diagnose_state", _boom)
    assert orphan_state_notice(tmp_path) is None


def test_import_failure_is_contained(monkeypatch, tmp_path):
    """A broken `flex_build` import must not raise out of this function —
    it is contained and yields `None`."""
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "flex_build":
            raise ImportError("simulated import failure")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    assert orphan_state_notice(tmp_path) is None

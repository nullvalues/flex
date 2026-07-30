"""Tests for skills/pairmode/scripts/flex_build.py's ``clear-stale-stories``
subcommand (INFRA-271, CER-080 operator half).

Each case is exercised through ``subprocess.run`` so the CLI's real argv
parsing and stdout/exit-code behaviour are validated end-to-end, matching
the style of ``test_flex_build.py``.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import scope_guard  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
    )


def _fresh_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stale_iso(days: float = 30) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _write_state(project: Path, state: dict) -> None:
    companion = project / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text(json.dumps(state))


# ---------------------------------------------------------------------------
# C2: report mode is the default and writes nothing.
# ---------------------------------------------------------------------------


def test_report_mode_prints_stale_entry_and_does_not_write(tmp_path: Path) -> None:
    _write_state(
        tmp_path,
        {"current_stories": {"INFRA-209": {"id": "INFRA-209", "set_at": _stale_iso()}}},
    )
    state_path = tmp_path / ".companion" / "state.json"
    before = state_path.read_bytes()

    result = _run("clear-stale-stories", "--project-dir", str(tmp_path))

    assert result.returncode == 0
    assert "STALE INFRA-209" in result.stdout
    assert "set_at=" in result.stdout
    assert "age=" in result.stdout
    after = state_path.read_bytes()
    assert after == before


def test_report_mode_does_not_report_fresh_entry(tmp_path: Path) -> None:
    _write_state(
        tmp_path,
        {"current_stories": {"INFRA-300": {"id": "INFRA-300", "set_at": _fresh_iso()}}},
    )
    result = _run("clear-stale-stories", "--project-dir", str(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# C3: --apply removes only stale keyed entries; a fresh sibling survives.
# ---------------------------------------------------------------------------


def test_apply_clears_only_stale_keyed_entry(tmp_path: Path) -> None:
    fresh_set_at = _fresh_iso()
    _write_state(
        tmp_path,
        {
            "current_stories": {
                "INFRA-300": {"id": "INFRA-300", "set_at": fresh_set_at},
                "INFRA-209": {"id": "INFRA-209", "set_at": _stale_iso()},
            }
        },
    )

    result = _run("clear-stale-stories", "--project-dir", str(tmp_path), "--apply")

    assert result.returncode == 0
    assert "CLEARED INFRA-209" in result.stdout
    assert "INFRA-300" not in result.stdout

    state = json.loads((tmp_path / ".companion" / "state.json").read_text())
    keyed = state.get("current_stories", {})
    assert "INFRA-209" not in keyed
    assert keyed["INFRA-300"]["set_at"] == fresh_set_at


# ---------------------------------------------------------------------------
# C4: a stale legacy-only stamp is cleared via clear-the-slate.
# ---------------------------------------------------------------------------


def test_apply_clears_stale_legacy_only_stamp(tmp_path: Path) -> None:
    _write_state(
        tmp_path,
        {"current_story": {"id": "INFRA-209", "set_at": _stale_iso()}},
    )

    result = _run("clear-stale-stories", "--project-dir", str(tmp_path), "--apply")

    assert result.returncode == 0
    assert "CLEARED INFRA-209" in result.stdout

    state = json.loads((tmp_path / ".companion" / "state.json").read_text())
    assert "current_story" not in state
    assert "current_stories" not in state


def test_report_mode_reports_stale_legacy_only_stamp(tmp_path: Path) -> None:
    _write_state(
        tmp_path,
        {"current_story": {"id": "INFRA-209", "set_at": _stale_iso()}},
    )
    state_path = tmp_path / ".companion" / "state.json"
    before = state_path.read_bytes()

    result = _run("clear-stale-stories", "--project-dir", str(tmp_path))

    assert result.returncode == 0
    assert "STALE INFRA-209" in result.stdout
    assert state_path.read_bytes() == before


# ---------------------------------------------------------------------------
# C5: a clean project produces no output, with and without --apply.
# ---------------------------------------------------------------------------


def test_no_state_json_produces_no_output(tmp_path: Path) -> None:
    for args in (["--project-dir", str(tmp_path)], ["--project-dir", str(tmp_path), "--apply"]):
        result = _run("clear-stale-stories", *args)
        assert result.returncode == 0
        assert result.stdout.strip() == ""


def test_no_companion_dir_produces_no_output(tmp_path: Path) -> None:
    result = _run("clear-stale-stories", "--project-dir", str(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_empty_state_produces_no_output(tmp_path: Path) -> None:
    _write_state(tmp_path, {})
    result = _run("clear-stale-stories", "--project-dir", str(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# C6: never raises, never exits non-zero.
# ---------------------------------------------------------------------------


def test_malformed_state_json_exits_zero(tmp_path: Path) -> None:
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text("{ not valid json !!!")
    result = _run("clear-stale-stories", "--project-dir", str(tmp_path))
    assert result.returncode == 0


def test_non_dict_current_stories_exits_zero(tmp_path: Path) -> None:
    _write_state(tmp_path, {"current_stories": "not-a-dict"})
    result = _run("clear-stale-stories", "--project-dir", str(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_entry_with_no_set_at_reported_as_stale(tmp_path: Path) -> None:
    _write_state(tmp_path, {"current_stories": {"INFRA-500": {"id": "INFRA-500"}}})
    result = _run("clear-stale-stories", "--project-dir", str(tmp_path))
    assert result.returncode == 0
    assert "STALE INFRA-500" in result.stdout
    assert "set_at=<none>" in result.stdout


def test_missing_project_directory_exits_zero(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    result = _run("clear-stale-stories", "--project-dir", str(missing))
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# C7: --max-age-hours is honoured.
# ---------------------------------------------------------------------------


def test_max_age_hours_override(tmp_path: Path) -> None:
    three_hours_old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    _write_state(
        tmp_path,
        {"current_stories": {"INFRA-600": {"id": "INFRA-600", "set_at": three_hours_old}}},
    )

    result_strict = _run(
        "clear-stale-stories", "--project-dir", str(tmp_path), "--max-age-hours", "1"
    )
    assert "STALE INFRA-600" in result_strict.stdout

    result_lenient = _run(
        "clear-stale-stories", "--project-dir", str(tmp_path), "--max-age-hours", "48"
    )
    assert result_lenient.stdout.strip() == ""


# ---------------------------------------------------------------------------
# C1: imports the staleness rule from scope_guard rather than re-deriving it.
# ---------------------------------------------------------------------------


def test_imports_staleness_rule_from_scope_guard() -> None:
    """C1: import from `scope_guard` rather than re-deriving the staleness
    rule. INFRA-320 widens this same import statement (§ A/B additions), so
    this checks membership of the two staleness names rather than pinning
    the exact import line."""
    import flex_build  # noqa: PLC0415

    assert flex_build.entry_is_fresh is scope_guard.entry_is_fresh
    assert flex_build.STATE_STORY_MAX_AGE_HOURS == scope_guard.STATE_STORY_MAX_AGE_HOURS
    text = _SCRIPT.read_text()
    assert re.search(r"from scope_guard import \(?[^)]*\bentry_is_fresh\b", text)
    assert re.search(
        r"from scope_guard import \(?[^)]*\bSTATE_STORY_MAX_AGE_HOURS\b", text, re.DOTALL
    )


# ---------------------------------------------------------------------------
# C8: flex's own state is verified clean.
# ---------------------------------------------------------------------------


def test_flex_own_state_has_no_stale_stamps() -> None:
    result = _run("clear-stale-stories", "--project-dir", str(_REPO_ROOT))
    assert result.returncode == 0
    assert result.stdout.strip() == ""

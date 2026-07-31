"""Tests for skills/pairmode/scripts/context_budget_check.py

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget_check.py -x -q
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Ensure the pairmode scripts directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))

from context_budget_check import main


def _create_db(companion_dir: Path, rows: list[dict]) -> Path:
    """Create a minimal effort.db with the attempts table and the given rows."""
    db_path = companion_dir / "effort.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT NOT NULL,
                phase TEXT,
                rail TEXT,
                agent_role TEXT NOT NULL,
                model TEXT,
                attempt_number INTEGER NOT NULL,
                tokens_total INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER,
                cache_read_tokens INTEGER,
                cache_write_tokens INTEGER,
                tool_uses INTEGER,
                duration_ms INTEGER,
                outcome TEXT,
                notes TEXT,
                ts TEXT NOT NULL,
                story_class TEXT,
                model_selection_reason TEXT
            )
        """)
        for row in rows:
            conn.execute(
                """
                INSERT INTO attempts
                    (story_id, phase, rail, agent_role, attempt_number, tokens_total, ts)
                VALUES
                    (:story_id, :phase, :rail, :agent_role, :attempt_number, :tokens_total, :ts)
                """,
                {
                    "story_id": row.get("story_id", "TEST-001"),
                    "phase": row.get("phase", "1"),
                    "rail": row.get("rail", "TEST"),
                    "agent_role": row.get("agent_role", "builder"),
                    "attempt_number": row.get("attempt_number", 1),
                    "tokens_total": row.get("tokens_total", 0),
                    "ts": "2026-01-01T00:00:00+00:00",
                },
            )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _create_state(companion_dir: Path, data: dict) -> Path:
    """Write state.json with the given data."""
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return state_path


# ---------------------------------------------------------------------------
# Test 1: status=ok when sum < threshold
# ---------------------------------------------------------------------------

def test_ok_when_sum_below_threshold(tmp_path):
    """Exit 0 and status=ok when total tokens are below default threshold."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)

    _create_db(companion_dir, [
        {"story_id": "A-001", "phase": "1", "tokens_total": 40000},
        {"story_id": "A-002", "phase": "1", "tokens_total": 30000},
    ])
    _create_state(companion_dir, {"effort_tracking": True})

    exit_code = main([
        "--project-dir", str(tmp_path),
        "--phase", "1",
    ])
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 2: status=over when sum > threshold
# ---------------------------------------------------------------------------

def test_over_when_sum_exceeds_threshold(tmp_path):
    """Exit 1 and status=over when total tokens exceed the default threshold."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)

    # Default threshold is 120000; insert attempts summing to 130000
    _create_db(companion_dir, [
        {"story_id": "A-001", "phase": "1", "tokens_total": 80000},
        {"story_id": "A-002", "phase": "1", "tokens_total": 50000},
    ])
    _create_state(companion_dir, {"effort_tracking": True})

    exit_code = main([
        "--project-dir", str(tmp_path),
        "--phase", "1",
    ])
    assert exit_code == 1


# ---------------------------------------------------------------------------
# Test 3: --threshold override beats state.json
# ---------------------------------------------------------------------------

def test_threshold_arg_overrides_state_json(tmp_path):
    """--threshold 999999 beats state.json's 50000 — result is ok."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)

    # Sum is 80000; state.json says 50000 (would fire); --threshold 999999 → ok
    _create_db(companion_dir, [
        {"story_id": "A-001", "phase": "1", "tokens_total": 80000},
    ])
    _create_state(companion_dir, {
        "effort_tracking": True,
        "context_budget_threshold": 50000,
    })

    exit_code = main([
        "--project-dir", str(tmp_path),
        "--phase", "1",
        "--threshold", "999999",
    ])
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 4: missing key in state.json falls back to default 120000
# ---------------------------------------------------------------------------

def test_missing_state_key_falls_back_to_default(tmp_path):
    """When state.json lacks context_budget_threshold, default 120000 is used."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)

    # Sum = 60000 < 120000 → ok
    _create_db(companion_dir, [
        {"story_id": "A-001", "phase": "1", "tokens_total": 60000},
    ])
    # state.json present but no threshold key
    _create_state(companion_dir, {"effort_tracking": True})

    exit_code = main([
        "--project-dir", str(tmp_path),
        "--phase", "1",
    ])
    assert exit_code == 0

    # Also verify: if sum exceeds 120000 it fires even without the key
    _create_db(companion_dir, [
        {"story_id": "A-001", "phase": "1", "tokens_total": 130000},
    ])
    exit_code2 = main([
        "--project-dir", str(tmp_path),
        "--phase", "1",
    ])
    assert exit_code2 == 1


# ---------------------------------------------------------------------------
# Test 5: phase filter is exclusive
# ---------------------------------------------------------------------------

def test_phase_filter_is_exclusive(tmp_path):
    """Attempts in phase '1' do not count toward phase '2' sum."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)

    _create_db(companion_dir, [
        {"story_id": "A-001", "phase": "1", "tokens_total": 200000},  # phase 1 — huge
        {"story_id": "B-001", "phase": "2", "tokens_total": 10000},   # phase 2 — small
    ])
    _create_state(companion_dir, {"effort_tracking": True})

    # Phase 2 sum is 10000 — well under 120000 → ok
    exit_code = main([
        "--project-dir", str(tmp_path),
        "--phase", "2",
    ])
    assert exit_code == 0

    # Phase 1 sum is 200000 — over → exit 1
    exit_code2 = main([
        "--project-dir", str(tmp_path),
        "--phase", "1",
    ])
    assert exit_code2 == 1


# ---------------------------------------------------------------------------
# Test 6: exit 2 when effort.db is missing
# ---------------------------------------------------------------------------

def test_exit_2_when_db_missing(tmp_path):
    """Exit 2 with a clear message when the effort DB does not exist."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)

    # Do NOT create effort.db in companion_dir
    _create_state(companion_dir, {"effort_tracking": True})

    exit_code = main([
        "--project-dir", str(tmp_path),
        "--phase", "1",
    ])
    assert exit_code == 2


# ---------------------------------------------------------------------------
# INFRA-321 § B6 — story-spend track renaming, threshold provenance,
# and removal of the "CONTEXT BUDGET EXCEEDED" / orchestrator-pause language.
# ---------------------------------------------------------------------------


def test_context_budget_check_stdout_declares_story_spend_track(tmp_path, capsys):
    """test_context_budget_check_stdout_declares_story_spend_track."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)
    _create_db(companion_dir, [{"story_id": "A-001", "phase": "1", "tokens_total": 40000}])
    _create_state(companion_dir, {"effort_tracking": True})

    exit_code = main(["--project-dir", str(tmp_path), "--phase", "1"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "track=story-spend" in out
    assert "threshold_source=default" in out


def test_context_budget_check_never_falls_back_to_orchestrator_threshold(tmp_path, capsys):
    """A state.json carrying only context_budget_threshold (no
    story_spend_threshold) must resolve to the module default, not to the
    orchestrator's threshold value — test_story_spend_threshold_never_falls
    _back_to_context_budget_threshold.
    """
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)
    # Sum is 130000 — over the module default (120000) but well under the
    # orchestrator's context_budget_threshold (500000). If the code fell back
    # to context_budget_threshold, this would report "ok"; it must report
    # "over" because the default (120000) is what actually applies.
    _create_db(companion_dir, [{"story_id": "A-001", "phase": "1", "tokens_total": 130000}])
    _create_state(companion_dir, {"context_budget_threshold": 500000})

    exit_code = main(["--project-dir", str(tmp_path), "--phase", "1"])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "threshold=120000" in out
    assert "threshold_source=default" in out


def test_context_budget_check_reads_story_spend_threshold_key(tmp_path, capsys):
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)
    _create_db(companion_dir, [{"story_id": "A-001", "phase": "1", "tokens_total": 90000}])
    _create_state(companion_dir, {"story_spend_threshold": 80000})

    exit_code = main(["--project-dir", str(tmp_path), "--phase", "1"])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "threshold=80000" in out
    assert "threshold_source=state" in out


def test_context_budget_check_over_threshold_message_removed_strings(tmp_path, capsys):
    """The strings 'CONTEXT BUDGET EXCEEDED' and 'Orchestrator MUST surface a
    proceed-vs-pause prompt' must no longer appear anywhere in the module.
    """
    src = Path(__file__).resolve().parent.parent.parent.joinpath(
        "skills", "pairmode", "scripts", "context_budget_check.py"
    ).read_text(encoding="utf-8")
    assert "CONTEXT BUDGET EXCEEDED" not in src
    assert "Orchestrator MUST surface a proceed-vs-pause prompt" not in src

    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)
    _create_db(companion_dir, [{"story_id": "A-001", "phase": "1", "tokens_total": 200000}])
    _create_state(companion_dir, {})
    exit_code = main(["--project-dir", str(tmp_path), "--phase", "1"])
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "NOT a context-headroom signal" in err
    assert "CONTEXT BUDGET EXCEEDED" not in err


def test_context_budget_check_exit_codes_unchanged(tmp_path):
    """test_context_budget_check_exit_codes_unchanged — the 0/1/2 exit-code
    table is byte-identical to before this story for the same inputs.
    """
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True)
    _create_db(companion_dir, [{"story_id": "A-001", "phase": "1", "tokens_total": 40000}])
    _create_state(companion_dir, {})
    assert main(["--project-dir", str(tmp_path), "--phase", "1"]) == 0

    _create_db(companion_dir, [{"story_id": "A-001", "phase": "1", "tokens_total": 200000}])
    assert main(["--project-dir", str(tmp_path), "--phase", "1"]) == 1

    no_db_dir = tmp_path / "no-db"
    (no_db_dir / ".companion").mkdir(parents=True)
    _create_state(no_db_dir / ".companion", {})
    assert main(["--project-dir", str(no_db_dir), "--phase", "1"]) == 2

"""Tests for ``flex_build.py checkpoint-report`` (INFRA-236).

Covers:
- Empty effort.db → minimal report, no crash.
- Populated effort.db → per-role cost rollup matching resolver-state's
  effort_by_role (reuses _query_effort_by_role — same numbers, no
  duplicated query logic).
- next-phase pointer: present when the index has a following row, absent
  ("none (end of index)") when the active phase is last.
- Pure-read: writes nothing to state.json or effort.db.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
    )


def _write_phase_index(project_dir: Path, rows: list[tuple[str, str]]) -> None:
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
    ]
    for phase_ref, status in rows:
        lines.append(f"| {phase_ref} | Some title | {status} | |\n")
        # Give every referenced phase an (empty) phase file so
        # resolve_current_phase can find it.
        (phases_dir / f"phase-{phase_ref}.md").write_text(
            f"# Phase {phase_ref}\n", encoding="utf-8"
        )
    (phases_dir / "index.md").write_text("".join(lines), encoding="utf-8")


def _seed_effort_db(project_dir: Path, rows: list[tuple[str, int]]) -> None:
    """rows: list of (agent_role, tokens_total)."""
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    db_path = companion / "effort.db"
    sys.path.insert(0, str(_REPO_ROOT / "skills" / "pairmode" / "scripts"))
    from effort_db import init_db, insert_attempt  # noqa: PLC0415

    init_db(db_path)
    for i, (role, tokens) in enumerate(rows):
        insert_attempt(
            db_path,
            story_id=f"INFRA-{i:03d}",
            phase="98",
            rail="INFRA",
            agent_role=role,
            model="claude-sonnet-5",
            attempt_number=1,
            tokens_total=tokens,
            tokens_in=None,
            tokens_out=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            tool_uses=None,
            duration_ms=None,
            outcome="PASS",
            notes=None,
            ts="2026-07-23T00:00:00+00:00",
        )


def test_checkpoint_report_no_effort_db(tmp_path: Path) -> None:
    _write_phase_index(tmp_path, [("98", "active")])

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "no effort.db attempts recorded yet" in result.stdout


def test_checkpoint_report_with_attempts(tmp_path: Path) -> None:
    _write_phase_index(tmp_path, [("98", "active")])
    _seed_effort_db(tmp_path, [("builder", 1000), ("builder", 2000), ("reviewer", 500)])

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "builder: 2 attempt(s)" in result.stdout
    assert "reviewer: 1 attempt(s)" in result.stdout


def test_checkpoint_report_next_phase_pointer_present(tmp_path: Path) -> None:
    _write_phase_index(tmp_path, [("98", "active"), ("99", "planned")])

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "next phase: 99" in result.stdout


def test_checkpoint_report_next_phase_pointer_absent_at_end_of_index(tmp_path: Path) -> None:
    _write_phase_index(tmp_path, [("98", "active")])

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "next phase: none (end of index)" in result.stdout


def test_checkpoint_report_is_pure_read(tmp_path: Path) -> None:
    _write_phase_index(tmp_path, [("98", "active")])
    _seed_effort_db(tmp_path, [("builder", 1000)])

    state_path = tmp_path / ".companion" / "state.json"
    state_path.write_text(json.dumps({"effort_tracking": True}), encoding="utf-8")
    before_state = state_path.read_bytes()
    db_path = tmp_path / ".companion" / "effort.db"
    conn = sqlite3.connect(str(db_path))
    before_count = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    conn.close()

    _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert state_path.read_bytes() == before_state
    conn = sqlite3.connect(str(db_path))
    after_count = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    conn.close()
    assert after_count == before_count

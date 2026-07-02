"""Tests for OBS-001: flex_build.py resolver-state --json.

Asserts the JSON shape against synthetic resolver-fixture trees:
  - action / next-action state present
  - Position fields present
  - per-role effort summary present when effort.db has rows
  - deferred phase reported inactive (CER-056)
  - pure-read (no files written after invocation)
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

FLEX_ROOT = Path(__file__).resolve().parents[2]
FLEX_BUILD = FLEX_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"


def _run_resolver_state(project_dir: Path) -> dict:
    """Run resolver-state and return parsed JSON."""
    result = subprocess.run(
        [sys.executable, str(FLEX_BUILD), "resolver-state", "--project-dir", str(project_dir)],
        capture_output=True,
        text=True,
        cwd=str(FLEX_ROOT),
        env={"PATH": f"{Path.home()}/.local/bin:/usr/bin:/bin", "HOME": str(Path.home())},
    )
    assert result.returncode == 0, f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    return json.loads(result.stdout)


def _make_minimal_project(tmp_path: Path) -> Path:
    """Create a minimal project tree the resolver can read without crashing."""
    companion = tmp_path / ".companion"
    companion.mkdir()
    (companion / "state.json").write_text("{}", encoding="utf-8")

    phases = tmp_path / "docs" / "phases"
    phases.mkdir(parents=True)

    # Minimal index with one planned and one deferred phase
    (phases / "index.md").write_text(
        "# Index\n\n"
        "| Phase | Title | Status | Tag |\n"
        "|-------|-------|--------|-----|\n"
        "| 1 | Init | complete | cp1 |\n"
        "| 2 | Active | planned | |\n"
        "| 3 | Old | deferred | |\n",
        encoding="utf-8",
    )
    # Phase 2 file so the resolver can find it
    (phases / "phase-2.md").write_text(
        "---\nera: \"001\"\nphase_class: production\n---\n\n# Phase 2\n\n## Stories\n\n"
        "| ID | Title | Status |\n|----|-------|--------|\n",
        encoding="utf-8",
    )
    return tmp_path


def _add_effort_db(project_dir: Path) -> None:
    """Add a synthetic effort.db with per-role rows."""
    db_path = project_dir / ".companion" / "effort.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """CREATE TABLE attempts (
                id INTEGER PRIMARY KEY,
                story_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                attempt_number INTEGER,
                ts TEXT,
                tokens_total INTEGER,
                duration_ms INTEGER,
                outcome TEXT,
                phase TEXT,
                rail TEXT
            )"""
        )
        rows = [
            ("CORE-001", "builder", 1, "2026-01-01T00:00:00Z", 10000, None, "PASS", "1", "CORE"),
            ("CORE-001", "builder", 2, "2026-01-02T00:00:00Z", 12000, None, "PASS", "1", "CORE"),
            ("CORE-001", "reviewer", 1, "2026-01-01T00:01:00Z", 5000, None, "PASS", "1", "CORE"),
        ]
        conn.executemany(
            "INSERT INTO attempts (story_id, agent_role, attempt_number, ts, tokens_total, "
            "duration_ms, outcome, phase, rail) VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestResolverStateCLI:
    def test_command_exists_in_flex_build(self) -> None:
        from skills.pairmode.scripts.flex_build import flex_build
        assert "resolver-state" in flex_build.commands, (
            "resolver-state command not registered in flex_build"
        )

    def test_schema_version_present(self, tmp_path: Path) -> None:
        project = _make_minimal_project(tmp_path)
        doc = _run_resolver_state(project)
        assert doc.get("schema_version") == 1

    def test_action_field_present(self, tmp_path: Path) -> None:
        project = _make_minimal_project(tmp_path)
        doc = _run_resolver_state(project)
        assert "action" in doc
        assert "action" in doc["action"], "action dict missing 'action' key"

    def test_position_fields_present(self, tmp_path: Path) -> None:
        project = _make_minimal_project(tmp_path)
        doc = _run_resolver_state(project)
        pos = doc.get("position", {})
        required_keys = {
            "active_phase_file", "next_story_id", "attempt_count",
            "last_attempt_outcome", "checkpoint_step", "needs_spec",
            "gate_stub", "gate_schema", "gate_auth",
        }
        missing = required_keys - set(pos.keys())
        assert not missing, f"Position missing keys: {missing}"

    def test_effort_by_role_present_when_db_exists(self, tmp_path: Path) -> None:
        project = _make_minimal_project(tmp_path)
        _add_effort_db(project)
        doc = _run_resolver_state(project)
        effort = doc.get("effort_by_role", {})
        assert "builder" in effort, "builder role missing from effort_by_role"
        assert "reviewer" in effort, "reviewer role missing from effort_by_role"
        assert effort["builder"]["count"] == 2
        assert effort["builder"]["median_tokens"] == 11000

    def test_effort_by_role_empty_without_db(self, tmp_path: Path) -> None:
        project = _make_minimal_project(tmp_path)
        doc = _run_resolver_state(project)
        assert doc.get("effort_by_role") == {}

    def test_index_present(self, tmp_path: Path) -> None:
        project = _make_minimal_project(tmp_path)
        doc = _run_resolver_state(project)
        assert "index" in doc
        assert isinstance(doc["index"], list)

    def test_deferred_phase_reported_inactive(self, tmp_path: Path) -> None:
        """CER-056: deferred phases must be reported as inactive=True."""
        project = _make_minimal_project(tmp_path)
        doc = _run_resolver_state(project)
        deferred = [e for e in doc["index"] if e["status"] == "deferred"]
        assert deferred, "No deferred phase in index (check fixture)"
        for entry in deferred:
            assert entry["active"] is False, (
                f"Deferred phase {entry['phase_ref']} should be active=False"
            )

    def test_complete_phase_reported_inactive(self, tmp_path: Path) -> None:
        """Complete phases are inactive (not available for new work)."""
        project = _make_minimal_project(tmp_path)
        doc = _run_resolver_state(project)
        complete = [e for e in doc["index"] if e["status"] == "complete"]
        for entry in complete:
            assert entry["active"] is False, (
                f"Complete phase {entry['phase_ref']} should be active=False"
            )

    def test_planned_phase_reported_active(self, tmp_path: Path) -> None:
        """Planned phases are active (work remaining)."""
        project = _make_minimal_project(tmp_path)
        doc = _run_resolver_state(project)
        planned = [e for e in doc["index"] if e["status"] == "planned"]
        assert planned, "No planned phase in index (check fixture)"
        for entry in planned:
            assert entry["active"] is True, (
                f"Planned phase {entry['phase_ref']} should be active=True"
            )

    def test_pure_read_no_writes(self, tmp_path: Path) -> None:
        """resolver-state must not write any files."""
        project = _make_minimal_project(tmp_path)
        before = {p: p.stat().st_mtime for p in project.rglob("*") if p.is_file()}
        _run_resolver_state(project)
        after_files = set(project.rglob("*"))
        new_files = {
            p for p in after_files
            if p.is_file()
            and str(p) not in {str(p) for p in before}
            and ".pytest_cache" not in p.parts
        }
        assert not new_files, f"resolver-state wrote new files: {new_files}"
        for p, mtime_before in before.items():
            if p.exists():
                assert p.stat().st_mtime == mtime_before, f"{p} was modified by resolver-state"

"""Tests for ``flex_build.py checkpoint-report`` (INFRA-236, INFRA-256).

Covers:
- Empty effort.db → minimal report, no crash.
- Populated effort.db → lifetime per-role cost rollup matching
  resolver-state's effort_by_role (reuses _query_effort_by_role — same
  numbers, no duplicated query logic).
- next-phase pointer: present when the index has a following row, absent
  ("none (end of index)") when the active phase is last.
- Pure-read: writes nothing to state.json or effort.db.
- Phase-scoped rollup (INFRA-256): only the active phase's ## Stories-table
  stories are counted in the phase-scoped section, even when effort.db holds
  rows from other phases' stories; a story listed with zero attempts gets an
  explicit marker; a story in effort.db but absent from the Stories table is
  excluded; no-active-phase and an unparseable/empty Stories table both
  degrade explicitly (scoping-unavailable line + lifetime rollup only).
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


def _write_stories_table(
    project_dir: Path, phase_ref: str, stories: list[tuple[str, str, str]]
) -> None:
    """Overwrite phase-<phase_ref>.md with a heading + ## Stories table.

    stories: list of (story_id, title, status). Requires
    ``_write_phase_index`` (or an equivalent phase-file writer) to have run
    first for *phase_ref* — this only rewrites that phase's own file, not
    the index. INFRA-256: phase-scoped rollup tests need a real Stories
    table; ``_write_phase_index`` alone only writes a bare heading.
    """
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Phase {phase_ref}\n\n",
        "## Stories\n\n",
        "| ID | Title | Status |\n",
        "|----|-------|--------|\n",
    ]
    for story_id, title, status in stories:
        lines.append(f"| {story_id} | {title} | {status} |\n")
    (phases_dir / f"phase-{phase_ref}.md").write_text("".join(lines), encoding="utf-8")


def _seed_effort_db(
    project_dir: Path,
    rows: list[tuple[str, int]],
    story_ids: list[str] | None = None,
    phase: str = "98",
) -> None:
    """rows: list of (agent_role, tokens_total).

    story_ids: optional parallel list of explicit story IDs (INFRA-256);
    defaults to synthetic ``INFRA-<NNN>`` IDs when omitted, preserving every
    existing call site's behaviour.
    """
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    db_path = companion / "effort.db"
    sys.path.insert(0, str(_REPO_ROOT / "skills" / "pairmode" / "scripts"))
    from effort_db import init_db, insert_attempt  # noqa: PLC0415

    init_db(db_path)
    for i, (role, tokens) in enumerate(rows):
        story_id = story_ids[i] if story_ids is not None else f"INFRA-{i:03d}"
        insert_attempt(
            db_path,
            story_id=story_id,
            phase=phase,
            rail="INFRA",
            agent_role=role,
            model="claude-sonnet-5",
            attempt_number=1,
            tokens_total=tokens,
            tokens_in=None,
            tokens_out=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
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


# ---------------------------------------------------------------------------
# Phase-scoped rollup (INFRA-256)
# ---------------------------------------------------------------------------


def test_checkpoint_report_phase_scoped_excludes_other_phase_stories(tmp_path: Path) -> None:
    """Rows from another phase's stories must not inflate the phase-scoped
    section, even though they do inflate the lifetime section — the
    motivating cp-100 bug this story fixes."""
    _write_phase_index(tmp_path, [("100", "complete"), ("101", "active")])
    _write_stories_table(
        tmp_path,
        "101",
        [("INFRA-256", "Phase-scoped rollup", "complete")],
    )

    # Phase 101's own story: one builder attempt.
    _seed_effort_db(
        tmp_path,
        [("builder", 1000)],
        story_ids=["INFRA-256"],
        phase="101",
    )
    # 18 unrelated attempts from a different phase's stories — these must
    # not show up in the phase-scoped section.
    _seed_effort_db(
        tmp_path,
        [("builder", 5000)] * 18,
        story_ids=[f"INFRA-{200 + i:03d}" for i in range(18)],
        phase="99",
    )

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "=== checkpoint cost rollup — phase 101 ===" in result.stdout
    assert "=== lifetime cost rollup (all phases) ===" in result.stdout

    phase_section, _, lifetime_section = result.stdout.partition(
        "=== lifetime cost rollup (all phases) ==="
    )
    assert "builder: 1 attempt(s), median 1,000 tokens" in phase_section
    assert "builder: 19 attempt(s)" in lifetime_section


def test_checkpoint_report_phase_scoped_story_zero_marker(tmp_path: Path) -> None:
    """A story listed in the Stories table with zero recorded attempts is
    shown with an explicit marker, not silently omitted."""
    _write_phase_index(tmp_path, [("101", "active")])
    _write_stories_table(
        tmp_path,
        "101",
        [
            ("INFRA-256", "Phase-scoped rollup", "complete"),
            ("INFRA-257", "attempt_number fix", "planned"),
        ],
    )
    _seed_effort_db(tmp_path, [("builder", 1000)], story_ids=["INFRA-256"], phase="101")

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "INFRA-257: no attempts recorded" in result.stdout
    assert "INFRA-256: builder: 1 attempt(s), median 1,000 tokens" in result.stdout


def test_checkpoint_report_phase_scoped_excludes_story_absent_from_table(tmp_path: Path) -> None:
    """A story ID present in effort.db but absent from the Stories table is
    excluded from the phase-scoped section entirely."""
    _write_phase_index(tmp_path, [("101", "active")])
    _write_stories_table(
        tmp_path,
        "101",
        [("INFRA-256", "Phase-scoped rollup", "complete")],
    )
    _seed_effort_db(
        tmp_path,
        [("builder", 1000), ("builder", 9000)],
        story_ids=["INFRA-256", "INFRA-999"],
        phase="101",
    )

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    phase_section, _, _ = result.stdout.partition("=== lifetime cost rollup (all phases) ===")
    assert "INFRA-999" not in phase_section
    assert "builder: 1 attempt(s), median 1,000 tokens" in phase_section


def test_checkpoint_report_no_active_phase_degrades_explicitly(tmp_path: Path) -> None:
    """No active phase resolved → explicit scoping-unavailable line + lifetime
    rollup, never a crash and never a phase-scoped heading."""
    _write_phase_index(tmp_path, [("98", "complete")])
    _seed_effort_db(tmp_path, [("builder", 1000)])

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "phase scoping unavailable" in result.stdout
    assert "no active phase resolved" in result.stdout
    assert "=== lifetime cost rollup (all phases) ===" in result.stdout
    assert "next phase: unknown (no active phase resolved)" in result.stdout


def test_checkpoint_report_unparseable_stories_table_degrades_explicitly(tmp_path: Path) -> None:
    """A resolved active phase with no ## Stories table (or an empty one)
    degrades explicitly rather than silently falling back."""
    _write_phase_index(tmp_path, [("98", "active")])
    _seed_effort_db(tmp_path, [("builder", 1000)])

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "phase scoping unavailable" in result.stdout
    assert "no parseable ## Stories table" in result.stdout
    assert "=== lifetime cost rollup (all phases) ===" in result.stdout
    assert "builder: 1 attempt(s)" in result.stdout


def test_checkpoint_report_phase_scoped_no_attempts_recorded(tmp_path: Path) -> None:
    """Scoping succeeds (a real Stories table exists) but none of its stories
    have recorded attempts — explicit 'no attempts recorded for phase <key>'
    line, not a silent fallback to lifetime numbers."""
    _write_phase_index(tmp_path, [("101", "active")])
    _write_stories_table(
        tmp_path,
        "101",
        [("INFRA-256", "Phase-scoped rollup", "planned")],
    )
    # Effort recorded, but for an unrelated story never listed in phase 101.
    _seed_effort_db(tmp_path, [("builder", 1000)], story_ids=["INFRA-999"], phase="99")

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "=== checkpoint cost rollup — phase 101 ===" in result.stdout
    assert "no attempts recorded for phase 101" in result.stdout
    assert "INFRA-256: no attempts recorded" in result.stdout


def _seed_pending_rows(project_dir: Path, story_ids: list[str], phase: str = "101") -> None:
    """INFRA-287 (CER-101): insert rows with tokens_total/outcome both NULL —
    the shape every async spawn's row has until reconciliation completes it."""
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    db_path = companion / "effort.db"
    sys.path.insert(0, str(_REPO_ROOT / "skills" / "pairmode" / "scripts"))
    from effort_db import init_db, insert_attempt  # noqa: PLC0415

    init_db(db_path)
    for story_id in story_ids:
        insert_attempt(
            db_path,
            story_id=story_id,
            phase=phase,
            rail="INFRA",
            agent_role="builder",
            attempt_number=1,
            ts="2026-07-28T00:00:00+00:00",
        )


def test_checkpoint_report_pending_rows_qualify_no_attempts_lines(tmp_path: Path) -> None:
    """INFRA-287 (CER-101, D2): pending (unreconciled) rows are reported as
    pending — both the phase-level and per-story 'no attempts' strings are
    qualified, so deferred reconciliation no longer reads as data loss."""
    _write_phase_index(tmp_path, [("101", "active")])
    _write_stories_table(
        tmp_path,
        "101",
        [
            ("INFRA-280", "Async story", "complete"),
            ("INFRA-281", "Another async story", "complete"),
        ],
    )
    _seed_pending_rows(tmp_path, ["INFRA-280", "INFRA-280", "INFRA-281"])

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "no attempts recorded for phase 101" in result.stdout
    assert (
        "3 attempt row(s) recorded but not yet reconciled — effort is pending, not absent"
        in result.stdout
    )
    assert "INFRA-280: no reconciled attempts (2 pending)" in result.stdout
    assert "INFRA-281: no reconciled attempts (1 pending)" in result.stdout


def test_checkpoint_report_story_with_neither_rows_keeps_bare_string(tmp_path: Path) -> None:
    """INFRA-287 (D2): a story with neither reconciled nor pending rows still
    prints the original bare string, byte-identical."""
    _write_phase_index(tmp_path, [("101", "active")])
    _write_stories_table(
        tmp_path,
        "101",
        [
            ("INFRA-280", "Async story", "complete"),
            ("INFRA-282", "Never spawned", "planned"),
        ],
    )
    _seed_pending_rows(tmp_path, ["INFRA-280"])

    result = _run("checkpoint-report", "--project-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "INFRA-282: no attempts recorded" in result.stdout
    assert "INFRA-282: no reconciled attempts" not in result.stdout


def test_checkpoint_report_stays_pure_read_no_reconcile_call(tmp_path: Path) -> None:
    """INFRA-287 (D3): checkpoint-report never calls
    reconcile_pending_attempts — the reconcile-first option was declined."""
    source = _SCRIPT.read_text(encoding="utf-8")
    start = source.index("def cmd_checkpoint_report")
    end = source.index("\n@flex_build.command", start)
    assert "reconcile_pending_attempts" not in source[start:end]

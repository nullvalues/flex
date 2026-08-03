"""Tests for the ``flex_build.py record-attempt`` alias (Story INFRA-263, CER-071/CER-073).

The alias (``cmd_record_attempt``, ``skills/pairmode/scripts/flex_build.py``)
delegates to ``record_attempt.py``. Prior to this story its Click declaration
was empty, so Click rejected every real flag before the body ran (`No such
option: --project-dir`). The fix declares the command with
``ignore_unknown_options=True`` and a variadic ``click.UNPROCESSED`` argument
so the full option set is forwarded verbatim, including ``--help``.

Tests invoke the CLI as a real subprocess (not ``CliRunner``) so the argv path
under test is the one downstream orchestrators actually exercise.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"

sys.path.insert(0, str(_REPO_ROOT))

from skills.pairmode.scripts import effort_db  # noqa: E402

_STORY_ID = "INFRA-263"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess:
    """Invoke flex_build.py with *args*; return the completed process."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(_REPO_ROOT),
        },
    )


def _enable_tracking(project_dir: Path) -> Path:
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state_path = companion / "state.json"
    state_path.write_text(json.dumps({"effort_tracking": True}), encoding="utf-8")
    return state_path


# ---------------------------------------------------------------------------
# Ensures 4 — full flag set round-trips through the alias
# ---------------------------------------------------------------------------


def test_full_flag_set_round_trips_through_alias(tmp_path: Path) -> None:
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"

    result = _run(
        "record-attempt",
        "--project-dir", str(tmp_path),
        "--story-id", _STORY_ID,
        "--phase", "104",
        "--rail", "INFRA",
        "--agent-role", "builder",
        "--model", "claude-sonnet-5",
        "--attempt-number", "1",
        "--tokens-total", "1000",
        "--tokens-in", "600",
        "--tokens-out", "400",
        "--cache-read-tokens", "50",
        "--cache-write-tokens", "20",
        "--duration-ms", "12345",
        "--outcome", "PASS",
        "--notes", "full flag round trip",
        "--story-class", "code",
        "--model-selection-reason", "auto-baseline",
        "--ts", "2026-07-25T00:00:00+00:00",
        "--db-path", str(db_path),
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    rows = effort_db.query_by_story(db_path, _STORY_ID)
    assert len(rows) == 1
    row = rows[0]
    assert row["phase"] == "104"
    assert row["rail"] == "INFRA"
    assert row["model"] == "claude-sonnet-5"
    assert row["tokens_total"] == 1000
    assert row["tokens_in"] == 600
    assert row["tokens_out"] == 400
    assert row["cache_read_tokens"] == 50
    assert row["cache_write_tokens"] == 20
    assert row["duration_ms"] == 12345
    assert row["outcome"] == "PASS"
    assert row["notes"] == "full flag round trip"
    assert row["story_class"] == "code"
    assert row["model_selection_reason"] == "auto-baseline"
    assert row["ts"] == "2026-07-25T00:00:00+00:00"


def test_notes_value_equal_to_subcommand_name_does_not_truncate_argv(tmp_path: Path) -> None:
    """Pins the CER-073/RELEASE-009-audit argument-truncation bug closed.

    Under the old ``sys.argv.index("record-attempt")`` slice, a ``--notes``
    value equal to the literal string "record-attempt" would find the wrong
    occurrence and truncate everything before it in the forwarded argv. The
    new implementation forwards the click.UNPROCESSED argument tuple, which
    is immune to this.
    """
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"

    result = _run(
        "record-attempt",
        "--project-dir", str(tmp_path),
        "--story-id", _STORY_ID,
        "--agent-role", "builder",
        "--notes", "record-attempt",
        "--outcome", "PASS",
        "--db-path", str(db_path),
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    rows = effort_db.query_by_story(db_path, _STORY_ID)
    assert len(rows) == 1
    assert rows[0]["notes"] == "record-attempt"
    assert rows[0]["outcome"] == "PASS"


# ---------------------------------------------------------------------------
# Ensures 5 — the exact reproducer from recon
# ---------------------------------------------------------------------------


def test_reproducer_from_cer_073_exits_zero(tmp_path: Path) -> None:
    _enable_tracking(tmp_path)

    result = _run(
        "record-attempt",
        "--project-dir", str(tmp_path),
        "--story-id", _STORY_ID,
        "--agent-role", "builder",
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "No such option" not in combined


# ---------------------------------------------------------------------------
# Ensures 6 — --story-file forwarding
# ---------------------------------------------------------------------------


def test_story_file_flag_is_forwarded(tmp_path: Path) -> None:
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"

    story_file = tmp_path / "INFRA-263.md"
    story_file.write_text(
        "---\n"
        "id: INFRA-263\n"
        "phase: \"104\"\n"
        "rail: INFRA\n"
        "story_class: code\n"
        "---\n\n"
        "## Ensures\n",
        encoding="utf-8",
    )

    result = _run(
        "record-attempt",
        "--project-dir", str(tmp_path),
        "--story-file", str(story_file),
        "--agent-role", "builder",
        "--db-path", str(db_path),
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    rows = effort_db.query_by_story(db_path, _STORY_ID)
    assert len(rows) == 1
    assert rows[0]["story_id"] == "INFRA-263"


# ---------------------------------------------------------------------------
# Ensures 7 — --help is forwarded, not answered locally
# ---------------------------------------------------------------------------


def test_help_is_forwarded_to_delegate() -> None:
    result = _run("record-attempt", "--help")
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "--story-id" in result.stdout
    assert "--agent-role" in result.stdout
    assert "--usage-block" in result.stdout


# ---------------------------------------------------------------------------
# Ensures 8 — delegate errors surface unchanged, with the delegate's exit code
# ---------------------------------------------------------------------------


def test_delegate_errors_propagate_exit_code(tmp_path: Path) -> None:
    _enable_tracking(tmp_path)

    missing_required = _run(
        "record-attempt",
        "--project-dir", str(tmp_path),
        "--story-id", "X",
    )
    combined = missing_required.stdout + missing_required.stderr
    assert missing_required.returncode == 2
    assert "--agent-role" in combined

    bogus_flag = _run(
        "record-attempt",
        "--project-dir", str(tmp_path),
        "--story-id", "X",
        "--agent-role", "builder",
        "--no-such-flag",
    )
    combined = bogus_flag.stdout + bogus_flag.stderr
    assert bogus_flag.returncode == 2
    assert "No such option: --no-such-flag" in combined
    assert "record_attempt.py" in combined
    assert "flex_build.py record-attempt" not in combined


# ---------------------------------------------------------------------------
# Ensures 9 — no regression to the group surface
# ---------------------------------------------------------------------------


def test_group_help_still_lists_record_attempt() -> None:
    result = _run("--help")
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "record-attempt" in result.stdout

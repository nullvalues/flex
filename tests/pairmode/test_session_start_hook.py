"""Tests for hooks/session_start.py — pairmode context injection."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "session_start.py"


def _run_hook(cwd: Path, *, tempdir: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke the SessionStart hook in ``cwd`` and return the completed process.

    ``tempdir``, when given, is passed as ``TMPDIR`` so the hook's hardcoded
    ``tempfile.gettempdir()``-derived PIPE_PATH (INFRA-238) resolves under a
    test-controlled directory instead of the real system tempdir.
    """
    env = dict(os.environ)
    if tempdir is not None:
        env["TMPDIR"] = str(tempdir)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _write_state(cwd: Path, state: dict) -> Path:
    """Write a .companion/state.json under ``cwd`` with the given state dict."""
    companion_dir = cwd / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _additional_context(stdout: str) -> str:
    """Parse stdout JSON and return the additionalContext string."""
    payload = json.loads(stdout)
    return payload["hookSpecificOutput"]["additionalContext"]


def test_no_output_without_state_json(tmp_path):
    """No state.json present → hook emits nothing on stdout."""
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_no_output_without_pairmode_version(tmp_path):
    """state.json exists but pairmode_version absent → no output."""
    _write_state(tmp_path, {"some_other_key": "value"})
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_emits_pairmode_version(tmp_path):
    """state.json with pairmode_version → additionalContext mentions it."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "Pairmode v0.1.0 is active" in ctx


def test_emits_current_story(tmp_path):
    """state.json with current_story → additionalContext mentions story id."""
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "current_story": {
                "id": "INFRA-001",
                "title": "depth guards",
                "status": "in-progress",
            },
        },
    )
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "INFRA-001" in ctx


def test_emits_no_story_message(tmp_path):
    """state.json with pairmode_version but no current_story → 'No active story'."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "No active story" in ctx


def test_sidebar_active_when_pipe_exists(tmp_path):
    """A real file at the hardcoded PIPE_PATH (INFRA-238) → 'Companion sidebar: active'.

    The `pipe_path` state.json key is retired — sidebar detection is purely a
    filesystem check against ``tempfile.gettempdir()/companion.pipe`` now, so
    this test points TMPDIR at tmp_path and creates the pipe file there.
    """
    pipe_file = tmp_path / "companion.pipe"
    pipe_file.write_text("", encoding="utf-8")
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _run_hook(tmp_path, tempdir=tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "Companion sidebar: active" in ctx


def test_sidebar_attachment_instructions_when_pipe_missing(tmp_path):
    """No file at the hardcoded PIPE_PATH → attachment instructions emitted."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _run_hook(tmp_path, tempdir=tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "To start" in ctx
    assert "start_sidebar.sh" in ctx


def test_reconciliation_call_does_not_break_existing_reset_behavior(tmp_path):
    """INFRA-258 Ensures 18: the SessionStart hook gains one best-effort
    delegated call to subagent_transcript.reconcile_pending_attempts, wrapped
    in its own try/except — the existing reset/status behaviour must be
    unaffected (no effort_tracking / no effort.db present here, so the
    reconciliation call is a real, harmless no-op — this is not a mock)."""
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "current_story": {"id": "INFRA-258", "title": "async effort", "status": "in-progress"},
        },
    )
    result = _run_hook(tmp_path, tempdir=tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "Pairmode v0.1.0 is active" in ctx
    assert "INFRA-258" in ctx


def test_reconciliation_raising_is_swallowed(tmp_path, monkeypatch):
    """A raising reconcile_pending_attempts must not break the hook's exit
    status or its existing additionalContext output."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})

    scripts_dir = Path(__file__).resolve().parent.parent.parent / "skills" / "pairmode" / "scripts"
    stub_path = scripts_dir / "subagent_transcript.py"
    original = stub_path.read_text(encoding="utf-8")
    try:
        stub_path.write_text(
            original
            + "\n\ndef reconcile_pending_attempts(*args, **kwargs):\n"
            "    raise RuntimeError('boom — reconciliation exploded')\n",
            encoding="utf-8",
        )
        result = _run_hook(tmp_path, tempdir=tmp_path)
    finally:
        stub_path.write_text(original, encoding="utf-8")

    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "Pairmode v0.1.0 is active" in ctx


def test_sidebar_ignores_retired_pipe_path_state_key(tmp_path):
    """A state.json `pipe_path` key pointing at a real file must be IGNORED —
    the hardcoded PIPE_PATH convention is the only source of truth
    (INFRA-238). This asserts the retired key has no effect, not that it's
    merely unused."""
    real_pipe_elsewhere = tmp_path / "elsewhere" / "companion.pipe"
    real_pipe_elsewhere.parent.mkdir()
    real_pipe_elsewhere.write_text("", encoding="utf-8")
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "pipe_path": str(real_pipe_elsewhere),
        },
    )
    # TMPDIR points somewhere with no companion.pipe file — the retired
    # pipe_path key must NOT cause "active" to be reported.
    (tmp_path / "empty_tmpdir").mkdir()
    result = _run_hook(tmp_path, tempdir=tmp_path / "empty_tmpdir")
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "Companion sidebar: active" not in ctx
    assert "To start" in ctx


# ---------------------------------------------------------------------------
# INFRA-285 (CER-097) — session-scoped SessionStart
# ---------------------------------------------------------------------------

import sqlite3  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

SCRIPTS = REPO_ROOT / "skills" / "pairmode" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _run_hook_with_stdin(
    cwd: Path, payload: "dict | str | None", *, tempdir: Path | None = None
) -> subprocess.CompletedProcess:
    """Invoke the SessionStart hook with an explicit stdin payload."""
    env = dict(os.environ)
    if tempdir is not None:
        env["TMPDIR"] = str(tempdir)
    if payload is None:
        raw = ""
    elif isinstance(payload, str):
        raw = payload
    else:
        raw = json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        cwd=str(cwd),
        input=raw,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _read_state_file(cwd: Path) -> dict:
    return json.loads((cwd / ".companion" / "state.json").read_text(encoding="utf-8"))


def _stamp(minutes_ago: float = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


class TestSessionScopedSessionStart:
    def test_payload_without_session_id_still_emits_status_block(self, tmp_path):
        """B1: the widened stdin reader keeps the no-session_id path working."""
        _write_state(tmp_path, {"pairmode_version": "0.1.0"})
        result = _run_hook_with_stdin(tmp_path, {"source": "startup"}, tempdir=tmp_path)
        assert result.returncode == 0
        ctx = _additional_context(result.stdout)
        assert "Pairmode v0.1.0 is active" in ctx
        assert "Context counter reset to 25000" in ctx
        # Falsy session id → flat keys only, no context_sessions entry (A4).
        state = _read_state_file(tmp_path)
        assert state["context_current_tokens"] == 25000
        assert "context_sessions" not in state

    def test_reset_lands_in_the_starting_sessions_own_entry(self, tmp_path):
        """B2: a side session's startup must not touch the build loop's counter."""
        _write_state(
            tmp_path,
            {
                "pairmode_version": "0.1.0",
                "context_current_tokens": 140000,
                "context_sessions": {
                    "LOOP": {
                        "context_current_tokens": 140000,
                        "last_seen_at": _stamp(),
                    }
                },
            },
        )
        result = _run_hook_with_stdin(
            tmp_path, {"source": "startup", "session_id": "SIDE"}, tempdir=tmp_path
        )
        assert result.returncode == 0
        state = _read_state_file(tmp_path)
        assert state["context_sessions"]["LOOP"]["context_current_tokens"] == 140000
        assert state["context_sessions"]["SIDE"]["context_current_tokens"] == 25000

    def test_session_reset_module_is_not_modified(self):
        """B2: decide_reset stays pure — no filesystem I/O (D11)."""
        source = (SCRIPTS / "session_reset.py").read_text(encoding="utf-8")
        assert "open(" not in source
        assert "write_text" not in source
        assert "Path" not in source

    def test_non_reset_source_seeds_the_entry_without_a_baseline(self, tmp_path):
        """B3: `resume` registers the session but writes no baseline."""
        _write_state(
            tmp_path,
            {
                "pairmode_version": "0.1.0",
                "context_current_tokens": 100000,
                "context_current_tokens_recorded_at": "2026-06-12T00:00:00+00:00",
            },
        )
        result = _run_hook_with_stdin(
            tmp_path, {"source": "resume", "session_id": "RESUMED"}, tempdir=tmp_path
        )
        assert result.returncode == 0
        state = _read_state_file(tmp_path)
        entry = state["context_sessions"]["RESUMED"]
        assert entry["context_current_tokens"] == 100000
        assert entry["context_current_tokens_recorded_at"] == "2026-06-12T00:00:00+00:00"
        assert "last_seen_at" in entry
        # Flat mirror's token values are unchanged.
        assert state["context_current_tokens"] == 100000
        assert "Context counter reset" not in _additional_context(result.stdout)

    def test_stale_entries_are_pruned_and_keep_is_retained(self, tmp_path):
        """A6: pruning happens inside the single SessionStart write."""
        _write_state(
            tmp_path,
            {
                "pairmode_version": "0.1.0",
                "context_sessions": {
                    "FRESH": {"last_seen_at": _stamp(5)},
                    "OLD": {"last_seen_at": _stamp(400)},
                    "GARBAGE": {"last_seen_at": "nonsense"},
                },
            },
        )
        result = _run_hook_with_stdin(
            tmp_path, {"source": "resume", "session_id": "GARBAGE"}, tempdir=tmp_path
        )
        assert result.returncode == 0
        sessions = _read_state_file(tmp_path)["context_sessions"]
        assert set(sessions) == {"FRESH", "GARBAGE"}

    def test_hook_calls_the_state_writer_at_most_once(self):
        """B4: one locked read-modify-write per invocation."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        writer_lines = [
            line
            for line in source.splitlines()
            if "_atomic_write_json" in line or "update_state_json" in line
        ]
        assert len(writer_lines) == 1, writer_lines
        assert "state_utils.update_state_json(" in writer_lines[0]

    def test_reset_failure_leaves_the_status_block_intact(self, tmp_path, monkeypatch):
        """B4: the block stays best-effort — a raising writer must not break it."""
        _write_state(tmp_path, {"pairmode_version": "0.1.0"})
        stub = SCRIPTS / "session_state.py"
        original = stub.read_text(encoding="utf-8")
        try:
            stub.write_text(
                original
                + "\n\ndef prune_stale_sessions(*args, **kwargs):\n"
                "    raise RuntimeError('boom — prune exploded')\n",
                encoding="utf-8",
            )
            result = _run_hook_with_stdin(
                tmp_path, {"source": "startup", "session_id": "S"}, tempdir=tmp_path
            )
        finally:
            stub.write_text(original, encoding="utf-8")
        assert result.returncode == 0
        assert "Pairmode v0.1.0 is active" in _additional_context(result.stdout)


# ---------------------------------------------------------------------------
# D5 / D7 — sweep ownership at SessionStart
# ---------------------------------------------------------------------------


def _pending_fail_row(project_dir: Path, story_id: str, output_file: Path) -> int:
    """Insert one pending attempts row whose spawn output parses as FAIL."""
    import effort_db

    db_path = project_dir / ".companion" / "effort.db"
    effort_db.init_db(db_path)
    row_id = effort_db.insert_attempt(
        db_path,
        story_id=story_id,
        agent_role="reviewer",
        attempt_number=1,
        ts=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "type": "assistant",
        "message": {
            "id": "msg_1",
            "model": "claude-sonnet-5",
            "stop_reason": "end_turn",
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "type": "REVIEW-RESULT",
                            "verdict": "FAIL",
                            "findings": ["x"],
                            "reason": "y",
                        }
                    ),
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
    }
    output_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    effort_db.set_spawn_ref(db_path, row_id, f"agent-{story_id}", str(output_file))
    return row_id


class TestSweepOwnershipAtSessionStart:
    def test_hook_wires_the_exclusion_filter(self):
        """D5: the SessionStart sweep excludes other live sessions' prefixes."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "exclude_output_prefixes=session_state.other_live_session_prefixes(" in source

    def test_single_session_project_still_reconciles_orphans(self, tmp_path):
        """D5: with no other live session the sweep behaves exactly as before."""
        import effort_db

        out = tmp_path / "sessA" / "tasks" / "a.output"
        _write_state(
            tmp_path,
            {
                "pairmode_version": "0.1.0",
                "effort_tracking": True,
                "current_stories": {"INFRA-901": {"id": "INFRA-901"}},
            },
        )
        _pending_fail_row(tmp_path, "INFRA-901", out)

        result = _run_hook_with_stdin(
            tmp_path, {"source": "resume", "session_id": "A"}, tempdir=tmp_path
        )
        assert result.returncode == 0

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-901")
        assert rows[0]["outcome"] == "FAIL"

    def test_other_live_sessions_rows_are_not_swept_or_bumped(self, tmp_path):
        """D7: cross-story counter bumps stop by construction."""
        import effort_db

        out_a = tmp_path / "sessA" / "tasks" / "a.output"
        out_b = tmp_path / "sessB" / "tasks" / "b.output"
        _write_state(
            tmp_path,
            {
                "pairmode_version": "0.1.0",
                "effort_tracking": True,
                "current_stories": {
                    "INFRA-902": {"id": "INFRA-902"},
                    "INFRA-903": {"id": "INFRA-903"},
                },
                "context_sessions": {
                    "B": {
                        "last_seen_at": _stamp(1),
                        "spawn_output_prefix": str(tmp_path / "sessB") + os.sep,
                    }
                },
            },
        )
        _pending_fail_row(tmp_path, "INFRA-902", out_a)
        _pending_fail_row(tmp_path, "INFRA-903", out_b)

        counter_path = tmp_path / ".companion" / "attempt_counter.json"
        assert not counter_path.exists()

        result = _run_hook_with_stdin(
            tmp_path, {"source": "resume", "session_id": "A"}, tempdir=tmp_path
        )
        assert result.returncode == 0

        db_path = tmp_path / ".companion" / "effort.db"
        # Session A's own orphan row was reconciled and bumped...
        assert effort_db.query_by_story(db_path, "INFRA-902")[0]["outcome"] == "FAIL"
        # ...and session B's live row was never reached.
        assert effort_db.query_by_story(db_path, "INFRA-903")[0]["outcome"] is None
        counter = json.loads(counter_path.read_text(encoding="utf-8"))
        assert "INFRA-903" not in json.dumps(counter)

    def test_story_accepts_late_bump_is_not_modified(self):
        """D7: INFRA-282 owns that helper — the fix here is unreachability."""
        source = (SCRIPTS / "subagent_transcript.py").read_text(encoding="utf-8")
        assert "def _story_accepts_late_bump(project_dir: \"Path | str\", story_id: str) -> bool:" in source
        assert "INFRA-285" not in source.split("def _story_accepts_late_bump")[1].split(
            "\ndef "
        )[0]


# ---------------------------------------------------------------------------
# F4 — legacy state files
# ---------------------------------------------------------------------------


def test_pre_infra_285_state_file_is_upgraded_on_first_write(tmp_path):
    """F4: no migration step — the keyed record appears on the next write."""
    _write_state(
        tmp_path,
        {"pairmode_version": "0.1.0", "context_current_tokens": 90000},
    )
    result = _run_hook_with_stdin(
        tmp_path, {"source": "clear", "session_id": "NEW"}, tempdir=tmp_path
    )
    assert result.returncode == 0
    state = _read_state_file(tmp_path)
    assert state["context_sessions"]["NEW"]["context_current_tokens"] == 25000
    assert state["context_current_tokens"] == 25000


def test_no_lock_file_is_left_inside_the_repository(tmp_path):
    """E6: lock files live beside state.json, under the gitignored .companion/."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    _run_hook_with_stdin(
        tmp_path, {"source": "startup", "session_id": "S"}, tempdir=tmp_path
    )
    assert (tmp_path / ".companion" / "state.json.lock").exists()
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".companion/" in gitignore.splitlines()

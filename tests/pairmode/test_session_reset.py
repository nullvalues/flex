"""Tests for skills/pairmode/scripts/session_reset.py and the SessionStart
hook's CER-047 / Phase 68 INFRA-175 (updated INFRA-245) live context-counter
reset.

Pure-decision tests cover ``decide_reset()`` (criteria 1-5). Hook-level tests
invoke ``hooks/session_start.py`` as a subprocess against a temp project
``state.json`` and inspect the resulting state and emitted ``additionalContext``
(criteria 6-8).

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_session_reset.py -x -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "session_start.py"

# Make the skill scripts importable directly.
sys.path.insert(
    0,
    str(REPO_ROOT / "skills" / "pairmode" / "scripts"),
)

import session_reset  # noqa: E402
import context_budget  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_hook(
    cwd: Path,
    stdin: str | None = None,
) -> "subprocess.CompletedProcess[str]":
    """Invoke the SessionStart hook in ``cwd`` with optional stdin payload."""
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        cwd=str(cwd),
        input=stdin if stdin is not None else "",
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_state(cwd: Path, state: dict) -> Path:
    """Write ``.companion/state.json`` under ``cwd`` and return its path."""
    companion = cwd / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state_path = companion / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _read_state(state_path: Path) -> dict:
    return json.loads(state_path.read_text(encoding="utf-8"))


def _additional_context(stdout: str) -> str:
    payload = json.loads(stdout)
    return payload["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------------
# Pure decision tests — ``session_reset.decide_reset``
# ---------------------------------------------------------------------------


# Acceptance criterion 1


def test_decide_reset_clear_returns_default_baseline():
    """`clear` source with pairmode_version returns dict with DEFAULT_BASELINE_TOKENS."""
    state = {"pairmode_version": "0.1.0"}
    result = session_reset.decide_reset("clear", state)
    assert isinstance(result, dict)
    assert result["should_reset"] is True
    assert result["context_current_tokens"] == 25_000
    assert session_reset.DEFAULT_BASELINE_TOKENS == 25_000


# Acceptance criterion 2


def test_decide_reset_startup_matches_clear():
    """`startup` source returns same baseline as `clear`."""
    state = {"pairmode_version": "0.1.0"}
    clear_result = session_reset.decide_reset("clear", state)
    startup_result = session_reset.decide_reset("startup", state)
    assert isinstance(startup_result, dict)
    assert startup_result["context_current_tokens"] == clear_result["context_current_tokens"]


# Acceptance criterion 3


@pytest.mark.parametrize("source", ["resume", None, ""])
def test_decide_reset_non_reset_sources_return_none(source):
    """Sources outside RESET_SOURCES | COMPACT_RESET_SOURCES never reset."""
    state = {"pairmode_version": "0.1.0"}
    assert session_reset.decide_reset(source, state) is None


def test_decide_reset_unknown_source_returns_none():
    """Unknown source strings never reset."""
    state = {"pairmode_version": "0.1.0"}
    assert session_reset.decide_reset("totally-unknown", state) is None


# Acceptance criterion 4


def test_decide_reset_without_pairmode_version_returns_none():
    """Non-pairmode repo (no pairmode_version) → never reset."""
    assert session_reset.decide_reset("clear", {}) is None
    assert session_reset.decide_reset("clear", {"foo": 1}) is None
    # falsy pairmode_version is also non-pairmode
    assert session_reset.decide_reset("clear", {"pairmode_version": ""}) is None
    assert session_reset.decide_reset("clear", {"pairmode_version": None}) is None


def test_decide_reset_non_dict_state_returns_none():
    """Defensive: non-dict state never resets."""
    assert session_reset.decide_reset("clear", None) is None  # type: ignore[arg-type]
    assert session_reset.decide_reset("clear", "string") is None  # type: ignore[arg-type]
    assert session_reset.decide_reset("clear", 42) is None  # type: ignore[arg-type]


# Acceptance criterion 5


def test_decide_reset_honors_context_baseline_tokens_override():
    """A positive integer override is returned in context_current_tokens."""
    state = {"pairmode_version": "0.1.0", "context_baseline_tokens": 30_000}
    result = session_reset.decide_reset("clear", state)
    assert isinstance(result, dict)
    assert result["context_current_tokens"] == 30_000


@pytest.mark.parametrize("bad", [0, -5, "abc", None])
def test_decide_reset_invalid_override_falls_back_to_default(bad):
    """Invalid/non-positive overrides fall back to DEFAULT_BASELINE_TOKENS."""
    state = {"pairmode_version": "0.1.0", "context_baseline_tokens": bad}
    result = session_reset.decide_reset("clear", state)
    assert isinstance(result, dict)
    assert result["context_current_tokens"] == 25_000


def test_decide_reset_string_integer_override_accepted():
    """A numeric string is coerced to int and accepted when positive."""
    state = {"pairmode_version": "0.1.0", "context_baseline_tokens": "40000"}
    result = session_reset.decide_reset("clear", state)
    assert isinstance(result, dict)
    assert result["context_current_tokens"] == 40_000


# ---------------------------------------------------------------------------
# INFRA-245: `compact` source now resets, using COMPACT_BASELINE_TOKENS
# ---------------------------------------------------------------------------


def test_decide_reset_compact_returns_compact_baseline():
    """`compact` source with pairmode_version resets to COMPACT_BASELINE_TOKENS."""
    state = {"pairmode_version": "0.1.0"}
    result = session_reset.decide_reset("compact", state)
    assert isinstance(result, dict)
    assert result["should_reset"] is True
    assert result["context_current_tokens"] == 45_000
    assert session_reset.COMPACT_BASELINE_TOKENS == 45_000


def test_decide_reset_compact_uses_distinct_baseline_from_clear():
    """`compact` baseline differs from `clear`/`startup` baseline by design."""
    state = {"pairmode_version": "0.1.0"}
    compact_result = session_reset.decide_reset("compact", state)
    clear_result = session_reset.decide_reset("clear", state)
    assert compact_result["context_current_tokens"] != clear_result["context_current_tokens"]


def test_decide_reset_compact_without_pairmode_version_returns_none():
    """Non-pairmode repo (no pairmode_version) → compact never resets either."""
    assert session_reset.decide_reset("compact", {}) is None
    assert session_reset.decide_reset("compact", {"pairmode_version": ""}) is None


def test_decide_reset_compact_honors_context_compact_baseline_tokens_override():
    """A positive integer override on the compact-specific key is honored."""
    state = {
        "pairmode_version": "0.1.0",
        "context_compact_baseline_tokens": 60_000,
    }
    result = session_reset.decide_reset("compact", state)
    assert isinstance(result, dict)
    assert result["context_current_tokens"] == 60_000


@pytest.mark.parametrize("bad", [0, -5, "abc", None])
def test_decide_reset_compact_invalid_override_falls_back_to_compact_default(bad):
    """Invalid/non-positive compact overrides fall back to COMPACT_BASELINE_TOKENS."""
    state = {
        "pairmode_version": "0.1.0",
        "context_compact_baseline_tokens": bad,
    }
    result = session_reset.decide_reset("compact", state)
    assert isinstance(result, dict)
    assert result["context_current_tokens"] == 45_000


def test_decide_reset_compact_ignores_clear_only_override():
    """`context_baseline_tokens` (the clear/startup override) does not leak
    into the compact path — the two are intentionally separate keys."""
    state = {
        "pairmode_version": "0.1.0",
        "context_baseline_tokens": 30_000,
    }
    result = session_reset.decide_reset("compact", state)
    assert isinstance(result, dict)
    assert result["context_current_tokens"] == 45_000


# ---------------------------------------------------------------------------
# Hook-level tests — ``hooks/session_start.py`` with stdin payloads
# ---------------------------------------------------------------------------


# Acceptance criterion 6


def test_hook_clear_resets_phantom_counter(tmp_path):
    """`{"source":"clear"}` rewrites the phantom counter and timestamp."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_current_tokens": 212_492,
            "context_current_tokens_recorded_at": "2026-06-12T00:00:00+00:00",
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "clear"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    assert state["context_current_tokens"] == 25_000
    # Timestamp rewritten — must be different from the seeded sentinel and
    # parseable as a tz-aware ISO-8601 string.
    new_ts = state["context_current_tokens_recorded_at"]
    assert new_ts != "2026-06-12T00:00:00+00:00"
    parsed = datetime.fromisoformat(new_ts)
    assert parsed.tzinfo is not None
    # additionalContext mentions the reset and the source.
    ctx = _additional_context(result.stdout)
    assert "Context counter reset to 25000" in ctx
    assert "clear" in ctx


def test_hook_startup_resets_phantom_counter(tmp_path):
    """`{"source":"startup"}` also resets (per criterion 2 + hook delegation)."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_current_tokens": 180_000,
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "startup"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    assert state["context_current_tokens"] == 25_000
    assert "context_current_tokens_recorded_at" in state
    ctx = _additional_context(result.stdout)
    assert "startup" in ctx


def test_hook_clear_honors_baseline_override(tmp_path):
    """`context_baseline_tokens` override is honored end-to-end."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_baseline_tokens": 30_000,
            "context_current_tokens": 200_000,
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "clear"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    assert state["context_current_tokens"] == 30_000


# Acceptance criterion 7


def test_hook_resume_leaves_state_byte_identical(tmp_path):
    """`{"source":"resume"}` must not rewrite the counter or timestamp."""
    seeded = {
        "pairmode_version": "0.1.0",
        "context_current_tokens": 100_000,
        "context_current_tokens_recorded_at": "2026-06-12T00:00:00+00:00",
    }
    state_path = _seed_state(tmp_path, seeded)
    before = state_path.read_bytes()
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "resume"}))
    assert result.returncode == 0
    assert state_path.read_bytes() == before
    # Status block still emits (no exception eats the output).
    ctx = _additional_context(result.stdout)
    assert "Pairmode v0.1.0 is active" in ctx
    assert "Context counter reset" not in ctx


def test_hook_empty_stdin_leaves_state_byte_identical(tmp_path):
    """No stdin payload → source=None → no reset and status block intact."""
    seeded = {
        "pairmode_version": "0.1.0",
        "context_current_tokens": 100_000,
        "context_current_tokens_recorded_at": "2026-06-12T00:00:00+00:00",
    }
    state_path = _seed_state(tmp_path, seeded)
    before = state_path.read_bytes()
    result = _run_hook(tmp_path, stdin="")
    assert result.returncode == 0
    assert state_path.read_bytes() == before
    ctx = _additional_context(result.stdout)
    assert "Pairmode v0.1.0 is active" in ctx
    assert "Context counter reset" not in ctx


def test_hook_garbage_stdin_leaves_state_byte_identical(tmp_path):
    """Unparseable stdin → source=None → no reset and status block intact."""
    seeded = {
        "pairmode_version": "0.1.0",
        "context_current_tokens": 100_000,
        "context_current_tokens_recorded_at": "2026-06-12T00:00:00+00:00",
    }
    state_path = _seed_state(tmp_path, seeded)
    before = state_path.read_bytes()
    result = _run_hook(tmp_path, stdin="not-json{")
    assert result.returncode == 0
    assert state_path.read_bytes() == before
    ctx = _additional_context(result.stdout)
    assert "Pairmode v0.1.0 is active" in ctx
    assert "Context counter reset" not in ctx


def test_hook_no_reset_when_pairmode_version_absent(tmp_path):
    """Non-pairmode repo with `clear` source emits nothing and writes nothing."""
    seeded = {"context_current_tokens": 99_999}
    state_path = _seed_state(tmp_path, seeded)
    before = state_path.read_bytes()
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "clear"}))
    assert result.returncode == 0
    # Hook early-exits before any output.
    assert result.stdout.strip() == ""
    assert state_path.read_bytes() == before


# Acceptance criterion 8


def test_hook_post_reset_unblocks_context_budget_gate(tmp_path):
    """After a clear-reset the budget gate reads the new baseline, not None."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_current_tokens": 212_492,
            "context_current_tokens_recorded_at": "2026-06-12T00:00:00+00:00",
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "clear"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    # The budget reader returns the baseline integer — i.e. NOT None — so the
    # CONTEXT CHECK REQUIRED block is not triggered.
    tokens = context_budget.read_context_tokens_from_state(state)
    assert tokens == 25_000


# ---------------------------------------------------------------------------
# INFRA-180: context_session_reset_at in decide_reset return
# ---------------------------------------------------------------------------


def test_decide_reset_clear_returns_context_session_reset_at():
    """`clear` → context_session_reset_at present in return dict."""
    state = {"pairmode_version": "0.1.0"}
    result = session_reset.decide_reset("clear", state)
    assert isinstance(result, dict)
    assert "context_session_reset_at" in result
    # Must be parseable as a UTC ISO-8601 string.
    parsed = datetime.fromisoformat(result["context_session_reset_at"])
    assert parsed.tzinfo is not None


def test_decide_reset_startup_returns_context_session_reset_at():
    """`startup` → context_session_reset_at present in return dict."""
    state = {"pairmode_version": "0.1.0"}
    result = session_reset.decide_reset("startup", state)
    assert isinstance(result, dict)
    assert "context_session_reset_at" in result
    parsed = datetime.fromisoformat(result["context_session_reset_at"])
    assert parsed.tzinfo is not None


def test_decide_reset_resume_no_context_session_reset_at():
    """`resume` → None returned; no context_session_reset_at."""
    state = {"pairmode_version": "0.1.0"}
    result = session_reset.decide_reset("resume", state)
    assert result is None


def test_decide_reset_compact_returns_context_session_reset_at():
    """`compact` → context_session_reset_at present in return dict (INFRA-245)."""
    state = {"pairmode_version": "0.1.0"}
    result = session_reset.decide_reset("compact", state)
    assert isinstance(result, dict)
    assert "context_session_reset_at" in result
    parsed = datetime.fromisoformat(result["context_session_reset_at"])
    assert parsed.tzinfo is not None


def test_hook_clear_writes_context_session_reset_at(tmp_path):
    """`clear` via hook: state.json gains context_session_reset_at."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_current_tokens": 100_000,
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "clear"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    assert "context_session_reset_at" in state
    parsed = datetime.fromisoformat(state["context_session_reset_at"])
    assert parsed.tzinfo is not None


def test_hook_resume_does_not_write_context_session_reset_at(tmp_path):
    """`resume` via hook: state.json does NOT gain context_session_reset_at."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_current_tokens": 100_000,
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "resume"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    assert "context_session_reset_at" not in state


# ---------------------------------------------------------------------------
# INFRA-245: `compact` hook-level reset + the wedge-simulation regression test
# ---------------------------------------------------------------------------


def test_hook_compact_resets_phantom_counter(tmp_path):
    """`{"source":"compact"}` rewrites the phantom (pre-compact) counter."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_current_tokens": 166_000,
            "context_current_tokens_recorded_at": "2026-06-12T00:00:00+00:00",
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "compact"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    assert state["context_current_tokens"] == 45_000
    new_ts = state["context_current_tokens_recorded_at"]
    assert new_ts != "2026-06-12T00:00:00+00:00"
    parsed = datetime.fromisoformat(new_ts)
    assert parsed.tzinfo is not None
    ctx = _additional_context(result.stdout)
    assert "Context counter reset to 45000" in ctx
    assert "compact" in ctx


def test_hook_compact_writes_context_session_reset_at(tmp_path):
    """`compact` via hook: state.json gains context_session_reset_at."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_current_tokens": 166_000,
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "compact"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    assert "context_session_reset_at" in state
    parsed = datetime.fromisoformat(state["context_session_reset_at"])
    assert parsed.tzinfo is not None


def test_hook_compact_honors_compact_baseline_override(tmp_path):
    """`context_compact_baseline_tokens` override is honored end-to-end."""
    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_compact_baseline_tokens": 55_000,
            "context_current_tokens": 200_000,
        },
    )
    result = _run_hook(tmp_path, stdin=json.dumps({"source": "compact"}))
    assert result.returncode == 0
    state = _read_state(state_path)
    assert state["context_current_tokens"] == 55_000


def test_wedge_compact_unblocks_context_budget_gate(tmp_path):
    """Regression test for the exact deadlock described in INFRA-245's Context.

    Simulates: state.json holds a stale high count (well above a low test
    threshold) → a `compact` SessionStart event fires → the post-compact
    counter must read back below the threshold, i.e. the next build-cycle
    spawn is NOT blocked on the phantom pre-compact number.
    """
    threshold = 50_000  # low enough that the stale pre-compact figure blocks
    stale_pre_compact_tokens = 166_000

    state_path = _seed_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "context_current_tokens": stale_pre_compact_tokens,
            "context_current_tokens_recorded_at": "2026-06-12T00:00:00+00:00",
        },
    )

    # Before the fix (source excluded from RESET_SOURCES): the stale count
    # would still be at stale_pre_compact_tokens here, which exceeds threshold
    # and would block the next spawn — the wedge described in the story.
    assert stale_pre_compact_tokens > threshold

    result = _run_hook(tmp_path, stdin=json.dumps({"source": "compact"}))
    assert result.returncode == 0

    state = _read_state(state_path)
    tokens = context_budget.read_context_tokens_from_state(state)
    assert tokens is not None
    assert tokens < threshold, (
        "post-compact counter still exceeds threshold — the wedge is not fixed"
    )

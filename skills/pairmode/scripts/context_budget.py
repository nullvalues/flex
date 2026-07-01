"""context_budget.py — Pure logic for the per-step context budget hook.

This module owns the decision logic for when to alert the orchestrator that
its context window is about to overflow. It is a library of pure (or
read-only) functions with no side effects on import.

Write/read split (INFRA-182):
- ``post_tool_use.py`` calls ``read_current_tokens()`` after each Task/Agent
  completion to read the live JSONL token count, then writes
  ``context_current_tokens`` + ``context_current_tokens_recorded_at`` to
  state.json.
- ``decide()`` reads ``context_current_tokens`` from state.json only (written
  by PostToolUse or by the SessionStart baseline on /clear). If absent or stale
  (recorded before the last session reset), ``decide()`` blocks with CONTEXT
  CHECK REQUIRED.
- ``set-context-tokens`` CLI remains available as a manual override /
  debugging escape hatch; it writes the scalar ``context_current_tokens``
  only.

Design boundary (D11):
- ``decide()`` MUST NOT write to state.json, effort.db, or the transcript.
- The hook (``hooks/pre_tool_use.py``) is the sole decision writer; it makes
  one delegated call: ``decide(project_dir)`` — reads
  ``context_current_tokens`` from state.json; the hook writes
  ``context_budget_acknowledged_at`` to state.json when the result has
  ``block=True``.

The hook is the sole state.json writer for context budget state. This
function (``decide``) is strictly read-only (D11).

INFRA-182: PostToolUse is now the writer of context_current_tokens.
PreToolUse reads state.json only — no JSONL reading in PreToolUse. No
per-story dict. No stale fallback (absent or stale = hard block).
Restored _derive_transcript_path, compute_context_tokens, read_current_tokens
bounded to last 500 lines (INFRA-183).

The companion phase-spend CLI ``context_budget_check.py`` is unrelated and
remains untouched.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

try:
    from skills.pairmode.scripts.context_model import THIN_HARNESS_STEP_TOKENS
except ImportError:
    from context_model import THIN_HARNESS_STEP_TOKENS  # type: ignore[no-redef]  # flat import via hook sys.path


# ---------------------------------------------------------------------------
# Fixture location — shared with tests and the future INFRA-129 template work.
# ---------------------------------------------------------------------------

_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "tests"
    / "pairmode"
    / "fixtures"
    / "context_budget_prompt.txt"
)


# ---------------------------------------------------------------------------
# Module-level message constants
# ---------------------------------------------------------------------------

_FLEX_BUILD_PATH = Path(__file__).resolve().parent / "flex_build.py"

_CONTEXT_CHECK_REQUIRED_MSG = (
    "CONTEXT CHECK REQUIRED\n"
    "Context token count is missing or stale. It will update automatically\n"
    "after the next tool call completes.\n"
)


# ---------------------------------------------------------------------------
# 0. JSONL transcript reading (PostToolUse writer path)
# ---------------------------------------------------------------------------


def _derive_transcript_path(
    cwd: Path,
    session_id: str,
    home: "Path | None" = None,
) -> "Path | None":
    """Derive the Claude Code session JSONL transcript path.

    ``home`` defaults to ``Path.home()`` when ``None``; callers (including
    tests) can inject an alternative root to avoid touching ``~/.claude/``.

    Constructs:
        home / ".claude" / "projects" / str(cwd.resolve()).replace("/", "-")
        / f"{session_id}.jsonl"

    Returns ``None`` if:
    - ``session_id`` is empty, None, or not a non-empty string.
    - The constructed path does not exist on disk (fail-open).
    - Any exception is caught.

    Pure function; no side effects.
    """
    try:
        if not session_id or not isinstance(session_id, str):
            return None
        if home is None:
            home = Path.home()
        cwd_key = str(Path(cwd).resolve()).replace("/", "-")
        candidate = home / ".claude" / "projects" / cwd_key / f"{session_id}.jsonl"
        resolved = candidate.resolve()
        if not resolved.is_relative_to((home / ".claude").resolve()):
            return None
        if not candidate.exists():
            return None
        return candidate
    except Exception:
        return None


def compute_context_tokens(transcript_path: Path) -> "int | None":
    """Bounded reverse scan of ``transcript_path``; return the live context token count.

    Reads the last 500 lines of the file (bounded tail) and walks them in
    reverse to find the last ``type: "assistant"`` entry with a
    ``message.usage`` block. Returns the sum of:
      ``input_tokens + cache_read_input_tokens + cache_creation_input_tokens``

    Returns ``None`` if:
    - File is missing or unreadable (OSError).
    - No valid assistant entry with a ``usage`` dict is found.
    - Any numeric value is non-numeric.
    - Any exception occurs.

    Never raises. No TTL is applied — the JSONL value always reflects the
    most recent completed response.
    """
    try:
        try:
            lines = transcript_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        tail = lines[-500:] if len(lines) > 500 else lines
        for line in reversed(tail):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "assistant":
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            try:
                input_tokens = int(usage.get("input_tokens", 0) or 0)
                cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
                cache_create = int(usage.get("cache_creation_input_tokens", 0) or 0)
            except (TypeError, ValueError):
                continue
            total = input_tokens + cache_read + cache_create
            if total < 0:
                continue
            return total
        return None
    except Exception:
        return None


def read_current_tokens(
    project_dir: Path,
    session_id: str = "",
    home: "Path | None" = None,
) -> "int | None":
    """JSONL-only read of the live context token count.

    No state.json fallback. This function is the PostToolUse hook's source
    for the live count it writes back to state.json. Keeping it JSONL-only
    avoids re-arming the CER-041 staleness TTL with a stale state.json value.

    Logic:
    1. If ``session_id`` is non-empty: derive the transcript path and call
       ``compute_context_tokens()``. Return the count if positive.
    2. Return ``None`` in all other cases.

    ``home`` is passed through to ``_derive_transcript_path`` for testability.
    """
    if not session_id:
        return None
    transcript_path = _derive_transcript_path(project_dir, session_id, home)
    if transcript_path is None:
        return None
    count = compute_context_tokens(transcript_path)
    if count is not None and count > 0:
        return count
    return None


# ---------------------------------------------------------------------------
# 1. Read the current context-window count from state.json
# ---------------------------------------------------------------------------


def read_context_tokens_from_state(
    state: dict,
    _now: datetime | None = None,
) -> int | None:
    """Return the recorded scalar token count from state.json.

    Reads ``state["context_current_tokens"]`` and returns it as a positive
    integer, or ``None`` when:
    - The key is absent.
    - The value is zero, negative, or non-numeric.
    - CER-041 staleness TTL: ``context_current_tokens_recorded_at`` is older
      than ``context_current_tokens_ttl_minutes`` (default 60 minutes).

    The ``_now`` parameter is private and exists solely for test injection
    (so tests can freeze the wall clock). Production callers (``decide()``)
    must not pass it.
    """
    if not isinstance(state, dict):
        return None

    if "context_current_tokens" not in state:
        return None
    raw = state.get("context_current_tokens")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None

    # CER-041 staleness check. A missing or unparseable recorded_at falls
    # through to returning ``value`` (preserving the pre-CER-041 contract).
    recorded_at = state.get("context_current_tokens_recorded_at")
    if not recorded_at:
        return value
    try:
        recorded_at_dt = datetime.fromisoformat(recorded_at)
    except (TypeError, ValueError):
        return value

    now = _now if _now is not None else datetime.now(timezone.utc)
    try:
        ttl_minutes = int(state.get("context_current_tokens_ttl_minutes", 60) or 60)
    except (TypeError, ValueError):
        ttl_minutes = 60

    age_minutes = (now - recorded_at_dt).total_seconds() / 60
    if age_minutes > ttl_minutes:
        return None
    return value


# ---------------------------------------------------------------------------
# 2. Estimate the cost of the next step from historical attempts
# ---------------------------------------------------------------------------


def estimate_next_step_tokens(
    db_path: Path | None,
    phase: str | None,
    seeded_default: int,
) -> int:
    """Waterfall estimation of the cost of the next step from historical data.

    Tier 1 — per-phase median: if ``db_path`` exists AND ``phase`` is set AND
    the attempts table has >=5 rows for that phase with non-null
    ``tokens_total``, return the median.

    Tier 2 — global median: if per-phase rows < 5 but total rows across all
    phases >= 5, return the global median (INFRA-171).

    Tier 3 — seeded default: if global rows < 5, return ``seeded_default``.
    """
    if db_path is None:
        return seeded_default
    if not isinstance(db_path, Path):
        db_path = Path(db_path)
    if not db_path.exists():
        return seeded_default

    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return seeded_default

    try:
        cur = conn.cursor()

        # Tier 1: per-phase query (requires phase to be set).
        if phase is not None:
            try:
                cur.execute(
                    "SELECT tokens_total FROM attempts "
                    "WHERE phase = ? AND tokens_total IS NOT NULL",
                    (phase,),
                )
                phase_rows = cur.fetchall()
            except sqlite3.Error:
                phase_rows = []
            phase_values = [int(r[0]) for r in phase_rows if r and r[0] is not None]
            if len(phase_values) >= 5:
                return int(statistics.median(phase_values))

        # Tier 2: global all-phases fallback.
        try:
            cur.execute(
                "SELECT tokens_total FROM attempts WHERE tokens_total IS NOT NULL"
            )
            global_rows = cur.fetchall()
        except sqlite3.Error:
            return seeded_default
        global_values = [int(r[0]) for r in global_rows if r and r[0] is not None]
        if len(global_values) >= 5:
            return int(statistics.median(global_values))
    finally:
        conn.close()

    # Tier 3: seeded default.
    return seeded_default


# ---------------------------------------------------------------------------
# 3. Pure decision: should we block and prompt?
# ---------------------------------------------------------------------------


def should_block(
    current_tokens: int,
    expected_next: int,
    threshold: int,
    overrun_pct: float,
    acknowledged_at: int | None,
    reprompt_margin: int = 0,
) -> bool:
    """Pure decision. Block iff:

      current + expected > threshold * (1 + overrun_pct)
      AND (acknowledged_at is None OR
           current_tokens >= acknowledged_at + reprompt_margin).
    """
    ceiling = threshold * (1.0 + overrun_pct)
    if (current_tokens + expected_next) <= ceiling:
        return False
    if acknowledged_at is None:
        return True
    return current_tokens >= acknowledged_at + reprompt_margin


# ---------------------------------------------------------------------------
# 4. Render the alert prompt body from the canonical fixture file
# ---------------------------------------------------------------------------


def render_alert_prompt(
    story_id: str | None,
    tokens: int,
    threshold: int,
    overrun_pct: float,
    expected_next: int,
) -> str:
    """Template the verbatim prompt body from
    ``tests/pairmode/fixtures/context_budget_prompt.txt`` with
    ``[story RAIL-NNN]``, ``[N]``, ``[T]``, ``[O]``, ``[E]``, and ``[R]``
    substituted. ``story_id`` falls back to ``"current"`` when ``None``.

    ``[E]`` is ``expected_next``; ``[R]`` is ``ceiling - tokens`` where
    ``ceiling = int(threshold * (1 + overrun_pct))``.
    """
    template = _FIXTURE_PATH.read_text(encoding="utf-8")
    story_label = story_id if story_id else "current"
    ceiling = int(threshold * (1.0 + overrun_pct))
    remaining = ceiling - tokens
    rendered = template.replace("[story RAIL-NNN]", f"[story {story_label}]")
    rendered = rendered.replace("[N]", f"{tokens:,}")
    rendered = rendered.replace("[T]", f"{threshold:,}")
    rendered = rendered.replace("[O]", f"{overrun_pct:.0%}")
    rendered = rendered.replace("[E]", f"{expected_next:,}")
    rendered = rendered.replace("[R]", f"{remaining:,}")
    return rendered


# ---------------------------------------------------------------------------
# 5. End-to-end glue — read-only orchestration of the four functions above
# ---------------------------------------------------------------------------


def _read_state(project_dir: Path) -> dict | None:
    """Load .companion/state.json.

    Returns:
        None   — file is absent (non-pairmode project, fail-open).
        {}     — file exists but is malformed (JSON error, OSError, or
                 non-dict root); the caller treats this as a pairmode project
                 with a broken state, triggering CONTEXT CHECK REQUIRED.
        dict   — file exists and parsed successfully.
    """
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _is_stale(state: dict) -> bool:
    """Return True when context_current_tokens_recorded_at < context_session_reset_at.

    Staleness rule (strict less-than): if recorded_at predates the last
    session reset, the value is stale. Equal timestamps are NOT stale —
    the SessionStart baseline sets both to the same timestamp, so equal
    means the baseline itself was just written.

    Returns False (not stale) when:
    - context_session_reset_at is absent from state (no reset recorded — fail-open).
    - Either timestamp is unparseable (fail-open for backwards compatibility).
    - recorded_at >= reset_at (fresh or equal to the reset instant).
    """
    reset_at_str = state.get("context_session_reset_at")
    if not reset_at_str:
        return False
    recorded_at_str = state.get("context_current_tokens_recorded_at", "")
    if not recorded_at_str:
        # No recorded_at means we cannot compare → treat as stale
        return True
    try:
        reset_dt = datetime.fromisoformat(reset_at_str)
        recorded_dt = datetime.fromisoformat(recorded_at_str)
    except (TypeError, ValueError, AttributeError):
        return False
    return recorded_dt < reset_dt


def decide(
    project_dir: Path,
    flex_factor: float = 1.0,
) -> "dict | None":
    """End-to-end glue. Reads ``state["context_current_tokens"]`` from state.json
    (written by ``post_tool_use.py`` after each Task/Agent completion, or by the
    SessionStart baseline on /clear), calls ``should_block``, and returns

        {"block": True, "reason": "<prompt>", "tokens": N,
         "acknowledged_at": N}

    when the next step would exceed the overrun ceiling, ``None`` when within
    budget, or a "CONTEXT CHECK REQUIRED" block dict when:
    - context_current_tokens is absent from state.json.
    - context_current_tokens_recorded_at < context_session_reset_at (stale).

    ``flex_factor`` scales the effective ceiling:
    ``ceiling = threshold * (1 + overrun_pct) * flex_factor``.
    Values <= 0 are clamped to 1.0; values > 5.0 are clamped to 5.0.
    The default of 1.0 preserves the pre-INFRA-160 behaviour exactly.

    The caller (the hook) is responsible for writing ``acknowledged_at`` back
    to state.json when blocking. ``post_tool_use.py`` is the sole writer of
    ``context_current_tokens`` (via read_current_tokens). This function is
    strictly read-only — it MUST NOT write to state.json or effort.db (D11).
    """
    import sys as _sys

    if not isinstance(project_dir, Path):
        project_dir = Path(project_dir)

    # Clamp flex_factor to a safe range.
    if flex_factor <= 0:
        print(
            f"context_budget.decide: flex_factor={flex_factor!r} is <= 0; clamped to 1.0",
            file=_sys.stderr,
        )
        flex_factor = 1.0
    elif flex_factor > 5.0:
        print(
            f"context_budget.decide: flex_factor={flex_factor!r} is > 5.0; clamped to 5.0",
            file=_sys.stderr,
        )
        flex_factor = 5.0

    state = _read_state(project_dir)
    if state is None:
        # No state.json — non-pairmode project, fail-open.
        return None

    # Read context_current_tokens directly (bypass TTL; session-reset check below).
    current_tokens: int | None = None
    raw = state.get("context_current_tokens")
    if raw is not None:
        try:
            v = int(raw)
            if v > 0:
                current_tokens = v
        except (TypeError, ValueError):
            pass

    # Absent → block hard.
    if current_tokens is None:
        return {
            "block": True,
            "reason": _CONTEXT_CHECK_REQUIRED_MSG,
            "tokens": 0,
            "acknowledged_at": 0,
        }

    # Staleness check: if recorded_at < reset_at (strict less-than), block hard.
    if _is_stale(state):
        return {
            "block": True,
            "reason": _CONTEXT_CHECK_REQUIRED_MSG,
            "tokens": 0,
            "acknowledged_at": 0,
        }

    threshold = int(state.get("context_budget_threshold", 130000) or 130000)
    overrun_pct = float(state.get("context_budget_overrun_pct", 0.10) or 0.10)
    seeded_default = int(state.get("expected_step_tokens", THIN_HARNESS_STEP_TOKENS) or THIN_HARNESS_STEP_TOKENS)
    reprompt_margin = int(state.get("context_budget_reprompt_margin", 10000) or 10000)
    acknowledged_at_raw = state.get("context_budget_acknowledged_at")
    acknowledged_at: int | None
    if acknowledged_at_raw is None:
        acknowledged_at = None
    else:
        try:
            acknowledged_at = int(acknowledged_at_raw)
        except (TypeError, ValueError):
            acknowledged_at = None

    # CER-053: window-growth constant must not be effort-derived.
    # Pass db_path=None to skip the effort.db median lookup entirely.
    expected_next = estimate_next_step_tokens(
        None,
        None,
        seeded_default,
    )

    # Apply flex_factor to the effective ceiling.
    ceiling = threshold * (1.0 + overrun_pct) * flex_factor
    blocked = (current_tokens + expected_next) > ceiling
    if not blocked:
        return None
    if acknowledged_at is not None and current_tokens < acknowledged_at + reprompt_margin:
        return None

    state_story_id = state.get("current_story") or state.get("story_id")
    prompt = render_alert_prompt(
        story_id=str(state_story_id) if state_story_id else None,
        tokens=current_tokens,
        threshold=threshold,
        overrun_pct=overrun_pct,
        expected_next=expected_next,
    )
    return {
        "block": True,
        "reason": prompt,
        "tokens": current_tokens,
        "acknowledged_at": current_tokens,
    }

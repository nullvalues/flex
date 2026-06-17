"""context_budget.py — Pure logic for the per-step context budget hook.

This module owns the decision logic for when to alert the orchestrator that
its context window is about to overflow. It is a library of pure (or
read-only) functions with no side effects on import.

Design boundary (D11):
- ``decide()`` MUST NOT write to state.json, effort.db, or the transcript.
- The hook (``hooks/pre_tool_use.py``) is the sole writer; it makes one
  delegated call:
  ``decide(project_dir, story_id)`` — reads ``context_story_tokens[story_id]``
  from state.json; the hook writes ``context_budget_acknowledged_at`` to
  state.json when the result has ``block=True``.

The hook is the sole state.json writer for context budget state. This
function (``decide``) is strictly read-only (D11).

Token source architecture (post INFRA-180/181):
- ``decide()`` accepts ``story_id`` and reads
  ``state["context_story_tokens"][story_id]`` as the primary source,
  validating freshness against ``state["context_session_reset_at"]``.
- Falls back to the scalar ``state["context_current_tokens"]`` when
  ``story_id`` is empty (backwards-compat for non-pairmode callers).
- ``read_context_tokens_from_state()`` is the sole token source for
  ``decide()``. There is no JSONL path — the orchestrator calls ``/context``
  before each story and writes the count via ``flex_build.py set-context-tokens``.
- ``set-context-tokens`` is the sole writer of ``context_story_tokens`` entries.
- The hook passes ``story_id`` from ``state["current_story"]["id"]``.

INFRA-180: replaced the mutable ``context_current_tokens`` scalar with the
per-story-ID dict ``context_story_tokens``. The JSONL waterfall added in
Phase 72 (INFRA-179) and removed in INFRA-180 is gone entirely.
INFRA-181: removed dead JSONL functions (_derive_transcript_path,
compute_context_tokens, read_current_tokens) and updated this docstring.

The companion phase-spend CLI ``context_budget_check.py`` is unrelated and
remains untouched.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path


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
    "No token count has been recorded for the current story in this session.\n"
    "Call /context and run:\n"
    f"  PATH=$HOME/.local/bin:$PATH uv run python {_FLEX_BUILD_PATH} \\\n"
    "    set-context-tokens --tokens N --project-dir .\n"
    "Replace N with the integer token count from /context.\n"
)


# ---------------------------------------------------------------------------
# 1. Read the current context-window count from state.json
# ---------------------------------------------------------------------------


def _read_story_token_entry(
    state: dict,
    story_id: str,
) -> "dict | None":
    """Return ``state["context_story_tokens"][story_id]`` when present and
    correctly shaped (``{"tokens": int, "recorded_at": str}``).

    Returns ``None`` if:
    - ``context_story_tokens`` is absent from state.
    - ``story_id`` is not a key in the dict.
    - The entry is malformed (missing ``tokens`` or ``recorded_at``, or
      ``tokens`` is not an int-coercible value).
    - Any exception occurs.

    Never raises.
    """
    try:
        token_dict = state.get("context_story_tokens")
        if not isinstance(token_dict, dict):
            return None
        entry = token_dict.get(story_id)
        if not isinstance(entry, dict):
            return None
        # Validate shape: tokens must be int-coercible, recorded_at must be str.
        tokens = entry.get("tokens")
        recorded_at = entry.get("recorded_at")
        if tokens is None or recorded_at is None:
            return None
        int(tokens)  # will raise if non-numeric
        if not isinstance(recorded_at, str):
            return None
        return entry
    except Exception:
        return None


def _is_entry_fresh(
    entry: dict,
    state: dict,
    _now: "datetime | None" = None,
) -> bool:
    """Return ``True`` when ``entry["recorded_at"]`` post-dates
    ``state["context_session_reset_at"]``.

    Rules:
    - Returns ``True`` if ``context_session_reset_at`` is absent from state
      (no reset recorded yet — fail-open).
    - Returns ``True`` if either timestamp is unparseable (fail-open for
      backwards compatibility).
    - Returns ``False`` if ``entry["recorded_at"]`` is not **strictly after**
      ``context_session_reset_at`` (equal timestamps are treated as stale —
      the entry was recorded at the same instant as the reset boundary).
    - ``_now`` is accepted for signature symmetry with other helpers but is
      not used.
    """
    reset_at_str = state.get("context_session_reset_at")
    if not reset_at_str:
        return True
    recorded_at_str = entry.get("recorded_at", "")
    try:
        reset_dt = datetime.fromisoformat(reset_at_str)
        recorded_dt = datetime.fromisoformat(recorded_at_str)
    except (TypeError, ValueError, AttributeError):
        return True
    return recorded_dt > reset_dt


def read_context_tokens_from_state(
    state: dict,
    story_id: str = "",
    _now: datetime | None = None,
) -> int | None:
    """Return the recorded token count for ``story_id`` when a fresh entry
    exists in ``state["context_story_tokens"]``, or fall back to the scalar
    ``state["context_current_tokens"]`` when ``story_id`` is empty.

    Primary path (when ``story_id`` is non-empty):
    1. Call ``_read_story_token_entry(state, story_id)``.
    2. If entry found and ``_is_entry_fresh(entry, state)`` is True: return
       ``entry["tokens"]`` as an int.
    3. If entry found but stale (recorded before last session reset): return
       ``None`` (stale = treat as absent).
    4. If entry not found: return ``None``.

    Scalar fallback path (when ``story_id`` is empty):
    Returns ``int(state["context_current_tokens"])`` when the key is present
    and the value is a valid positive integer. Returns ``None`` for any other
    case (absent, zero, negative, non-numeric). This path is used by tests
    that do not yet pass a story ID and by callers in non-pairmode projects.

    CER-041: the scalar path checks ``context_current_tokens_recorded_at``
    against ``context_current_tokens_ttl_minutes`` (default 60 minutes). A
    missing or unparseable ``recorded_at`` skips the staleness check.

    The ``_now`` parameter is private and exists solely for test injection
    (so tests can freeze the wall clock). Production callers (``decide()``)
    must not pass it.
    """
    if not isinstance(state, dict):
        return None

    # Primary path: per-story dict lookup.
    if story_id:
        entry = _read_story_token_entry(state, story_id)
        if entry is None:
            return None
        if not _is_entry_fresh(entry, state, _now):
            return None
        try:
            return int(entry["tokens"])
        except (TypeError, ValueError, KeyError):
            return None

    # Scalar fallback path (story_id="" — backwards-compat and non-pairmode).
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


def decide(
    project_dir: Path,
    story_id: str = "",
    flex_factor: float = 1.0,
) -> "dict | None":
    """End-to-end glue. Reads ``state["context_story_tokens"][story_id]``
    (primary) or ``state["context_current_tokens"]`` (scalar fallback when
    ``story_id`` is empty), calls ``should_block``, and returns

        {"block": True, "reason": "<prompt>", "tokens": N,
         "acknowledged_at": N}

    when the next step would exceed the overrun ceiling, ``None`` when within
    budget, or a "CONTEXT CHECK REQUIRED" block dict when no token count can
    be derived.

    ``story_id`` is passed to ``read_context_tokens_from_state()`` for the
    per-story dict lookup. When empty (default), falls back to the scalar
    ``context_current_tokens`` path (backwards-compat).

    ``flex_factor`` scales the effective ceiling:
    ``ceiling = threshold * (1 + overrun_pct) * flex_factor``.
    Values <= 0 are clamped to 1.0; values > 5.0 are clamped to 5.0.
    The default of 1.0 preserves the pre-INFRA-160 behaviour exactly.

    The caller (the hook) is responsible for writing ``acknowledged_at`` back
    to state.json when blocking. ``set-context-tokens`` is the sole writer of
    ``context_story_tokens``. This function is strictly read-only — it MUST
    NOT write to state.json or effort.db (D11).
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

    # Read the current token count: per-story dict (primary) or scalar fallback.
    current_tokens: int | None = read_context_tokens_from_state(state, story_id)
    if current_tokens is None:
        return {
            "block": True,
            "reason": _CONTEXT_CHECK_REQUIRED_MSG,
            "tokens": 0,
            "acknowledged_at": 0,
        }

    threshold = int(state.get("context_budget_threshold", 120000) or 120000)
    overrun_pct = float(state.get("context_budget_overrun_pct", 0.10) or 0.10)
    seeded_default = int(state.get("expected_step_tokens", 53000) or 53000)
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

    phase = state.get("current_phase") or state.get("phase")
    db_path = project_dir / ".companion" / "effort.db"
    expected_next = estimate_next_step_tokens(
        db_path if db_path.exists() else None,
        str(phase) if phase is not None else None,
        seeded_default,
    )

    # Apply flex_factor to the effective ceiling.
    ceiling = threshold * (1.0 + overrun_pct) * flex_factor
    blocked = (current_tokens + expected_next) > ceiling
    if not blocked:
        return None
    if acknowledged_at is not None and current_tokens < acknowledged_at + reprompt_margin:
        return None

    state_story_id = story_id or state.get("current_story") or state.get("story_id")
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

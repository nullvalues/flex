"""context_budget.py — Pure logic for the per-step context budget hook.

This module owns the decision logic for when to alert the orchestrator that
its context window is about to overflow. It is a library of pure (or
read-only) functions with no side effects on import.

Design boundary (D11):
- ``decide()`` MUST NOT write to state.json, effort.db, or the transcript.
- The hook (INFRA-128) is the only writer; it persists
  ``context_budget_acknowledged_at`` to state.json when ``decide()`` returns
  ``block=True``.

The companion phase-spend CLI ``context_budget_check.py`` is unrelated and
remains untouched.
"""

from __future__ import annotations

import collections
import json
import sqlite3
import statistics
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
# 1. Compute current context-window usage from a transcript JSONL file
# ---------------------------------------------------------------------------


def compute_context_tokens(transcript_path: str) -> int | None:
    """Return the orchestrator context-window estimate at the last assistant
    turn (``input_tokens + cache_read_input_tokens +
    cache_creation_input_tokens``), or ``None`` if the transcript is missing,
    malformed, or has no assistant turns yet.

    Tail-reads the last ~50 lines to avoid the cost of a full-file parse.
    """
    if not transcript_path:
        return None
    path = Path(transcript_path)
    if not path.exists() or not path.is_file():
        return None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            tail = collections.deque(fh, maxlen=50)
    except OSError:
        return None

    # Walk tail in reverse to find the LAST assistant message with usage.
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
        return input_tokens + cache_read + cache_create

    return None


# ---------------------------------------------------------------------------
# 2. Estimate the cost of the next step from historical attempts
# ---------------------------------------------------------------------------


def estimate_next_step_tokens(
    db_path: Path | None,
    phase: str | None,
    seeded_default: int,
) -> int:
    """If ``db_path`` exists AND ``phase`` is set AND the attempts table has
    >=5 rows for that phase with non-null ``tokens_total``: return the median.
    Otherwise return ``seeded_default``.
    """
    if db_path is None or phase is None:
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
        cur.execute(
            "SELECT tokens_total FROM attempts "
            "WHERE phase = ? AND tokens_total IS NOT NULL",
            (phase,),
        )
        rows = cur.fetchall()
    except sqlite3.Error:
        return seeded_default
    finally:
        conn.close()

    values = [int(r[0]) for r in rows if r and r[0] is not None]
    if len(values) < 5:
        return seeded_default
    return int(statistics.median(values))


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
) -> str:
    """Template the verbatim prompt body from
    ``tests/pairmode/fixtures/context_budget_prompt.txt`` with
    ``[story RAIL-NNN]``, ``[N]``, ``[T]``, and ``[O]`` substituted.
    ``story_id`` falls back to ``"current"`` when ``None``.
    """
    template = _FIXTURE_PATH.read_text(encoding="utf-8")
    story_label = story_id if story_id else "current"
    rendered = template.replace("[story RAIL-NNN]", f"[story {story_label}]")
    rendered = rendered.replace("[N]", f"{tokens:,}")
    rendered = rendered.replace("[T]", f"{threshold:,}")
    rendered = rendered.replace("[O]", f"{overrun_pct:.0%}")
    return rendered


# ---------------------------------------------------------------------------
# 5. End-to-end glue — read-only orchestration of the four functions above
# ---------------------------------------------------------------------------


def _read_state(project_dir: Path) -> dict | None:
    """Load .companion/state.json, or None if missing/malformed."""
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def decide(project_dir: Path, transcript_path: str) -> dict | None:
    """End-to-end glue. Reads state.json + effort.db + transcript, calls
    ``should_block``, and returns

        {"block": True, "reason": "<prompt>", "tokens": N,
         "acknowledged_at": N}

    when the next step would exceed the overrun ceiling, else ``None``.

    The caller (the hook) is responsible for writing ``acknowledged_at`` back
    to state.json after consuming. This function is strictly read-only — it
    MUST NOT write to state.json, effort.db, or the transcript (D11).
    """
    if not isinstance(project_dir, Path):
        project_dir = Path(project_dir)

    state = _read_state(project_dir)
    if state is None:
        return None

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

    current_tokens = compute_context_tokens(transcript_path)
    if current_tokens is None:
        return None

    phase = state.get("current_phase") or state.get("phase")
    db_path = project_dir / ".companion" / "effort.db"
    expected_next = estimate_next_step_tokens(
        db_path if db_path.exists() else None,
        str(phase) if phase is not None else None,
        seeded_default,
    )

    blocked = should_block(
        current_tokens=current_tokens,
        expected_next=expected_next,
        threshold=threshold,
        overrun_pct=overrun_pct,
        acknowledged_at=acknowledged_at,
        reprompt_margin=reprompt_margin,
    )
    if not blocked:
        return None

    story_id = state.get("current_story") or state.get("story_id")
    prompt = render_alert_prompt(
        story_id=str(story_id) if story_id else None,
        tokens=current_tokens,
        threshold=threshold,
        overrun_pct=overrun_pct,
    )
    return {
        "block": True,
        "reason": prompt,
        "tokens": current_tokens,
        "acknowledged_at": current_tokens,
    }

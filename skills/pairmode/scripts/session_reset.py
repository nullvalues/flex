"""session_reset.py — Pure decision logic for SessionStart context counter reset.

CER-047 / Phase 68 INFRA-175.  Updated INFRA-180.

`context_current_tokens` is a dead-reckoning counter: anchored once from a real
`/context` reading, then advanced by each builder/reviewer's measured cost.
Dead-reckoning has no built-in signal for "the window was just wiped." After
`/clear`, `state.json` retains the previous session's accumulated total and the
context gate then blocks the next builder spawn on a phantom number.

Claude Code fires the SessionStart hook with a stdin JSON payload containing
`source`: ``"startup"`` (new process), ``"resume"`` (``--resume`` /
``--continue``), ``"clear"`` (``/clear``), or ``"compact"`` (auto-compaction).
This module decides — purely from the source string and the current state dict
— whether to reset the counter and, if so, what baseline value to write.

Design boundary (D11, mirrors ``context_budget.py``):
- ``decide_reset()`` MUST NOT read or write the filesystem.
- The hook (INFRA-175 / ``hooks/session_start.py``) is the only writer; it
  persists the returned keys to state.json when ``decide_reset()`` returns a
  dict with ``should_reset=True``.

INFRA-180: ``decide_reset()`` now returns a dict (or None) instead of an int
(or None). The dict includes ``context_session_reset_at`` so the hook can write
the session boundary timestamp alongside the existing counter fields.
"""

from __future__ import annotations

from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

#: Session sources that trigger a counter reset. ``"resume"`` never resets (the
#: same window is restored — counter is still correct). ``"compact"`` never
#: resets either (post-compact window size is unknown; stale counter overstates,
#: which over-blocks — fail-safe; deferred per CER-047).
RESET_SOURCES = frozenset({"clear", "startup"})

#: Default baseline token value for the new session window. A fresh window
#: genuinely contains ~15-25k tokens (system prompt, CLAUDE.md, memory, hook
#: output). 25_000 is deliberately on the high side: overstating fails safe
#: (gate blocks slightly early); understating erodes the overflow margin.
#: Operators can tune per-project via ``state["context_baseline_tokens"]``.
DEFAULT_BASELINE_TOKENS = 25_000


# ---------------------------------------------------------------------------
# Pure decision
# ---------------------------------------------------------------------------


def decide_reset(source: str | None, state: dict) -> "dict | None":
    """Return the reset decision dict, or ``None`` for no reset.

    When a reset is warranted, returns:
        {
            "should_reset": True,
            "context_current_tokens": baseline,
            "context_current_tokens_recorded_at": now_iso,
            "context_session_reset_at": now_iso,
        }

    Rules:
      - Returns ``None`` unless ``source in RESET_SOURCES``.
      - Returns ``None`` unless ``state`` is a dict containing a truthy
        ``pairmode_version`` (non-pairmode repos are untouched, matching the
        existing early-exit in ``session_start.py``).
      - Otherwise returns a dict with ``should_reset=True`` and the baseline
        value from ``state["context_baseline_tokens"]`` (positive int) else
        ``DEFAULT_BASELINE_TOKENS``.

    The function performs no filesystem I/O. The caller (the SessionStart
    hook) is responsible for writing the returned keys to state.json.
    """
    if source not in RESET_SOURCES:
        return None
    if not isinstance(state, dict):
        return None
    if not state.get("pairmode_version"):
        return None

    raw_override = state.get("context_baseline_tokens")
    if raw_override is not None:
        try:
            override = int(raw_override)
        except (TypeError, ValueError):
            override = None
        if override is not None and override > 0:
            baseline = override
        else:
            baseline = DEFAULT_BASELINE_TOKENS
    else:
        baseline = DEFAULT_BASELINE_TOKENS

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "should_reset": True,
        "context_current_tokens": baseline,
        "context_current_tokens_recorded_at": now_iso,
        "context_session_reset_at": now_iso,
    }

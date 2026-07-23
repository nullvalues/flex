"""session_reset.py — Pure decision logic for SessionStart context counter reset.

CER-047 / Phase 68 INFRA-175.  Updated INFRA-180.  Updated INFRA-245.

`context_current_tokens` is the live context-window token count. Since
INFRA-182, its authoritative source is a bounded reverse scan of the session's
JSONL transcript (``context_budget.compute_context_tokens``), performed by
``hooks/post_tool_use.py`` after every completed Task/Agent spawn and written
to ``state.json``. Between spawns, ``state.json`` simply holds whatever value
was last written — it does not track window occupancy on its own. That value
has no built-in signal for "the window just changed size out from under it."
After `/clear` (a fresh window) or auto-compaction (a shrunk window),
`state.json` still holds the previous window's figure, and the context gate
then blocks the next builder spawn on a stale number.

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

INFRA-245: ``"compact"`` now also resets (previously deliberately excluded —
see CER-070/CER-047 history below). Deriving the real post-compact count would
require reading the JSONL transcript for the first assistant `usage` entry
after the `compact_boundary` marker — filesystem I/O that decide_reset() may
not perform (D11), and a change to the transcript-parsing surface that this
story's Out-of-scope explicitly reserves for INFRA-241 alone. So the compact
path uses a documented conservative constant instead, exactly analogous to
``DEFAULT_BASELINE_TOKENS`` for `clear`/`startup`. See ``COMPACT_BASELINE_TOKENS``.
"""

from __future__ import annotations

from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

#: Session sources that trigger a counter reset to the fresh-session baseline
#: (``DEFAULT_BASELINE_TOKENS``). ``"resume"`` never resets (the same window is
#: restored — counter is still correct).
RESET_SOURCES = frozenset({"clear", "startup"})

#: Session sources that trigger a counter reset to the post-compact baseline
#: (``COMPACT_BASELINE_TOKENS``). Split from ``RESET_SOURCES`` because the two
#: cases warrant different baseline values (see module docstring, INFRA-245).
COMPACT_RESET_SOURCES = frozenset({"compact"})

#: Default baseline token value for the new session window. A fresh window
#: genuinely contains ~15-25k tokens (system prompt, CLAUDE.md, memory, hook
#: output). 25_000 is deliberately on the high side: overstating fails safe
#: (gate blocks slightly early); understating erodes the overflow margin.
#: Operators can tune per-project via ``state["context_baseline_tokens"]``.
DEFAULT_BASELINE_TOKENS = 25_000

#: Default baseline token value for the window immediately after auto-compaction.
#: Unlike a fresh session, a post-compact window is NOT small: compaction
#: replaces old turns with a summary but the summary plus carried-forward
#: context is substantial. A directly-observed trace this phase (INFRA-245
#: adversarial audit) showed usage at ~39k tokens immediately after a
#: `compact_boundary` entry (dropped from ~166k pre-compact). 45_000 is set
#: above that observed figure, deliberately on the high side for the same
#: fail-safe reason as ``DEFAULT_BASELINE_TOKENS``: overstating blocks slightly
#: early; understating would let the gate under-block a window that's still
#: large. Operators can tune per-project via
#: ``state["context_compact_baseline_tokens"]``.
COMPACT_BASELINE_TOKENS = 45_000


# ---------------------------------------------------------------------------
# Pure decision
# ---------------------------------------------------------------------------


def _resolve_baseline(state: dict, override_key: str, default: int) -> int:
    """Return ``state[override_key]`` coerced to a positive int, else ``default``.

    Shared by both reset paths (fresh-session and post-compact) — same
    coercion rules, different override key and default per caller.
    """
    raw_override = state.get(override_key)
    if raw_override is not None:
        try:
            override = int(raw_override)
        except (TypeError, ValueError):
            override = None
        if override is not None and override > 0:
            return override
    return default


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
      - Returns ``None`` unless ``source in RESET_SOURCES | COMPACT_RESET_SOURCES``.
      - Returns ``None`` unless ``state`` is a dict containing a truthy
        ``pairmode_version`` (non-pairmode repos are untouched, matching the
        existing early-exit in ``session_start.py``).
      - For ``source in RESET_SOURCES`` (``clear``/``startup``): baseline is
        ``state["context_baseline_tokens"]`` (positive int) else
        ``DEFAULT_BASELINE_TOKENS``.
      - For ``source in COMPACT_RESET_SOURCES`` (``compact``): baseline is
        ``state["context_compact_baseline_tokens"]`` (positive int) else
        ``COMPACT_BASELINE_TOKENS`` (INFRA-245 — see module docstring for why
        this is a documented constant rather than a transcript re-derivation).

    The function performs no filesystem I/O. The caller (the SessionStart
    hook) is responsible for writing the returned keys to state.json.
    """
    if source not in RESET_SOURCES and source not in COMPACT_RESET_SOURCES:
        return None
    if not isinstance(state, dict):
        return None
    if not state.get("pairmode_version"):
        return None

    if source in COMPACT_RESET_SOURCES:
        baseline = _resolve_baseline(
            state, "context_compact_baseline_tokens", COMPACT_BASELINE_TOKENS
        )
    else:
        baseline = _resolve_baseline(
            state, "context_baseline_tokens", DEFAULT_BASELINE_TOKENS
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "should_reset": True,
        "context_current_tokens": baseline,
        "context_current_tokens_recorded_at": now_iso,
        "context_session_reset_at": now_iso,
    }

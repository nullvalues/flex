"""effort_recorder.py — in-process helper for cross-skill effort recording.

This helper is the in-process counterpart to ``record_attempt.py``'s CLI.  It
exists so seed and companion Python code (which run with
``disable-model-invocation: true`` and therefore cannot be subagent-called by
the build orchestrator) can record their own LLM-call effort directly.

Usage from a sibling skill:

    import sys
    from pathlib import Path
    _ANCHOR_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    if str(_ANCHOR_ROOT) not in sys.path:
        sys.path.insert(0, str(_ANCHOR_ROOT))
    from skills.pairmode.scripts.effort_recorder import record_effort

    record_effort(
        project_dir=Path.cwd(),
        story_id="seed:reconcile",
        agent_role="seed-reconcile",
        model="claude-sonnet-4-6",
        usage={"input_tokens": 1234, "output_tokens": 567},
    )

Behaviour
---------
- Silently no-ops (returns ``None``) when:
  - ``project_dir/.companion/state.json`` is missing.
  - ``state.json["effort_tracking"]`` is missing or false.
  - The state file is unreadable.
- Never raises on database errors (these are logged via ``log_fn`` if
  supplied, otherwise swallowed).  Effort recording is best-effort
  observability and must never break the calling skill.
- ``phase`` and ``rail`` are intentionally left ``None`` for cross-skill
  rows; seed/sidebar work happens outside the phase/rail model.

The synthetic ``story_id`` values used by callers (``seed:<session-id>``,
``seed:reconcile``, ``sidebar:<story-id-or-no-story>``) distinguish these
rows from pairmode-loop attempts.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from typing import Any, Callable

# Ensure the anchor repo root is importable so ``effort_db`` resolves whether
# this module is loaded as ``skills.pairmode.scripts.effort_recorder`` or as a
# bare module.
_ANCHOR_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ANCHOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANCHOR_ROOT))

from skills.pairmode.scripts import effort_db as _effort_db  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()


def _read_state(project_dir: Path) -> dict | None:
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_usage(usage: Any) -> dict[str, int | None]:
    """Pull token fields out of an SDK usage dict (or ResultMessage-like).

    Recognised keys (Anthropic-style):
      - ``input_tokens`` / ``output_tokens``
      - ``cache_read_input_tokens`` / ``cache_creation_input_tokens``

    Falls back gracefully if ``usage`` is None or unrecognised.
    """

    if usage is None:
        return {
            "tokens_in": None,
            "tokens_out": None,
            "tokens_total": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
        }

    # Allow either dict-like or attribute-bearing objects.
    def _get(key: str) -> Any:
        if isinstance(usage, dict):
            return usage.get(key)
        return getattr(usage, key, None)

    tokens_in = _coerce_int(_get("input_tokens"))
    tokens_out = _coerce_int(_get("output_tokens"))
    cache_read = _coerce_int(_get("cache_read_input_tokens"))
    cache_write = _coerce_int(_get("cache_creation_input_tokens"))

    parts = [t for t in (tokens_in, tokens_out) if t is not None]
    tokens_total = sum(parts) if parts else None

    return {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_total,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
    }


def record_effort(
    *,
    project_dir: Path | str,
    story_id: str,
    agent_role: str,
    model: str | None = None,
    usage: Any = None,
    attempt_number: int = 1,
    duration_ms: int | None = None,
    outcome: str | None = None,
    notes: str | None = None,
    phase: str | None = None,
    rail: str | None = None,
    log_fn: Callable[[str], None] | None = None,
) -> int | None:
    """Record one LLM-call attempt row, or silently no-op.

    Returns the inserted row id on success, ``None`` if recording was skipped
    (tracking disabled, state missing) or the underlying write failed.

    Required fields are passed as kwargs to make the call site self-documenting
    and avoid positional ambiguity at every wrapped call site.
    """

    project_path = Path(project_dir).resolve()
    state = _read_state(project_path)

    if not state or not state.get("effort_tracking"):
        return None

    if not story_id or not agent_role:
        # Required by effort_db; fail closed by no-op.
        return None

    tokens = _normalize_usage(usage)
    ts = _utc_now_iso()

    try:
        db_path = _effort_db.resolve_effort_db_path(project_path)
        _effort_db.init_db(db_path)
        return _effort_db.insert_attempt(
            db_path,
            story_id=story_id,
            phase=phase,
            rail=rail,
            agent_role=agent_role,
            model=model,
            attempt_number=attempt_number,
            tokens_total=tokens["tokens_total"],
            tokens_in=tokens["tokens_in"],
            tokens_out=tokens["tokens_out"],
            cache_read_tokens=tokens["cache_read_tokens"],
            cache_write_tokens=tokens["cache_write_tokens"],
            tool_uses=None,
            duration_ms=duration_ms,
            outcome=outcome,
            notes=notes,
            ts=ts,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort observability
        if log_fn is not None:
            try:
                log_fn(f"effort_recorder error: {exc}")
            except Exception:
                pass
        return None

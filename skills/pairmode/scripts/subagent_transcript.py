"""subagent_transcript.py — hook-side effort-attempt recording (INFRA-236).

Restores the effort-tracking pipeline's missing token source. 0.2's
builder/reviewer agent templates ended every final message with a
self-reported ``<usage>total_tokens: N</usage>`` block that
``record_attempt.py --usage-block`` parsed; 0.3's builder/reviewer
``procedure.md`` files forbid that format (WORKER-004 grammar) and nothing
replaced it, so ``.companion/effort.db`` never received a row.

This module is the replacement mechanism. It is called by
``hooks/post_tool_use.py``'s Task/Agent branch as the second of its two
delegated calls (the first being ``context_budget.read_current_tokens`` —
unchanged, INFRA-182). It reads the just-completed Task/Agent spawn's own
usage data directly from the live session JSONL transcript — the same
mechanical source ``context_budget.py`` already trusts for
``context_current_tokens`` — and from the tool call's own ``tool_input`` /
``tool_response``, never from agent-authored prose.

DP7 invariant (see ``docs/architecture.md`` § effort.db ≠ context-control):
the token totals this module writes to ``effort.db`` are a DIFFERENT metric
than ``context_budget``'s ``context_current_tokens`` — a subagent's own
resource cost never entered the orchestrator's own context window. This
module must NEVER write to ``context_current_tokens`` / ``state.json``'s
context-budget keys, and ``context_budget.py`` must never sum these
per-attempt totals into its own live-window count. The two pipelines read
the same transcript file but extract disjoint data: ``context_budget``
scans the orchestrator's own (non-sidechain) turns; this module scans the
spawned subagent's own (``isSidechain: true``) turns.

Public entry point: ``record_attempt_from_transcript()``. Every function in
this module is best-effort and never raises — a hook branch calling this
must stay millisecond-thin and must never block on a malformed transcript,
a missing state.json, or an unrecognised tool_response shape.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from skills.pairmode.scripts.context_budget import _derive_transcript_path
    from skills.pairmode.scripts.effort_recorder import record_effort
except ImportError:
    from context_budget import _derive_transcript_path  # type: ignore[no-redef]  # flat import via hook sys.path
    from effort_recorder import record_effort  # type: ignore[no-redef]  # flat import via hook sys.path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Agent roles this module writes effort.db attempt rows for. Deliberately
#: separate from hooks/pre_tool_use.py's BUILD_CYCLE_SUBAGENTS (the
#: context-budget *gate's* scope) — ``reviewer`` IS recorded here (INFRA-246
#: only exempts it from the budget gate, not from effort accounting).
#: Non-build-cycle spawns (general-purpose / Plan / Explore / absent
#: subagent_type) are never recorded, matching record_attempt.py's
#: documented --agent-role values for the pairmode build loop.
RECORDABLE_SUBAGENT_ROLES: frozenset[str] = frozenset({
    "builder",
    "reviewer",
    "loop-breaker",
    "security-auditor",
    "intent-reviewer",
})

_STORY_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]*-\d{2,})\b")
_FAIL_CAUSE_LINE_RE = re.compile(r"FAIL-CAUSE:\s*(.+)")

_EMPTY_USAGE: dict[str, Any] = {
    "tokens_in": None,
    "tokens_out": None,
    "tokens_total": None,
    "cache_read_tokens": None,
    "cache_write_tokens": None,
    "duration_ms": None,
    "model": None,
}


# ---------------------------------------------------------------------------
# state.json read
# ---------------------------------------------------------------------------


def _read_state(project_dir: Path) -> "dict | None":
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# tool_response → outcome / fail_cause extraction
# ---------------------------------------------------------------------------


def _flatten_tool_response(tool_response: Any) -> str:
    """Best-effort flatten of a Task/Agent tool_response payload into text.

    Handles the common shapes: a bare string, ``{"content": [...]}``,
    ``{"content": "..."}``, a list of ``{"type": "text", "text": ...}``
    blocks, or an arbitrary dict/list (JSON-dumped as a last resort).
    Never raises.
    """
    try:
        if tool_response is None:
            return ""
        if isinstance(tool_response, str):
            return tool_response
        if isinstance(tool_response, dict):
            for key in ("content", "result", "text"):
                if key in tool_response:
                    return _flatten_tool_response(tool_response[key])
            return json.dumps(tool_response)
        if isinstance(tool_response, list):
            parts = []
            for item in tool_response:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        return str(tool_response)
    except Exception:
        return ""


def parse_worker_outcome(tool_response: Any) -> "tuple[str | None, str | None]":
    """Extract ``(outcome, fail_cause)`` from a completed Task/Agent's own
    returned result text.

    Reads the WORKER-004 BUILD-RESULT / REVIEW-RESULT JSON grammar
    (``worker_result.py``) directly out of the flattened tool_response text
    — no reliance on the orchestrator's own re-derivation of what the
    subagent reported. Falls back to the human-readable ``FAIL-CAUSE:``
    transcript line (``reviewer/procedure.md``) when no JSON ``fail_cause``
    field is present. Returns ``(None, None)`` when no recognisable result
    object is found. Never raises.
    """
    text = _flatten_tool_response(tool_response)
    if not text:
        return None, None

    outcome: "str | None" = None
    fail_cause: "str | None" = None

    for match in re.finditer(r"\{[^{}]*\}", text, re.DOTALL):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        rtype = obj.get("type")
        if rtype == "BUILD-RESULT":
            outcome = obj.get("outcome") or outcome
            fail_cause = obj.get("fail_cause") or fail_cause
        elif rtype == "REVIEW-RESULT":
            verdict = obj.get("verdict")
            if verdict in ("PASS", "FAIL"):
                outcome = verdict
            fail_cause = obj.get("fail_cause") or fail_cause

    if fail_cause is None:
        m = _FAIL_CAUSE_LINE_RE.search(text)
        if m:
            fail_cause = m.group(1).strip()

    return outcome, fail_cause


# ---------------------------------------------------------------------------
# Transcript → per-spawn usage extraction
# ---------------------------------------------------------------------------


def extract_subagent_usage(
    transcript_path: "Path | None",
    tool_use_id: "str | None",
) -> dict[str, Any]:
    """Sum token usage across the ``isSidechain: true`` transcript entries
    attributable to the subagent spawn identified by *tool_use_id*.

    Claude Code interleaves a spawned subagent's own turns into the SAME
    session JSONL transcript file as ``isSidechain: true`` entries,
    immediately following the ``tool_use`` block (matched by its ``id``)
    that launched them. This walks the transcript top to bottom, starts
    accumulating once it finds the matching ``tool_use`` entry, sums every
    ``isSidechain`` assistant turn's usage until the first non-sidechain
    entry (the subagent's completion, back on the main thread), and returns
    the totals.

    Returns a dict of all-``None`` fields (see ``_EMPTY_USAGE``) when
    *transcript_path* is ``None``, *tool_use_id* is falsy, the file is
    unreadable, no matching ``tool_use`` entry is found, or no sidechain
    usage data follows it. Never raises.
    """
    if transcript_path is None or not tool_use_id:
        return dict(_EMPTY_USAGE)

    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return dict(_EMPTY_USAGE)

    tokens_in = tokens_out = cache_read = cache_write = 0
    model: "str | None" = None
    found_any = False
    matched_chain = False

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue

        if not matched_chain:
            message = entry.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_use"
                        and block.get("id") == tool_use_id
                    ):
                        matched_chain = True
                        break
            continue

        if entry.get("isSidechain") and entry.get("type") == "assistant":
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            if model is None:
                model = message.get("model")
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            try:
                tokens_in += int(usage.get("input_tokens", 0) or 0)
                tokens_out += int(usage.get("output_tokens", 0) or 0)
                cache_read += int(usage.get("cache_read_input_tokens", 0) or 0)
                cache_write += int(usage.get("cache_creation_input_tokens", 0) or 0)
                found_any = True
            except (TypeError, ValueError):
                continue
        elif not entry.get("isSidechain"):
            # First non-sidechain entry after the match ends this spawn's
            # own turn window — the subagent has returned to the main thread.
            break

    if not found_any:
        return dict(_EMPTY_USAGE)

    return {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "duration_ms": None,
        "model": model,
    }


# ---------------------------------------------------------------------------
# story_id derivation
# ---------------------------------------------------------------------------


def _derive_story_id(tool_input: dict, state: "dict | None") -> "str | None":
    """Best-effort story-id derivation from tool_input, falling back to
    state.json's ``current_story``. Never raises."""
    for key in ("prompt", "description"):
        value = tool_input.get(key)
        if value:
            m = _STORY_ID_RE.search(str(value))
            if m:
                return m.group(1)

    if isinstance(state, dict):
        current_story = state.get("current_story")
        if isinstance(current_story, dict):
            sid = current_story.get("id")
            if sid:
                return str(sid)
        elif isinstance(current_story, str) and current_story:
            return current_story

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def record_attempt_from_transcript(
    *,
    project_dir: "Path | str",
    session_id: str,
    tool_input: "dict | None",
    tool_response: Any = None,
    tool_use_id: "str | None" = None,
    home: "Path | None" = None,
) -> "int | None":
    """The hook's single delegated call for effort-attempt recording.

    Writes one row to ``.companion/effort.db`` via
    ``effort_recorder.record_effort`` when ``tool_input.subagent_type`` is a
    member of :data:`RECORDABLE_SUBAGENT_ROLES` and ``effort_tracking`` is
    ``true`` in ``.companion/state.json``. Returns the inserted row id, or
    ``None`` when recording was skipped or failed for any reason (never
    raises — the caller is a millisecond-thin hook branch).

    Field sourcing (all derived from ``tool_input``, ``tool_response``, the
    live JSONL transcript, or ``state.json`` — never from agent-authored
    prose the hook has to trust blindly):

    - ``agent_role`` — ``tool_input.subagent_type``.
    - ``story_id`` — ``RAIL-NNN`` pattern in ``tool_input.prompt`` /
      ``description``, falling back to ``state.json["current_story"]``.
    - ``model`` — the orchestrator's pinned ``tool_input.model``
      (``CLAUDE.build.md``'s ``model=a.model`` override) if present,
      otherwise the model the subagent's own transcript turns report.
    - ``outcome`` / notes (``fail_cause``) — parsed from the subagent's own
      returned BUILD-RESULT / REVIEW-RESULT JSON (``parse_worker_outcome``).
    - ``tokens_*`` — summed from the subagent's own sidechain transcript
      turns (``extract_subagent_usage``). ``None`` when no sidechain usage
      data is available (e.g. an async-launched spawn whose transcript
      lives in a separate output file) — a known limitation, not silently
      fabricated data.
    """
    try:
        if not isinstance(tool_input, dict):
            return None
        subagent_type = tool_input.get("subagent_type")
        if subagent_type not in RECORDABLE_SUBAGENT_ROLES:
            return None

        project_path = Path(project_dir) if not isinstance(project_dir, Path) else project_dir
        state = _read_state(project_path)
        if not state or not state.get("effort_tracking"):
            return None

        story_id = _derive_story_id(tool_input, state)

        transcript_path = _derive_transcript_path(project_path, session_id, home)
        usage = extract_subagent_usage(transcript_path, tool_use_id)

        model = tool_input.get("model") or usage.get("model")
        outcome, fail_cause = parse_worker_outcome(tool_response)

        rail = story_id.split("-", 1)[0] if story_id and "-" in story_id else None

        return record_effort(
            project_dir=project_path,
            story_id=story_id or f"unattributed:{subagent_type}",
            agent_role=str(subagent_type),
            model=model,
            usage={
                "input_tokens": usage.get("tokens_in"),
                "output_tokens": usage.get("tokens_out"),
                "cache_read_input_tokens": usage.get("cache_read_tokens"),
                "cache_creation_input_tokens": usage.get("cache_write_tokens"),
            },
            duration_ms=usage.get("duration_ms"),
            outcome=outcome,
            notes=fail_cause,
            phase=None,
            rail=rail,
        )
    except Exception:
        return None

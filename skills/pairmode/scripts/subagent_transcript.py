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

INFRA-237: this is also the sole per-attempt call site that has both a
completed builder/reviewer spawn's outcome and its story_id in hand, so it
additionally bumps ``.companion/attempt_counter.json`` (via
``flex_build.bump_attempt_count``) on a FAIL outcome. That counter is core
build-loop control state that ``next_action.infer_position`` depends on
(not observability) — the bump runs unconditionally on FAIL, independent of
``effort_tracking``, so a project with effort recording disabled does not
lose its loop-breaker/human-pause escalation. The counter is cleared on the
opposite end by ``flex_build.py merge-story-worktree`` on a successful land.

INFRA-258: Agent spawns are asynchronous — at PostToolUse time the
``tool_response`` is launch metadata only (``isAsync``/``agentId``/
``outputFile``), never the completed result. Recording is now two-phase:
(1) at PostToolUse time a row is written immediately with ``tokens_total``
and ``outcome`` both ``NULL``, plus the spawn's own ``agent_id``/
``output_file`` persisted via ``effort_db.set_spawn_ref``; (2)
``reconcile_pending_attempts`` — invoked both from this module's own entry
point (before the next spawn's row is written) and from
``hooks/session_start.py`` — later reads the spawn's own ``output_file``
JSONL directly (``read_completed_spawn``) and fills in the row via
``effort_db.reconcile_attempt`` once the spawn has actually finished. See
``docs/architecture.md`` § Effort tracking for the full mechanism, the
accepted losses (evicted `/tmp` output files, `effort_tracking`-disabled
projects), and why checkpoint-role spawns (``CHECKPOINT_ROLES``) are
attributed to ``phase:<key>`` rather than to a story id.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from skills.pairmode.scripts.context_budget import _derive_transcript_path
    from skills.pairmode.scripts import effort_db
    from skills.pairmode.scripts.effort_recorder import record_effort
    from skills.pairmode.scripts.flex_build import bump_attempt_count, read_attempt_count
except ImportError:
    from context_budget import _derive_transcript_path  # type: ignore[no-redef]  # flat import via hook sys.path
    import effort_db  # type: ignore[no-redef]  # flat import via hook sys.path
    from effort_recorder import record_effort  # type: ignore[no-redef]  # flat import via hook sys.path
    from flex_build import bump_attempt_count, read_attempt_count  # type: ignore[no-redef]  # flat import via hook sys.path

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

#: Checkpoint-stage worker roles (INFRA-258). `next_action.py`'s
#: `checkpoint-security` / `checkpoint-intent` actions spawn these with
#: `scalar=""` — they belong to no single story — but their prompts enumerate
#: the *phase's* story ids (e.g. "...docs/phases/phase-101.md — stories
#: INFRA-256 ..., INFRA-257 ..."). Attributing by first-match story regex
#: (as every other role does) silently stamps an entire phase's checkpoint
#: cost onto whichever story happens to be named first in the prompt
#: (observed: effort.db ids 339-340 stamped `INFRA-256`). These roles are
#: therefore routed to `_derive_attribution`'s phase-key branch instead —
#: never `_STORY_ID_RE`, never `state.json["current_story"]` — so a
#: per-story rollup that filters `story_id IN (<phase's story ids>)`
#: correctly excludes them while `query_by_phase` still finds them.
CHECKPOINT_ROLES: frozenset[str] = frozenset({"security-auditor", "intent-reviewer"})

_STORY_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]*-\d{2,})\b")
_FAIL_CAUSE_LINE_RE = re.compile(r"FAIL-CAUSE:\s*(.+)")

# Phase-key derivation (INFRA-258, Ensures 22): tries the
# `docs/phases/phase-<key>.md` path pattern first, then a bare `Phase <key>`
# mention. `<key>` matches `[A-Za-z0-9][A-Za-z0-9._-]*` with trailing
# punctuation stripped so both `101` and `HARNESS001-main` resolve.
_PHASE_KEY_CHARS = r"[A-Za-z0-9][A-Za-z0-9._-]*"
_PHASE_DOC_PATH_RE = re.compile(r"docs/phases/phase-(" + _PHASE_KEY_CHARS + r")\.md")
_PHASE_BARE_RE = re.compile(r"\bPhase\s+(" + _PHASE_KEY_CHARS + r")")

#: Bounds on the reconciliation sweep (Instructions 12a / Ensures 15) — a
#: hook-path invocation must never scan unbounded work.
RECONCILE_MAX_ROWS = 5
RECONCILE_MAX_LINES = 20000

#: CER-088: the sweep's age cutoff, single-sourced from effort_db so the
#: number is never re-literalled at this call site.
RECONCILE_MAX_AGE_DAYS = effort_db.PENDING_MAX_AGE_DAYS

#: Directory component every Claude Code spawn-output file sits under
#: (CER-089). Observed live shape: `/tmp/claude-<uid>/<slug>/<session>/tasks/<hash>.output`.
SPAWN_TASKS_DIR_NAME = "tasks"

#: A quiescent-retirement row must be both this old (its DB row `ts`) *and*
#: have an output file whose mtime is this old, before `include_quiescent`
#: will retire it (CER-091 defect 3/8). Age is checked twice because a row
#: can be old while its agent is still actively writing — reconciling a
#: live agent is exactly what INFRA-258's completion detection exists to
#: prevent.
QUIESCENT_AGE_SECONDS = 900

#: CER-091 defect 1: recognised `decision` values for `log_recording_event`.
#: Not exhaustive — `error:<ExceptionClassName>` is dynamic — but every
#: static decision this module emits is listed here so tests can enumerate
#: the set.
RECORDING_DECISIONS: frozenset[str] = frozenset({
    "recorded",
    "skip:not-recordable-role",
    "skip:no-tool-input",
    "skip:no-state",
    "skip:effort-tracking-off",
    "observed:non-spawn-tool",
    "log-truncated",
})

#: Size cap for .companion/effort_recording.log (CER-091 defect 1). Exceeding
#: this truncates and restarts the log with a single log-truncated marker.
RECORDING_LOG_MAX_BYTES = 262_144

#: CER-091 defect 4: a story whose frontmatter `status` is one of these is
#: considered finished — a reconciliation-time FAIL bump must not resurrect
#: `.companion/attempt_counter.json` for it.
_LATE_BUMP_BLOCKED_STATUSES: frozenset[str] = frozenset(
    {"complete", "merged", "deferred", "backlog"}
)
_STATUS_LINE_RE = re.compile(r'^\s*status:\s*["\']?([\w-]+)["\']?\s*$', re.MULTILINE)

#: CER-091 defect 3: the enumerable set of reasons `classify_pending_reason`
#: returns. `reconcilable` means "the next default sweep will complete this
#: row"; every other value names a specific reason it will not.
PENDING_REASONS: tuple[str, ...] = (
    "no-output-file",
    "file-missing",
    "file-empty",
    "in-flight",
    "not-terminated",
    "no-usage",
    "line-cap",
    "no-outcome",
    "reconcilable",
)

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


# CER-091 defect 2: mirrors worker_result.py's `_SCHEMAS[REVIEW_RESULT]`
# "verdict" enum ({"PASS", "FAIL", "ALIGNED"}) — the source of truth for
# which verdicts are recognised. Not imported directly: this module is on
# the hook path and must stay import-light (worker_result.py pulls in the
# broader WORKER-004 grammar machinery this module has no other need for).
# Dropping ALIGNED here is what stranded effort.db row 344 — an honest
# intent-reviewer ALIGNED return was parsed as "no outcome" and its tokens
# committed with outcome permanently NULL.
RECOGNISED_REVIEW_VERDICTS: frozenset[str] = frozenset({"PASS", "FAIL", "ALIGNED"})


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
            if verdict in RECOGNISED_REVIEW_VERDICTS:
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


def _sum_deduped_usage(entries: "list[dict]") -> dict[str, Any]:
    """Dedupe assistant usage entries by ``message.id`` (last write wins),
    then sum the token/cache fields (INFRA-258).

    Both the synchronous sidechain path (``extract_subagent_usage``) and the
    async output-file path (``read_completed_spawn``) route through this
    single helper so the two report the same metric under the same rules.

    A subagent's own JSONL contains multiple entries per assistant message —
    streaming snapshots sharing one ``message.id``, with monotonically
    growing ``output_tokens`` (observed: one ``message.id`` appearing three
    times with ``output_tokens`` 5, 5, 263 — only the last, 263, is the true
    total). Naively summing every ``usage`` block double- (or triple-)
    counts. Entries with no ``message.id`` are summed individually under a
    synthetic unique key (nothing to dedupe against).

    *entries* is an iterable of already-parsed JSONL entry dicts; each is
    expected to be a ``type == "assistant"`` entry carrying
    ``message.usage``. Non-conforming entries are silently skipped. Returns
    the ``_EMPTY_USAGE``-shaped dict — all fields ``None`` when no usage data
    was found in any entry. Never raises.
    """
    by_key: dict[Any, dict] = {}
    synthetic = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        msg_id = message.get("id")
        key = msg_id if msg_id else ("__synthetic__", synthetic)
        if not msg_id:
            synthetic += 1
        by_key[key] = message  # last write wins per id

    tokens_in = tokens_out = cache_read = cache_write = 0
    model: "str | None" = None
    found_any = False

    for message in by_key.values():
        usage = message.get("usage") or {}
        try:
            tokens_in += int(usage.get("input_tokens", 0) or 0)
            tokens_out += int(usage.get("output_tokens", 0) or 0)
            cache_read += int(usage.get("cache_read_input_tokens", 0) or 0)
            cache_write += int(usage.get("cache_creation_input_tokens", 0) or 0)
        except (TypeError, ValueError):
            continue
        found_any = True
        if message.get("model"):
            model = message.get("model")

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

    matched_chain = False
    candidate_entries: list[dict] = []

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
            candidate_entries.append(entry)
        elif not entry.get("isSidechain"):
            # First non-sidechain entry after the match ends this spawn's
            # own turn window — the subagent has returned to the main thread.
            break

    # INFRA-258: dedupe by message.id (last write wins) before summing — a
    # subagent's own turns can appear as multiple streaming-snapshot JSONL
    # lines sharing one message.id with monotonically growing output_tokens.
    return _sum_deduped_usage(candidate_entries)


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


def _strip_trailing_punct(value: str) -> str:
    return value.rstrip(".,;:")


def _derive_phase_key(tool_input: dict) -> "str | None":
    """Derive a phase key from a checkpoint spawn's own prompt (INFRA-258).

    Tries the ``docs/phases/phase-<key>.md`` path pattern first, then a bare
    ``Phase <key>`` mention. ``<key>`` matches ``[A-Za-z0-9][A-Za-z0-9._-]*``
    with trailing punctuation stripped, so both ``101`` and
    ``HARNESS001-main`` resolve. Returns ``None`` when neither pattern is
    found. Never raises.
    """
    try:
        for key in ("prompt", "description"):
            value = tool_input.get(key)
            if not value:
                continue
            text = str(value)
            m = _PHASE_DOC_PATH_RE.search(text)
            if m:
                return _strip_trailing_punct(m.group(1))
            m = _PHASE_BARE_RE.search(text)
            if m:
                return _strip_trailing_punct(m.group(1))
    except Exception:
        return None
    return None


def _derive_attribution(
    tool_input: dict, state: "dict | None", subagent_type: "str | None"
) -> "tuple[str | None, str | None, str | None]":
    """Return ``(story_id, phase_key, rail)`` for a completed spawn (INFRA-258).

    For :data:`CHECKPOINT_ROLES` (``security-auditor``, ``intent-reviewer``),
    ``next_action.py`` emits ``checkpoint-security`` / ``checkpoint-intent``
    with ``scalar=""`` (no story), while their prompts enumerate the phase's
    story ids — a first-match story-id regex would attribute an entire
    phase's checkpoint cost to whichever story is named first in the prompt
    (observed: effort.db ids 339-340 stamped ``INFRA-256``). These roles
    therefore never consult ``_STORY_ID_RE`` or ``state.json["current_story"]``;
    the returned ``story_id`` is always the synthetic ``phase:<key>`` (with
    ``phase_key`` set, ``rail`` ``None``) or ``unattributed:<subagent_type>``
    (when no phase key is derivable) — never an individual story id.

    For every other role, behaviour is unchanged from the pre-INFRA-258
    ``_derive_story_id``: prompt story-id regex, then
    ``state.json["current_story"]``, then ``None`` (the caller applies the
    ``unattributed:<role>`` fallback). Never raises.
    """
    if subagent_type in CHECKPOINT_ROLES:
        phase_key = _derive_phase_key(tool_input)
        if phase_key:
            return f"phase:{phase_key}", phase_key, None
        return f"unattributed:{subagent_type}", None, None

    story_id = _derive_story_id(tool_input, state)
    rail = story_id.split("-", 1)[0] if story_id and "-" in story_id else None
    return story_id, None, rail


# ---------------------------------------------------------------------------
# Async spawn reconciliation (INFRA-258)
# ---------------------------------------------------------------------------


def default_spawn_output_roots() -> "tuple[Path, ...]":
    """Return the containment roots used by :func:`_contained_spawn_output`
    when no explicit ``tasks_root`` is supplied (CER-089).

    Always includes the resolved ``tempfile.gettempdir()``. Also includes a
    resolved ``$TMPDIR`` when set and distinct from the first root — some
    environments point ``TMPDIR`` at a different location than the Python
    default. Never raises.
    """
    roots: "list[Path]" = []
    try:
        roots.append(Path(tempfile.gettempdir()).resolve())
    except Exception:
        pass

    tmpdir_env = os.environ.get("TMPDIR")
    if tmpdir_env:
        try:
            candidate = Path(tmpdir_env).resolve()
            if candidate not in roots:
                roots.append(candidate)
        except Exception:
            pass

    return tuple(roots)


def _contained_spawn_output(
    output_file: "str | Path | None", tasks_root: "Path | str | None" = None
) -> "Path | None":
    """Return a resolved, contained spawn-output ``Path``, or ``None`` when
    *output_file* is not an acceptable spawn-output location (CER-089).

    Pure: never raises, never opens the file, performs no writes. Only
    ``Path.resolve()`` (which stats the filesystem to follow symlinks) and
    ``Path.is_file()`` are used.

    Default rule (``tasks_root=None``): the resolved path must (1) be
    contained under one of :func:`default_spawn_output_roots`, (2) have the
    literal component ``"tasks"`` (:data:`SPAWN_TASKS_DIR_NAME`) somewhere in
    its ``.parts``, and (3) be an existing file. Explicit ``tasks_root``
    (used by tests, and available to callers that know the real root):
    the resolved path must be ``.relative_to()`` the resolved *tasks_root*
    and be an existing file — the temp-root and ``tasks``-component rules do
    not apply in this mode.

    Design note — deliberately looser than the observed live shape. The
    observed shape is
    `/tmp/claude-<uid>/<project-slug>/<session-id>/tasks/<hash>.output`
    (effort.db rows 357-362, 2026-07-25), but this guard checks only *temp
    root + a `tasks` path component*, not the full `claude-<uid>/<slug>/
    <session>` shape. Pinning the fuller shape would make every
    ``output_file`` uncontained the moment the harness changes its directory
    layout — silently stopping all reconciliation, rows pending forever,
    exactly the CER-091 failure class this phase closes. The looser rule
    still blocks what CER-089 is about: a persisted path pointing at
    `/etc/passwd`, a repository file, or `~/.ssh/*`.
    """
    if output_file is None:
        return None

    try:
        candidate = output_file if isinstance(output_file, Path) else Path(str(output_file))
        resolved = candidate.resolve()

        if tasks_root is not None:
            root = Path(tasks_root).resolve()
            resolved.relative_to(root)
            if not resolved.is_file():
                return None
            return resolved

        roots = default_spawn_output_roots()
        if not any(_is_relative_to(resolved, root) for root in roots):
            return None
        if SPAWN_TASKS_DIR_NAME not in resolved.parts:
            return None
        if not resolved.is_file():
            return None
        return resolved
    except Exception:
        return None


def _is_relative_to(path: Path, root: Path) -> bool:
    """``Path.is_relative_to`` back-port (Python 3.9+ has it natively, but
    guard against older stdlib behaviour differences by implementing it
    directly). Never raises — any failure is treated as "not relative"."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _stream_spawn_output(path: Path) -> dict:
    """Stream a spawn output JSONL file once, returning the raw structured
    data both :func:`read_completed_spawn` and :func:`classify_pending_reason`
    need (CER-091 defect 3).

    A single shared reader means the two callers can never diverge on *how*
    a file is read — a second, independently-written reader is exactly how
    ``read_completed_spawn``'s six-way ``None`` became unattributable in the
    first place.

    Streams with a plain ``for line in fh:`` loop — never ``read_text()``/
    ``readlines()`` — and stops (setting ``line_cap_exceeded``) past
    :data:`RECONCILE_MAX_LINES` lines. Never raises; a missing path or any
    read error yields the all-default shape with ``exists`` reflecting
    reality where determinable.
    """
    result: dict = {
        "exists": False,
        "line_cap_exceeded": False,
        "any_parsed": False,
        "assistant_entries": [],
        "last_entry": None,
        "first_ts": None,
        "last_ts": None,
    }
    try:
        if not path.exists():
            return result
        result["exists"] = True

        line_count = 0
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line_count += 1
                if line_count > RECONCILE_MAX_LINES:
                    result["line_cap_exceeded"] = True
                    return result
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue

                result["any_parsed"] = True
                result["last_entry"] = entry
                ts = entry.get("timestamp")
                if isinstance(ts, str) and ts:
                    if result["first_ts"] is None:
                        result["first_ts"] = ts
                    result["last_ts"] = ts

                if entry.get("type") == "assistant":
                    result["assistant_entries"].append(entry)
    except Exception:
        pass
    return result


def classify_pending_reason(row: dict) -> str:
    """Return the single reason a ``pending_reconcilable`` row has not
    reconciled (CER-091 defect 3).

    Pure — no writes, no db access, takes an already-fetched row dict.
    Never raises. Returns one of :data:`PENDING_REASONS`. Reuses
    :func:`_stream_spawn_output` so this classifier and
    :func:`read_completed_spawn` can never read the same file two different
    ways.
    """
    try:
        output_file = row.get("output_file") if isinstance(row, dict) else None
        if not output_file:
            return "no-output-file"

        path = output_file if isinstance(output_file, Path) else Path(str(output_file))
        data = _stream_spawn_output(path)

        if not data["exists"]:
            return "file-missing"
        if data["line_cap_exceeded"]:
            return "line-cap"
        if not data["any_parsed"]:
            return "file-empty"

        last_entry = data["last_entry"]
        if not isinstance(last_entry, dict) or last_entry.get("type") != "assistant":
            return "not-terminated"

        message = last_entry.get("message")
        if not isinstance(message, dict):
            return "not-terminated"

        stop_reason = message.get("stop_reason")
        if stop_reason and stop_reason != "end_turn":
            return "in-flight"
        if stop_reason != "end_turn":
            # Falsy/absent stop_reason on an otherwise-assistant last entry —
            # a mid-stream snapshot rather than a genuine terminator.
            return "not-terminated"

        usage = _sum_deduped_usage(data["assistant_entries"])
        if usage.get("tokens_total") is None:
            return "no-usage"

        final_text = _flatten_tool_response(message)
        outcome, _ = parse_worker_outcome(final_text)
        if outcome is None:
            return "no-outcome"

        return "reconcilable"
    except Exception:
        return "file-empty"


def read_completed_spawn(
    output_file: "str | Path | None",
    *,
    tasks_root: "Path | str | None" = None,
) -> "dict | None":
    """Read a spawned agent's own JSONL output file (INFRA-258).

    Returns ``None`` when the spawn is not yet complete, the file is
    unreadable/missing/empty, no usage data is found, or *output_file* is not
    a contained spawn-output path (CER-089 — see below). Otherwise returns a
    dict with ``tokens_in``, ``tokens_out``, ``tokens_total``,
    ``cache_read_tokens``, ``cache_write_tokens``, ``duration_ms``,
    ``model``, ``outcome``, ``fail_cause``, ``final_text``.

    Completion detection: the **last parseable** JSONL entry must be
    ``type == "assistant"`` with ``message.stop_reason == "end_turn"``. An
    entry with ``stop_reason == "tool_use"``, a truncated/unparseable
    trailing line with no earlier ``end_turn`` terminator, an empty file, or
    a nonexistent path all yield ``None`` — an in-flight agent is never
    reconciled.

    CER-089 containment: before anything is opened, *output_file* is routed
    through :func:`_contained_spawn_output` (default rule when *tasks_root*
    is ``None``: temp-root-contained with a ``tasks`` path component; strict
    ``tasks_root`` containment otherwise). A rejected path returns ``None``
    immediately — no ``open()`` call is ever made on it. The failure mode
    this creates: an ``output_file`` value that fails containment leaves its
    ``effort.db`` row pending forever (the same shape as an evicted `/tmp`
    file) — a future reader debugging a stuck row should look here.

    Public signature (besides the new keyword-only ``tasks_root``) and
    return shape unchanged from pre-CER-091 (other callers and INFRA-258's
    own tests depend on both); internally this now delegates its file walk
    to :func:`_stream_spawn_output`, the same reader
    :func:`classify_pending_reason` uses (CER-091 defect 3). Never raises.
    """
    try:
        path = _contained_spawn_output(output_file, tasks_root=tasks_root)
        if path is None:
            return None

        data = _stream_spawn_output(path)
        if not data["exists"] or data["line_cap_exceeded"]:
            return None

        last_entry = data["last_entry"]
        if last_entry is None or last_entry.get("type") != "assistant":
            return None

        last_message = last_entry.get("message")
        if not isinstance(last_message, dict):
            return None
        if last_message.get("stop_reason") != "end_turn":
            return None

        usage = _sum_deduped_usage(data["assistant_entries"])
        if usage.get("tokens_total") is None:
            # No usage data anywhere in the file — not reconcilable.
            return None

        first_ts = data["first_ts"]
        last_ts = data["last_ts"]
        duration_ms: "int | None" = None
        if first_ts and last_ts:
            try:
                t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                duration_ms = int((t1 - t0).total_seconds() * 1000)
            except Exception:
                duration_ms = None

        final_text = _flatten_tool_response(last_message)
        outcome, fail_cause = parse_worker_outcome(final_text)

        return {
            "tokens_in": usage.get("tokens_in"),
            "tokens_out": usage.get("tokens_out"),
            "tokens_total": usage.get("tokens_total"),
            "cache_read_tokens": usage.get("cache_read_tokens"),
            "cache_write_tokens": usage.get("cache_write_tokens"),
            "duration_ms": duration_ms,
            "model": usage.get("model"),
            "outcome": outcome,
            "fail_cause": fail_cause,
            "final_text": final_text,
        }
    except Exception:
        return None


def _extract_spawn_ref(tool_response: Any) -> "tuple[str | None, str | None]":
    """Extract ``(agent_id, output_file)`` from a Task/Agent ``tool_response``
    (INFRA-258).

    Tries the structured dict shapes first — ``outputFile``/``output_file``
    and ``agentId``/``agent_id`` keys, at the top level or nested under a
    ``toolUseResult`` key — then falls back to regexes over
    ``_flatten_tool_response(tool_response)`` for ``output_file:\\s*(\\S+)``
    and ``agentId:\\s*(\\S+)``. A missing/unrecognised shape returns
    ``(None, None)``. Never raises.
    """
    agent_id: "str | None" = None
    output_file: "str | None" = None
    try:
        candidates: "list[dict]" = []
        if isinstance(tool_response, dict):
            candidates.append(tool_response)
            nested = tool_response.get("toolUseResult")
            if isinstance(nested, dict):
                candidates.append(nested)

        for candidate in candidates:
            if output_file is None:
                value = candidate.get("outputFile") or candidate.get("output_file")
                if value:
                    output_file = str(value)
            if agent_id is None:
                value = candidate.get("agentId") or candidate.get("agent_id")
                if value:
                    agent_id = str(value)

        if output_file is None or agent_id is None:
            text = _flatten_tool_response(tool_response)
            if output_file is None:
                m = re.search(r"output_file:\s*(\S+)", text)
                if m:
                    output_file = m.group(1)
            if agent_id is None:
                m = re.search(r"agentId:\s*(\S+)", text)
                if m:
                    agent_id = m.group(1)
    except Exception:
        pass

    return agent_id, output_file


def _story_accepts_late_bump(project_dir: "Path | str", story_id: str) -> bool:
    """Gate a *reconciliation-time* FAIL bump of the attempt counter
    (CER-091 defect 4).

    Returns ``False`` (bump must be skipped) when **either**:

    1. the story's own file ``docs/stories/<RAIL>/<story_id>.md`` is
       readable and its frontmatter ``status:`` line is one of
       :data:`_LATE_BUMP_BLOCKED_STATUSES`; or
    2. ``.companion/attempt_counter.json`` does not already record this
       ``story_id`` **and** ``.companion/state.json`` does not show it as
       currently being built — the build loop is not currently building it,
       so a bump would *create* a counter file for a story nobody is working
       on. Liveness is resolved against the story-keyed ``current_stories``
       record (INFRA-281's authority) when present; the flat
       ``current_story`` key is a fallback for pre-INFRA-281 state files
       only. With two builders in flight the flat mirror names only one of
       them, so keying the check on it would refuse the *other* story's
       first late FAIL bump and stall its escalation ladder at attempt 1
       (INFRA-282, CER-095.3).

    Returns ``True`` otherwise. Pure read (no writes on any path); never
    raises — an unreadable story file or state file falls through to rule 2
    rather than propagating.

    The synchronous PostToolUse-time bump in
    :func:`record_attempt_from_transcript` is deliberately **not** gated by
    this helper: the story was just spawned for, so it is active by
    construction, and gating it would risk silently dropping a real first
    FAIL. Only the reconciliation-time bump — arbitrarily later, possibly
    post-merge, possibly post-``/clear`` — needs the guard.
    """
    try:
        project_path = (
            project_dir if isinstance(project_dir, Path) else Path(project_dir)
        )

        rail = story_id.split("-", 1)[0] if story_id and "-" in story_id else None
        if rail:
            try:
                story_path = project_path / "docs" / "stories" / rail / f"{story_id}.md"
                if story_path.exists():
                    text = story_path.read_text(encoding="utf-8")
                    m = _STATUS_LINE_RE.search(text)
                    if m and m.group(1).strip().lower() in _LATE_BUMP_BLOCKED_STATUSES:
                        return False
            except Exception:
                pass

        counter_recorded = False
        try:
            counter_recorded = read_attempt_count(story_id, project_path) > 0
        except Exception:
            counter_recorded = False

        is_current = False
        try:
            state = _read_state(project_path)
            if isinstance(state, dict):
                current_stories = state.get("current_stories")
                if isinstance(current_stories, dict):
                    is_current = story_id in current_stories
                else:
                    current = state.get("current_story")
                    if isinstance(current, dict) and current.get("id") == story_id:
                        is_current = True
        except Exception:
            pass

        if not counter_recorded and not is_current:
            return False

        return True
    except Exception:
        return False


def log_recording_event(project_dir: "Path | str", **fields: Any) -> None:
    """Append one diagnostic JSON line to ``.companion/effort_recording.log``
    (CER-091 defect 1/3).

    Carries at least ``ts`` (added here, UTC ISO-8601) plus whatever
    *fields* the caller supplies — conventionally ``tool_name``,
    ``subagent_type``, ``tool_use_id``, ``story_id``, ``decision``, and
    ``row_id`` (see :data:`RECORDING_DECISIONS`). Plain append
    (``open(path, "a")``) — this is an append-only diagnostic log, not
    state, so the atomic-replace machinery in ``state_utils`` is neither
    needed nor appropriate.

    Bounded: when the file exceeds :data:`RECORDING_LOG_MAX_BYTES` it is
    truncated and restarted with a single ``{"decision": "log-truncated"}``
    line before the new entry is appended. Never raises — this is a
    hook-path diagnostic; a logging failure must never surface as a
    recording failure. Not gated on ``effort_tracking``: the log's entire
    purpose is explaining why recording did or did not happen, including
    when tracking itself is off.
    """
    try:
        project_path = (
            project_dir if isinstance(project_dir, Path) else Path(project_dir)
        )
        log_path = project_path / ".companion" / "effort_recording.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if log_path.exists() and log_path.stat().st_size > RECORDING_LOG_MAX_BYTES:
                log_path.write_text(
                    json.dumps({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "decision": "log-truncated",
                    }) + "\n",
                    encoding="utf-8",
                )
        except Exception:
            pass

        entry: dict = {"ts": datetime.now(timezone.utc).isoformat()}
        entry.update(fields)
        line = json.dumps(entry, default=str) + "\n"

        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass


def reconcile_pending_attempts(
    *,
    project_dir: "Path | str",
    limit: int = RECONCILE_MAX_ROWS,
    home: "Path | None" = None,
    include_quiescent: bool = False,
    max_age_days: "int | None" = None,
    tasks_root: "Path | str | None" = None,
) -> int:
    """Sweep pending (``tokens_total IS NULL OR outcome IS NULL``) rows and
    reconcile the completed ones (INFRA-258, CER-091).

    Reads ``.companion/state.json``; returns ``0`` immediately unless
    ``effort_tracking`` is ``true``. Fetches at most *limit* pending rows via
    ``effort_db.pending_reconcilable``, calls ``read_completed_spawn`` on
    each, and writes the completed ones back via ``effort_db.reconcile_attempt``.

    *max_age_days* (CER-088): ``None`` (the default) means "use
    :data:`RECONCILE_MAX_AGE_DAYS`" — the sweep is always bounded; an
    explicitly-passed value overrides it. This is deliberately unlike
    ``effort_db.pending_reconcilable``'s own default (off) — that shared
    query is also used by diagnostics (e.g. INFRA-264's pending-row
    diagnostic) that must keep seeing permanently-pending rows, since
    surfacing them is their entire purpose. Only this sweep, which cannot
    act on a permanently-pending row anyway, opts into the bound.

    *tasks_root* (CER-089) is forwarded to every :func:`read_completed_spawn`
    call this sweep makes. Its default (``None``) means "use the default
    allow-rule" — production behaviour is unchanged except that an
    uncontained ``output_file`` is now skipped (left pending) instead of
    opened.

    A ``read_completed_spawn`` result whose ``outcome`` is ``None`` is
    skipped for the fully-terminated path — no ``reconcile_attempt`` call,
    the row stays pending (CER-091 defect 2/4). With :data:`RECOGNISED_REVIEW_VERDICTS`
    including ``ALIGNED``, the common case that used to hit this branch no
    longer does; the branch still exists so a genuinely unparseable return
    leaves a *pending* row rather than committing a *partial* one.

    On a successful (non-quiescent) reconciliation whose resolved
    ``outcome`` is ``FAIL`` and whose ``story_id`` is a real story id (no
    ``:`` — never a ``phase:`` or ``unattributed:`` synthetic),
    :func:`_story_accepts_late_bump` gates whether
    ``flex_build.bump_attempt_count`` is called (CER-091 defect 4) — the
    escalation ladder's late-bump path for a FAIL outcome that only became
    knowable after PostToolUse time.

    When *include_quiescent* is ``True`` (never the default for either hook
    call site — see Instructions 8), a row whose :func:`classify_pending_reason`
    is not ``reconcilable``/``in-flight``/``file-missing``/``no-output-file``,
    whose row ``ts`` is older than :data:`QUIESCENT_AGE_SECONDS`, **and**
    whose output file's own mtime is older than the same threshold, is
    retired with ``outcome="UNKNOWN"`` (when no verdict is parseable) and a
    ``reconciled-quiescent: <reason>`` note. A quiescent reconciliation never
    calls ``bump_attempt_count`` — ``UNKNOWN`` is not ``FAIL``, and a
    fabricated escalation is worse than a missing one. A row with no usage
    data at all is still skipped even in the quiescent path (nothing
    truthful to write).

    Returns the count of rows actually reconciled. Never raises — this is a
    hook-path entry point (called from both ``record_attempt_from_transcript``
    and ``hooks/session_start.py``, and from the explicit sweep CLI).
    """
    try:
        project_path = (
            project_dir if isinstance(project_dir, Path) else Path(project_dir)
        )
        state = _read_state(project_path)
        if not state or not state.get("effort_tracking"):
            return 0

        resolved_max_age_days = (
            RECONCILE_MAX_AGE_DAYS if max_age_days is None else max_age_days
        )

        db_path = effort_db.resolve_effort_db_path(project_path)
        rows = effort_db.pending_reconcilable(
            db_path, limit, max_age_days=resolved_max_age_days
        )

        reconciled = 0
        for row in rows:
            output_file = row.get("output_file")
            if not output_file:
                continue

            path = output_file if isinstance(output_file, Path) else Path(str(output_file))
            result = read_completed_spawn(path, tasks_root=tasks_root)

            if result is not None and result.get("outcome") is not None:
                fields: "dict[str, Any]" = {
                    "tokens_total": result.get("tokens_total"),
                    "tokens_in": result.get("tokens_in"),
                    "tokens_out": result.get("tokens_out"),
                    "cache_read_tokens": result.get("cache_read_tokens"),
                    "cache_write_tokens": result.get("cache_write_tokens"),
                    "duration_ms": result.get("duration_ms"),
                    "outcome": result.get("outcome"),
                    "notes": result.get("fail_cause"),
                }
                if row.get("model") is None and result.get("model"):
                    fields["model"] = result.get("model")

                updated = effort_db.reconcile_attempt(db_path, row["id"], **fields)
                if not updated:
                    continue

                reconciled += 1

                if result.get("outcome") == "FAIL":
                    story_id = row.get("story_id")
                    if story_id and ":" not in str(story_id):
                        try:
                            if _story_accepts_late_bump(project_path, story_id):
                                bump_attempt_count(story_id, project_path)
                        except Exception:
                            pass

                continue

            # Either in-flight/unreadable (result is None) or complete-but-
            # no-outcome (CER-091 defect 2/4 shape) — never commit a partial
            # row on the default sweep.
            if not include_quiescent:
                continue

            reason = classify_pending_reason(row)
            if reason in ("reconcilable", "in-flight", "file-missing", "no-output-file"):
                continue

            row_ts = row.get("ts")
            if not _older_than_seconds(row_ts, QUIESCENT_AGE_SECONDS):
                continue

            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            now_epoch = datetime.now(timezone.utc).timestamp()
            if (now_epoch - mtime) < QUIESCENT_AGE_SECONDS:
                continue

            data = _stream_spawn_output(path)
            usage = _sum_deduped_usage(data["assistant_entries"])
            if usage.get("tokens_total") is None:
                # Nothing truthful to write — still skipped.
                continue

            outcome_val: "str | None" = None
            last_entry = data["last_entry"]
            if isinstance(last_entry, dict):
                message = last_entry.get("message")
                if isinstance(message, dict):
                    final_text = _flatten_tool_response(message)
                    outcome_val, _ = parse_worker_outcome(final_text)

            quiescent_fields: "dict[str, Any]" = {
                "tokens_total": usage.get("tokens_total"),
                "tokens_in": usage.get("tokens_in"),
                "tokens_out": usage.get("tokens_out"),
                "cache_read_tokens": usage.get("cache_read_tokens"),
                "cache_write_tokens": usage.get("cache_write_tokens"),
                "duration_ms": None,
                "outcome": outcome_val or "UNKNOWN",
                "notes": f"reconciled-quiescent: {reason}",
            }
            if row.get("model") is None and usage.get("model"):
                quiescent_fields["model"] = usage.get("model")

            updated = effort_db.reconcile_attempt(db_path, row["id"], **quiescent_fields)
            if updated:
                reconciled += 1
            # Never bump_attempt_count from the quiescent branch — UNKNOWN
            # is not FAIL, and a fabricated escalation is worse than a
            # missing one.

        return reconciled
    except Exception:
        return 0


def _older_than_seconds(ts: Any, seconds: float) -> bool:
    """Return ``True`` when ISO-8601 *ts* is more than *seconds* in the past.

    Never raises: an unparseable/missing *ts* returns ``False`` (never
    treated as old enough for the quiescent path — the conservative default).
    """
    if not isinstance(ts, str) or not ts:
        return False
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - parsed
        return age.total_seconds() > seconds
    except Exception:
        return False


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
    tool_name: "str | None" = None,
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
      lives in a separate output file) — the row is then completed later by
      ``reconcile_pending_attempts`` (INFRA-258) rather than left permanently
      null.

    INFRA-258: also persists the spawn's own ``agent_id``/``output_file``
    (extracted from ``tool_response``) via ``effort_db.set_spawn_ref``, and
    sweeps up to :data:`RECONCILE_MAX_ROWS` previously-pending rows via
    ``reconcile_pending_attempts`` before writing the new row.

    CER-091 defect 1: calls :func:`log_recording_event` exactly once on
    every return path (including the outer ``except``), so the *next*
    silent-recording occurrence is attributable from one ``tail`` instead of
    an archaeology session. Not gated on ``effort_tracking`` — the log
    explains why recording did or did not happen, including when tracking
    is off. *tool_name* (optional, defaults ``None``) is carried through
    only for that log line; it does not affect recording behaviour.
    """
    project_path = Path(project_dir) if not isinstance(project_dir, Path) else project_dir
    subagent_type: Any = None
    story_id: "str | None" = None
    try:
        if not isinstance(tool_input, dict):
            log_recording_event(
                project_path, tool_name=tool_name, subagent_type=None,
                tool_use_id=tool_use_id, story_id=None,
                decision="skip:no-tool-input", row_id=None,
            )
            return None
        subagent_type = tool_input.get("subagent_type")
        if subagent_type not in RECORDABLE_SUBAGENT_ROLES:
            log_recording_event(
                project_path, tool_name=tool_name, subagent_type=subagent_type,
                tool_use_id=tool_use_id, story_id=None,
                decision="skip:not-recordable-role", row_id=None,
            )
            return None

        state = _read_state(project_path)

        story_id, phase_key, rail = _derive_attribution(tool_input, state, subagent_type)
        outcome, fail_cause = parse_worker_outcome(tool_response)

        # INFRA-237: attempt-counter bump runs unconditionally on FAIL — it
        # is core build-loop control state next_action.py depends on, not
        # observability, so it must not be gated on effort_tracking. Kept
        # best-effort/non-raising like every other branch in this function.
        # INFRA-258: never bump on a synthetic phase:/unattributed: id — the
        # escalation ladder tracks real stories only (Ensures 21).
        # CER-091 defect 4: this PostToolUse-time bump is deliberately
        # ungated by _story_accepts_late_bump — see that helper's docstring.
        if story_id and outcome == "FAIL" and ":" not in story_id:
            try:
                bump_attempt_count(story_id, project_path)
            except Exception:
                pass

        if not state or not state.get("effort_tracking"):
            log_recording_event(
                project_path, tool_name=tool_name, subagent_type=subagent_type,
                tool_use_id=tool_use_id, story_id=story_id,
                decision="skip:no-state" if not state else "skip:effort-tracking-off",
                row_id=None,
            )
            return None

        # INFRA-258: sweep previously-pending (async, now-completed) rows
        # before writing this new spawn's row. Runs after the
        # effort_tracking early return so a project with tracking disabled
        # does zero additional db work. Its own try/except so a sweep
        # failure never prevents the new row from being written.
        try:
            reconcile_pending_attempts(project_dir=project_path, home=home)
        except Exception:
            pass

        # Hoist the effective story id actually being recorded so the
        # attempt-number derivation and the row use the identical value
        # (INFRA-257).
        effective_story_id = story_id or f"unattributed:{subagent_type}"

        transcript_path = _derive_transcript_path(project_path, session_id, home)
        usage = extract_subagent_usage(transcript_path, tool_use_id)

        model = tool_input.get("model") or usage.get("model")

        # INFRA-257: derive the lifetime spawn ordinal for this
        # (story_id, agent_role) pair from effort.db's own row history
        # rather than .companion/attempt_counter.json (which counts
        # failures and is cleared on merge — see docs/architecture.md
        # § Effort tracking). Best-effort: a derivation failure degrades to
        # 1 rather than losing the row. Single COUNT(*) query, no
        # transaction spanning this read and the recorder's write — the
        # era's serial (no-nested-spawning) build loop makes the resulting
        # race a non-issue for best-effort observability.
        try:
            attempt_number = effort_db.next_attempt_number(
                effort_db.resolve_effort_db_path(project_path),
                effective_story_id,
                str(subagent_type),
            )
        except Exception:
            attempt_number = 1

        row_id = record_effort(
            project_dir=project_path,
            story_id=effective_story_id,
            agent_role=str(subagent_type),
            model=model,
            usage={
                "input_tokens": usage.get("tokens_in"),
                "output_tokens": usage.get("tokens_out"),
                "cache_read_input_tokens": usage.get("cache_read_tokens"),
                "cache_creation_input_tokens": usage.get("cache_write_tokens"),
            },
            attempt_number=attempt_number,
            duration_ms=usage.get("duration_ms"),
            outcome=outcome,
            notes=fail_cause,
            phase=phase_key,
            rail=rail,
        )

        # INFRA-258: persist the spawn ref so a later reconciliation pass
        # (this function's own next call, or hooks/session_start.py) can
        # find and complete this row from its own output_file. Best-effort —
        # a missing/unrecognised tool_response shape leaves both columns
        # NULL and is not an error.
        if row_id is not None:
            try:
                agent_id, output_file = _extract_spawn_ref(tool_response)
                if output_file:
                    effort_db.set_spawn_ref(
                        effort_db.resolve_effort_db_path(project_path),
                        row_id,
                        agent_id,
                        output_file,
                    )
            except Exception:
                pass

        log_recording_event(
            project_path, tool_name=tool_name, subagent_type=subagent_type,
            tool_use_id=tool_use_id, story_id=effective_story_id,
            decision="recorded", row_id=row_id,
        )
        return row_id
    except Exception as exc:
        try:
            log_recording_event(
                project_path, tool_name=tool_name, subagent_type=subagent_type,
                tool_use_id=tool_use_id, story_id=story_id,
                decision=f"error:{type(exc).__name__}", row_id=None,
            )
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# CLI entry point (CER-091 defect 4/trigger-coverage — Instructions 11)
# ---------------------------------------------------------------------------


def _cli_main(argv: "list[str] | None" = None) -> int:
    """CLI entry point; returns the exit code.

    A thin ``argparse`` shell (stdlib-only — this module is imported by
    hooks and must not gain a ``click`` dependency) over the single
    ``reconcile`` subcommand, which is itself a thin call into
    :func:`reconcile_pending_attempts` — the same function both hook call
    sites use. No second reconciliation implementation exists in this tree.
    Behind ``if __name__ == "__main__":`` so importing this module (the
    hook's import path) has no side effects.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="subagent_transcript CLI — explicit effort.db reconciliation sweep (CER-091)"
    )
    subparsers = parser.add_subparsers(dest="command")

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Sweep pending effort.db rows and reconcile the completed ones.",
    )
    reconcile_parser.add_argument(
        "--project-dir", default=".", help="Project root directory (default: current directory)."
    )
    reconcile_parser.add_argument(
        "--limit", type=int, default=RECONCILE_MAX_ROWS,
        help=f"Maximum rows to sweep (default: {RECONCILE_MAX_ROWS}).",
    )
    reconcile_parser.add_argument(
        "--include-quiescent", action="store_true",
        help="Also retire quiescent rows (see reconcile_pending_attempts docstring).",
    )
    reconcile_parser.add_argument(
        "--json", dest="as_json", action="store_true", help="Emit JSON instead of plain text."
    )

    args = parser.parse_args(argv)

    if args.command == "reconcile":
        count = reconcile_pending_attempts(
            project_dir=args.project_dir,
            limit=args.limit,
            include_quiescent=args.include_quiescent,
        )
        if args.as_json:
            print(json.dumps({"reconciled": count}))
        else:
            print(f"reconciled {count} row(s)")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(_cli_main())

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
    from skills.pairmode.scripts.effort_recorder import record_effort, record_effort_ex
    from skills.pairmode.scripts.flex_build import bump_attempt_count, read_attempt_count
except ImportError:
    from context_budget import _derive_transcript_path  # type: ignore[no-redef]  # flat import via hook sys.path
    import effort_db  # type: ignore[no-redef]  # flat import via hook sys.path
    from effort_recorder import record_effort, record_effort_ex  # type: ignore[no-redef]  # flat import via hook sys.path
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
#:
#: CER-105 (INFRA-299): the consequence — `attempts.phase` is populated only
#: for these roles and is NULL on every story row — is documented, and
#: deliberately not changed, in `docs/architecture.md` § Effort tracking.
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

# INFRA-289 (CER-103(b)): the bare-mention pattern above matches the word
# after "Phase" in ordinary prose, not just a real phase key — observed live:
# flex row 416 recorded `story_id = "phase:key"` (from "...Phase key: see the
# phase doc...") and meander rows 233-236 recorded `story_id =
# "phase:checkpoint"` (from "...Phase checkpoint step 3..."). Neither is a
# phase; both are synthetic ids invisible to `query_by_phase` and to no
# per-story rollup's exclusion. This shape gate closes that: a whole
# candidate must be either all-digits, or an alphanumeric run ending in a
# digit, optionally followed by a `-main` / `-ante<N>` / `-post<N>` suffix.
# An all-alphabetic word (`key`, `checkpoint`, `doc`, `docs`, `report`, ...)
# never ends in a digit, so it can never match.
_PHASE_KEY_STRICT_RE = re.compile(r"^[A-Za-z0-9]*\d(?:-main|-ante\d+|-post\d+)?$")

#: Bounds on the reconciliation sweep (Instructions 12a / Ensures 15) — a
#: hook-path invocation must never scan unbounded work.
RECONCILE_MAX_ROWS = 5
RECONCILE_MAX_LINES = 20000

#: CER-096, item D3: the sweep also fetches this many rows from the
#: *oldest* end (``order="oldest"``) on every invocation, so the oldest
#: legitimately-pending rows are reached even while ``RECONCILE_MAX_ROWS``
#: newest-first rows are re-examined every sweep. Kept small — this is a
#: hook-path bound, not a general query — because the newest-first fetch is
#: already the common, high-value case; the oldest-first fetch exists only
#: to stop the tail from starving, not to compete with it for budget.
RECONCILE_OLDEST_ROWS: int = 2

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
#:
#: INFRA-298 (CER-114): the quiescence sweep (`reconcile_pending_attempts`'
#: `include_quiescent` branch) is a BACKSTOP, not the primary completion
#: path. `reconcile_one` — driven by the `SubagentStop` hook, which fires
#: deterministically the moment a spawn actually finishes — is primary. The
#: backstop still exists, unchanged, for the cases `SubagentStop` cannot
#: cover: a crashed or timed-out `hooks/subagent_stop.py`, a project that
#: installs pairmode without the plugin's `hooks.json` (no `SubagentStop`
#: registration at all), or a `tmp` output file evicted before either path
#: reaches it. This value and this age-doubling rule are unchanged by that
#: story — see its Ensures A5/D2.
QUIESCENT_AGE_SECONDS = 900

#: CER-091 defect 1: recognised `decision` values for `log_recording_event`.
#: Not exhaustive — `error:<ExceptionClassName>` is dynamic — but every
#: static decision this module emits is listed here so tests can enumerate
#: the set.
RECORDING_DECISIONS: frozenset[str] = frozenset({
    "recorded",
    # INFRA-288 (CER-104): the write matched a live pending row via the
    # agent_id idempotency key and updated it instead of inserting — the
    # observable trace of a doubled hook invocation.
    "recorded:deduped",
    "skip:not-recordable-role",
    "skip:no-tool-input",
    "skip:no-state",
    "skip:effort-tracking-off",
    "observed:non-spawn-tool",
    "log-truncated",
    # INFRA-289 (CER-103(a)): a prompt named a target project that failed
    # A3's registered_projects admission test. Recording never stops on
    # this — the row still gets written against the session project — this
    # line is the alarm that a fleet-campaign target was silently refused.
    "skip:target-unregistered",
    # INFRA-289 (CER-102): the reconciliation-time FAIL bump's own trace —
    # see reconcile_pending_attempts.
    "bump:late-fail",
    "skip:late-bump-blocked",
    # INFRA-298 (CER-114): reconcile_one's own decision set — the
    # SubagentStop relay's single-row reconcile, distinct from every
    # decision above so a `tail` of effort_recording.log tells the two
    # completion paths apart without reading code (Ensures C4).
    #
    # The payload carried a usable outcome (parse_worker_outcome on
    # last_assistant_message) and reconcile_attempt committed both tokens
    # (from the payload's own agent_transcript_path) and outcome together.
    "reconciled:payload",
    # The payload carried no usable outcome; read_completed_spawn on the
    # row's stored output_file supplied both tokens and outcome instead.
    "reconciled:file-fallback",
    # The SubagentStop payload carried no agent_id at all — nothing to key
    # a reconcile on.
    "skip:no-agent-id",
    # agent_id was present but no live pending row (tokens_total IS NULL OR
    # outcome IS NULL) carries it — already reconciled by a PostToolUse
    # sweep, the spawn was never recorded, or a doubled SubagentStop firing
    # (idempotency: the second call is this decision, not a second write).
    "skip:no-pending-row",
    # Neither the payload's last_assistant_message nor (on fallback) the
    # row's output_file yielded a parseable BUILD-RESULT/REVIEW-RESULT
    # verdict — the row stays pending for a later sweep.
    "skip:no-outcome",
    # An outcome resolved but no usage/token data was found in the source
    # consulted (agent_transcript_path on the payload path, output_file on
    # the fallback path) — _ATOMIC_RECONCILE_FIELDS forbids writing tokens
    # alone, so nothing is committed.
    "skip:no-usage",
    # CER-113 (INFRA-299): a worker returned a syntactically valid
    # BUILD-RESULT/REVIEW-RESULT JSON object whose verdict word is outside
    # the WORKER-004 enum (RECOGNISED_BUILD_OUTCOMES /
    # RECOGNISED_REVIEW_VERDICTS) — e.g. "SUCCESS", "PARTIAL", lowercase
    # "pass". That is a worker-contract violation, not a transport failure:
    # the return was found and parsed fine, it just did not speak the
    # grammar. The verdict is refused (the row stays pending rather than
    # committing a word no reader recognises) and this line names the
    # refused value(s) under `rejected_outcomes`. Emitted IN ADDITION TO —
    # never instead of — the call site's own row-write decision.
    "skip:non-enum-outcome",
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
    # INFRA-287 (CER-101): a non-empty output_file that _contained_spawn_output
    # rejects. Distinct from file-missing — a row stuck because of a
    # containment rule and a row stuck because /tmp was evicted are different
    # operational problems and must not print the same word. Ordered here
    # because is_reconcilable_spawn_output evaluates it second.
    "uncontained",
    "file-missing",
    "file-empty",
    "in-flight",
    "not-terminated",
    "no-usage",
    "line-cap",
    "no-outcome",
    "reconcilable",
)

#: INFRA-287 (CER-101): the success sentinel `is_reconcilable_spawn_output`
#: returns when a spawn's output file is contained AND terminated. Deliberately
#: NOT a member of PENDING_REASONS — it is the absence of a pending reason.
SPAWN_TERMINATED: str = "terminated"

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

# CER-113 (INFRA-299): mirrors worker_result.py's `_SCHEMAS[BUILD_RESULT]`
# "outcome" enum ({"PASS", "FAIL"}) — the source of truth for which BUILD
# verdicts are recognised. Not imported directly, for the same reason as its
# REVIEW sibling above: this module is on the hook path and must stay
# import-light (worker_result.py pulls in the broader WORKER-004 grammar
# machinery this module has no other need for). The copy is legitimate only
# because it is pinned to its source by an import-identity test — see
# tests/pairmode/test_worker_result.py's TestSubagentTranscriptEnumMirror,
# which fails the suite if either enum is edited in worker_result.py without
# this mirror following.
#
# The gap this closes: the JSON BUILD-RESULT branch below used to write
# `obj.get("outcome")` through unvalidated, so a worker returning
# `{"outcome": "SUCCESS"}` — or "PARTIAL", or lowercase "pass" — had that
# string committed verbatim into `attempts.outcome`, where every downstream
# reader (checkpoint-report's rollup, the escalation ladder's
# `outcome == "FAIL"` test, the SPA's waypoint timeline) silently mis-buckets
# it. INFRA-299's fleet audit found 3 such rows across 7 projects.
RECOGNISED_BUILD_OUTCOMES: frozenset[str] = frozenset({"PASS", "FAIL"})


# INFRA-293 (E6b / CER-101 downstream): 0.2-era workers emitted a plain-text
# result grammar (``BUILD-RESULT: DONE``, ``REVIEW-RESULT: PASS``) instead of
# the WORKER-004 JSON grammar the loop above reads. A stranded consumer row
# is unreconcilable until this pattern is recognised. Anchored as a whole
# line (leading/trailing whitespace tolerated, arbitrary trailing prose is
# not) so a quoted example inside a worker's own instructions/transcript —
# e.g. an agent body literally containing the string "BUILD-RESULT: DONE" as
# documentation — is not misread as a real verdict.
_LEGACY_RESULT_LINE_RE = re.compile(
    r"^[ \t]*(BUILD-RESULT|REVIEW-RESULT):[ \t]*([A-Z-]+)[ \t]*$",
    re.MULTILINE,
)

# The 0.2-era builder had no plain-text FAIL form: a stuck builder emitted
# the prose "BUILDER STUCK — ..." instead, which produces no
# "BUILD-RESULT: <verdict>" line at all. DONE is therefore unambiguously the
# 0.2 success token, and normalizing it to worker_result.py's BUILD enum
# member "PASS" loses nothing. DONE cannot be stored verbatim because
# worker_result.py's `_SCHEMAS[BUILD_RESULT]["enums"]["outcome"]` is exactly
# {"PASS", "FAIL"} — there is no "DONE" member. A verdict token absent from
# this mapping (anything else) yields no outcome rather than being written
# through unvalidated.
_LEGACY_BUILD_VERDICTS: dict[str, str] = {
    "DONE": "PASS",
    "PASS": "PASS",
    "FAIL": "FAIL",
}


#: CER-113 (INFRA-299): cap on the length of a rejected verdict value as
#: recorded into the *rejected* out-list. The value comes from an untrusted
#: worker return and is only ever a diagnostic string, so a runaway value
#: must not be able to bloat `.companion/effort_recording.log`.
_REJECTED_OUTCOME_MAX_CHARS = 120


def parse_worker_outcome(
    tool_response: Any,
    *,
    rejected: "list[str] | None" = None,
) -> "tuple[str | None, str | None]":
    """Extract ``(outcome, fail_cause)`` from a completed Task/Agent's own
    returned result text.

    Reads the WORKER-004 BUILD-RESULT / REVIEW-RESULT JSON grammar
    (``worker_result.py``) directly out of the flattened tool_response text
    — no reliance on the orchestrator's own re-derivation of what the
    subagent reported. Falls back to the human-readable ``FAIL-CAUSE:``
    transcript line (``reviewer/procedure.md``) when no JSON ``fail_cause``
    field is present. Returns ``(None, None)`` when no recognisable result
    object is found. Never raises.

    Both JSON verdict fields are enum-gated: a ``BUILD-RESULT``'s ``outcome``
    against :data:`RECOGNISED_BUILD_OUTCOMES` (CER-113, INFRA-299) and a
    ``REVIEW-RESULT``'s ``verdict`` against
    :data:`RECOGNISED_REVIEW_VERDICTS` (CER-091). A refused verdict yields
    *no* outcome — the row is left pending, which the sweep can recover, in
    preference to committing a verdict word no reader recognises. Rejection
    is strict: no case-folding, no trimming, no fuzzy rescue; the plain-text
    0.2-era grammar below is a separate, deliberately distinct vocabulary.
    ``fail_cause`` extraction is *not* gated — a worker whose verdict word is
    unrecognised has still told us why it failed, and discarding that would
    be a second data loss on top of the first.

    *rejected* (keyword-only, CER-113) is an optional out-list: when supplied,
    every JSON verdict value this parser refuses is appended to it as a
    string (non-strings coerced with ``str()``, truncated to
    :data:`_REJECTED_OUTCOME_MAX_CHARS`). It exists because this function
    cannot log for itself — it takes no ``project_dir``, and giving it one
    would turn a pure text parser into a filesystem writer on the hook path,
    crossing the thin-relay boundary. Do not "simplify" this by passing a
    path; the caller that holds a project directory does the logging (see
    :data:`RECORDING_DECISIONS`' ``skip:non-enum-outcome``). The return type
    is unchanged — Era 003's DP4 additive-until-flip contract forbids
    reshaping an existing function's return during the migration window, and
    three of the four call sites do not want a third value. With *rejected*
    left at ``None`` (every pre-existing caller), behaviour is identical to
    before.
    """
    def _note_rejected(value: Any) -> None:
        # Total by construction: never raises, never lets a hostile value
        # through unbounded, and is a no-op for the default caller.
        if rejected is None:
            return
        try:
            text_value = value if isinstance(value, str) else str(value)
            rejected.append(text_value[:_REJECTED_OUTCOME_MAX_CHARS])
        except Exception:
            pass

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
            # CER-113 (INFRA-299): membership-gated, structurally mirroring
            # the REVIEW branch below. `fail_cause` stays ungated on purpose.
            build_outcome = obj.get("outcome")
            if isinstance(build_outcome, str) and build_outcome in RECOGNISED_BUILD_OUTCOMES:
                outcome = build_outcome
            elif build_outcome is not None and build_outcome != "":
                _note_rejected(build_outcome)
            fail_cause = obj.get("fail_cause") or fail_cause
        elif rtype == "REVIEW-RESULT":
            verdict = obj.get("verdict")
            if isinstance(verdict, str) and verdict in RECOGNISED_REVIEW_VERDICTS:
                outcome = verdict
            elif verdict is not None and verdict != "":
                _note_rejected(verdict)
            fail_cause = obj.get("fail_cause") or fail_cause

    # INFRA-293: legacy 0.2-era plain-text grammar is a fallback only, run
    # strictly below the JSON grammar above (JSON wins on conflict) so a
    # transcript that quotes both never has the plain-text line override an
    # honest JSON result.
    if outcome is None:
        for legacy_match in _LEGACY_RESULT_LINE_RE.finditer(text):
            label, verdict = legacy_match.group(1), legacy_match.group(2)
            if label == "BUILD-RESULT":
                mapped = _LEGACY_BUILD_VERDICTS.get(verdict)
                if mapped is not None:
                    outcome = mapped
            elif label == "REVIEW-RESULT":
                if verdict in RECOGNISED_REVIEW_VERDICTS:
                    outcome = verdict
                else:
                    # CER-113: the only change to this INFRA-293 block — a
                    # refused verdict is reported to the out-list. The
                    # legacy BUILD vocabulary (_LEGACY_BUILD_VERDICTS, which
                    # accepts DONE) stays a deliberately distinct grammar
                    # from the JSON one and is untouched.
                    _note_rejected(verdict)

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


def _phase_doc_verified(project_dir: "Path | str | None", candidate: str) -> bool:
    """``True`` unless *project_dir* has a ``docs/phases/`` directory that
    does not contain a matching ``phase-<candidate>.md`` (INFRA-289, B2).

    ``project_dir`` absent, or present but with no ``docs/phases/``
    directory, means "cannot check" — the shape gate alone decides, never
    the reverse (a consumer project mid-bootstrap, or a unit test with no
    project context, must not have every candidate rejected just because
    there is nothing to check against). Never raises.
    """
    if project_dir is None:
        return True
    try:
        project_path = project_dir if isinstance(project_dir, Path) else Path(project_dir)
        phases_dir = project_path / "docs" / "phases"
        if not phases_dir.is_dir():
            return True
        return (phases_dir / f"phase-{candidate}.md").is_file()
    except Exception:
        return True


def _derive_phase_key(
    tool_input: dict, project_dir: "Path | str | None" = None
) -> "str | None":
    """Derive a phase key from a checkpoint spawn's own prompt (INFRA-258;
    strict shape gate + optional doc verification added INFRA-289, CER-103(b)).

    Tries the ``docs/phases/phase-<key>.md`` path pattern first, then a bare
    ``Phase <key>`` mention. ``<key>`` matches ``[A-Za-z0-9][A-Za-z0-9._-]*``
    with trailing punctuation stripped, so both ``101`` and
    ``HARNESS001-main`` resolve — but a captured candidate from *either*
    pattern must additionally pass :data:`_PHASE_KEY_STRICT_RE` (all-digits,
    or an alphanumeric run ending in a digit with an optional
    ``-main``/``-ante<N>``/``-post<N>`` suffix) before it is accepted. This
    is what stops the bare pattern from matching the word after "Phase" in
    ordinary prose (observed: ``story_id = "phase:key"`` / ``"phase:checkpoint"``
    on rows that were never phases at all) — and the same standard applies to
    the path pattern's capture, which is harder to trip accidentally but is
    still held to it (there is no reason a path-derived key should be
    trusted more than a bare one).

    When *project_dir* is supplied and ``<project_dir>/docs/phases/`` exists,
    a shape-passing candidate must also name a real phase doc
    (:func:`_phase_doc_verified`) — when that directory does not exist, the
    existence check is skipped and the shape gate alone decides.

    Returns ``None`` when nothing qualifies. Never raises.
    """
    try:
        for key in ("prompt", "description"):
            value = tool_input.get(key)
            if not value:
                continue
            text = str(value)
            for pattern in (_PHASE_DOC_PATH_RE, _PHASE_BARE_RE):
                m = pattern.search(text)
                if not m:
                    continue
                candidate = _strip_trailing_punct(m.group(1))
                if not _PHASE_KEY_STRICT_RE.match(candidate):
                    continue
                if not _phase_doc_verified(project_dir, candidate):
                    continue
                return candidate
    except Exception:
        return None
    return None


def _derive_attribution(
    tool_input: dict,
    state: "dict | None",
    subagent_type: "str | None",
    project_dir: "Path | str | None" = None,
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
    (when no phase key is derivable, per :func:`_derive_phase_key`'s strict
    shape gate — INFRA-289, CER-103(b): rejection is honest, not a
    plausible-looking ``phase:<English word>`` lie) — never an individual
    story id.

    For every other role, behaviour is unchanged from the pre-INFRA-258
    ``_derive_story_id``: prompt story-id regex, then
    ``state.json["current_story"]``, then ``None`` (the caller applies the
    ``unattributed:<role>`` fallback). ``project_dir`` (optional, INFRA-289)
    is forwarded to :func:`_derive_phase_key` for its doc-existence check —
    the caller passes the *resolved recording target* (item A), so the phase
    doc is looked up in the project the checkpoint is actually for, not
    necessarily the session's own project. Never raises.
    """
    if subagent_type in CHECKPOINT_ROLES:
        phase_key = _derive_phase_key(tool_input, project_dir)
        if phase_key:
            return f"phase:{phase_key}", phase_key, None
        return f"unattributed:{subagent_type}", None, None

    story_id = _derive_story_id(tool_input, state)
    rail = story_id.split("-", 1)[0] if story_id and "-" in story_id else None
    return story_id, None, rail


# ---------------------------------------------------------------------------
# Recording-target resolution (INFRA-289, CER-103(a))
# ---------------------------------------------------------------------------

#: Enumerable source vocabulary for :func:`resolve_recording_project`'s
#: second return value. Mirrors the shape of ``scope_guard``'s
#: ``RESOLVE_CALL_STORY_SOURCES`` — "which project is this spawn's effort
#: row for?" is the same kind of per-call question "which story is this call
#: for?" is, and a single global slot cannot answer either once more than
#: one live answer exists.
RECORDING_TARGET_SOURCES: "tuple[str, ...]" = (
    "explicit-flag",
    "explicit-label",
    "worktree-path",
    "session-cwd",
    "rejected-unregistered",
)

#: `--project-dir <path>`, optionally `=`-joined, optionally single/double
#: quoted. Absolute paths only (Instructions 2).
_RECORDING_FLAG_RE = re.compile(r"--project-dir(?:=|\s+)[\"']?(/[^\s\"']+)[\"']?")

#: `Project dir:` / `project_dir:` / `project_dir=` (case-insensitive on the
#: label, space or underscore between the two words — deliberately distinct
#: from the hyphenated `--project-dir` flag form above so the two patterns
#: never overlap on the same text).
_RECORDING_LABEL_RE = re.compile(
    r"(?i)project[ _]?dir\s*[:=]\s*[\"']?(/[^\s\"']+)[\"']?"
)

#: Marker used to find a `.pairmode-worktrees/<ID>/` segment in a candidate
#: path (Instructions 2) — the resolver collapses to the path *above* this
#: marker and does not re-derive the story id itself (that is
#: `scope_guard.resolve_call_story`'s job; duplicating it here would create
#: a second, drifting copy).
_WORKTREE_MARKER = "/.pairmode-worktrees/"


def _extract_flagged_or_labelled_path(text: str, source: str) -> "str | None":
    pattern = _RECORDING_FLAG_RE if source == "explicit-flag" else _RECORDING_LABEL_RE
    m = pattern.search(text)
    if not m:
        return None
    candidate = _strip_trailing_punct(m.group(1).rstrip("/"))
    return candidate or None


def _extract_worktree_root(text: str) -> "str | None":
    """Return the path *above* the `.pairmode-worktrees` marker in *text*, or
    ``None`` when no such marker is present or the preceding token is not an
    absolute path. Never raises."""
    idx = text.find(_WORKTREE_MARKER)
    if idx == -1:
        return None
    start = idx
    while start > 0 and text[start - 1] not in (" ", "\t", "\n", "\r", '"', "'", "="):
        start -= 1
    candidate = text[start:idx]
    if not candidate.startswith("/"):
        return None
    candidate = _strip_trailing_punct(candidate.rstrip("/"))
    return candidate or None


def _admit_recording_target(
    candidate_path: Path,
    session_path: Path,
    session_state: "dict | None",
) -> bool:
    """A3's admission test — an operator-controlled allowlist, never prompt
    trust. Returns ``True`` only when *candidate_path* is absolute, resolves
    to an existing directory whose ``.companion`` subdirectory already
    exists (never created here), and is either the session project itself
    or present, after ``Path.resolve()``, in
    ``state.json["registered_projects"]``. Never raises, never writes."""
    try:
        if not candidate_path.is_absolute():
            return False
        if not candidate_path.is_dir():
            return False
        if not (candidate_path / ".companion").is_dir():
            return False

        resolved_candidate = candidate_path.resolve()
        resolved_session = session_path.resolve()
        if resolved_candidate == resolved_session:
            return True

        state = session_state if isinstance(session_state, dict) else _read_state(session_path)
        if not isinstance(state, dict):
            return False
        registered = state.get("registered_projects")
        if not isinstance(registered, list):
            return False
        for entry in registered:
            if not entry:
                continue
            try:
                if Path(str(entry)).resolve() == resolved_candidate:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def resolve_recording_project(
    tool_input: "dict | None",
    session_project_dir: "Path | str",
    session_state: "dict | None" = None,
) -> "tuple[Path, str]":
    """Resolve which project's ``effort.db`` a completed spawn's attempt row
    belongs to (INFRA-289, CER-103(a)).

    A single ``project_dir`` (the session's own cwd) answers "where does
    this row go?" correctly for a native session, but not for a spawn
    dispatched *from* one flex session *against* another project — a fleet
    campaign's ``--project-dir /mnt/work/meander`` in the prompt, or a cwd
    living under that project's own ``.pairmode-worktrees/``. The RELEASE-063
    canary is the proof: those spawns recorded into flex's db while
    meander's held nothing. This mirrors
    ``scope_guard.resolve_call_story``'s shape — resolve the answer from the
    call itself, in a documented precedence, rather than trusting one global
    slot that now has more than one live answer.

    The one thing that shape must not import naively is trust: a target path
    lifted out of a prompt is agent-authored input, exactly the kind this
    module's public entry point commits to never trusting blindly. A
    candidate is therefore only ever *admitted*, via
    :func:`_admit_recording_target`'s operator-controlled allowlist check
    against ``state.json["registered_projects"]`` — never used because it
    merely looked plausible. This function performs no writes and creates no
    directories on any path (including a rejected one) — `log_recording_event`
    itself ``mkdir``s, so a resolver that logged its own rejection would
    materialise ``.companion/`` at the exact path it just refused; logging is
    the caller's job.

    Precedence, each candidate derived from ``tool_input["prompt"]`` then
    ``tool_input["description"]``:

    1. ``explicit-flag`` — an absolute path following ``--project-dir``
       (optionally ``=``-joined, optionally quoted);
    2. ``explicit-label`` — an absolute path following a ``Project dir:`` /
       ``project_dir:`` / ``project_dir=`` label (case-insensitive on the
       label);
    3. ``worktree-path`` — an absolute path containing a
       ``/.pairmode-worktrees/<ID>/`` segment, collapsed to the path above
       ``.pairmode-worktrees``;
    4. ``session-cwd`` — no candidate derivable: returns
       ``Path(session_project_dir)``, today's behaviour, unchanged.

    The **first candidate found** (in source order above) is the only one
    tried. If it fails A3's admission test, resolution does **not** fall
    through to the next source — it returns
    ``(Path(session_project_dir), "rejected-unregistered")`` immediately. A
    prompt naming a target flex will not write to is a contradiction between
    intent and configuration worth surfacing, not a reason to keep guessing.

    Returns ``(project_path, source)`` where ``source`` is a member of
    :data:`RECORDING_TARGET_SOURCES`. Never raises — any exception resolves
    to ``(Path(session_project_dir), "session-cwd")``.
    """
    session_path = Path(session_project_dir)
    try:
        if not isinstance(tool_input, dict):
            return session_path, "session-cwd"

        texts = []
        for key in ("prompt", "description"):
            value = tool_input.get(key)
            if value:
                texts.append(str(value))

        for source in ("explicit-flag", "explicit-label", "worktree-path"):
            candidate_str: "str | None" = None
            for text in texts:
                if source == "worktree-path":
                    candidate_str = _extract_worktree_root(text)
                else:
                    candidate_str = _extract_flagged_or_labelled_path(text, source)
                if candidate_str:
                    break
            if not candidate_str:
                continue

            try:
                candidate_path = Path(candidate_str)
            except Exception:
                continue
            if not candidate_path.is_absolute():
                # A relative path is never a candidate (Instructions 2) —
                # try the next source rather than treating this as a
                # rejection.
                continue

            if _admit_recording_target(candidate_path, session_path, session_state):
                return candidate_path.resolve(), source
            return session_path, "rejected-unregistered"

        return session_path, "session-cwd"
    except Exception:
        return session_path, "session-cwd"


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


def _lexical_spawn_output_path(
    output_file: "str | Path | None", tasks_root: "Path | str | None" = None
) -> "Path | None":
    """Placement-only half of the containment rule (INFRA-287, CER-101):
    normalise *output_file* with ``os.path.abspath`` (which applies
    ``normpath`` — collapsing ``..`` and ``.`` — **without** following
    symlinks) and judge *where the path is*, lexically, as given.

    No existence check, no ``open()``, no symlink following — the "is the
    file real and is its target acceptable?" half lives in
    :func:`_contained_spawn_output`. Splitting the two lets
    :func:`is_reconcilable_spawn_output` tell "this path is in a place the
    harness never writes spawn output" (``uncontained``) apart from "this
    path is well-placed but the file is gone" (``file-missing``).

    Default rule (``tasks_root=None``): the lexical path must be contained
    under one of :func:`default_spawn_output_roots` and have the literal
    component ``"tasks"`` (:data:`SPAWN_TASKS_DIR_NAME`) in its ``.parts``.
    Explicit ``tasks_root``: the lexical path must be contained under
    ``os.path.abspath(tasks_root)``. Returns the lexical ``Path`` or
    ``None``. Never raises.
    """
    if output_file is None:
        return None
    try:
        candidate = Path(os.path.abspath(str(output_file)))

        if tasks_root is not None:
            root = Path(os.path.abspath(str(tasks_root)))
            if not _is_relative_to(candidate, root):
                return None
            return candidate

        roots = default_spawn_output_roots()
        if not any(_is_relative_to(candidate, root) for root in roots):
            return None
        if SPAWN_TASKS_DIR_NAME not in candidate.parts:
            return None
        return candidate
    except Exception:
        return None


def _permitted_output_target(path: Path, home: "Path | None" = None) -> bool:
    """Allowlist check on a spawn-output symlink's *target* (INFRA-287, A3).

    CER-089's protection is preserved by moving it from the link *path* to
    the link *target*. What CER-089 protects against: ``output_file`` is a
    persisted string, and an unchecked one pointing at ``/etc/passwd``, a
    repository file, or ``~/.ssh/*`` would be opened and parsed by a
    hook-path function. The pre-INFRA-287 rule applied its containment check
    to ``Path.resolve()``'s output — but Claude Code writes the spawn output
    at ``<tmp>/.../tasks/<hash>.output`` as a **symlink** into
    ``~/.claude/projects/<slug>/<session>/subagents/``, so resolving first
    made every real output file fail containment (294/294 measured live,
    2026-07-28) and no async row ever reconciled. The split: *placement* is
    judged lexically on the link path (:func:`_lexical_spawn_output_path`),
    and this helper separately allowlists where the link may *point*:
    ``(home or Path.home()) / ".claude"`` — the same transcript root
    ``context_budget._derive_transcript_path`` already confines itself to,
    and where Claude Code genuinely puts subagent transcripts — plus the
    temp roots themselves. A ``/etc/passwd`` or ``~/.ssh`` target is under
    neither and is still rejected; only the *location* of the check moved.

    Returns ``True`` when *path* is not a symlink, or when
    ``os.path.realpath(path)`` is contained under an allowlisted root.
    *home* is injectable for tests, mirroring
    ``context_budget._derive_transcript_path``. Never raises — any failure
    is ``False`` (rejected).
    """
    try:
        if not os.path.islink(str(path)):
            return True
        target = Path(os.path.realpath(str(path)))
        allowed_roots: "list[Path]" = [((home or Path.home()) / ".claude").resolve()]
        allowed_roots.extend(default_spawn_output_roots())
        return any(_is_relative_to(target, root) for root in allowed_roots)
    except Exception:
        return False


def _contained_spawn_output(
    output_file: "str | Path | None",
    tasks_root: "Path | str | None" = None,
    home: "Path | None" = None,
) -> "Path | None":
    """Return a contained spawn-output ``Path``, or ``None`` when
    *output_file* is not an acceptable spawn-output location (CER-089;
    symlink-aware since INFRA-287, CER-101).

    Pure: never raises, never opens the file, performs no writes.

    Three checks, in order:

    1. **Lexical placement** (:func:`_lexical_spawn_output_path`) — the path
       *as given*, normalised with ``os.path.abspath`` but never resolved
       through symlinks, must satisfy the default rule (temp-root-contained
       with a ``"tasks"`` component) or explicit-``tasks_root`` containment.
       Judged lexically because the real live output file is a symlink into
       ``~/.claude/`` — resolving first applies the rule to the link target
       and rejects every real path (the CER-101 root cause).
    2. ``Path.is_file()`` — which *does* follow a link: the file must
       genuinely exist and be a file, not a directory or a broken link.
    3. **Target allowlist** (:func:`_permitted_output_target`) — a symlink
       may only point under ``(home or Path.home())/".claude"`` or a temp
       root. This is where CER-089's protection now lives; see that
       helper's docstring.

    The returned path is the **lexical** path (the one in the ``tasks/``
    directory), never the link target — ``output_file``,
    :func:`session_output_prefix`, the ``pending_reconcilable`` ownership
    filter and the recording log all stay expressed in the same
    session-identifying namespace.

    Design note — deliberately looser than the observed live shape. The
    observed shape is
    `/tmp/claude-<uid>/<project-slug>/<session-id>/tasks/<hash>.output`,
    but this guard checks only *temp root + a `tasks` path component*, not
    the full `claude-<uid>/<slug>/<session>` shape. Pinning the fuller shape
    would make every ``output_file`` uncontained the moment the harness
    changes its directory layout — silently stopping all reconciliation,
    rows pending forever, exactly the failure class CER-101 documented.
    """
    try:
        path = _lexical_spawn_output_path(output_file, tasks_root=tasks_root)
        if path is None:
            return None
        if not path.is_file():
            return None
        if not _permitted_output_target(path, home=home):
            return None
        return path
    except Exception:
        return None


def session_output_prefix(output_file: "str | Path | None") -> "str | None":
    """Return the owning session's spawn-output path prefix, or ``None``.

    INFRA-285 (CER-097, item D1). Claude Code writes an async spawn's output to
    ``<tmp>/claude-<uid>/<project-slug>/<session-id>/tasks/<hash>.output``, so
    the path up to and including the parent of the
    :data:`SPAWN_TASKS_DIR_NAME` component identifies the *session* that
    produced it — which is what lets one session's effort.db rows be told apart
    from another's without adding a column::

        /tmp/claude-1000/-mnt-work-flex/abc-123/tasks/x.output
            -> /tmp/claude-1000/-mnt-work-flex/abc-123/

    The trailing separator matters: without it, a prefix filter for session
    ``abc-123`` would also match ``abc-1234``.

    INFRA-287 (CER-101 collateral): the parts are derived from
    ``os.path.abspath(output_file)`` — lexical, never resolved through
    symlinks. The live output file is a *symlink* under ``tasks/`` pointing
    into ``~/.claude/projects/.../subagents/``, so the pre-INFRA-287
    ``Path.resolve()`` walked through it to a path with no ``tasks``
    component and this function returned ``None`` for every production path
    between INFRA-285 and INFRA-287 — meaning the ``spawn_output_prefix``
    ownership filter CER-097 built was never armed and
    ``record_attempt_from_transcript``'s sweep ran unfiltered. It is
    filtered from here on: a reader who finds ``spawn_output_prefix``
    populated in ``state.json`` for the first time is seeing new behaviour,
    not new data.

    Pure. Performs no filesystem I/O — in particular it does not require the
    file to exist, because a prefix is derived at spawn time while the output
    file may still be being written. Returns ``None`` for ``None``, for a
    path with no ``tasks`` component, and for anything that raises. Never
    raises.
    """
    if output_file is None:
        return None
    try:
        parts = Path(os.path.abspath(str(output_file))).parts
        if SPAWN_TASKS_DIR_NAME not in parts:
            return None
        index = parts.index(SPAWN_TASKS_DIR_NAME)
        if index == 0:
            return None
        return str(Path(*parts[:index])) + os.sep
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


def _empty_stream_result() -> dict:
    """The all-default :func:`_stream_spawn_output` result shape — the value
    both that reader and :func:`is_reconcilable_spawn_output` return when
    nothing was read."""
    return {
        "exists": False,
        "line_cap_exceeded": False,
        "any_parsed": False,
        "assistant_entries": [],
        "last_entry": None,
        "first_ts": None,
        "last_ts": None,
    }


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
    result = _empty_stream_result()
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


def _file_quiescent(path: Path) -> bool:
    """``True`` when *path*'s own mtime is at least
    :data:`QUIESCENT_AGE_SECONDS` in the past — the same stat-and-compare
    :func:`reconcile_pending_attempts`'s ``include_quiescent`` branch has
    always used, promoted to a shared helper by INFRA-287 so the terminator
    predicate and the retirement path apply one physical judgment under one
    threshold. Best-effort: an ``OSError`` on ``stat()`` means "not
    quiescent" — never an exception and never a promotion.
    """
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    return (datetime.now(timezone.utc).timestamp() - mtime) >= QUIESCENT_AGE_SECONDS


def is_reconcilable_spawn_output(
    output_file: "str | Path | None",
    *,
    tasks_root: "Path | str | None" = None,
    home: "Path | None" = None,
) -> "tuple[Path | None, str, dict]":
    """The single containment + terminator predicate (INFRA-287, CER-101).

    Both :func:`read_completed_spawn` (the sweep's reader) and
    :func:`classify_pending_reason` (the ``pairmode_effort pending``
    diagnostic) route through this one function, so the two can never again
    disagree about the same row — the cp-109 contradiction ("14
    reconcilable" reported, 0 reconciled) was exactly the two halves of this
    judgment living in two drifting copies, one of which never applied
    containment at all.

    Returns ``(path, reason, data)``:

    - ``path`` — the contained **lexical** path (see
      :func:`_contained_spawn_output`), or ``None`` when containment failed;
    - ``reason`` — a member of :data:`PENDING_REASONS`, or
      :data:`SPAWN_TERMINATED` when the spawn is contained and finished;
    - ``data`` — the :func:`_stream_spawn_output` result shape (the
      all-default shape when nothing was read).

    Reasons, in evaluation order: ``no-output-file`` (falsy *output_file*),
    ``uncontained`` (containment rejected a non-empty path — with the one
    honest exception that a well-*placed* path whose file has simply
    vanished reports ``file-missing``, because a containment rejection and
    an evicted ``/tmp`` file are different operational problems),
    ``file-missing``, ``line-cap``, ``file-empty``, then the terminator
    verdict on the last parseable entry.

    Terminator (B4): the last parseable entry must be ``type ==
    "assistant"`` with a ``dict`` ``message``; anything else is
    ``not-terminated`` regardless of mtime (the quiescence promotion applies
    only where there is an assistant turn to extract usage from — the
    ``include_quiescent`` retirement path in
    :func:`reconcile_pending_attempts` remains the route for the rest).
    Given that assistant last entry, the spawn is terminated when its stop
    reason is ``end_turn`` **or** the file has been quiescent for
    :data:`QUIESCENT_AGE_SECONDS` (measured live 2026-07-28: 51 of 294
    output files — ~18% of completed spawns — end on an assistant entry
    with no stop-reason stamp at all, and 50 of those 51 had been untouched
    for over an hour: finished agents, not in-flight ones; ``end_turn``
    itself remains the majority terminator at 215 of 294 and must keep
    working). A truthy non-``end_turn`` stop reason on a still-fresh file is
    ``in-flight``; a falsy/absent one on a still-fresh file is
    ``not-terminated``.

    Pure: no writes, no db access, never raises — any exception yields
    ``(None, "file-empty", <empty shape>)``, matching
    :func:`classify_pending_reason`'s long-standing except-branch value.
    """
    try:
        if not output_file:
            return None, "no-output-file", _empty_stream_result()

        path = _contained_spawn_output(output_file, tasks_root=tasks_root, home=home)
        if path is None:
            lexical = _lexical_spawn_output_path(output_file, tasks_root=tasks_root)
            if lexical is not None and not os.path.exists(lexical):
                # Placement is fine; the file (or its link target) is simply
                # gone — an evicted /tmp, not a containment rejection.
                return None, "file-missing", _empty_stream_result()
            return None, "uncontained", _empty_stream_result()

        data = _stream_spawn_output(path)
        if not data["exists"]:
            return path, "file-missing", data
        if data["line_cap_exceeded"]:
            return path, "line-cap", data
        if not data["any_parsed"]:
            return path, "file-empty", data

        last_entry = data["last_entry"]
        message = last_entry.get("message") if isinstance(last_entry, dict) else None
        if (
            not isinstance(last_entry, dict)
            or last_entry.get("type") != "assistant"
            or not isinstance(message, dict)
        ):
            return path, "not-terminated", data

        stop = message.get("stop_reason")
        if stop == "end_turn" or _file_quiescent(path):
            return path, SPAWN_TERMINATED, data
        if stop:
            return path, "in-flight", data
        return path, "not-terminated", data
    except Exception:
        return None, "file-empty", _empty_stream_result()


def classify_pending_reason(
    row: dict,
    *,
    tasks_root: "Path | str | None" = None,
    home: "Path | None" = None,
) -> str:
    """Return the single reason a ``pending_reconcilable`` row has not
    reconciled (CER-091 defect 3; shared predicate since INFRA-287).

    Pure — no writes, no db access, takes an already-fetched row dict.
    Never raises. Returns one of :data:`PENDING_REASONS`. Routes through
    :func:`is_reconcilable_spawn_output` — the same predicate
    :func:`read_completed_spawn` uses — so this classifier and the sweep can
    never disagree about whether a row is reachable (CER-101's diagnostic
    lie: this function used to open ``row["output_file"]`` directly, never
    applying the containment rule the sweep applied, so it reported rows
    "reconcilable" that the sweep could never touch). *tasks_root*/*home*
    are keyword-only with defaults, so existing single-argument call sites
    (``pairmode_effort.py pending``) are unchanged.
    """
    try:
        output_file = row.get("output_file") if isinstance(row, dict) else None
        path, reason, data = is_reconcilable_spawn_output(
            output_file, tasks_root=tasks_root, home=home
        )
        if reason != SPAWN_TERMINATED:
            return reason

        usage = _sum_deduped_usage(data["assistant_entries"])
        if usage.get("tokens_total") is None:
            return "no-usage"

        final_text = _flatten_tool_response(data["last_entry"].get("message"))
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
    home: "Path | None" = None,
    rejected: "list[str] | None" = None,
) -> "dict | None":
    """Read a spawned agent's own JSONL output file (INFRA-258).

    Returns ``None`` when the spawn is not yet complete, the file is
    unreadable/missing/empty, no usage data is found, or *output_file* is not
    a contained spawn-output path (CER-089 — see below). Otherwise returns a
    dict with ``tokens_in``, ``tokens_out``, ``tokens_total``,
    ``cache_read_tokens``, ``cache_write_tokens``, ``duration_ms``,
    ``model``, ``outcome``, ``fail_cause``, ``final_text``.

    Containment **and** completion detection are delegated wholesale to
    :func:`is_reconcilable_spawn_output` (INFRA-287, CER-101) — this
    function returns ``None`` unless that shared predicate reports
    :data:`SPAWN_TERMINATED`, then does only usage/duration/outcome
    extraction from the returned data. See the predicate's docstring for
    the terminator rule (``end_turn`` or file quiescence on an assistant
    last entry) and the containment split (lexical link path + allowlisted
    link target). A rejected path returns ``None`` with no ``open()`` call
    ever made on it; the failure mode this creates — an ``output_file``
    value that fails containment leaves its ``effort.db`` row pending
    forever — is now *visible* as ``classify_pending_reason``'s
    ``uncontained``, no longer indistinguishable from an evicted file.

    Public signature (besides the keyword-only ``tasks_root``, ``home``
    added by INFRA-287 for test injection of the target allowlist's
    ``~/.claude`` root, and ``rejected`` added by INFRA-299) and return shape
    unchanged from pre-CER-091 (other callers and INFRA-258's own tests
    depend on both). Never raises.

    *rejected* (keyword-only, CER-113) is passed straight through to
    :func:`parse_worker_outcome`; see that function's docstring for why the
    out-list, rather than a project directory, is the mechanism. The return
    dict is unchanged, and a caller that omits *rejected* — the default —
    behaves exactly as before.
    """
    try:
        path, reason, data = is_reconcilable_spawn_output(
            output_file, tasks_root=tasks_root, home=home
        )
        if reason != SPAWN_TERMINATED or path is None:
            return None

        last_message = data["last_entry"].get("message")

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
        outcome, fail_cause = parse_worker_outcome(final_text, rejected=rejected)

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


# ---------------------------------------------------------------------------
# reconcile_one — the SubagentStop relay's single delegated call (INFRA-298,
# CER-114)
# ---------------------------------------------------------------------------


def _find_pending_by_agent_id(db_path: Path, agent_id: str) -> "dict | None":
    """Return the live pending ``attempts`` row whose ``agent_id`` column
    equals *agent_id*, or ``None`` (INFRA-298).

    "Pending" is the same predicate :func:`effort_db.pending_reconcilable`
    uses: ``tokens_total IS NULL OR outcome IS NULL``. Deliberately built on
    :func:`effort_db.query_all` rather than a new ``effort_db`` query
    function — this story's declared file scope does not touch
    ``effort_db.py``, and :func:`reconcile_one` is the sole caller, invoked
    at most once per completed spawn (a hook-path frequency, not a hot
    loop), so a full-table scan is the appropriate cost here rather than a
    reason to widen ``effort_db.py``'s public surface. When more than one
    row matches (a doubled hook invocation racing this same lookup, or an
    ``agent_id`` value reused across two rows), the highest ``id`` — the
    most recently inserted — wins, since that is the row this specific
    ``SubagentStop`` event's own spawn produced. Never raises; any failure
    (missing db, corrupt file) returns ``None``.
    """
    try:
        rows = effort_db.query_all(db_path)
    except Exception:
        return None

    candidates = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("agent_id") == agent_id
        and (row.get("tokens_total") is None or row.get("outcome") is None)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda row: row.get("id") or 0)
    return candidates[-1]


def _contained_agent_transcript(
    path: Any, *, home: "Path | None" = None
) -> "Path | None":
    """Return a contained ``agent_transcript_path`` ``Path`` from a
    ``SubagentStop`` payload, or ``None`` (INFRA-298, CER-114).

    ``agent_transcript_path`` is a string supplied by the hook's own stdin
    payload — trusted harness input (same trust level ``cwd`` gets
    elsewhere on the hook path — see the security-auditor procedure's
    thin-delegation exception list), but a path value nonetheless, so it is
    still confined before ``open()`` ever sees it, applying the same
    allowlist-the-root discipline CER-089/INFRA-287 established for
    ``output_file``: contained under ``(home or Path.home()) / ".claude"``
    — the one root Claude Code genuinely writes subagent transcripts under,
    already allowlisted as a symlink *target* by
    :func:`_permitted_output_target`. This is the *same physical file* an
    ``output_file`` value in the ``tasks/`` directory would resolve to via
    symlink (see that function's docstring) — reading it directly here is
    what lets :func:`reconcile_one` get a spawn's usage data without
    touching the ``tasks/`` file at all, which is the whole point (Ensures
    C3): the ``tasks/`` file's mtime is refreshed continuously by harness
    re-serialization (CER-114), but ``agent_transcript_path`` is the
    resolved, final artifact and ``SubagentStop`` firing is itself the
    completion signal — no ``end_turn``/quiescence re-derivation needed.

    Lexical containment plus ``Path.is_file()`` — no symlink-target check
    beyond that, because *this* path is not itself expected to be a
    symlink. Never raises.
    """
    if not path:
        return None
    try:
        candidate = Path(os.path.abspath(str(path)))
        root = ((home or Path.home()) / ".claude").resolve()
        if not _is_relative_to(candidate, root):
            return None
        if not candidate.is_file():
            return None
        return candidate
    except Exception:
        return None


def reconcile_one(
    *,
    project_dir: "Path | str",
    agent_id: "str | None",
    payload: "dict | None",
    home: "Path | None" = None,
    tasks_root: "Path | str | None" = None,
) -> str:
    """Reconcile at most one ``attempts`` row from a ``SubagentStop`` event
    (INFRA-298, CER-114).

    The single delegated call ``hooks/subagent_stop.py`` makes. Keys on
    *agent_id* against the live pending row whose ``agent_id`` column
    matches (:func:`_find_pending_by_agent_id`) — never on story/role/text
    matching. Returns the :data:`RECORDING_DECISIONS` value it emitted, so
    the hook and this function's own tests observe the same string
    (:func:`log_recording_event` is called on every return path). Never
    raises.

    Two outcome/usage sources, tried in order (Ensures C3/C4):

    1. **Payload path** — when ``payload["last_assistant_message"]`` yields
       a parseable outcome via :func:`parse_worker_outcome` (reused
       unchanged — no second outcome parser), usage is read from
       ``payload["agent_transcript_path"]`` via the SAME extraction
       machinery :func:`read_completed_spawn` uses
       (:func:`_stream_spawn_output` + :func:`_sum_deduped_usage` — no new
       usage-extraction logic), through :func:`_contained_agent_transcript`
       rather than :func:`_contained_spawn_output`. The row's own
       ``output_file`` (the ``tasks/`` symlink CER-114 documents as
       possibly mid-flush) is never stat'd or read on this path.
    2. **File fallback** — when the payload carries no usable outcome,
       :func:`read_completed_spawn` is called on the row's stored
       ``output_file`` (unchanged, existing function, existing containment
       rule) for both outcome and usage together.

    Either source's result is written via ``effort_db.reconcile_attempt``,
    which inherits ``_ATOMIC_RECONCILE_FIELDS`` — tokens and outcome commit
    together or not at all; a source that yields one without the other
    commits nothing (``skip:no-usage`` / ``skip:no-outcome``).

    Never bumps ``.companion/attempt_counter.json`` on any outcome,
    including ``FAIL`` (Ensures C6) — the reconciliation-time late-bump
    path belongs to ``reconcile_pending_attempts`` alone; a ``SubagentStop``
    firing *during* the driving session runs where the synchronous
    PostToolUse bump already owns that decision, and a second bump source
    in the same session is the double-count CER-102 closed.

    Idempotent (Ensures C5): once a row's ``tokens_total`` and ``outcome``
    are both non-``None``, :func:`_find_pending_by_agent_id` no longer
    matches it, so a repeat call with the same payload is a
    ``skip:no-pending-row`` no-op, not a second write.
    """
    project_path = Path(project_dir) if not isinstance(project_dir, Path) else project_dir
    row_id: "int | None" = None
    try:
        state = _read_state(project_path)
        if not state or not state.get("pairmode_version"):
            log_recording_event(project_path, decision="skip:no-state", agent_id=agent_id, row_id=None)
            return "skip:no-state"
        if not state.get("effort_tracking"):
            log_recording_event(
                project_path, decision="skip:effort-tracking-off", agent_id=agent_id, row_id=None,
            )
            return "skip:effort-tracking-off"

        if not agent_id:
            log_recording_event(project_path, decision="skip:no-agent-id", agent_id=agent_id, row_id=None)
            return "skip:no-agent-id"

        payload = payload if isinstance(payload, dict) else {}

        db_path = effort_db.resolve_effort_db_path(project_path)
        row = _find_pending_by_agent_id(db_path, agent_id)
        if row is None:
            log_recording_event(
                project_path, decision="skip:no-pending-row", agent_id=agent_id, row_id=None,
            )
            return "skip:no-pending-row"
        row_id = row.get("id")

        outcome, fail_cause = parse_worker_outcome(payload.get("last_assistant_message"))

        source: "str | None" = None
        usage: "dict[str, Any] | None" = None
        model: "str | None" = None
        duration_ms: "int | None" = None

        if outcome is not None:
            transcript_path = _contained_agent_transcript(
                payload.get("agent_transcript_path"), home=home
            )
            if transcript_path is not None:
                data = _stream_spawn_output(transcript_path)
                candidate_usage = _sum_deduped_usage(data["assistant_entries"])
                if candidate_usage.get("tokens_total") is not None:
                    usage = candidate_usage
                    model = candidate_usage.get("model")
                    source = "payload"

        if usage is None:
            # C4: file fallback — only reached when the payload path above
            # did not both resolve an outcome AND find usage from
            # agent_transcript_path. read_completed_spawn re-derives its own
            # outcome from the file; when the payload already gave us one,
            # the payload's outcome wins on conflict (it is the fresher,
            # event-driven signal), but a fallback outcome fills the gap
            # when the payload gave none.
            result = read_completed_spawn(
                row.get("output_file"), tasks_root=tasks_root, home=home
            )
            if result is not None and result.get("tokens_total") is not None:
                usage = result
                model = result.get("model")
                duration_ms = result.get("duration_ms")
                if outcome is None:
                    outcome = result.get("outcome")
                    fail_cause = result.get("fail_cause")
                source = "file-fallback"

        if outcome is None:
            log_recording_event(
                project_path, decision="skip:no-outcome", agent_id=agent_id, row_id=row_id,
            )
            return "skip:no-outcome"

        if usage is None or usage.get("tokens_total") is None:
            log_recording_event(
                project_path, decision="skip:no-usage", agent_id=agent_id, row_id=row_id,
            )
            return "skip:no-usage"

        fields: "dict[str, Any]" = {
            "tokens_total": usage.get("tokens_total"),
            "tokens_in": usage.get("tokens_in"),
            "tokens_out": usage.get("tokens_out"),
            "cache_read_tokens": usage.get("cache_read_tokens"),
            "cache_write_tokens": usage.get("cache_write_tokens"),
            "duration_ms": duration_ms if duration_ms is not None else usage.get("duration_ms"),
            "outcome": outcome,
            "notes": fail_cause,
        }
        if row.get("model") is None and model:
            fields["model"] = model

        updated = effort_db.reconcile_attempt(db_path, row_id, **fields)
        if not updated:
            log_recording_event(
                project_path, decision="skip:no-pending-row", agent_id=agent_id, row_id=row_id,
            )
            return "skip:no-pending-row"

        decision = "reconciled:payload" if source == "payload" else "reconciled:file-fallback"
        log_recording_event(project_path, decision=decision, agent_id=agent_id, row_id=row_id)
        return decision
    except Exception as exc:
        decision = f"error:{type(exc).__name__}"
        try:
            log_recording_event(project_path, decision=decision, agent_id=agent_id, row_id=row_id)
        except Exception:
            pass
        return decision


def reconcile_pending_attempts(
    *,
    project_dir: "Path | str",
    limit: int = RECONCILE_MAX_ROWS,
    home: "Path | None" = None,
    include_quiescent: bool = False,
    max_age_days: "int | None" = None,
    tasks_root: "Path | str | None" = None,
    output_prefix: "str | None" = None,
    exclude_output_prefixes: "tuple[str, ...] | list[str] | None" = None,
) -> int:
    """Sweep pending (``tokens_total IS NULL OR outcome IS NULL``) rows and
    reconcile the completed ones (INFRA-258, CER-091; two-ended cursor and
    ownership added CER-096, item D).

    Reads ``.companion/state.json``; returns ``0`` immediately unless
    ``effort_tracking`` is ``true``. Fetches candidate rows as the union of
    two bounded ``effort_db.pending_reconcilable`` queries — up to *limit*
    rows with ``order="newest"`` and up to :data:`RECONCILE_OLDEST_ROWS`
    rows with ``order="oldest"``, deduplicated by ``id`` and merged
    preserving newest-first processing order — then calls
    ``read_completed_spawn`` on each and writes the completed ones back via
    ``effort_db.reconcile_attempt``.

    The two-ended fetch (CER-096, item D3) exists because
    ``ORDER BY id DESC LIMIT <limit>`` alone re-examines the same newest
    rows on every sweep while older pending rows — a busy parallel build
    can hold ten or more legitimately-pending rows at once — are never
    reached again until they age out under :data:`RECONCILE_MAX_AGE_DAYS`
    and are lost. The sweep still issues at most two
    ``pending_reconcilable`` queries and calls ``read_completed_spawn`` at
    most ``limit + RECONCILE_OLDEST_ROWS`` times per invocation — bounded
    work is preserved.

    *max_age_days* (CER-088): ``None`` (the default) means "use
    :data:`RECONCILE_MAX_AGE_DAYS`" — the sweep is always bounded; an
    explicitly-passed value overrides it. This is deliberately unlike
    ``effort_db.pending_reconcilable``'s own default (off) — that shared
    query is also used by diagnostics (e.g. INFRA-264's pending-row
    diagnostic) that must keep seeing permanently-pending rows, since
    surfacing them is their entire purpose. Only this sweep, which cannot
    act on a permanently-pending row anyway, opts into the bound. Both the
    newest-first and oldest-first queries receive the same
    *max_age_days*/*output_prefix* values.

    *output_prefix* (CER-096, item D5) is forwarded, unchanged, to both
    ``pending_reconcilable`` calls — it exposes the query layer's ownership
    filter but does not invent an ownership value. Its default (``None``)
    means "no filter", and neither of this module's own call sites nor
    ``hooks/session_start.py`` pass one — production sweep behaviour is
    unchanged except for the two-ended fetch. Deriving a real session-scoped
    prefix (which session a hook belongs to) is INFRA-285's (CER-097's) job;
    that story wires it at the ``record_attempt_from_transcript`` call site via
    :func:`session_output_prefix`.

    *exclude_output_prefixes* (CER-097, item D4) is likewise forwarded,
    unchanged, to **both** ``pending_reconcilable`` calls — passing it to the
    newest-first query alone would let INFRA-284's anti-starvation oldest-first
    cursor route straight around the exclusion and reach exactly the rows the
    caller said it must not touch.

    The two ownership filters point in **opposite directions on purpose**, and
    the asymmetry is the whole design:

    - the PostToolUse sweep (``record_attempt_from_transcript``) runs *inside* a
      session that just spawned, so an inclusive ``output_prefix`` — "only my
      own rows" — is both correct and the cheapest possible query;
    - the SessionStart sweep runs at a moment when the only rows it must not
      touch are *other live sessions'*. An inclusive filter there would strand
      every orphan row left by a session that has since died — the exact rows
      INFRA-258 built this sweep to collect — so it uses
      ``exclude_output_prefixes`` instead and keeps its global reach.

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

    INFRA-298 (CER-114): this sweep — and especially its ``include_quiescent``
    branch — is now a BACKSTOP behind :func:`reconcile_one`, the
    ``SubagentStop``-hook-driven single-row reconcile that fires
    deterministically the moment a spawn actually finishes. This function's
    own behaviour, thresholds, and call sites are unchanged; only its role in
    the overall completion story has been renamed in this docstring (Ensures
    D1/D2 — a prose-only change, verified by ``git diff`` showing no
    executable line touched here or around :data:`QUIESCENT_AGE_SECONDS`).
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
        # CER-096, item D3: fetch both ends so no pending row starves. The
        # newest-first batch is the common, high-value case; the
        # oldest-first batch (bounded by RECONCILE_OLDEST_ROWS) is what
        # stops the tail of a busy parallel build's pending rows from
        # being permanently re-shadowed by the newest ones. Deduplicated
        # by id, merged preserving newest-first processing order — two
        # queries total, never more.
        newest_rows = effort_db.pending_reconcilable(
            db_path,
            limit,
            max_age_days=resolved_max_age_days,
            output_prefix=output_prefix,
            exclude_output_prefixes=exclude_output_prefixes,
            order="newest",
        )
        oldest_rows = effort_db.pending_reconcilable(
            db_path,
            RECONCILE_OLDEST_ROWS,
            max_age_days=resolved_max_age_days,
            output_prefix=output_prefix,
            exclude_output_prefixes=exclude_output_prefixes,
            order="oldest",
        )
        seen_ids = {row["id"] for row in newest_rows}
        rows = list(newest_rows) + [
            row for row in oldest_rows if row["id"] not in seen_ids
        ]

        reconciled = 0
        for row in rows:
            output_file = row.get("output_file")
            if not output_file:
                continue

            path = output_file if isinstance(output_file, Path) else Path(str(output_file))
            # INFRA-287: *home* is forwarded so the target allowlist's
            # ~/.claude root is injectable end-to-end in tests; the
            # production default (None -> Path.home()) is unchanged.
            # INFRA-299 (CER-113): a fresh out-list per row collects any JSON
            # verdict the parser refused, so a worker-contract violation
            # leaves a trace instead of just an eternally-pending row.
            row_rejected: "list[str]" = []
            result = read_completed_spawn(
                path, tasks_root=tasks_root, home=home, rejected=row_rejected
            )

            if row_rejected:
                # In addition to — never instead of — this row's normal
                # decision. Nothing below branches on it: the row is still
                # processed exactly as it would have been (it stays pending,
                # because a refused verdict yields outcome=None).
                try:
                    log_recording_event(
                        project_path, story_id=row.get("story_id"),
                        row_id=row.get("id"),
                        decision="skip:non-enum-outcome",
                        rejected_outcomes=row_rejected,
                    )
                except Exception:
                    pass

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
                        # CER-102: this is the escalation ladder's real
                        # path — see the comment above the (structurally
                        # unreachable on the async path) insert-time bump
                        # in record_attempt_from_transcript for why. A late
                        # bump was previously a silent side effect of a
                        # sweep; it now leaves exactly one trace line per
                        # decision, inside the same best-effort discipline
                        # as the bump itself — a logging failure here must
                        # never propagate and must never prevent the bump.
                        try:
                            if _story_accepts_late_bump(project_path, story_id):
                                bump_attempt_count(story_id, project_path)
                                try:
                                    log_recording_event(
                                        project_path, story_id=story_id,
                                        row_id=row.get("id"),
                                        decision="bump:late-fail",
                                    )
                                except Exception:
                                    pass
                            else:
                                try:
                                    log_recording_event(
                                        project_path, story_id=story_id,
                                        row_id=row.get("id"),
                                        decision="skip:late-bump-blocked",
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            pass

                continue

            # Either in-flight/unreadable (result is None) or complete-but-
            # no-outcome (CER-091 defect 2/4 shape) — never commit a partial
            # row on the default sweep.
            if not include_quiescent:
                continue

            reason = classify_pending_reason(row)
            # CER-099: an "uncontained" row must never be opened by this
            # branch — INFRA-287 introduced the "uncontained" pending
            # reason after this skip-list was written, leaving a
            # containment-guard parity gap where the quiescent path fell
            # straight through to raw stat()/streaming below.
            if reason in (
                "reconcilable",
                "in-flight",
                "file-missing",
                "no-output-file",
                "uncontained",
            ):
                continue

            row_ts = row.get("ts")
            if not _older_than_seconds(row_ts, QUIESCENT_AGE_SECONDS):
                continue

            # CER-099: never stat()/stream the raw, unvalidated
            # attempts.output_file value — resolve through
            # _contained_spawn_output first, exactly as read_completed_spawn
            # does above, forwarding tasks_root/home identically so the
            # ~/.claude root stays injectable end-to-end for tests
            # (INFRA-287).
            contained_path = _contained_spawn_output(
                output_file, tasks_root=tasks_root, home=home
            )
            if contained_path is None:
                continue

            try:
                mtime = contained_path.stat().st_mtime
            except OSError:
                continue
            now_epoch = datetime.now(timezone.utc).timestamp()
            if (now_epoch - mtime) < QUIESCENT_AGE_SECONDS:
                continue

            data = _stream_spawn_output(contained_path)
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
                # INFRA-299 (CER-113): "UNKNOWN" is written HERE, by the
                # quiescent retirement sweep, as a deliberate retirement
                # marker — it is not a worker verdict and never passes
                # through parse_worker_outcome's enum gate. Do not "complete"
                # the CER-113 enum work by adding UNKNOWN to
                # RECOGNISED_BUILD_OUTCOMES or by tightening this write: the
                # two are different vocabularies serving different purposes,
                # and constraining this one breaks the sweep's ability to
                # retire a row it can never learn a real verdict for.
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
    output_prefix: "str | None" = None,
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

    CER-097 item D6: *output_prefix* (optional) is forwarded to the internal
    :func:`reconcile_pending_attempts` call so this sweep only reconciles rows
    belonging to the calling session — the hook passes the
    ``spawn_output_prefix`` it stored for that session. ``None`` (the default,
    and the real case on a session's very first spawn, before any prefix has
    been observed) deliberately means "no filter", i.e. today's global sweep:
    turning an unknown prefix into an *exclusion* would make that first sweep a
    no-op and strand orphan rows forever.

    INFRA-289 (CER-103(a)): *project_dir* is now the **session fallback**,
    not necessarily the recording target. Immediately after validating
    ``tool_input`` is a dict, :func:`resolve_recording_project` resolves the
    project this spawn's row actually belongs to — the incoming session
    directory for a native session, or a different, allowlisted project when
    the spawn's own prompt names one (a fleet-campaign
    ``--project-dir``/worktree-cwd dispatch). Every subsequent use of the
    project path in this function body — ``_read_state``, the
    ``effort_tracking`` gate, the db path, ``reconcile_pending_attempts``,
    ``bump_attempt_count``, and every ``log_recording_event`` call after
    resolution — uses the *resolved* target. Only the transcript-file lookup
    (``_derive_transcript_path``) stays keyed on the session's own
    ``project_dir``: that path identifies where the *session's own* JSONL
    transcript lives on disk, a property of the session, not of the spawn's
    target (DP7's context-budget/effort-recording separation applies here in
    spirit — this function's own session-vs-target split must not be
    conflated with that one either).
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

        # INFRA-289 (CER-103(a)): resolve the recording target from the
        # spawn itself — immediately after the tool_input dict guard, before
        # _read_state, per the module docstring above. Every
        # log_recording_event call from here on carries target_project/
        # target_source (A5) except the outer `except` below, which is a
        # diagnostic about a spawn flex could not interpret at all and stays
        # on the session path.
        target_path, target_source = resolve_recording_project(
            tool_input, project_path, session_state=None
        )
        if target_source == "rejected-unregistered":
            # Recording never stops here — it falls back to (and continues
            # against) the session project, exactly as target_path already
            # is in this branch. This line is the alarm: a prompt named a
            # target flex will not write to.
            log_recording_event(
                target_path, tool_name=tool_name, subagent_type=subagent_type,
                tool_use_id=tool_use_id, story_id=None,
                decision="skip:target-unregistered", row_id=None,
                target_project=str(target_path), target_source=target_source,
            )

        if subagent_type not in RECORDABLE_SUBAGENT_ROLES:
            log_recording_event(
                target_path, tool_name=tool_name, subagent_type=subagent_type,
                tool_use_id=tool_use_id, story_id=None,
                decision="skip:not-recordable-role", row_id=None,
                target_project=str(target_path), target_source=target_source,
            )
            return None

        state = _read_state(target_path)

        story_id, phase_key, rail = _derive_attribution(
            tool_input, state, subagent_type, target_path
        )
        # INFRA-299 (CER-113): collect any JSON verdict the parser refuses so
        # the worker-contract violation is observable. Logged below, after
        # the attribution fields are in hand; the log line is additional to
        # this call's own `recorded`/`skip:*` decision and changes no branch.
        parse_rejected: "list[str]" = []
        outcome, fail_cause = parse_worker_outcome(
            tool_response, rejected=parse_rejected
        )
        if parse_rejected:
            log_recording_event(
                target_path, tool_name=tool_name, subagent_type=subagent_type,
                tool_use_id=tool_use_id, story_id=story_id,
                decision="skip:non-enum-outcome", row_id=None,
                rejected_outcomes=parse_rejected,
                target_project=str(target_path), target_source=target_source,
            )

        # INFRA-237: attempt-counter bump runs unconditionally on FAIL — it
        # is core build-loop control state next_action.py depends on, not
        # observability, so it must not be gated on effort_tracking. Kept
        # best-effort/non-raising like every other branch in this function.
        # INFRA-258: never bump on a synthetic phase:/unattributed: id — the
        # escalation ladder tracks real stories only (Ensures 21).
        # CER-091 defect 4: this PostToolUse-time bump is deliberately
        # ungated by _story_accepts_late_bump — see that helper's docstring.
        # CER-102: this branch is structurally unreachable for every spawn
        # the live async build loop actually makes — for an async-launched
        # Agent spawn, `tool_response` at PostToolUse time is the launch
        # stub (isAsync/agentId/outputFile), never the completed result, so
        # `parse_worker_outcome` above always yields `outcome=None` here and
        # this `if` can never be true on that path. It is retained for
        # synchronous spawns and direct callers, where a real outcome *is*
        # available immediately. The reconcile-time bump in
        # `reconcile_pending_attempts` (below) is the escalation ladder's
        # real path for the live loop — do not "fix" this branch by
        # loosening its gate; the fix is arriving at the correct data, not
        # relaxing the check.
        if story_id and outcome == "FAIL" and ":" not in story_id:
            try:
                bump_attempt_count(story_id, target_path)
            except Exception:
                pass

        if not state or not state.get("effort_tracking"):
            log_recording_event(
                target_path, tool_name=tool_name, subagent_type=subagent_type,
                tool_use_id=tool_use_id, story_id=story_id,
                decision="skip:no-state" if not state else "skip:effort-tracking-off",
                row_id=None,
                target_project=str(target_path), target_source=target_source,
            )
            return None

        # INFRA-258: sweep previously-pending (async, now-completed) rows
        # before writing this new spawn's row. Runs after the
        # effort_tracking early return so a project with tracking disabled
        # does zero additional db work. Its own try/except so a sweep
        # failure never prevents the new row from being written.
        try:
            reconcile_pending_attempts(
                project_dir=target_path, home=home, output_prefix=output_prefix
            )
        except Exception:
            pass

        # Hoist the effective story id actually being recorded so the
        # attempt-number derivation and the row use the identical value
        # (INFRA-257).
        effective_story_id = story_id or f"unattributed:{subagent_type}"

        # Transcript-file lookup stays keyed on the session's own
        # project_dir (see docstring) — the JSONL transcript lives on disk
        # under the session's own cwd-derived key, regardless of which
        # project the row is being recorded against.
        transcript_path = _derive_transcript_path(project_path, session_id, home)
        usage = extract_subagent_usage(transcript_path, tool_use_id)

        model = tool_input.get("model") or usage.get("model")

        # INFRA-288 (CER-104): extract the spawn ref BEFORE the write so the
        # row carries agent_id/output_file in the same statement that
        # creates it, and so agent_id can serve as the idempotency key when
        # a doubled hook registration fires this recording twice.
        # _extract_spawn_ref never raises; a missing/unrecognised shape
        # yields (None, None) and the write behaves exactly as before.
        spawn_agent_id, spawn_output_file = _extract_spawn_ref(tool_response)

        # CER-096, item C: the lifetime spawn ordinal for this
        # (story_id, agent_role) pair is derived atomically on the write
        # side by record_effort/insert_attempt_derived — inside the same
        # transaction as the insert — rather than pre-computed here with a
        # separate read. Phase 109 makes parallel spawns real, so a
        # read-then-write pair across two separate calls (the pre-CER-096
        # shape, once justified by a serial build loop) would let two
        # concurrent spawns for the same pair read the same count and
        # write duplicate ordinals.
        # record_effort_ex (not record_effort) so the deduped flag is
        # observable for the log line below — record_effort's int | None
        # return is DP4-frozen and cannot carry it (INFRA-288).
        row_id, deduped = record_effort_ex(
            project_dir=target_path,
            story_id=effective_story_id,
            agent_role=str(subagent_type),
            model=model,
            usage={
                "input_tokens": usage.get("tokens_in"),
                "output_tokens": usage.get("tokens_out"),
                "cache_read_input_tokens": usage.get("cache_read_tokens"),
                "cache_creation_input_tokens": usage.get("cache_write_tokens"),
            },
            attempt_number=None,
            duration_ms=usage.get("duration_ms"),
            outcome=outcome,
            notes=fail_cause,
            phase=phase_key,
            rail=rail,
            agent_id=spawn_agent_id,
            output_file=spawn_output_file,
        )

        # INFRA-258: persist the spawn ref so a later reconciliation pass
        # (this function's own next call, or hooks/session_start.py) can
        # find and complete this row from its own output_file. Best-effort —
        # a missing/unrecognised tool_response shape leaves both columns
        # NULL and is not an error.
        # INFRA-288: redundant on the derived path above (the insert now
        # stamps both columns itself) but retained as the only writer for
        # every other path — it rewrites the same values and is idempotent;
        # deleting it would trade a written-never-read column for a
        # required-never-written one.
        if row_id is not None:
            try:
                agent_id, output_file = _extract_spawn_ref(tool_response)
                if output_file:
                    effort_db.set_spawn_ref(
                        effort_db.resolve_effort_db_path(target_path),
                        row_id,
                        agent_id,
                        output_file,
                    )
            except Exception:
                pass

        log_recording_event(
            target_path, tool_name=tool_name, subagent_type=subagent_type,
            tool_use_id=tool_use_id, story_id=effective_story_id,
            decision="recorded:deduped" if deduped else "recorded",
            row_id=row_id,
            target_project=str(target_path), target_source=target_source,
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

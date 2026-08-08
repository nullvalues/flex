"""
next_action.py — Action grammar and position-inference read-model for the
next-action resolver (RESOLVER-001, RESOLVER-002, RESOLVER-003, RESOLVER-005,
RESOLVER-007, RESOLVER-008).

RESOLVER-001 (grammar layer):
  Defines the versioned action vocabulary, the canonical dict constructor,
  and the stdlib-only validator.  No third-party imports.  No I/O.

RESOLVER-002 (read-model layer):
  ``infer_position(project_dir)`` reconstructs "where are we" entirely from
  durable state — phase docs, Stories tables, story frontmatter, git log
  (commit-authority), ``.companion/attempt_counter.json``,
  ``.companion/state.json``, and gate helpers from ``flex_build``.

  Invariants (DP7):
  - Pure read: no file is written, no ``write_text``/``open(...,"w")``/
    ``json.dump`` call is made in this module.
  - No subprocess/os.system shelling-out to other CLIs.
  - Composes sibling modules as a library (``next_story``, ``story_resolver``,
    ``model_selector``, ``flex_build`` extractions).

RESOLVER-005 (gate-worker wiring):
  Adds ``spawn-gate-worker`` to the action vocabulary (DP4) and splits Row 4
  along the DP2 boundary: stub is mechanical (``await-user`` directly); schema/
  auth are judged gates (``spawn-gate-worker``).

  ``spawn-gate-worker`` is the **safe-clear seam** (DP4.5): budget hooks fire
  here (``pre_tool_use``/``post_tool_use``) before any mutation.  Re-emission
  across a ``/clear`` is idempotent (DP4.3) — the worker's inputs are durable
  and unchanged, so the resolver simply re-emits the same action.

  The verdict arrives as data (orchestrator-held re-entry, DP4.3).  No API
  call is made from this module; tests inject verdict maps directly into
  ``route_gate_verdict``.

RESOLVER-007 (checkpoint step tracker):
  Adds four checkpoint actions (``checkpoint-security``, ``checkpoint-intent``,
  ``checkpoint-docs``, ``checkpoint-tag``) to replace the monolithic
  ``checkpoint`` action (removed in RESOLVER-007, routing added in
  RESOLVER-008).  ``infer_position`` now reads
  ``state.json["checkpoint_step"]`` (list of completed step-ID strings) and
  exposes it as ``position["checkpoint_step"]``.  ``SCHEMA_VERSION`` bumped
  from 2 to 3.

  REMOVAL NOTE: ``CHECKPOINT = "checkpoint"`` constant is retained for
  backward import compatibility but is no longer a member of ``ACTIONS``.

RESOLVER-008 (checkpoint routing):
  Replaces the temporary Row-9 stub with real pre-checkpoint guard checks and
  step sequencing.  Three guards run when ``next_story_id`` is ``None`` (all
  phase stories done): (1) phase completion (all stories complete/deferred),
  (2) CER Do Now clear (no unresolved items in ``docs/cer/backlog.md``), and
  (3) build gate (pytest exits 0).  If any guard fails, ``await-user`` is
  emitted with ``reason="checkpoint-guard-failed:<which>"``.  When all guards
  pass, the next uncompleted step from ``_CHECKPOINT_SEQUENCE`` is emitted.
  After all four steps appear in ``position["checkpoint_step"]``, ``done`` is
  emitted.  The build gate is injectable via a ``gate_fn`` parameter on
  ``resolve_next_action`` and ``check_checkpoint_guards`` so tests never run
  the real pytest subprocess.

RESOLVER-009 (spec-writer action + needs_spec flag):
  Adds ``spawn-spec-writer`` to the action vocabulary and ``_SPAWN_ACTIONS``.
  ``infer_position`` now sets ``position["needs_spec"] = True`` when the next
  story file has ``status: planned`` AND the ``## Ensures`` section is absent
  or contains fewer than 5 non-blank lines (stub heuristic).  Row 2 in
  ``resolve_next_action`` is split: when ``needs_spec`` is True the resolver
  emits ``spawn-spec-writer`` (model="opus", reason="needs-spec") instead of
  proceeding to ``spawn-builder``.  ``SCHEMA_VERSION`` bumped from 3 to 4.

RESOLVER-011 (resolver read-model integration + CER-056 fix):
  ``infer_position`` now uses ``is_phase_inactive`` from ``index_integrity``
  (CER-056) to select the active phase.  Previously only ``complete`` phases
  were treated as inactive; now ``deferred`` and ``backlog`` phases are also
  skipped when searching for the active phase.  A private helper
  ``_resolve_active_phase`` encapsulates this logic and falls back to
  ``resolve_current_phase`` (flex_build) when no index file is present.

  Invariant: the change is pure-read and does not alter ``resolve_next_action``
  routing — only ``active_phase_file`` (and therefore ``next_story_id``) in the
  Position dict can differ for projects where the last non-complete phase is
  deferred or backlog.

INFRA-260 (CER-083 — phase-stamped checkpoint state):
  ``infer_position`` now also reads ``state.json["checkpoint_phase"]`` (written
  by ``flex_build.py``'s ``_record_checkpoint_step``). When that stamp is a
  non-empty string and differs from the active phase's own key, the exposed
  ``position["checkpoint_step"]`` is forced to ``[]`` — a checkpoint_step list
  recorded for a phase other than the one currently active is stale and must
  not be honoured (this is what let phase-100 silently resolve straight to
  ``checkpoint-tag`` at cp99→phase-100, skipping all three gates). Absent,
  empty, or matching stamps leave the stored list untouched, so state files
  predating this story keep resuming correctly. Still pure-read: this module
  never writes ``checkpoint_phase`` or ``checkpoint_step``.

INFRA-265 (CER-077 -- ambiguous-active-phase read-model):
  ``_resolve_active_phase`` composes ``flex_build._active_phase_candidates``
  for its row walk (no second, independently-maintained index parse) and
  raises ``flex_build.AmbiguousActivePhaseError`` when more than one
  candidate row is flagged ``active`` -- the exception propagates out of
  ``infer_position`` uncaught by this module (it is not swallowed by the
  ``except Exception`` around the ``checkpoint_phase``/``checkpoint_step``
  state read, whose scope stays limited to tolerating an unreadable
  ``state.json``). Callers (``flex_build.py``'s CLI commands) catch it at
  the CLI boundary and exit 2 with the message on stderr rather than a
  traceback. Multiple ``planned`` rows are unaffected -- only a genuine
  double-``active`` index raises. Still pure-read: this module never
  repairs or clears a stamp/index row it observes.

INFRA-283 (CER-095.4 -- phase-keyed checkpoint step state):
  ``infer_position`` now prefers ``state.json["checkpoint_steps"]`` (a
  ``dict[phase_key, list[step_id]]`` written by ``flex_build.py``'s
  ``_record_checkpoint_step``) as the authority for
  ``position["checkpoint_step"]``: when present, the exposed list is the
  active phase's own entry, keyed by the same
  ``Path(active_phase_file).stem`` derivation used elsewhere in this module.
  Two phases resolve independently under this path, because each has its
  own key -- the INFRA-260/CER-083 stamp comparison below is only reachable
  on the legacy fallback, where no keyed record exists yet and a single flat
  ``checkpoint_step`` + ``checkpoint_phase`` stamp is all there is to read.
  Still pure-read: this module writes neither the keyed record nor the flat
  ``checkpoint_step``/``checkpoint_phase`` mirror keys.

INFRA-294 (Phase 112 -- CER Do Now guard tolerates the scaffolded placeholder
row):
  ``_check_cer_do_now`` no longer treats the ``docs/cer/backlog.md.j2``
  template's scaffolded empty-state placeholder row as an unresolved Do Now
  item. It now imports and consumes the shared
  ``cer.is_placeholder_row`` predicate to skip that row before the
  ``RESOLVED``/``SUPERSEDED`` test, so a freshly bootstrapped project's first
  checkpoint no longer fails this guard on the placeholder alone. Pure-read
  and grammar-unchanged: no ``SCHEMA_VERSION`` bump, no Position shape or
  routing change.

INFRA-322 (Phase 114 -- anchored, case-insensitive CER resolution-marker
grammar, CER-130):
  ``_check_cer_do_now``'s membership test — a bare, case-sensitive
  ``"RESOLVED" not in stripped and "SUPERSEDED" not in stripped`` — is
  replaced with a call to the shared ``cer.is_resolution_marked`` predicate.
  The old test was wrong in both directions: it permanently blocked
  title-case ``Resolved cp-34 — …`` rows (a consuming repo's convention),
  and it silently passed genuinely unresolved rows like ``UNRESOLVED …``
  and ``should be RESOLVED``. The guard's shape did not change — same
  fail-open, same ``## Do Now``-only scan, same placeholder exemption, same
  ``{"ok": …, "failed_guard": "cer-do-now"}`` contract at the call site —
  only the grammar behind the boolean test changed. No ``SCHEMA_VERSION``
  bump, no Position shape or routing change.

INFRA-315 (Phase 116 -- pre-build intent review, resolver-emitted, opt-in):
  Adds one new row (Row PBI), evaluated once a next unbuilt story is known
  and before Row 8/Row 4/Row 3/Row 2. When the active project's
  ``CLAUDE.build.md`` Build standards carry ``intent_review=`pre-build``,
  the active phase's Stories table shows no story started
  (``_phase_is_fresh``, reusing INFRA-297's ``_has_story_commit``/
  ``_git_log_oneline`` for the git-evidence half of that check), and
  ``attempt_count == 0``, the resolver emits ``spawn-intent-reviewer``
  (scalar = phase key, ``model=null``) exactly once per phase — subsequent
  calls read the recorded verdict from
  ``state.json["pre_build_intent_review"][phase_key]`` (written by
  ``flex_build.py record-intent-review``, mirroring the phase-keyed
  ``checkpoint_steps`` shape from INFRA-283) and either fall through to
  normal resolution (PASS/ALIGNED) or emit ``await-user`` (anything else —
  spec drift is an operator decision). Absent the opt-in key (or any value
  other than the literal string ``pre-build``), this row never fires and
  resolver output for a given fixture is byte-identical to pre-INFRA-315
  behaviour. No ``SCHEMA_VERSION`` bump — the action grammar itself is
  unchanged (``SPAWN_INTENT_REVIEWER`` already existed); only the Position
  dict gained three new pure-read keys (``intent_review_opt_in``,
  ``phase_is_fresh``, ``pre_build_intent_verdict``).

INFRA-316 (Phase 116 -- between-story context etiquette, Row PC) -- REMOVED
  by INFRA-339 (Phase 117, ``SCHEMA_VERSION`` 5 -> 6). INFRA-316 added
  ``pause-context`` to the action vocabulary and wired a check into the
  Row-8 seam ("story just committed (PASS), more stories remain"): before
  emitting the next ``spawn-builder``, the resolver would read
  ``.companion/state.json`` directly and delegate to
  ``context_budget.should_block`` to decide whether the orchestrator's own
  context-window occupancy was over budget and unacknowledged, emitting
  ``pause-context`` instead of ``spawn-builder`` when it was.

  The Phase-117 cold-eyes review (F2/F12) found two independent problems:
  (1) ``OUTCOME_PASS`` is provably unreachable from a live ``infer_position``
  call -- ``next_story.find_next_story`` (the source of ``next_story_id``)
  and ``infer_position`` both call the same ``_has_story_commit`` against
  the same ``_git_log_oneline`` output microseconds apart, so the two calls
  can never disagree, and the Row-8 branch this check lived in only ever
  fired in hand-constructed test fixtures; (2) even setting reachability
  aside, the check hand-assembled its verdict from the flat top-level
  ``state.json`` mirror rather than the session-scoped values the equivalent
  PreToolUse hook check uses (``context_budget.decide(...,
  session_id=...)``) -- under a concurrent second session it could read
  that session's window instead of the calling orchestrator's, the exact
  CER-097 under-blocking shape INFRA-285 fixed for the hook. See
  ``docs/stories/INFRA/INFRA-339.md`` § Requires 2 for the full analysis and
  the recorded decision to remove the feature rather than invent a new
  reachability signal for it. The orchestrator-track budget gate that
  remains live is the PreToolUse hook (``hooks/pre_tool_use.py`` +
  ``context_budget.decide``) only; this module no longer imports
  ``context_budget`` at all. ``PAUSE_CONTEXT`` the constant is retained for
  backward import compatibility (mirrors the ``CHECKPOINT`` precedent);
  nothing produces the value at runtime, and it is no longer a member of
  ``ACTIONS``.

INFRA-318 (Phase 116 -- spec-time model review, Repo-G item A#7/AG-6):
  ``infer_position`` §4 (builder model selection) now reads the next story's
  optional ``model:`` frontmatter field (validated against
  ``schema_validator.VALID_MODEL_TIERS``) and applies it via
  ``model_selector.apply_declared_model_floor`` to the already-auto-selected
  ``(builder_model, builder_model_reason)`` pair: an outright override at
  attempt 1 (reason becomes ``"story-declared"``), a floor -- never a
  downgrade -- on retry (attempt >= 2). A story without ``model:`` gets
  byte-identical output to pre-INFRA-318 behaviour (Ensures 2/5). This also
  means Row 3's ``prompted-upgrade`` operator prompt never fires for a
  declaring story at attempt 1, because its reason is already
  ``"story-declared"`` by the time Row 3 checks it -- the spec-writer's
  asymmetric raise/lower prompt (Requires 3, spec-writer/procedure.md)
  already recorded operator approval for a raise at spec time, so dispatch
  does not re-prompt.

  ``reviewer_model:`` (the analogous floor for ``spawn-reviewer``) is
  resolved entirely on the ``flex_build.py select-reviewer-model`` CLI path
  (which the orchestrator calls directly before the manual reviewer spawn,
  per ``CLAUDE.build.md`` § Build loop) using the same
  ``apply_declared_model_floor`` helper -- it is NOT threaded through this
  module's Position/action grammar, because ``resolve_next_action`` never
  emits ``spawn-reviewer`` in the first place (CER-074, see the
  ``SPAWN_REVIEWER`` constant's declaration comment below): there is no
  resolver-legible action object for a reviewer-model field to ride on. The
  null-rule relaxation Requires 2 asks for was already satisfied before this
  story -- ``spawn-reviewer`` has been a member of ``_SPAWN_ACTIONS`` (and so
  already permitted a non-null ``model``) since HARNESS003-main; this story
  changes no code at ``validate_action``'s model-constraint check, only the
  comment there, to say so explicitly.

  Pure-read, grammar-unchanged: no new action type, no ``_REQUIRED_KEYS`` or
  ``ACTIONS``/``_SPAWN_ACTIONS`` change, no ``SCHEMA_VERSION`` bump (still 5)
  -- only Position's ``builder_model``/``builder_model_reason`` values can
  differ, and only for a story that declares ``model:``.

INFRA-333 (CER-139, AG-13 -- model-selection completeness for the three
  remaining agent roles):
  ``infer_position`` now exposes ``position["story_class"]`` (the same value
  already used internally to compute ``builder_model``) so Row 2's
  ``spawn-spec-writer`` branch can pass it to the new
  ``model_selector.select_spec_writer_model``. Three call sites are wired:

  - Row 2 (``spawn-spec-writer``): replaces the hardcoded ``model="opus"``
    literal with ``select_spec_writer_model(story_class)`` -- resolves to
    ``"opus"`` unconditionally today (Ensures 3), so no behavior change for
    the one production case that exists.
  - Row 9's ``checkpoint-docs`` step: replaces the unconditional
    ``model=None`` with ``select_docs_reviewer_model(phase_class)`` (read
    from the active phase manifest's frontmatter via the new
    ``_phase_class_for`` helper) -- ``checkpoint-docs`` is a
    ``_SPAWN_ACTIONS`` member, so a non-null model here is grammar-legal and
    was already anticipated by the pre-INFRA-333 comment ("the harness sets
    model at spawn time via model_selector").
  - Row 4b (``spawn-gate-worker``): calls the new phase_class-keyed
    gate-worker selector added to ``model_selector.py`` this story (see that
    module's docstring) and surfaces the result as two advisory ``meta``
    keys -- NOT the action's ``model`` field, which stays ``None``.
    ``spawn-gate-worker`` is deliberately not a ``_SPAWN_ACTIONS`` member
    (``validate_action`` requires ``model=null`` for it, locked in by
    ``test_spawn_gate_worker_with_model_fails_validate``); promoting it
    would be an action-grammar redesign out of this story's narrow
    "wire the missing selectors" scope, so the "spawn-gate-worker carries no
    builder model" comment on the ``SPAWN_GATE_WORKER`` constant below
    remains accurate for the ``model`` field after this story. (INFRA-340
    later removes this Row 4b call entirely -- see the INFRA-340 entry
    below.)

  Grammar-unchanged: no new action type, no ``ACTIONS``/``_SPAWN_ACTIONS``
  membership change, no ``SCHEMA_VERSION`` bump (still 5) -- only
  Position gains one new read-only key (``story_class``) and two actions'
  resolved ``model``/``meta`` values can differ from before this story.

INFRA-340 (Phase 117 -- close the F3/F4 cold-eyes gaps left by INFRA-333):
  (a) Row 9 now resolves ``checkpoint-security``'s and ``checkpoint-intent``'s
  models via ``model_selector.select_security_auditor_model(phase_class)``/
  ``select_intent_reviewer_model(phase_class)`` respectively, mirroring the
  ``checkpoint-docs`` wiring INFRA-333 already added -- closes F3 (both
  checkpoint roles previously carried a hardcoded ``model=None``, contrary to
  the model-override contract documented on ``.claude/agents/
  security-auditor.md``/``intent-reviewer.md``). ``phase_class`` is now
  resolved once (via ``_phase_class_for``) above the Row 9 ``if``/``elif``
  chain and shared by all three checkpoint branches.
  (b) Row 4b no longer calls the phase_class-keyed gate-worker selector added
  to ``model_selector.py`` by INFRA-333 -- that call computed a
  ``(model, reason)`` pair and parked it in two advisory ``meta`` keys that
  nothing ever consumed. Per the Phase-117 cold-eyes review's own conclusion
  (F4), a computed-and-discarded value is worse than not calling the selector
  at all, so this story removes the Row 4b call site rather than promoting
  ``spawn-gate-worker`` into ``_SPAWN_ACTIONS`` (that remains explicitly out
  of scope -- see ``docs/stories/INFRA/INFRA-340.md`` § Context § Decision).
  The selector function itself is retained, unused, in ``model_selector.py``
  for a future real consumer (possibly INFRA-341); see that module's
  docstring for its full name and selection table.
  Grammar-unchanged: no new action type, no ``ACTIONS``/``_SPAWN_ACTIONS``
  membership change, no ``SCHEMA_VERSION`` bump (still 6) -- only two
  actions' resolved ``model`` values differ, and ``spawn-gate-worker``'s
  ``meta`` dict loses two advisory keys it never should have kept.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

# Allow sibling imports when this module is imported from the scripts directory.
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from table_utils import split_table_row  # noqa: E402

# ---------------------------------------------------------------------------
# Story-content hashing (INFRA-444)
# ---------------------------------------------------------------------------


def story_content_hash(path: "str | Path") -> "str | None":
    """Return the SHA-256 hexdigest of *path*'s raw bytes, or ``None`` when
    the file cannot be read.

    Single definition shared by both the recorder (``flex_build.py
    cmd_record_gate_verdict``, which hashes the story file at record time)
    and the reader (this module's ``infer_position`` section 8, which
    re-hashes the story file at read time) — so the two sides can never
    disagree about what "the same story content" means. Hashes raw bytes,
    not decoded text, so the comparison is exact regardless of encoding.
    """
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION: int = 6

# ---------------------------------------------------------------------------
# Action vocabulary (closed set for Era 003; designed to be extended later)
# ---------------------------------------------------------------------------

SPAWN_BUILDER: str = "spawn-builder"
SPAWN_LOOP_BREAKER: str = "spawn-loop-breaker"
SPAWN_GATE_WORKER: str = "spawn-gate-worker"
# SPAWN_REVIEWER is never emitted by resolve_next_action — by design, not by
# omission (CER-074). The reviewer dispatch is intra-cycle: the orchestrator
# dispatches the reviewer itself inside the same spawn-builder iteration
# (builder spawn → reviewer spawn → merge-or-discard, one next-action poll per
# story). DP3 outcome inference is git-authoritative (PASS ⇔ a story-<ID>
# commit exists), and only the reviewer commits, so no resolver-legible state
# exists between builder-return and merge from which to emit this action.
# Retained in ACTIONS/_SPAWN_ACTIONS because the orchestrator's
# ACTION_SUBAGENT_TYPE map and the model-override rule key on it.
# See docs/agreements/HARNESS003-main.md § 2.
SPAWN_REVIEWER: str = "spawn-reviewer"
SPAWN_SECURITY_AUDITOR: str = "spawn-security-auditor"
SPAWN_INTENT_REVIEWER: str = "spawn-intent-reviewer"
SPAWN_SPEC_WRITER: str = "spawn-spec-writer"
# CHECKPOINT ("checkpoint") was removed from ACTIONS in RESOLVER-007.
# The constant is retained for backward import compatibility only.
# Routing to the decomposed checkpoint actions lands in RESOLVER-008.
CHECKPOINT: str = "checkpoint"
CHECKPOINT_SECURITY: str = "checkpoint-security"
CHECKPOINT_INTENT: str = "checkpoint-intent"
CHECKPOINT_DOCS: str = "checkpoint-docs"
CHECKPOINT_TAG: str = "checkpoint-tag"  # inline action — NOT in _SPAWN_ACTIONS
AWAIT_USER: str = "await-user"
DONE: str = "done"
# PAUSE_CONTEXT ("pause-context") was removed from ACTIONS by INFRA-339.
# INFRA-316 (Phase 116) added this between-story context-etiquette handoff at
# the Row-8 seam, but F2/F12 of the Phase-117 cold-eyes review found it was
# structurally unreachable from a live infer_position call (the same
# next_story.find_next_story predicate that selects next_story_id also
# excludes any story it already returned true for, so
# last_attempt_outcome == OUTCOME_PASS could never be observed) and, even
# setting reachability aside, read the flat top-level state.json mirror
# instead of the session-scoped values the equivalent PreToolUse hook check
# uses — the exact CER-097 under-blocking shape INFRA-285 fixed. INFRA-339
# removed the feature rather than repair it (see docs/stories/INFRA/
# INFRA-339.md § Requires 2 for the recorded design decision); the
# orchestrator-track budget gate that remains live is the PreToolUse hook
# (hooks/pre_tool_use.py + context_budget.decide) only. The constant is
# retained for backward import compatibility only (mirrors the CHECKPOINT
# precedent above) — nothing produces this value at runtime.
PAUSE_CONTEXT: str = "pause-context"

ACTIONS: frozenset[str] = frozenset(
    {
        SPAWN_BUILDER,
        SPAWN_LOOP_BREAKER,
        SPAWN_GATE_WORKER,
        SPAWN_REVIEWER,
        SPAWN_SECURITY_AUDITOR,
        SPAWN_INTENT_REVIEWER,
        SPAWN_SPEC_WRITER,
        CHECKPOINT_SECURITY,
        CHECKPOINT_INTENT,
        CHECKPOINT_DOCS,
        CHECKPOINT_TAG,
        AWAIT_USER,
        DONE,
    }
)

# Actions for which model may be non-null (auto-resolved spawn actions only).
# spawn-gate-worker carries no builder model (the gate worker tier is not a
# builder-model decision), so it is NOT in _SPAWN_ACTIONS — model must be None.
# INFRA-333 added a phase_class-keyed selector for this role in
# model_selector.py, but promoting spawn-gate-worker into _SPAWN_ACTIONS to
# carry its result would be an action-grammar redesign, out of scope.
# INFRA-333 instead surfaced the result as two advisory `meta` keys;
# INFRA-340 removed that call site entirely (nothing consumed the advisory
# meta) — Row 4b calls no selector today, and `model` stays None.
# spawn-reviewer, spawn-security-auditor, and spawn-intent-reviewer carry a
# model override (checkpoint-agent model selection) and ARE in _SPAWN_ACTIONS.
# (spawn-reviewer membership is for orchestrator dispatch only — the resolver
# never emits it; see the CER-074 note at its declaration above.)
# INFRA-318: this is also the null-rule relaxation a story-declared
# `reviewer_model:` floor depends on — spawn-reviewer already permits a
# non-null model (has since HARNESS003-main, well before INFRA-318), so no
# code change was needed here for reviewer_model dispatch to reach a real
# spawn-reviewer action object; only this comment is new. The actual
# reviewer_model floor is applied by the orchestrator's
# `flex_build.py select-reviewer-model` CLI call (see CLAUDE.build.md §
# Build loop), not by anything in this module — see the INFRA-318 module
# docstring entry above for why (resolve_next_action never emits
# spawn-reviewer, so there is no action object here for the field to ride).
# checkpoint-security, checkpoint-intent, checkpoint-docs carry a model override
# (checkpoint-agent model selection) and ARE in _SPAWN_ACTIONS. INFRA-333
# wired checkpoint-docs's model via select_docs_reviewer_model(phase_class);
# INFRA-340 closes the remaining gap (F3) by wiring checkpoint-security via
# select_security_auditor_model(phase_class) and checkpoint-intent via
# select_intent_reviewer_model(phase_class) — all three checkpoint roles now
# resolve a real model instead of two of them hardcoding model=None.
# checkpoint-tag is an inline action and is NOT in _SPAWN_ACTIONS.
# spawn-spec-writer carries a model override and IS in _SPAWN_ACTIONS.
# INFRA-333: the model is now resolved via select_spec_writer_model(story_class)
# instead of a hardcoded "opus" literal — still resolves to opus for the one
# production case that exists today.
_SPAWN_ACTIONS: frozenset[str] = frozenset(
    {
        SPAWN_BUILDER,
        SPAWN_LOOP_BREAKER,
        SPAWN_REVIEWER,
        SPAWN_SECURITY_AUDITOR,
        SPAWN_INTENT_REVIEWER,
        SPAWN_SPEC_WRITER,
        CHECKPOINT_SECURITY,
        CHECKPOINT_INTENT,
        CHECKPOINT_DOCS,
    }
)

# Ordered sequence of checkpoint sub-actions emitted one per resolver call (RESOLVER-008).
# The harness writes the completed step into state.json["checkpoint_step"] after execution.
# ``checkpoint-tag`` is an inline action (NOT in _SPAWN_ACTIONS); all others may carry a model.
_CHECKPOINT_SEQUENCE: tuple[str, ...] = (
    CHECKPOINT_SECURITY,
    CHECKPOINT_INTENT,
    CHECKPOINT_DOCS,
    CHECKPOINT_TAG,
)

# Top-level keys that every action object must carry.
_REQUIRED_KEYS: frozenset[str] = frozenset({"action", "scalar", "model", "reason", "meta"})

# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def make_action(
    action: str,
    scalar: str = "",
    model: "str | None" = None,
    reason: str = "",
    meta: "dict | None" = None,
) -> dict:
    """Return a canonical action dict.

    The returned ``meta`` dict always carries ``schema_version == SCHEMA_VERSION``.
    The caller's ``meta`` dict is never mutated — a shallow copy is made first.

    Recognised optional meta fields (all optional except schema_version):
      - ``attempt``   (int)       — builder attempt number
      - ``gate``      (str)       — gate name that triggered the action
      - ``fail_rung`` (str)       — loop-breaker failure rung
      - ``warnings``  (list[str]) — advisory messages for the orchestrator
    """
    built_meta: dict = dict(meta) if meta is not None else {}
    built_meta["schema_version"] = SCHEMA_VERSION

    return {
        "action": action,
        "scalar": scalar,
        "model": model,
        "reason": reason,
        "meta": built_meta,
    }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate_action(obj: object) -> list[str]:
    """Return a list of human-readable violation strings for *obj*.

    An empty list means the object is valid.
    This is a pure function: no I/O, no global mutation.
    """
    violations: list[str] = []

    if not isinstance(obj, dict):
        violations.append(
            f"action object must be a dict; got {type(obj).__name__}"
        )
        return violations  # nothing further is checkable

    # --- Required top-level keys ---
    missing = _REQUIRED_KEYS - obj.keys()
    for key in sorted(missing):
        violations.append(f"missing required key '{key}'")

    # If top-level keys are missing we cannot safely check the values below.
    if missing:
        return violations

    # --- action value ---
    action = obj["action"]
    if action not in ACTIONS:
        violations.append(
            f"unknown action '{action}'; valid values are: "
            + ", ".join(sorted(ACTIONS))
        )

    # --- model constraint ---
    # model must be null for any action other than spawn-builder / spawn-loop-breaker.
    model = obj["model"]
    if action not in _SPAWN_ACTIONS and model is not None:
        violations.append(
            f"action '{action}' must have model=null; got model={model!r}"
        )

    # --- meta ---
    meta = obj["meta"]
    if not isinstance(meta, dict):
        violations.append(
            f"meta must be a dict; got {type(meta).__name__}"
        )
    else:
        if "schema_version" not in meta:
            violations.append("meta is missing required field 'schema_version'")
        elif meta["schema_version"] != SCHEMA_VERSION:
            violations.append(
                f"meta.schema_version is {meta['schema_version']!r}; "
                f"expected {SCHEMA_VERSION}"
            )

    return violations


# ---------------------------------------------------------------------------
# Pre-checkpoint guards (RESOLVER-008)
#
# Three deterministic, pure-read guards run when all phase stories are
# complete/deferred (Row 9 of the DP2 table).  Each guard is a standalone
# function so tests can exercise them directly.  The build-gate guard is
# injectable via ``gate_fn`` to avoid spawning a subprocess in unit tests.
# ---------------------------------------------------------------------------


def _phase_class_for(phase_path: "Path | None") -> str:
    """Read ``phase_class`` from *phase_path*'s frontmatter (INFRA-333).

    Returns ``model_selector.DEFAULT_PHASE_CLASS`` ("production") when
    *phase_path* is ``None``, the file is absent/unreadable, or the file
    carries no ``phase_class`` field — the same fail-safe default
    ``model_selector.select_intent_reviewer_model``/
    ``select_security_auditor_model`` already apply for an absent field.
    Used by Row 9's ``checkpoint-security``/``checkpoint-intent``/
    ``checkpoint-docs`` steps (``select_security_auditor_model``/
    ``select_intent_reviewer_model``/``select_docs_reviewer_model``).
    (Row 4b used this for its own gate-worker model selector through
    INFRA-333; INFRA-340 removed that call site — see the Row 4b comment.)
    """
    from model_selector import DEFAULT_PHASE_CLASS  # type: ignore[import]

    if phase_path is None:
        return DEFAULT_PHASE_CLASS
    try:
        from schema_validator import _parse_frontmatter  # type: ignore[import]

        text = Path(phase_path).read_text(encoding="utf-8")
        fm = _parse_frontmatter(text) or {}
        return str(fm.get("phase_class") or DEFAULT_PHASE_CLASS)
    except Exception:  # noqa: BLE001
        return DEFAULT_PHASE_CLASS


def _check_phase_completion(
    active_phase_file: "Path | None", project_dir: "Path | None" = None
) -> bool:
    """Return True if every story row in the phase manifest is complete or deferred.

    Reads the ``## Stories`` table of ``active_phase_file``.  Returns True
    when the file is absent or unreadable (fail-open) and when the Stories
    table is empty (vacuously complete).

    ``project_dir`` (INFRA-346, F13): when ``None`` (the default), behaviour
    is byte-identical to before this story — a bare ``"deferred"`` table
    cell counts as complete-for-guard-purposes, with no corroboration
    against any story file's own frontmatter. This preserves every existing
    call site/unit test that constructs a bare phase file with no sibling
    ``docs/stories/`` tree.

    When ``project_dir`` is given, a ``"deferred"`` row is additionally
    cross-checked against ``index_integrity.is_formally_deferred`` — the
    same predicate ``flex_build._deferral_gate_message`` already uses at
    ``checkpoint-tag`` — so this resolver-side guard can no longer diverge
    from the stronger, terminal-step gate and pass a phase that
    ``checkpoint-tag`` would refuse. A ``"deferred"`` row with no
    corroborating story file, or whose story file's own frontmatter
    disagrees, fails the guard (ideology § Accepted constraints, "Never
    silently pass contradictions"). ``"complete"`` rows are not re-verified
    against frontmatter — only ``"deferred"`` rows gain the cross-check.
    """
    if active_phase_file is None:
        return True
    try:
        text = Path(active_phase_file).read_text(encoding="utf-8")
    except OSError:
        return True  # fail open

    # INFRA-346 A2: when project_dir is given, build the {story_id: status}
    # frontmatter map once per call, before the Stories-table loop, scoped
    # to stories whose frontmatter `phase:` equals this phase's key — the
    # same restriction shape `flex_build._deferral_gate_message` already
    # applies.
    frontmatter_status_by_id: "dict[str, str] | None" = None
    if project_dir is not None:
        from schema_validator import _parse_frontmatter  # noqa: PLC0415

        phase_key = Path(active_phase_file).stem
        if phase_key.startswith("phase-"):
            phase_key = phase_key[len("phase-") :]

        frontmatter_status_by_id = {}
        stories_dir = Path(project_dir) / "docs" / "stories"
        if stories_dir.exists():
            for story_file in stories_dir.rglob("*.md"):
                try:
                    story_text = story_file.read_text(encoding="utf-8")
                except OSError:
                    continue
                fm = _parse_frontmatter(story_text) or {}
                story_phase = str(fm.get("phase") or "").strip()
                if story_phase != phase_key:
                    continue
                story_id = (fm.get("id") or story_file.stem).strip()
                status = (fm.get("status") or "").lower().strip()
                frontmatter_status_by_id[story_id] = status

    in_stories = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Stories"):
            in_stories = True
            continue
        if in_stories and stripped.startswith("## "):
            break  # left the Stories section
        if in_stories and stripped.startswith("|"):
            if "---" in stripped:
                continue  # separator row
            # split rationale: `table_utils.split_table_row`
            raw_cols = split_table_row(stripped)
            cols = [c.strip() for c in raw_cols if c.strip()]
            if not cols:
                continue
            if cols[0].lower() in ("id",):
                continue  # header row
            if len(cols) < 3:
                continue
            status = cols[2].lower()
            if status not in ("complete", "deferred"):
                return False
            if status == "deferred" and frontmatter_status_by_id is not None:
                from index_integrity import is_formally_deferred  # noqa: PLC0415

                story_id = cols[0]
                fm_status = frontmatter_status_by_id.get(story_id)
                if fm_status is None:
                    return False  # uncorroborated deferred claim — fail closed
                if not is_formally_deferred(fm_status, story_id, text):
                    return False

    return True


def _check_cer_do_now(project_dir: "Path") -> bool:
    """Return True when the CER Do Now backlog has no unresolved items.

    Scans ``docs/cer/backlog.md`` in ``project_dir``.  A row under
    ``## Do Now`` is unresolved unless it contains a resolution marker as
    defined by ``cer.is_resolution_marked`` (INFRA-322/CER-130) — the
    anchored, case-insensitive grammar that is the single source of truth
    for what counts as a ``RESOLVED``/``SUPERSEDED`` annotation. The
    keyword must *begin* an annotation segment (start of text, a `|` cell
    boundary, sentence-ending punctuation plus a space, or an
    emphasis/bracket opener); a bare case-sensitive substring test on
    ``"RESOLVED"``/``"SUPERSEDED"`` anywhere in the row was replaced
    because it was wrong in both directions — it blocked a title-case
    ``Resolved cp-34 — …`` row forever, and it silently waved through
    genuinely unresolved rows like ``UNRESOLVED …`` and
    ``this should be RESOLVED before cp``.

    A row is also exempted, before the resolution test runs, when it is
    the scaffolded empty-state placeholder row the
    ``docs/cer/backlog.md.j2`` template emits for an empty quadrant — via
    the shared predicate ``cer.is_placeholder_row`` (INFRA-294), which is
    this exemption's source of truth. Without it, every freshly
    bootstrapped project fails its first checkpoint on this guard alone.
    Returns True when the file is absent or unreadable (fail-open).

    The scan itself (header tracking, separator/header-row/placeholder-row
    skipping, the resolution-marker test) is hoisted into
    ``cer.find_open_do_now_rows`` (INFRA-313, Requires 1) — this function is
    now a thin file-read wrapper around it, so ``gate``/``checkpoint-tag``
    (``cer.py``'s consumers of the same predicate) cannot silently drift
    from the resolver's behaviour by each carrying their own copy of the
    scan.
    """
    from cer import find_open_do_now_rows  # type: ignore[import]

    cer_path = Path(project_dir) / "docs" / "cer" / "backlog.md"
    if not cer_path.exists():
        return True
    try:
        text = cer_path.read_text(encoding="utf-8")
    except OSError:
        return True  # fail open

    return len(find_open_do_now_rows(text)) == 0


def _run_build_gate_subprocess(project_dir: "Path") -> bool:
    """Run the project's build gate in ``project_dir`` (CER-072, INFRA-230).

    Two paths:

    - **Config-driven** — if ``project_dir/.companion/pairmode_context.json``
      exists, is valid JSON, and has a non-empty ``test_command`` string, that
      exact command is run via a shell (``shell=True``, since it may be an
      ``&&``-chained command like ``pnpm build && pnpm typecheck && pnpm test``).
      Its real exit code is honored (0 → gate green, non-zero → gate red).
    - **Fallback** — if that file is absent, unreadable, invalid JSON, or has
      no non-empty ``test_command``, the guard falls back to the historical
      hardcoded ``uv run pytest tests/pairmode/ -q --tb=no`` (flex-harness's
      own checkpoint gate, which has no ``pairmode_context.json``, is
      unaffected).

    Returns True (gate green) when the chosen command's exit code is 0.

    A genuine ``subprocess.TimeoutExpired`` (the command was still running
    when the deadline arrived) now returns **False** (gate red, fail closed)
    per INFRA-343 — this guard exists specifically to catch what the
    human-run reviewer suite might miss between review and checkpoint, and a
    suite that never finishes cannot honestly report green. Any other
    execution error (e.g. a missing ``uv``/``pytest`` binary, a bad ``cwd``)
    still returns True (advisory pass, CER-072/INFRA-230 bootstrap
    tolerance) — those indicate the tooling isn't runnable in this
    environment, not that the suite ran and something was wrong with it.
    """
    import os
    import subprocess

    env = os.environ.copy()
    home = env.get("HOME", "")
    if home:
        local_bin = str(Path(home) / ".local" / "bin")
        current_path = env.get("PATH", "")
        if local_bin not in current_path.split(":"):
            env["PATH"] = f"{local_bin}:{current_path}"

    # Config-driven path: read test_command from pairmode_context.json.
    test_command: "str | None" = None
    context_path = Path(project_dir) / ".companion" / "pairmode_context.json"
    if context_path.exists():
        try:
            data = json.loads(context_path.read_text(encoding="utf-8"))
            candidate = data.get("test_command")
            if isinstance(candidate, str) and candidate.strip():
                test_command = candidate
        except Exception:  # noqa: BLE001
            test_command = None  # malformed → fall through to pytest fallback

    try:
        if test_command is not None:
            result = subprocess.run(
                test_command,
                shell=True,
                cwd=str(project_dir),
                capture_output=True,
                timeout=600,
                env=env,
            )
        else:
            result = subprocess.run(
                ["uv", "run", "pytest", "tests/pairmode/", "-q", "--tb=no"],
                cwd=str(project_dir),
                capture_output=True,
                timeout=600,
                env=env,
            )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        # Fail closed: the suite was still running at the 600s deadline.
        # This guard's entire purpose is to catch what the human-run
        # reviewer suite might miss between review and checkpoint — a run
        # that never completes is itself a signal worth stopping on, not
        # something to wave through as green (INFRA-343).
        return False
    except Exception:  # noqa: BLE001
        # advisory: fail open — tooling/environment error, not a suite
        # result (CER-072/INFRA-230 bootstrap tolerance preserved)
        return True


def check_checkpoint_guards(
    project_dir: "str | Path | None",
    active_phase_file: "str | Path | None",
    *,
    gate_fn: "object" = None,
) -> dict:
    """Run the three pre-checkpoint guards (RESOLVER-008).

    Parameters
    ----------
    project_dir:
        Root of the project (used to locate ``docs/cer/backlog.md``).
    active_phase_file:
        Path to the active phase manifest (checked for story completion).
    gate_fn:
        Optional ``callable() -> bool`` for the build gate.  When ``None``
        the real ``uv run pytest`` subprocess runner is used.  Tests inject
        ``lambda: True`` to skip the live run.

    Returns
    -------
    dict
        ``{"ok": True}`` when all guards pass.
        ``{"ok": False, "failed_guard": str}`` on first failure.
        ``failed_guard`` is one of ``"phase-incomplete"``, ``"cer-do-now"``,
        or ``"build-gate"``.
    """
    project_path = Path(project_dir).resolve() if project_dir is not None else None
    phase_path = Path(active_phase_file) if active_phase_file is not None else None

    # Guard 1: all stories in phase are complete or deferred.
    if not _check_phase_completion(phase_path, project_path):
        return {"ok": False, "failed_guard": "phase-incomplete"}

    # Guard 2: no unresolved Do Now items in the CER backlog.
    if project_path is not None and not _check_cer_do_now(project_path):
        return {"ok": False, "failed_guard": "cer-do-now"}

    # Guard 3: build gate (injectable). A genuine ``subprocess.TimeoutExpired``
    # fails closed (INFRA-343) — the guard exists to catch what the
    # human-run reviewer suite might miss; any other exception remains
    # advisory fail-open (CER-072/INFRA-230 bootstrap tolerance).
    if gate_fn is not None:
        import subprocess

        try:
            gate_ok = bool(gate_fn())
        except subprocess.TimeoutExpired:
            gate_ok = False  # fail closed: the run never completed
        except Exception:  # noqa: BLE001
            gate_ok = True  # advisory: fail open
    elif project_path is not None:
        gate_ok = _run_build_gate_subprocess(project_path)
    else:
        gate_ok = True  # no project_dir → advisory pass

    if not gate_ok:
        return {"ok": False, "failed_guard": "build-gate"}

    return {"ok": True}


# ---------------------------------------------------------------------------
# Spec-stub heuristic (RESOLVER-009)
# ---------------------------------------------------------------------------


def _count_ensures_nonblank_lines(text: str) -> "int | None":
    """Count non-blank content lines inside the ``## Ensures`` section.

    Scans the text for a line beginning with ``## Ensures`` (case-sensitive),
    then counts non-blank lines until the next ``## `` heading or end of file.
    Returns ``None`` when the ``## Ensures`` section is absent entirely.

    Pure function: no I/O, no global state.  Used only by ``infer_position``
    to compute the ``needs_spec`` flag (RESOLVER-009).
    """
    in_ensures = False
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Ensures"):
            in_ensures = True
            continue
        if in_ensures:
            if stripped.startswith("## "):
                break  # left the Ensures section
            if stripped:
                count += 1
    return count if in_ensures else None


# ---------------------------------------------------------------------------
# Active-phase selector (RESOLVER-011 / CER-056)
# ---------------------------------------------------------------------------


def _resolve_active_phase(project_path: "Path") -> "Path | None":
    """Return the active phase file using ``is_phase_inactive`` (CER-056 fix).

    Reads ``docs/phases/index.md`` and finds the first candidate row whose
    status is **not** inactive.  Inactive statuses are ``complete``,
    ``deferred``, and ``backlog`` — as defined by
    ``index_integrity.is_phase_inactive``.

    Previously ``resolve_current_phase`` (flex_build) only skipped ``complete``
    phases, so a trailing ``deferred`` or ``backlog`` row would be returned as
    the active phase.  This helper fixes that by composing ``is_phase_inactive``
    from the same source of truth used by the index-integrity checker.

    Composes ``flex_build._active_phase_candidates`` (CER-077 — INFRA-265)
    for the row walk itself — no second, independently-maintained parse of
    ``docs/phases/index.md`` lives here. When more than one candidate row is
    flagged ``active`` (or ``active``-prefixed), raises
    ``flex_build.AmbiguousActivePhaseError`` rather than picking one, exactly
    as ``resolve_current_phase`` does; the two functions apply the same rule
    against the same candidate list. Multiple ``planned`` rows are not an
    error here either, for the same reason ``resolve_current_phase``
    tolerates them (see that function's docstring).

    Falls back to ``resolve_current_phase`` when no index file is present
    (legacy layout).

    Pure read: no writes.  Called only by ``infer_position``.
    """
    from flex_build import (  # type: ignore[import]
        _active_phase_candidates as _apc,
        AmbiguousActivePhaseError,
        resolve_current_phase as _rcp,
    )

    index_path = project_path / "docs" / "phases" / "index.md"
    if not index_path.exists():
        return _rcp(project_path)

    candidates = _apc(project_path)

    active_candidates = [
        ref
        for ref, status in candidates
        if status == "active" or status.startswith("active")
    ]
    if len(active_candidates) > 1:
        raise AmbiguousActivePhaseError(
            "CER-077: docs/phases/index.md has more than one row flagged "
            "'active' with an existing phase file: "
            f"{', '.join(active_candidates)}. Refusing to guess which "
            "phase is active — fix the index so only one row is active."
        )

    if candidates:
        active_phase_ref = candidates[0][0]  # first candidate row wins
        candidate = project_path / "docs" / "phases" / f"phase-{active_phase_ref}.md"
        if candidate.exists():
            return candidate

    return None


# ---------------------------------------------------------------------------
# Pre-build intent review (INFRA-315)
#
# Build standards opt-in: ``**Build standards**`` in ``CLAUDE.build.md`` is a
# one-line ``key=`value`` | key=`value` | ...`` block (INFRA-240 pattern,
# rendered from ``CLAUDE.build.md.j2:50``). ``intent_review`` joins that
# block; the only recognised value that turns this behaviour on is the
# literal string ``pre-build``. Any other value (or the key's absence, or
# the file's absence) leaves today's resolver output byte-identical —
# ``_intent_review_opt_in`` fails closed (returns False) on every read
# error, so a malformed/missing CLAUDE.build.md never silently opts a
# project in.
# ---------------------------------------------------------------------------

_BUILD_STANDARDS_KV_RE = re.compile(r"(\w+)=`([^`]*)`")


def _read_build_standards(project_dir: "Path") -> dict[str, str]:
    """Parse the ``**Build standards**`` key=value line from CLAUDE.build.md.

    Returns ``{}`` when the file is absent, unreadable, or carries no
    ``**Build standards**`` line. Pure read: no I/O other than the one
    ``read_text`` call.
    """
    claude_build_path = Path(project_dir) / "CLAUDE.build.md"
    try:
        text = claude_build_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    for line in text.splitlines():
        if line.strip().startswith("**Build standards**"):
            return dict(_BUILD_STANDARDS_KV_RE.findall(line))
    return {}


def _intent_review_opt_in(project_dir: "Path") -> bool:
    """Return True when ``intent_review=`pre-build`` is set in Build standards."""
    values = _read_build_standards(project_dir)
    return values.get("intent_review", "").strip() == "pre-build"


#: Story-table statuses that count as "not yet started" for freshness purposes.
_FRESH_STORY_STATUSES: frozenset[str] = frozenset({"", "draft", "planned"})


def _phase_is_fresh(active_phase_file: "Path", project_dir: "Path") -> bool:
    """Return True when no story in *active_phase_file* has started.

    "Started" means either: (a) the Stories table status is anything other
    than ``draft``/``planned``/blank, or (b) the git log carries build
    evidence for the story (INFRA-297's ``_has_story_commit``, reused here
    rather than forked — Requires 4). An empty Stories table is not fresh
    (vacuously false, mirroring the fail-closed posture of the opt-in
    check above): there is nothing to pre-build-review. Returns False (not
    fresh) on any read error — fail-closed, since this gate only ever
    *adds* a spawn, never removes one; failing open here would risk an
    infinite fresh-phase loop on a corrupt phase file.
    """
    from next_story import (  # type: ignore[import]
        _git_log_oneline,
        _has_story_commit,
        _parse_stories_table_statuses,
    )
    from story_resolver import _parse_stories_table  # type: ignore[import]

    try:
        text = Path(active_phase_file).read_text(encoding="utf-8")
    except OSError:
        return False

    story_ids = _parse_stories_table(text)
    if not story_ids:
        return False

    statuses = _parse_stories_table_statuses(text)
    for story_id in story_ids:
        if statuses.get(story_id, "") not in _FRESH_STORY_STATUSES:
            return False

    git_log = _git_log_oneline(Path(project_dir))
    for story_id in story_ids:
        if _has_story_commit(story_id, git_log):
            return False

    return True


# ---------------------------------------------------------------------------
# Position read-model (RESOLVER-002)
# ---------------------------------------------------------------------------

#: Outcome values returned in Position["last_attempt_outcome"]
OUTCOME_PASS: str = "PASS"
OUTCOME_FAIL: str = "FAIL"
OUTCOME_NONE: str = "none"       # No attempt yet (attempt_count == 0)
OUTCOME_UNKNOWN: str = "unknown"  # Cannot be determined from durable state


def infer_position(project_dir: "str | Path") -> dict:
    """Return a Position dict that describes the current build state.

    Reads only durable state (DP7 invariant): no file is written, no new
    private state is introduced.  If any required fact cannot be derived from
    existing durable state, the corresponding field is set to ``None`` or an
    appropriate default.

    Returned dict keys
    ------------------
    active_phase_file : Path | None
        The active phase file, or None when all phases are complete.
    next_story_id : str | None
        The next unbuilt story ID, or None when the phase is complete.
    next_story_file : str | None
        The resolved path to the next story file (str), or None.
    attempt_count : int
        Persisted attempt count for the next story (0 when no attempts yet).
    builder_model : str | None
        Selected builder model name (e.g. "sonnet", "opus", "haiku"), or None
        when no next story is known. INFRA-318: when the next story declares
        a `model:` frontmatter field, this already reflects the declared
        floor — an outright override at attempt 1, a floor (never a
        downgrade) on retry — via
        `model_selector.apply_declared_model_floor`.
    builder_model_reason : str | None
        Selection reason (e.g. "auto-baseline", "prompted-upgrade", or
        "story-declared" when a `model:` floor applied at attempt 1), or None.
    gate_stub : dict
        ``{"ok": bool, "blocked_reason": str}`` for the stub check.
    gate_schema : dict
        ``{"ok": bool, "blocked_reason": str}`` for the schema-introduces check.
    gate_auth : dict
        ``{"ok": bool, "blocked_reason": str}`` for the auth-gated check.
    last_attempt_outcome : str
        One of ``"PASS"``, ``"FAIL"``, ``"none"``, ``"unknown"``.
        - ``"PASS"``    — a ``story-<ID>`` commit exists in the git log.
        - ``"FAIL"``    — no commit, status still ``planned``, attempt_count > 0.
        - ``"none"``    — attempt_count == 0 (no attempt has been made).
        - ``"unknown"`` — state is ambiguous (e.g. story file unresolvable).
    needs_spec : bool
        True when the next story file's ``## Ensures`` section is absent or
        contains fewer than 5 non-blank lines (stub heuristic, RESOLVER-009).
        False when the section is present and sufficiently detailed.
        Defaults to False when ``next_story_id`` is None.
    claimed_stories : list[str]
        Sorted story IDs currently claimed by a live in-flight story
        worktree, per ``flex_build.claimed_story_ids`` (CER-095.1). Present
        on every call, including when ``active_phase_file`` is None.
    claimed_skipped : list[str]
        Claimed story IDs skipped while selecting ``next_story_id``, or —
        when ``all_stories_claimed`` is True — every remaining claimed story
        in the active phase's table.
    all_stories_claimed : bool
        True when a claim-filtered pass over the active phase found no
        story, but an unfiltered pass over the same phase did — i.e. every
        remaining story is claimed, not that the phase is complete.
    intent_review_opt_in : bool
        True when ``CLAUDE.build.md``'s Build standards line carries
        ``intent_review=`pre-build``` (INFRA-315).
    phase_is_fresh : bool
        True when no story in the active phase's Stories table has started
        (INFRA-315) — see ``_phase_is_fresh``.
    pre_build_intent_verdict : str | None
        The recorded pre-build intent-review verdict for the active phase's
        key (``state.json["pre_build_intent_review"][phase_key]``), or None
        when no review has been recorded yet (INFRA-315).
    gate_verdict : dict[str, str] | None
        The recorded gate-worker verdict map for ``next_story_id``
        (``state.json["gate_verdict"][next_story_id]``), or None when
        ``next_story_id`` is None or no verdict has been recorded yet for it
        (INFRA-341). Fail-open: any missing file, missing key, non-dict
        value, or parse error also yields None. INFRA-444: also None when
        the story file's current content hash no longer matches
        ``state.json["gate_verdict_story_hash"][next_story_id]`` recorded
        at verdict time — an edited story invalidates a stale verdict. A
        story file that cannot itself be hashed (unreadable) still trusts
        the recorded verdict unchanged (avoids a re-gate loop neither side
        can resolve).
    """
    from next_story import find_next_story  # type: ignore[import]
    from model_selector import select_builder_model  # type: ignore[import]
    from flex_build import (  # type: ignore[import]
        read_attempt_count,
        check_stub_gate,
        check_schema_gate_result,
        check_auth_gate_result,
        claimed_story_ids,
    )
    from schema_validator import _parse_frontmatter, VALID_MODEL_TIERS  # type: ignore[import]

    project_path = Path(project_dir).resolve()

    # ------------------------------------------------------------------
    # 0. In-flight claims (CER-095.1). Computed unconditionally so the three
    #    claim keys are present on every Position, even with no active phase.
    # ------------------------------------------------------------------
    try:
        claimed = claimed_story_ids(project_path)
    except Exception:  # noqa: BLE001
        claimed = set()
    claimed_stories: "list[str]" = sorted(claimed)
    claimed_skipped: "list[str]" = []
    all_stories_claimed: bool = False

    # ------------------------------------------------------------------
    # 1. Active phase (CER-056: uses is_phase_inactive to skip deferred/backlog)
    # ------------------------------------------------------------------
    active_phase_file: "Path | None" = _resolve_active_phase(project_path)

    # ------------------------------------------------------------------
    # 2. Next unbuilt story
    # ------------------------------------------------------------------
    next_story_id: "str | None" = None
    next_story_file: "str | None" = None
    story_class: str = "code"
    primary_files: "list[str]" = []
    needs_spec: bool = False  # RESOLVER-009: set below when story file is read
    # INFRA-318: story-declared `model:` floor, read alongside story_class /
    # primary_files below. None when absent or not a valid model tier — an
    # invalid value here means the story failed schema validation upstream,
    # so this resolver treats it fail-safe as "undeclared" rather than
    # guessing.
    declared_model: "str | None" = None

    if active_phase_file is not None:
        try:
            result = find_next_story(active_phase_file, project_path, claimed=claimed)
        except Exception:  # noqa: BLE001
            result = None

        if result is not None:
            claimed_skipped = list(result.get("claimed_skipped") or [])
        elif claimed:
            # The claim-filtered pass found nothing, but stories are claimed:
            # this may be "every remaining story is claimed" rather than
            # "phase complete" (A7/CER-095.1). Distinguish with a second,
            # unfiltered pass — strictly conditional so the extra
            # `_git_log_oneline` subprocess never runs on the hot path
            # (nothing claimed, or a story found on the first pass).
            try:
                unfiltered = find_next_story(active_phase_file, project_path)
            except Exception:  # noqa: BLE001
                unfiltered = None
            if unfiltered is not None:
                all_stories_claimed = True
                try:
                    from story_resolver import (  # type: ignore[import]
                        _parse_stories_table,
                    )

                    table_ids = set(
                        _parse_stories_table(
                            active_phase_file.read_text(encoding="utf-8")
                        )
                    )
                    claimed_skipped = sorted(claimed & table_ids)
                except Exception:  # noqa: BLE001
                    claimed_skipped = sorted(claimed)

        if result is not None:
            next_story_id = result.get("story_id")
            next_story_file = result.get("story_file")

            # Read story frontmatter to get story_class, primary_files, and
            # the needs_spec flag (RESOLVER-009).
            if next_story_file and next_story_file != "UNRESOLVED":
                try:
                    story_text = Path(next_story_file).read_text(encoding="utf-8")
                    fm = _parse_frontmatter(story_text) or {}
                    story_class = fm.get("story_class") or "code"
                    primary_files = fm.get("primary_files") or []
                    ensures_count = _count_ensures_nonblank_lines(story_text)
                    needs_spec = ensures_count is None or ensures_count < 5
                    _raw_declared_model = fm.get("model")
                    if (
                        isinstance(_raw_declared_model, str)
                        and _raw_declared_model in VALID_MODEL_TIERS
                    ):
                        declared_model = _raw_declared_model
                except OSError:
                    needs_spec = True  # fail-safe: unreadable file → treat as stub

    # ------------------------------------------------------------------
    # 3. Attempt count
    # ------------------------------------------------------------------
    attempt_count: int = 0
    if next_story_id is not None:
        attempt_count = read_attempt_count(next_story_id, project_path)

    # ------------------------------------------------------------------
    # 3b. Last-attempt outcome inference (DP3)
    #
    # Computed *before* model selection (§4) so the retry-tier composition
    # (CF-1 / CER-060, DP7.2) can select at the *next* attempt number on FAIL.
    #
    # PASS  — a story-<ID> commit exists (git-authoritative).
    # FAIL  — no commit + status still planned + attempt_count > 0
    # none  — attempt_count == 0 (first launch)
    # unknown — anything else
    # ------------------------------------------------------------------
    last_attempt_outcome: str = OUTCOME_UNKNOWN

    if next_story_id is None:
        # No active story — either all complete or phase empty.
        last_attempt_outcome = OUTCOME_NONE
    elif attempt_count == 0:
        last_attempt_outcome = OUTCOME_NONE
    else:
        # Check for a story-<ID> commit (git-authoritative).
        from next_story import _git_log_oneline, _has_story_commit  # type: ignore[import]
        git_log = _git_log_oneline(project_path)
        if _has_story_commit(next_story_id, git_log):
            last_attempt_outcome = OUTCOME_PASS
        else:
            # No commit, attempt_count > 0 → last attempt failed.
            last_attempt_outcome = OUTCOME_FAIL

    # ------------------------------------------------------------------
    # 4. Builder model selection
    #
    # DP7.2 (CF-1 ← CER-060): on inferred FAIL the Position must hold the model
    # for the *next* attempt so Row 5 can emit position.builder_model and the
    # selector becomes the single source of the retry tier.  Otherwise
    # (none/PASS/unknown) select at the current attempt as before.
    # ------------------------------------------------------------------
    builder_model: "str | None" = None
    builder_model_reason: "str | None" = None

    if next_story_id is not None:
        try:
            import json as _json
            import re as _re

            # Read protected files from .claude/settings.json (fail-safe).
            settings_path = project_path / ".claude" / "settings.json"
            protected_files: "list[str]" = []
            if settings_path.exists():
                try:
                    settings_data = _json.loads(settings_path.read_text(encoding="utf-8"))
                    deny_rules: "list[str]" = (
                        settings_data.get("permissions", {}).get("deny", [])
                    )
                    for rule in deny_rules:
                        m = _re.match(r"^\w+\((.+)\)$", rule)
                        if m:
                            protected_files.append(m.group(1))
                        else:
                            protected_files.append(rule)
                except (OSError, _json.JSONDecodeError):
                    pass

            effective_attempt = (
                attempt_count + 1
                if last_attempt_outcome == OUTCOME_FAIL
                else max(attempt_count, 1)
            )
            builder_model, builder_model_reason = select_builder_model(
                story_class,
                list(primary_files),
                protected_files,
                attempt_number=effective_attempt,
            )
            # INFRA-318: a story-declared `model:` floor overrides attempt 1
            # outright and floors (never lowers) attempt >= 2's retry tier.
            # No-op when declared_model is None — undeclared stories keep
            # byte-identical output (Ensures 2/5).
            from model_selector import apply_declared_model_floor  # type: ignore[import]

            builder_model, builder_model_reason = apply_declared_model_floor(
                builder_model,
                builder_model_reason,
                declared_model,
                effective_attempt,
            )
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # 5. Gate signals (deterministic read-only, no verdict)
    # ------------------------------------------------------------------
    _no_gate: dict = {"ok": True, "blocked_reason": ""}

    if next_story_id is not None:
        raw_stub = check_stub_gate(next_story_id, project_path)
        gate_stub: dict = {
            "ok": raw_stub.get("ok", True),
            "blocked_reason": (raw_stub.get("reasons") or [""])[0]
            if not raw_stub.get("ok", True)
            else "",
        }

        raw_schema = check_schema_gate_result(next_story_id, project_path)
        gate_schema: dict = {
            "ok": raw_schema.get("ok", True),
            "blocked_reason": raw_schema.get("blocked_reason", ""),
        }

        raw_auth = check_auth_gate_result(next_story_id, project_path)
        gate_auth: dict = {
            "ok": raw_auth.get("ok", True),
            "blocked_reason": raw_auth.get("blocked_reason", ""),
        }
    else:
        gate_stub = dict(_no_gate)
        gate_schema = dict(_no_gate)
        gate_auth = dict(_no_gate)

    # ------------------------------------------------------------------
    # 6. Checkpoint step (RESOLVER-007)
    #
    # Reads state.json["checkpoint_step"] — a list of completed step-ID
    # strings.  Defaults to [] when the key is absent or the state.json
    # cannot be read.  Pure read: this module never writes checkpoint_step.
    # ------------------------------------------------------------------
    checkpoint_step: "list[str]" = []
    try:
        import json as _json_cs

        state_path = project_path / ".companion" / "state.json"
        if state_path.exists():
            raw_state = _json_cs.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(raw_state, dict):
                # The active phase's own key, computed once and used by
                # either read path below (INFRA-283).
                _active_phase_key = ""
                if active_phase_file is not None:
                    _active_phase_key = Path(active_phase_file).stem
                    if _active_phase_key.startswith("phase-"):
                        _active_phase_key = _active_phase_key[len("phase-") :]

                raw_keyed = raw_state.get("checkpoint_steps")
                if isinstance(raw_keyed, dict):
                    # INFRA-283 (CER-095.4): the keyed record is the
                    # authority. Two phases checkpointing concurrently each
                    # get their own entry, so this call resolves the active
                    # phase's own list directly — no second index parse, no
                    # new I/O, and the CER-083 stamp comparison below is
                    # structurally unnecessary on this path: keying by the
                    # active phase's own key means a sibling phase's entry
                    # can never be mistaken for this one's.
                    raw_cs = raw_keyed.get(_active_phase_key)
                    if isinstance(raw_cs, list):
                        checkpoint_step = [s for s in raw_cs if isinstance(s, str)]
                    else:
                        checkpoint_step = []
                else:
                    # Legacy fallback: no keyed record present yet.
                    raw_cs = raw_state.get("checkpoint_step")
                    if isinstance(raw_cs, list):
                        checkpoint_step = [s for s in raw_cs if isinstance(s, str)]

                    # CER-083: a checkpoint_step list stamped for a phase
                    # other than the one currently active is stale —
                    # honouring it would silently skip the newly-active
                    # phase's checkpoint gates (the cp99→phase-100 incident).
                    # Compare the stamp against the active phase's own key; a
                    # mismatch clears the exposed list. Absent/empty stamp,
                    # or a stamp equal to the active phase key, means "trust
                    # the stored list" (backward compatible with state files
                    # written before this story). Pure read: this module
                    # never writes checkpoint_phase or the keyed record.
                    raw_phase_stamp = raw_state.get("checkpoint_phase")
                    if isinstance(raw_phase_stamp, str) and raw_phase_stamp:
                        if raw_phase_stamp != _active_phase_key:
                            checkpoint_step = []
    except Exception:  # noqa: BLE001
        pass

    # ------------------------------------------------------------------
    # 7. Pre-build intent review (INFRA-315)
    #
    # ``intent_review_opt_in`` and ``phase_is_fresh`` are pure-read
    # derivations (Build standards text + Stories table + git log).
    # ``pre_build_intent_verdict`` is the durable "already reviewed"
    # evidence: ``state.json["pre_build_intent_review"]`` is a
    # ``dict[phase_key, verdict_str]`` (mirrors the ``checkpoint_steps``
    # phase-keyed shape above, INFRA-283 pattern) written by
    # ``flex_build.py record-intent-review`` once the checkpoint-time
    # ``intent-reviewer`` spawn returns. Absent entry → None (not yet
    # reviewed). Pure read: this module never writes this key.
    # ------------------------------------------------------------------
    intent_review_opt_in: bool = _intent_review_opt_in(project_path)
    phase_is_fresh: bool = False
    if active_phase_file is not None:
        try:
            phase_is_fresh = _phase_is_fresh(Path(active_phase_file), project_path)
        except Exception:  # noqa: BLE001
            phase_is_fresh = False

    pre_build_intent_verdict: "str | None" = None
    if active_phase_file is not None:
        _review_phase_key = Path(active_phase_file).stem
        if _review_phase_key.startswith("phase-"):
            _review_phase_key = _review_phase_key[len("phase-") :]
        try:
            state_path2 = project_path / ".companion" / "state.json"
            if state_path2.exists():
                raw_state2 = json.loads(state_path2.read_text(encoding="utf-8"))
                if isinstance(raw_state2, dict):
                    reviews = raw_state2.get("pre_build_intent_review")
                    if isinstance(reviews, dict):
                        candidate_verdict = reviews.get(_review_phase_key)
                        if isinstance(candidate_verdict, str):
                            pre_build_intent_verdict = candidate_verdict
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # 8. Gate-worker verdict (INFRA-341)
    #
    # ``gate_verdict`` is the durable evidence a real gate-worker verdict
    # was recorded for ``next_story_id`` — ``state.json["gate_verdict"]`` is
    # a ``dict[story_id, verdict_map]`` written by
    # ``flex_build.py record-gate-verdict`` once the judged-gate-tripped
    # ``spawn-gate-worker`` spawn returns. Absent entry -> None (not yet
    # recorded). Mirrors ``pre_build_intent_verdict`` exactly (same
    # try/except Exception: pass shape, same isinstance guards on both the
    # outer dict and the per-story value). Pure read: this module never
    # writes this key.
    # ------------------------------------------------------------------
    # INFRA-444: a recorded verdict is trusted only while the story file's
    # content is byte-identical to what it was when the verdict was
    # recorded — an edit to the story spec after the verdict was judged
    # invalidates it, so a rewritten "## Ensures" can never be routed to
    # spawn-builder on the strength of a verdict that judged different text.
    gate_verdict: "dict[str, str] | None" = None
    if next_story_id is not None:
        try:
            state_path3 = project_path / ".companion" / "state.json"
            if state_path3.exists():
                raw_state3 = json.loads(state_path3.read_text(encoding="utf-8"))
                if isinstance(raw_state3, dict):
                    verdicts = raw_state3.get("gate_verdict")
                    if isinstance(verdicts, dict):
                        candidate_verdict_map = verdicts.get(next_story_id)
                        if isinstance(candidate_verdict_map, dict):
                            gate_verdict = candidate_verdict_map
                            current_hash = None
                            if next_story_file and next_story_file != "UNRESOLVED":
                                current_hash = story_content_hash(next_story_file)
                            if current_hash is not None:
                                hashes = raw_state3.get("gate_verdict_story_hash")
                                recorded_hash = (
                                    hashes.get(next_story_id)
                                    if isinstance(hashes, dict)
                                    else None
                                )
                                if recorded_hash is None or recorded_hash != current_hash:
                                    gate_verdict = None
        except Exception:  # noqa: BLE001
            pass

    return {
        "active_phase_file": active_phase_file,
        "next_story_id": next_story_id,
        "next_story_file": next_story_file,
        "attempt_count": attempt_count,
        "story_class": story_class,
        "builder_model": builder_model,
        "builder_model_reason": builder_model_reason,
        "gate_stub": gate_stub,
        "gate_schema": gate_schema,
        "gate_auth": gate_auth,
        "last_attempt_outcome": last_attempt_outcome,
        "checkpoint_step": checkpoint_step,
        "needs_spec": needs_spec,
        "claimed_stories": claimed_stories,
        "claimed_skipped": claimed_skipped,
        "all_stories_claimed": all_stories_claimed,
        "intent_review_opt_in": intent_review_opt_in,
        "phase_is_fresh": phase_is_fresh,
        "pre_build_intent_verdict": pre_build_intent_verdict,
        "gate_verdict": gate_verdict,
    }


# ---------------------------------------------------------------------------
# State machine (RESOLVER-003)
#
# Maps a Position → exactly one action via the 9-state DP2 table.
# Pure function — no I/O, no side effects.
# ---------------------------------------------------------------------------

#: Advisory signals that appear in meta.warnings[] but never change the action.
_ADVISORY_GUARDRAIL: str = "guardrail-fired"
_ADVISORY_CONTEXT: str = "context-budget-exceeded"


def resolve_next_action(
    position: dict,
    *,
    warnings: "list[str] | None" = None,
    gate_fn: "object" = None,
) -> dict:
    """Map a Position dict to a canonical action dict (RESOLVER-003, DP2).

    Parameters
    ----------
    position:
        A Position dict as returned by ``infer_position``.
    warnings:
        Optional list of advisory signal strings (e.g. ``["guardrail-fired"]``
        or ``["context-budget-exceeded"]``).  These are surfaced in
        ``meta.warnings[]`` and **never** change the emitted action (DP2).
    gate_fn:
        Optional ``callable() -> bool`` injected into the Row-9 build-gate
        guard.  When ``None`` the real ``uv run pytest`` subprocess is used.
        Tests pass ``lambda: True`` to skip the live run.

    Returns
    -------
    dict
        A canonical action dict produced by ``make_action``; always passes
        ``validate_action`` (returns ``[]``).

    DP2 state table (evaluated in precedence order)
    ------------------------------------------------
    Row 1  — no active phase / all complete                → done
    Row "all-stories-claimed" (CER-095.1) — no next story, but every
               remaining story in the phase table is claimed by an
               in-flight worktree; evaluated before Row 9 so a
               still-building phase never checkpoints → await-user
               (all-stories-claimed, meta.claimed_stories)
    Row 9  — all phase stories done → checkpoint routing (RESOLVER-008):
               guard fail → await-user (checkpoint-guard-failed:<which>)
               guards pass → next uncompleted checkpoint step
               all steps done → done
    Row PBI (INFRA-315) — opted-in (Build standards intent_review=`pre-build`)
               + phase_is_fresh + attempt_count == 0:
               no recorded verdict yet             → spawn-intent-reviewer
                                                       (scalar=phase key, model=null)
               recorded verdict PASS/ALIGNED        → falls through (Row 8/2, once only)
               recorded verdict anything else       → await-user
                                                       (pre-build-intent-review-flagged)
               Absent the opt-in (or any other value), this row never fires and
               resolver output is byte-identical to pre-INFRA-315 behaviour.
    Row 8  — story committed (PASS), more stories remain:
                                                              → spawn-builder (next story, attempt 1)
    Row 4  — any pre-flight gate blocked                   → await-user (gate-blocked:<which>)
    Row 3  — model reason == prompted-upgrade, counter 0   → await-user (model-upgrade)
    Row 2  — counter 0, auto model (RESOLVER-009 branch):
               needs_spec True                             → spawn-spec-writer (model=opus)
               needs_spec False                            → spawn-builder (attempt 1)
    Row 5  — counter 1, FAIL                               → spawn-builder (attempt 2, retry-upgrade)
    Row 6  — counter 2, FAIL                               → spawn-loop-breaker
    Row 7  — counter ≥ 3 or any other pause condition      → await-user (build-paused)

    DP4 binding property: rows 3, 4, 7 are judgment-handoff states — the
    resolver emits await-user and stops; it never computes the verdict.

    DP6: model is embedded only for auto-resolved spawn actions
    (``auto-baseline``, ``auto-downgrade``, ``retry-upgrade``).
    ``prompted-upgrade`` routes to await-user:model-upgrade with the suggested
    model in ``meta.suggested_model``; ``model`` field is None.

    scalar is set per DP1:
      - spawn actions: the target story ID
      - checkpoint: the phase key (phase file stem)
      - done / await-user: empty string
    """
    meta_base: dict = {}
    if warnings:
        meta_base["warnings"] = list(warnings)

    active_phase_file = position.get("active_phase_file")
    next_story_id: "str | None" = position.get("next_story_id")
    attempt_count: int = int(position.get("attempt_count") or 0)
    builder_model: "str | None" = position.get("builder_model")
    builder_model_reason: "str | None" = position.get("builder_model_reason")
    last_attempt_outcome: str = position.get("last_attempt_outcome") or OUTCOME_UNKNOWN
    gate_stub: dict = position.get("gate_stub") or {"ok": True, "blocked_reason": ""}
    gate_schema: dict = position.get("gate_schema") or {"ok": True, "blocked_reason": ""}
    gate_auth: dict = position.get("gate_auth") or {"ok": True, "blocked_reason": ""}
    claimed_stories: "list[str]" = list(position.get("claimed_stories") or [])
    claimed_skipped: "list[str]" = list(position.get("claimed_skipped") or [])
    all_stories_claimed: bool = bool(position.get("all_stories_claimed"))

    # ------------------------------------------------------------------
    # Row 1 — no active phase (all phases complete, or no phases at all)
    # ------------------------------------------------------------------
    if active_phase_file is None:
        return make_action(DONE, scalar="", model=None, reason="", meta=meta_base)

    # ------------------------------------------------------------------
    # All-stories-claimed (CER-095.1) — MUST be evaluated before Row 9.
    #
    # next_story_id is None here for two different reasons: the phase is
    # genuinely complete, or every remaining story is claimed by an
    # in-flight worktree. Row 9 treats "no next story" as "phase done" and
    # its terminal step tags the phase complete — if this branch were placed
    # below Row 9 it would be dead code and a still-building phase would get
    # checkpointed (the CER-077 class of failure: an irreversible write
    # derived from an ambiguous read). Placed here, a claimed-but-unfinished
    # phase stops and reports rather than silently proceeding to checkpoint.
    # ------------------------------------------------------------------
    if next_story_id is None and all_stories_claimed:
        return make_action(
            AWAIT_USER,
            scalar="",
            model=None,
            reason="all-stories-claimed",
            meta={**meta_base, "claimed_stories": claimed_stories},
        )

    # ------------------------------------------------------------------
    # Row 9 — active phase, no next story (all stories done → checkpoint)
    #
    # RESOLVER-008: run pre-checkpoint guards, then sequence the checkpoint
    # sub-actions one at a time based on position["checkpoint_step"].
    # ------------------------------------------------------------------
    if next_story_id is None:
        # Derive project_dir from the active phase file path.
        _phase_path = Path(active_phase_file) if active_phase_file is not None else None
        _project_dir = _phase_path.parent.parent.parent if _phase_path is not None else None

        guard_result = check_checkpoint_guards(
            _project_dir,
            _phase_path,
            gate_fn=gate_fn,
        )
        if not guard_result.get("ok", True):
            _failed = guard_result.get("failed_guard", "unknown")
            return make_action(
                AWAIT_USER,
                scalar="",
                model=None,
                reason=f"checkpoint-guard-failed:{_failed}",
                meta=meta_base,
            )

        # Guards pass — find the next uncompleted checkpoint step.
        _checkpoint_step: "list[str]" = list(position.get("checkpoint_step") or [])
        _remaining = [s for s in _CHECKPOINT_SEQUENCE if s not in _checkpoint_step]

        if not _remaining:
            # All checkpoint steps complete → done.
            return make_action(DONE, scalar="", model=None, reason="", meta=meta_base)

        _next_step = _remaining[0]
        # checkpoint-tag is NOT in _SPAWN_ACTIONS → model must be None.
        # checkpoint-security, checkpoint-intent, and checkpoint-docs each
        # resolve a real model via their respective model_selector functions
        # (INFRA-333 Ensures 2 for checkpoint-docs; INFRA-340 closes F3 for
        # checkpoint-security/checkpoint-intent, which previously carried
        # model=None unconditionally). phase_class is resolved once via
        # _phase_class_for, shared across all three branches.
        _checkpoint_model: "str | None" = None
        _checkpoint_phase_class = _phase_class_for(_phase_path)
        if _next_step == CHECKPOINT_DOCS:
            from model_selector import select_docs_reviewer_model  # type: ignore[import]

            _checkpoint_model, _ = select_docs_reviewer_model(_checkpoint_phase_class)
        elif _next_step == CHECKPOINT_SECURITY:
            from model_selector import select_security_auditor_model  # type: ignore[import]

            _checkpoint_model, _ = select_security_auditor_model(_checkpoint_phase_class)
        elif _next_step == CHECKPOINT_INTENT:
            from model_selector import select_intent_reviewer_model  # type: ignore[import]

            _checkpoint_model, _ = select_intent_reviewer_model(_checkpoint_phase_class)

        return make_action(
            _next_step,
            scalar="",
            model=_checkpoint_model,
            reason="",
            meta=meta_base,
        )

    # From here, next_story_id is non-None — there is an unbuilt story.

    # ------------------------------------------------------------------
    # A10 (CER-095.1): spawn actions surface any claim skips that shaped the
    # selection of next_story_id, so an operator watching the loop can see
    # that a story was passed over because it is already in flight. Absent
    # any skip, the meta key is omitted — an action for a phase with nothing
    # in flight looks exactly as it did before this story.
    # ------------------------------------------------------------------
    def _with_claimed_skipped(meta_dict: dict) -> dict:
        if claimed_skipped:
            meta_dict = dict(meta_dict)
            meta_dict["claimed_skipped"] = list(claimed_skipped)
        return meta_dict

    # ------------------------------------------------------------------
    # Row PBI — pre-build intent review (INFRA-315).
    #
    # Evaluated before Row 8/Row 2 (Instructions 1: "add the new row above
    # the spawn-builder rows"). Guarded by three independent conditions, ALL
    # of which must hold for this row to fire at all:
    #   - opted in (Build standards intent_review=`pre-build`)
    #   - phase_is_fresh (no story in the phase has started — Ensures 3)
    #   - attempt_count == 0 (belt-and-suspenders: a fresh phase's first
    #     story can only ever be at attempt 0 by definition, but this keeps
    #     the guard self-contained rather than relying solely on
    #     phase_is_fresh's git-log scan)
    #
    # Without the opt-in (or any value other than the literal "pre-build"),
    # this whole block is skipped and resolution falls straight through to
    # Row 8/Row 4/Row 3/Row 2 exactly as before this story (Ensures 1).
    # ------------------------------------------------------------------
    intent_review_opt_in: bool = bool(position.get("intent_review_opt_in"))
    phase_is_fresh: bool = bool(position.get("phase_is_fresh"))
    pre_build_intent_verdict: "str | None" = position.get("pre_build_intent_verdict")

    if intent_review_opt_in and phase_is_fresh and attempt_count == 0:
        _phase_key = Path(active_phase_file).stem
        if _phase_key.startswith("phase-"):
            _phase_key = _phase_key[len("phase-") :]

        if pre_build_intent_verdict is None:
            # No review recorded yet for this phase — spawn it once, before
            # any builder. model=null (Requires 1: the model-null rule for
            # non-builder spawns) — unlike checkpoint-time's checkpoint-intent
            # (which resolves a model via select_intent_reviewer_model, INFRA-340),
            # this emission carries no model override.
            return make_action(
                SPAWN_INTENT_REVIEWER,
                scalar=_phase_key,
                model=None,
                reason="pre-build-intent-review",
                meta=meta_base,
            )

        # A verdict is recorded (Requires 3 evidence). Ensures 4: mirrors
        # the PASS/ALIGNED-clean vs FAIL/flag-block shape of the
        # checkpoint-time intent-review verdict handling (worker_result's
        # REVIEW-RESULT enum — PASS, FAIL, ALIGNED) rather than forking a
        # new vocabulary. PASS/ALIGNED falls through to normal resolution
        # below (Row 8/Row 2) — this is what makes the emission fire only
        # once per phase (Ensures 2). Anything else (FAIL, or an
        # unrecognised string) is spec drift — an operator decision, not an
        # auto-fix — and blocks with await-user (Ensures 4).
        if pre_build_intent_verdict not in ("PASS", "ALIGNED"):
            meta = dict(meta_base)
            meta["pre_build_intent_verdict"] = pre_build_intent_verdict
            return make_action(
                AWAIT_USER,
                scalar="",
                model=None,
                reason="pre-build-intent-review-flagged",
                meta=meta,
            )
        # else: PASS/ALIGNED — fall through to Row 8 / Row 4 / Row 3 / Row 2.

    # ------------------------------------------------------------------
    # Row 8 — story just committed (PASS) but more stories remain.
    # The orchestrator hasn't cleared the counter yet, so we check outcome.
    # Attempt number for the next story resets to 1.
    #
    # INFRA-339 removed the INFRA-316 between-story context-etiquette check
    # that used to sit here (see the PAUSE_CONTEXT constant's declaration
    # comment above for why) — this seam is unconditional again, exactly as
    # it was before INFRA-316.
    # ------------------------------------------------------------------
    if last_attempt_outcome == OUTCOME_PASS:
        meta: dict = dict(meta_base)
        meta["attempt"] = 1
        return make_action(
            SPAWN_BUILDER,
            scalar=next_story_id,
            model=builder_model,
            reason=builder_model_reason or "auto-baseline",
            meta=_with_claimed_skipped(meta),
        )

    # ------------------------------------------------------------------
    # Row 4 — pre-flight gate blocked (DP2 split by DP2 boundary)
    #
    # stub  — mechanical gate: emit await-user directly (no worker).
    # schema / auth — judged gates: emit spawn-gate-worker so the gate worker
    #   can evaluate and return a verdict.  The safe-clear seam (DP4.5) fires
    #   here — budget hooks fire before any mutation.  Re-emission is
    #   idempotent across /clear (DP4.3).
    # ------------------------------------------------------------------
    # 4a. stub (mechanical — await-user directly)
    if not gate_stub.get("ok", True):
        meta = dict(meta_base)
        meta["gate"] = "stub"
        meta["gate_reason"] = gate_stub.get("blocked_reason", "")
        return make_action(
            AWAIT_USER,
            scalar="",
            model=None,
            reason="gate-blocked:stub",
            meta=meta,
        )

    # 4b. schema / auth (judged gates — spawn-gate-worker)
    judged_tripped = [
        name for name, gate_dict in (("schema", gate_schema), ("auth", gate_auth))
        if not gate_dict.get("ok", True)
    ]
    if judged_tripped:
        meta = dict(meta_base)
        meta["gates_tripped"] = judged_tripped
        meta["gate_reasons"] = {
            name: (gate_schema if name == "schema" else gate_auth).get("blocked_reason", "")
            for name in judged_tripped
        }
        # INFRA-340: no model_selector call is made here. INFRA-333 had
        # called this role's phase_class-keyed selector in model_selector.py
        # and surfaced its result as two advisory `meta` keys, but nothing
        # consumed them (the action's `model` field stays None —
        # validate_action requires model=null for any action outside
        # `_SPAWN_ACTIONS`, and spawn-gate-worker is deliberately not a
        # member — see the SPAWN_GATE_WORKER comment above and
        # test_spawn_gate_worker_with_model_fails_validate). Per the
        # Phase-117 cold-eyes review (F4), a computed-and-discarded value is
        # worse than not calling the selector at all, so this story removed
        # the call site. The selector function itself remains defined in
        # model_selector.py for a future real consumer (see
        # docs/stories/INFRA/INFRA-340.md).
        #
        # INFRA-341: this is the livelock fix (F8 of the phase-117 cold-eyes
        # review). Once a real gate-worker verdict has been recorded for
        # this story (``position["gate_verdict"]`` is not None), apply the
        # existing DP3.2 aggregation (``route_gate_verdict``) to it instead
        # of re-emitting spawn-gate-worker again — routing to await-user on
        # any block, or spawn-builder on flag/clean. The first poll after a
        # judged gate trips still spawns the gate worker (no verdict
        # recorded yet -> falls through below, unchanged); every poll after
        # the orchestrator records that worker's verdict resolves instead of
        # looping.
        if position.get("gate_verdict") is not None:
            return route_gate_verdict(
                position["gate_verdict"],
                next_story_id,
                meta_base=_with_claimed_skipped(meta),
            )
        return make_action(
            SPAWN_GATE_WORKER,
            scalar=next_story_id,
            model=None,
            reason="judged-gate-tripped",
            meta=_with_claimed_skipped(meta),
        )

    # ------------------------------------------------------------------
    # Row 3 — model selection requires user judgment (prompted-upgrade)
    # Only applies at attempt 0 (first attempt decision).
    # ------------------------------------------------------------------
    if builder_model_reason == "prompted-upgrade" and attempt_count == 0:
        meta = dict(meta_base)
        meta["attempt"] = 1
        if builder_model is not None:
            meta["suggested_model"] = builder_model
        return make_action(
            AWAIT_USER,
            scalar="",
            model=None,
            reason="model-upgrade",
            meta=meta,
        )

    # ------------------------------------------------------------------
    # Row 2 — first attempt, auto model (counter 0, no gate blocked, auto reason)
    #
    # Row-2 branch (RESOLVER-009): story is a spec stub → spawn-spec-writer.
    # The spec-writer elaborates the story before a builder is spawned.
    # INFRA-333: the model is now resolved via select_spec_writer_model
    # instead of the hardcoded model="opus" literal this branch used to
    # carry — the current single known case (attempt 1, any story_class)
    # still resolves to "opus" (Ensures 3), so this is a refactor of the
    # call site onto the shared mechanism, not a behavior change.
    # ------------------------------------------------------------------
    if attempt_count == 0:
        needs_spec: bool = bool(position.get("needs_spec", False))
        if needs_spec:
            from model_selector import select_spec_writer_model  # type: ignore[import]

            _spec_story_class = str(position.get("story_class") or "code")
            _spec_writer_model, _ = select_spec_writer_model(_spec_story_class)
            return make_action(
                SPAWN_SPEC_WRITER,
                scalar=next_story_id,
                model=_spec_writer_model,
                reason="needs-spec",
                meta=_with_claimed_skipped(meta_base),
            )
        meta = dict(meta_base)
        meta["attempt"] = 1
        return make_action(
            SPAWN_BUILDER,
            scalar=next_story_id,
            model=builder_model,
            reason=builder_model_reason or "auto-baseline",
            meta=_with_claimed_skipped(meta),
        )

    # ------------------------------------------------------------------
    # Rows 5, 6, 7 — FAIL ladder (attempt_count >= 1, no commit)
    # ------------------------------------------------------------------

    # Row 5 — attempt 1 cycle failed → spawn attempt 2.
    #
    # DP7.2 (CF-1 ← CER-060): the retry tier is sourced from the Position's
    # builder_model / builder_model_reason (computed at attempt_count + 1 on
    # FAIL in infer_position §4), making the selector the single source of the
    # retry tier rather than hardcoding opus / retry-upgrade in two places.
    # Defensive fallback only if the Position carries no model (e.g. a directly
    # constructed Position in a test).
    if attempt_count == 1 and last_attempt_outcome == OUTCOME_FAIL:
        meta = dict(meta_base)
        meta["attempt"] = 2
        meta["fail_rung"] = "single-fail"
        return make_action(
            SPAWN_BUILDER,
            scalar=next_story_id,
            model=builder_model if builder_model is not None else "opus",
            reason=builder_model_reason if builder_model is not None else "retry-upgrade",
            meta=_with_claimed_skipped(meta),
        )

    # Row 6 — attempt 2 failed → loop-breaker
    if attempt_count == 2 and last_attempt_outcome == OUTCOME_FAIL:
        from model_selector import select_loop_breaker_model  # type: ignore[import]

        meta = dict(meta_base)
        meta["attempt"] = 3
        meta["fail_rung"] = "double-fail"
        loop_breaker_model, _loop_breaker_reason = select_loop_breaker_model()

        # INFRA-328: surface the most recent FAIL attempt's recorded
        # fail_cause (effort.db's `notes` column, written by
        # subagent_transcript.record_attempt_from_transcript) as this
        # action's `reason`, so the orchestrator can construct the
        # `LOOP-BREAKER: [error] | FILE: [file:line] | TRIED: [what
        # failed]` prompt CLAUDE.md's loop-breaker mode requires instead
        # of dispatching with a bare empty string. `notes` is already a
        # single free-text field that naturally embeds a file reference
        # when one is available (e.g. "FAIL-CAUSE: ... file:line ..."),
        # so no separate FILE extraction is attempted here.
        #
        # Fails open (Ensures): any error resolving project_dir/db path,
        # an empty/missing effort.db, no FAIL rows, or a FAIL row with no
        # notes all silently degrade to reason="" — the pre-INFRA-328
        # behavior. This branch never blocks or downgrades the action.
        fail_cause = ""
        try:
            import effort_db  # type: ignore[import]

            _phase_path = (
                Path(active_phase_file) if active_phase_file is not None else None
            )
            _project_dir = (
                _phase_path.parent.parent.parent if _phase_path is not None else None
            )
            if _project_dir is not None:
                db_path = effort_db.resolve_effort_db_path(Path(_project_dir).resolve())
                rows = effort_db.query_by_story(db_path, next_story_id)
                fail_rows = [r for r in rows if r.get("outcome") == OUTCOME_FAIL]
                if fail_rows:
                    notes = fail_rows[-1].get("notes")
                    if notes:
                        fail_cause = str(notes)
        except Exception:  # noqa: BLE001
            fail_cause = ""

        return make_action(
            SPAWN_LOOP_BREAKER,
            scalar=next_story_id,
            model=loop_breaker_model,
            reason=fail_cause,
            meta=_with_claimed_skipped(meta),
        )

    # Row 7 — attempt 3+ failed (or any other pause: user-pause, DEVELOPER-ACTION)
    meta = dict(meta_base)
    meta["attempt"] = attempt_count + 1
    meta["fail_rung"] = "triple-fail-or-pause"
    return make_action(
        AWAIT_USER,
        scalar="",
        model=None,
        reason="build-paused",
        meta=meta,
    )


# ---------------------------------------------------------------------------
# Gate-worker verdict helpers (RESOLVER-005, DP3 / DP6.2)
#
# These are module-level pure functions (no I/O).  The resolver state machine
# decides *whether* to spawn the gate worker; these helpers decide *what the
# verdict means* once the worker returns.  The separation mirrors HARNESS001's
# grammar/state-machine boundary.
# ---------------------------------------------------------------------------


def parse_worker_verdict_json(text: str) -> dict:
    """Parse gate worker JSON stdout into a per-gate verdict map (RESOLVER-013).

    Workers emit a single JSON object on stdout with keys ``schema``, ``auth``,
    and ``stub``.  Values are ``"clean"`` or ``"block:<reason>"``.  All other
    output goes to stderr.

    On :exc:`json.JSONDecodeError` or a missing required key, all gates are
    blocked (fail-closed) with ``reason="malformed-verdict"``.

    Example valid input::

        {"schema": "clean", "auth": "block:no-owner-check", "stub": "clean"}

    Returns a dict with exactly the keys ``schema``, ``auth``, and ``stub``.
    """
    _FAIL_CLOSED = {
        "schema": "block:malformed-verdict",
        "auth": "block:malformed-verdict",
        "stub": "block:malformed-verdict",
    }
    _REQUIRED_KEYS = {"schema", "auth", "stub"}
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return dict(_FAIL_CLOSED)
    if not isinstance(result, dict) or not _REQUIRED_KEYS.issubset(result.keys()):
        return dict(_FAIL_CLOSED)
    return {k: result[k] for k in _REQUIRED_KEYS}


def route_gate_verdict(
    verdict_map: dict,
    next_story_id: str,
    *,
    meta_base: "dict | None" = None,
) -> dict:
    """Apply the DP3.2 aggregation rule to a verdict map and return an action.

    DP3.2 precedence:
    - Any ``block`` verdict → ``await-user`` with ``reason="gate-blocked:<gate(s)>"``
      and the worker reason(s) carried in ``meta.gate_block_reasons``.
    - Else any ``flag`` verdict → ``spawn-builder`` (proceed) with the flag
      reason(s) appended to ``meta.warnings[]``.
    - Else all ``clean`` → ``spawn-builder`` (proceed).

    Parameters
    ----------
    verdict_map:
        Per-gate verdict dict as returned by :func:`parse_worker_verdict_json`
        or injected directly in tests.
    next_story_id:
        The story ID to use as ``scalar`` for spawn-builder actions.
    meta_base:
        Optional base meta dict (e.g. carrying existing ``warnings``).

    Returns
    -------
    dict
        A canonical action dict produced by :func:`make_action`; always passes
        :func:`validate_action` (returns ``[]``).
    """
    from gate_verdict import parse_verdict, VERBS  # type: ignore[import]  # noqa: F401

    _meta: dict = dict(meta_base) if meta_base is not None else {}
    _meta["verdict_map"] = dict(verdict_map)

    # Collect block and flag verdicts.
    block_gates: list[str] = []
    block_reasons: dict[str, str] = {}
    flag_gates: list[str] = []
    flag_reasons: dict[str, str] = {}

    for gate, verdict_str in verdict_map.items():
        verb, reason = parse_verdict(verdict_str)
        if verb == "block":
            block_gates.append(gate)
            block_reasons[gate] = reason
        elif verb == "flag":
            flag_gates.append(gate)
            flag_reasons[gate] = reason

    # Any block → await-user.
    if block_gates:
        gate_label = ":".join(sorted(block_gates))
        meta = dict(_meta)
        meta["gate_block_reasons"] = block_reasons
        return make_action(
            AWAIT_USER,
            scalar="",
            model=None,
            reason=f"gate-blocked:{gate_label}",
            meta=meta,
        )

    # Any flag → spawn-builder, flag reasons in warnings[].
    if flag_gates:
        meta = dict(_meta)
        existing_warnings: list = list(meta.get("warnings") or [])
        for gate in sorted(flag_gates):
            existing_warnings.append(f"gate-flag:{gate}:{flag_reasons[gate]}")
        meta["warnings"] = existing_warnings
        return make_action(
            SPAWN_BUILDER,
            scalar=next_story_id,
            model=None,
            reason="gate-flag-proceed",
            meta=meta,
        )

    # All clean → spawn-builder.
    return make_action(
        SPAWN_BUILDER,
        scalar=next_story_id,
        model=None,
        reason="gate-clean-proceed",
        meta=_meta,
    )

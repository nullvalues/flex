"""
next_action.py — Action grammar and position-inference read-model for the
next-action resolver (RESOLVER-001, RESOLVER-002, RESOLVER-003, RESOLVER-005).

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
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow sibling imports when this module is imported from the scripts directory.
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION: int = 1

# ---------------------------------------------------------------------------
# Action vocabulary (closed set for Era 003; designed to be extended later)
# ---------------------------------------------------------------------------

SPAWN_BUILDER: str = "spawn-builder"
SPAWN_LOOP_BREAKER: str = "spawn-loop-breaker"
SPAWN_GATE_WORKER: str = "spawn-gate-worker"
CHECKPOINT: str = "checkpoint"
AWAIT_USER: str = "await-user"
DONE: str = "done"

ACTIONS: frozenset[str] = frozenset(
    {SPAWN_BUILDER, SPAWN_LOOP_BREAKER, SPAWN_GATE_WORKER, CHECKPOINT, AWAIT_USER, DONE}
)

# Actions for which model may be non-null (auto-resolved spawn actions only).
# spawn-gate-worker carries no builder model (the gate worker tier is not a
# builder-model decision), so it is NOT in _SPAWN_ACTIONS — model must be None.
_SPAWN_ACTIONS: frozenset[str] = frozenset({SPAWN_BUILDER, SPAWN_LOOP_BREAKER})

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
        when no next story is known.
    builder_model_reason : str | None
        Selection reason (e.g. "auto-baseline", "prompted-upgrade"), or None.
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
    """
    from next_story import find_next_story  # type: ignore[import]
    from model_selector import select_builder_model  # type: ignore[import]
    from flex_build import (  # type: ignore[import]
        resolve_current_phase,
        read_attempt_count,
        check_stub_gate,
        check_schema_gate_result,
        check_auth_gate_result,
    )
    from schema_validator import _parse_frontmatter  # type: ignore[import]

    project_path = Path(project_dir).resolve()

    # ------------------------------------------------------------------
    # 1. Active phase
    # ------------------------------------------------------------------
    active_phase_file: "Path | None" = resolve_current_phase(project_path)

    # ------------------------------------------------------------------
    # 2. Next unbuilt story
    # ------------------------------------------------------------------
    next_story_id: "str | None" = None
    next_story_file: "str | None" = None
    story_class: str = "code"
    primary_files: "list[str]" = []

    if active_phase_file is not None:
        try:
            result = find_next_story(active_phase_file, project_path)
        except Exception:  # noqa: BLE001
            result = None

        if result is not None:
            next_story_id = result.get("story_id")
            next_story_file = result.get("story_file")

            # Read story frontmatter to get story_class and primary_files.
            if next_story_file and next_story_file != "UNRESOLVED":
                try:
                    story_text = Path(next_story_file).read_text(encoding="utf-8")
                    fm = _parse_frontmatter(story_text) or {}
                    story_class = fm.get("story_class") or "code"
                    primary_files = fm.get("primary_files") or []
                except OSError:
                    pass

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

    return {
        "active_phase_file": active_phase_file,
        "next_story_id": next_story_id,
        "next_story_file": next_story_file,
        "attempt_count": attempt_count,
        "builder_model": builder_model,
        "builder_model_reason": builder_model_reason,
        "gate_stub": gate_stub,
        "gate_schema": gate_schema,
        "gate_auth": gate_auth,
        "last_attempt_outcome": last_attempt_outcome,
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


def resolve_next_action(position: dict, *, warnings: "list[str] | None" = None) -> dict:
    """Map a Position dict to a canonical action dict (RESOLVER-003, DP2).

    Parameters
    ----------
    position:
        A Position dict as returned by ``infer_position``.
    warnings:
        Optional list of advisory signal strings (e.g. ``["guardrail-fired"]``
        or ``["context-budget-exceeded"]``).  These are surfaced in
        ``meta.warnings[]`` and **never** change the emitted action (DP2).

    Returns
    -------
    dict
        A canonical action dict produced by ``make_action``; always passes
        ``validate_action`` (returns ``[]``).

    DP2 state table (evaluated in precedence order)
    ------------------------------------------------
    Row 1  — no active phase / all complete                → done
    Row 9  — last story committed (PASS, no next story)    → checkpoint
    Row 8  — story committed (PASS), more stories remain   → spawn-builder (next story, attempt 1)
    Row 4  — any pre-flight gate blocked                   → await-user (gate-blocked:<which>)
    Row 3  — model reason == prompted-upgrade, counter 0   → await-user (model-upgrade)
    Row 2  — counter 0, auto model                         → spawn-builder (attempt 1)
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

    # ------------------------------------------------------------------
    # Row 1 — no active phase (all phases complete, or no phases at all)
    # ------------------------------------------------------------------
    if active_phase_file is None:
        return make_action(DONE, scalar="", model=None, reason="", meta=meta_base)

    # ------------------------------------------------------------------
    # Row 9 — active phase, no next story (last story committed → checkpoint)
    # Row also covers all-stories-complete within the active phase.
    # ------------------------------------------------------------------
    if next_story_id is None:
        phase_key = active_phase_file.stem if hasattr(active_phase_file, "stem") else str(active_phase_file)
        return make_action(
            CHECKPOINT,
            scalar=phase_key,
            model=None,
            reason="",
            meta=meta_base,
        )

    # From here, next_story_id is non-None — there is an unbuilt story.

    # ------------------------------------------------------------------
    # Row 8 — story just committed (PASS) but more stories remain.
    # The orchestrator hasn't cleared the counter yet, so we check outcome.
    # Attempt number for the next story resets to 1.
    # ------------------------------------------------------------------
    if last_attempt_outcome == OUTCOME_PASS:
        meta: dict = dict(meta_base)
        meta["attempt"] = 1
        return make_action(
            SPAWN_BUILDER,
            scalar=next_story_id,
            model=builder_model,
            reason=builder_model_reason or "auto-baseline",
            meta=meta,
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
        return make_action(
            SPAWN_GATE_WORKER,
            scalar=next_story_id,
            model=None,
            reason="judged-gate-tripped",
            meta=meta,
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
    # ------------------------------------------------------------------
    if attempt_count == 0:
        meta = dict(meta_base)
        meta["attempt"] = 1
        return make_action(
            SPAWN_BUILDER,
            scalar=next_story_id,
            model=builder_model,
            reason=builder_model_reason or "auto-baseline",
            meta=meta,
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
            meta=meta,
        )

    # Row 6 — attempt 2 failed → loop-breaker
    if attempt_count == 2 and last_attempt_outcome == OUTCOME_FAIL:
        meta = dict(meta_base)
        meta["attempt"] = 3
        meta["fail_rung"] = "double-fail"
        return make_action(
            SPAWN_LOOP_BREAKER,
            scalar=next_story_id,
            model="opus",
            reason="",
            meta=meta,
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


def parse_worker_verdict_text(text: str) -> dict:
    """Parse a worker's text return into a per-gate verdict map (DP6.2).

    The worker returns one ``gate: verdict`` line per judged gate.  Lines not
    matching that pattern are ignored so the format is forward-compatible.

    Example input::

        schema: block:missing management surface story
        auth: clean

    Returns a dict ``{"schema": "block:missing management surface story",
    "auth": "clean"}``.

    Imports ``gate_verdict.JUDGED_GATES`` to constrain which keys are accepted;
    unknown gate names are silently skipped.  The returned dict is suitable for
    direct use with :func:`route_gate_verdict` and
    ``gate_verdict.validate_verdict_map``.
    """
    from gate_verdict import JUDGED_GATES  # type: ignore[import]

    result: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        gate_name, _, verdict = line.partition(":")
        gate_name = gate_name.strip()
        # Re-attach the colon separator for block/flag payloads.
        verdict_str = verdict.strip()
        if gate_name in JUDGED_GATES:
            result[gate_name] = verdict_str
    return result


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
        Per-gate verdict dict as returned by :func:`parse_worker_verdict_text`
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

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
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow sibling imports when this module is imported from the scripts directory.
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION: int = 4

# ---------------------------------------------------------------------------
# Action vocabulary (closed set for Era 003; designed to be extended later)
# ---------------------------------------------------------------------------

SPAWN_BUILDER: str = "spawn-builder"
SPAWN_LOOP_BREAKER: str = "spawn-loop-breaker"
SPAWN_GATE_WORKER: str = "spawn-gate-worker"
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
# spawn-reviewer, spawn-security-auditor, and spawn-intent-reviewer carry a
# model override (checkpoint-agent model selection) and ARE in _SPAWN_ACTIONS.
# checkpoint-security, checkpoint-intent, checkpoint-docs carry a model override
# (checkpoint-agent model selection) and ARE in _SPAWN_ACTIONS.
# checkpoint-tag is an inline action and is NOT in _SPAWN_ACTIONS.
# spawn-spec-writer carries a model override (opus, for spec elaboration) and
# IS in _SPAWN_ACTIONS.
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


def _check_phase_completion(active_phase_file: "Path | None") -> bool:
    """Return True if every story row in the phase manifest is complete or deferred.

    Reads the ``## Stories`` table of ``active_phase_file``.  Returns True
    when the file is absent or unreadable (fail-open) and when the Stories
    table is empty (vacuously complete).
    """
    if active_phase_file is None:
        return True
    try:
        text = Path(active_phase_file).read_text(encoding="utf-8")
    except OSError:
        return True  # fail open

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
            cols = [c.strip() for c in stripped.split("|") if c.strip()]
            if not cols:
                continue
            if cols[0].lower() in ("id",):
                continue  # header row
            if len(cols) < 3:
                continue
            status = cols[2].lower()
            if status not in ("complete", "deferred"):
                return False

    return True


def _check_cer_do_now(project_dir: "Path") -> bool:
    """Return True when the CER Do Now backlog has no unresolved items.

    Scans ``docs/cer/backlog.md`` in ``project_dir``.  A row under
    ``## Do Now`` without ``RESOLVED`` or ``SUPERSEDED`` anywhere in it is
    treated as unresolved.  Returns True when the file is absent or
    unreadable (fail-open).
    """
    cer_path = Path(project_dir) / "docs" / "cer" / "backlog.md"
    if not cer_path.exists():
        return True
    try:
        text = cer_path.read_text(encoding="utf-8")
    except OSError:
        return True  # fail open

    in_do_now = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Do Now"):
            in_do_now = True
            continue
        if in_do_now and stripped.startswith("## "):
            break  # left the Do Now section
        if in_do_now and stripped.startswith("|"):
            if "---" in stripped:
                continue  # separator row
            cols = [c.strip() for c in stripped.split("|") if c.strip()]
            if not cols or cols[0].lower() in ("id", "finding"):
                continue  # header row
            if "RESOLVED" not in stripped and "SUPERSEDED" not in stripped:
                return False  # unresolved Do Now item

    return True


def _run_build_gate_subprocess(project_dir: "Path") -> bool:
    """Run ``uv run pytest tests/pairmode/ -q --tb=no`` in ``project_dir``.

    Returns True (gate green) when the exit code is 0.
    Returns True (advisory pass) on timeout or any execution error.
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

    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/pairmode/", "-q", "--tb=no"],
            cwd=str(project_dir),
            capture_output=True,
            timeout=60,
            env=env,
        )
        return result.returncode == 0
    except Exception:  # noqa: BLE001
        return True  # advisory: fail open on error or timeout


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
    if not _check_phase_completion(phase_path):
        return {"ok": False, "failed_guard": "phase-incomplete"}

    # Guard 2: no unresolved Do Now items in the CER backlog.
    if project_path is not None and not _check_cer_do_now(project_path):
        return {"ok": False, "failed_guard": "cer-do-now"}

    # Guard 3: build gate (injectable; advisory-only on error/timeout).
    if gate_fn is not None:
        try:
            gate_ok = bool(gate_fn())
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

    Reads ``docs/phases/index.md`` and walks the phase rows in order, keeping
    the first row whose status is **not** inactive.  Inactive statuses are
    ``complete``, ``deferred``, and ``backlog`` — as defined by
    ``index_integrity.is_phase_inactive``.

    Previously ``resolve_current_phase`` (flex_build) only skipped ``complete``
    phases, so a trailing ``deferred`` or ``backlog`` row would be returned as
    the active phase.  This helper fixes that by composing ``is_phase_inactive``
    from the same source of truth used by the index-integrity checker.

    Falls back to ``resolve_current_phase`` when no index file is present
    (legacy layout).

    Pure read: no writes.  Called only by ``infer_position``.
    """
    from index_integrity import is_phase_inactive as _is_phase_inactive  # type: ignore[import]
    from flex_build import (  # type: ignore[import]
        _parse_index_phases as _pip,
        resolve_current_phase as _rcp,
    )

    index_path = project_path / "docs" / "phases" / "index.md"
    if not index_path.exists():
        return _rcp(project_path)

    try:
        index_text = index_path.read_text(encoding="utf-8")
    except OSError:
        return _rcp(project_path)

    phase_rows = _pip(index_text)
    active_phase_ref: "str | None" = None
    for phase_ref, status in phase_rows:
        if not _is_phase_inactive(status):
            active_phase_ref = phase_ref  # first non-inactive row wins
            break

    if active_phase_ref is not None:
        candidate = project_path / "docs" / "phases" / f"phase-{active_phase_ref}.md"
        if candidate.exists():
            return candidate

    return None


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
    needs_spec : bool
        True when the next story file's ``## Ensures`` section is absent or
        contains fewer than 5 non-blank lines (stub heuristic, RESOLVER-009).
        False when the section is present and sufficiently detailed.
        Defaults to False when ``next_story_id`` is None.
    """
    from next_story import find_next_story  # type: ignore[import]
    from model_selector import select_builder_model  # type: ignore[import]
    from flex_build import (  # type: ignore[import]
        read_attempt_count,
        check_stub_gate,
        check_schema_gate_result,
        check_auth_gate_result,
    )
    from schema_validator import _parse_frontmatter  # type: ignore[import]

    project_path = Path(project_dir).resolve()

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

    if active_phase_file is not None:
        try:
            result = find_next_story(active_phase_file, project_path)
        except Exception:  # noqa: BLE001
            result = None

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
                raw_cs = raw_state.get("checkpoint_step")
                if isinstance(raw_cs, list):
                    checkpoint_step = [s for s in raw_cs if isinstance(s, str)]
    except Exception:  # noqa: BLE001
        pass

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
        "checkpoint_step": checkpoint_step,
        "needs_spec": needs_spec,
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
    Row 9  — all phase stories done → checkpoint routing (RESOLVER-008):
               guard fail → await-user (checkpoint-guard-failed:<which>)
               guards pass → next uncompleted checkpoint step
               all steps done → done
    Row 8  — story committed (PASS), more stories remain   → spawn-builder (next story, attempt 1)
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

    # ------------------------------------------------------------------
    # Row 1 — no active phase (all phases complete, or no phases at all)
    # ------------------------------------------------------------------
    if active_phase_file is None:
        return make_action(DONE, scalar="", model=None, reason="", meta=meta_base)

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
        # checkpoint-security/intent/docs ARE in _SPAWN_ACTIONS; model=None
        # here — the harness sets model at spawn time via model_selector.
        return make_action(
            _next_step,
            scalar="",
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
    #
    # Row-2 branch (RESOLVER-009): story is a spec stub → spawn-spec-writer.
    # The spec-writer elaborates the story before a builder is spawned.
    # ------------------------------------------------------------------
    if attempt_count == 0:
        needs_spec: bool = bool(position.get("needs_spec", False))
        if needs_spec:
            return make_action(
                SPAWN_SPEC_WRITER,
                scalar=next_story_id,
                model="opus",
                reason="needs-spec",
                meta=meta_base,
            )
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

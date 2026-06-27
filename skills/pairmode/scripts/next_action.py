"""
next_action.py — Action grammar and position-inference read-model for the
next-action resolver (RESOLVER-001, RESOLVER-002).

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
CHECKPOINT: str = "checkpoint"
AWAIT_USER: str = "await-user"
DONE: str = "done"

ACTIONS: frozenset[str] = frozenset(
    {SPAWN_BUILDER, SPAWN_LOOP_BREAKER, CHECKPOINT, AWAIT_USER, DONE}
)

# Actions for which model may be non-null (auto-resolved spawn actions only).
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
    # 4. Builder model selection
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

            builder_model, builder_model_reason = select_builder_model(
                story_class,
                list(primary_files),
                protected_files,
                attempt_number=max(attempt_count, 1),
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
    # 6. Last-attempt outcome inference (DP3)
    #
    # PASS  — a story-<ID> commit exists (reuse next_story's commit-authority;
    #          if such a commit exists, find_next_story would have skipped it —
    #          we therefore check git directly here to cover the edge where the
    #          story is identified by find_next_story as not committed yet).
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

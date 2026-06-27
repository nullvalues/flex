"""
next_action.py — Action grammar for the next-action resolver (RESOLVER-001).

This module defines the versioned action vocabulary, the canonical dict
constructor, and the stdlib-only validator. No third-party imports.
No I/O. No side effects.
"""

from __future__ import annotations

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

"""
gate_verdict.py — gate verdict grammar for Era 003 leaf-worker return contract (WORKER-001).

Contract: a verdict map is a dict whose keys are a subset of the judged gate names
(``schema``, ``auth``).  Each value is a verdict string following the grammar:

    clean
    block:<reason>
    flag:<reason>

where <reason> is freeform human text (may contain colons).  ``stub`` is NOT a
judged gate and is NOT a valid verdict-map key.

This module is stdlib-only and has no I/O.  It is the WORKER-rail contract
analogue of RESOLVER-001's action grammar.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Grammar constants
# ---------------------------------------------------------------------------

#: The set of recognised verdict verbs.
VERBS: frozenset[str] = frozenset({"clean", "block", "flag"})

#: The set of gate names that receive a judged verdict.
#: ``stub`` is mechanical (DP2) and is deliberately excluded.
JUDGED_GATES: frozenset[str] = frozenset({"schema", "auth"})


# ---------------------------------------------------------------------------
# Parse helper
# ---------------------------------------------------------------------------

def parse_verdict(verdict: str) -> tuple[str, str]:
    """Parse a single verdict string into ``(verb, reason)``.

    The split is on the **first** colon only, so a reason string may itself
    contain colons and will round-trip verbatim.

    Returns:
        ``(verb, reason)`` where *reason* is ``""`` for ``clean`` and the
        freeform text after the first ``:`` for ``block``/``flag``.

    Raises:
        ValueError: if *verdict* is not a non-empty string.

    Note:
        This function does **not** validate the verb or reason — it is a
        structural parse only.  Call :func:`validate_verdict_map` to check
        correctness of a full verdict map.
    """
    if not isinstance(verdict, str) or not verdict:
        raise ValueError(f"verdict must be a non-empty string, got {verdict!r}")

    if ":" in verdict:
        verb, reason = verdict.split(":", 1)
    else:
        verb, reason = verdict, ""

    return verb, reason


# ---------------------------------------------------------------------------
# Validate helper
# ---------------------------------------------------------------------------

def validate_verdict_map(verdict_map: dict) -> list[str]:
    """Validate a verdict map and return a list of human-readable violations.

    An empty list means the map is valid.

    Rules:
    - Keys must be a subset of :data:`JUDGED_GATES` (empty map is valid).
    - Each value must start with a recognised verb from :data:`VERBS`.
    - ``block`` and ``flag`` must carry a non-empty ``<reason>`` payload.
    - ``clean`` must carry **no** reason payload (no colon).
    """
    violations: list[str] = []

    if not isinstance(verdict_map, dict):
        violations.append(f"verdict_map must be a dict, got {type(verdict_map).__name__}")
        return violations

    for key, value in verdict_map.items():
        # Key check
        if key not in JUDGED_GATES:
            violations.append(
                f"unknown gate key {key!r}; allowed keys are {sorted(JUDGED_GATES)}"
            )

        # Value must be a non-empty string
        if not isinstance(value, str) or not value:
            violations.append(
                f"gate {key!r}: verdict must be a non-empty string, got {value!r}"
            )
            continue

        verb, reason = parse_verdict(value)

        # Verb check
        if verb not in VERBS:
            violations.append(
                f"gate {key!r}: unknown verb {verb!r}; allowed verbs are {sorted(VERBS)}"
            )
            continue  # no further checks make sense for unknown verb

        # Reason presence check
        if verb == "clean":
            if reason:
                violations.append(
                    f"gate {key!r}: verb 'clean' must carry no reason payload, "
                    f"got {value!r}"
                )
        else:
            # block / flag
            if not reason:
                violations.append(
                    f"gate {key!r}: verb {verb!r} requires a non-empty reason "
                    f"(expected '{verb}:<reason>'), got {value!r}"
                )

    return violations

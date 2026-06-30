"""
worker_result.py — generalized worker return contract for Era 003 (WORKER-004).

Defines four typed result envelopes covering all non-gate workers in the
HARNESS003 fleet:

    BUILD-RESULT   — builder outcome (PASS / FAIL)
    REVIEW-RESULT  — reviewer verdict (PASS / FAIL, with findings list)
    ADVICE         — loop-breaker recommendation (free-form approach + rationale)
    SPEC-RESULT    — spec-writer output (done / revised)

Each result is a JSON object whose ``type`` field selects the schema.  The
module is stdlib-only and has no I/O — mirroring ``gate_verdict.py``'s design
philosophy.  It is the WORKER-rail contract analogue of the action grammar
in ``next_action.py``.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# Result type constants
# ---------------------------------------------------------------------------

BUILD_RESULT: str = "BUILD-RESULT"
REVIEW_RESULT: str = "REVIEW-RESULT"
ADVICE: str = "ADVICE"
SPEC_RESULT: str = "SPEC-RESULT"

#: All recognised result type strings.
RESULT_TYPES: frozenset[str] = frozenset({BUILD_RESULT, REVIEW_RESULT, ADVICE, SPEC_RESULT})

# ---------------------------------------------------------------------------
# Per-type field schemas
# ---------------------------------------------------------------------------
#
# Each schema entry is a dict with:
#   required  — list[str]  required field names (excluding ``type``)
#   allowed   — set[str]   all allowed field names (including ``type``)
#   enums     — dict[str, set] value-constrained fields → allowed values
#
# ``type`` is implicitly required for all result types and is handled by
# parse_worker_result / validate_worker_result directly.

_SCHEMAS: dict[str, dict] = {
    BUILD_RESULT: {
        "required": ["outcome", "story_id", "reason"],
        "allowed": {"type", "outcome", "story_id", "reason"},
        "enums": {"outcome": {"PASS", "FAIL"}},
    },
    REVIEW_RESULT: {
        "required": ["verdict", "findings", "reason"],
        "allowed": {"type", "verdict", "findings", "reason"},
        # ALIGNED is the canonical intent-review verdict (WORKER-009): the
        # checkpoint-intent action relies on the "ALIGNED/[findings]" output
        # format. The grammar admits string verdicts beyond PASS/FAIL for
        # clarity; PASS, FAIL, and ALIGNED are the recognised members. Any
        # other verdict string (e.g. "MAYBE") remains a violation.
        "enums": {"verdict": {"PASS", "FAIL", "ALIGNED"}},
    },
    ADVICE: {
        "required": ["approach", "rationale"],
        "allowed": {"type", "approach", "rationale"},
        "enums": {},
    },
    SPEC_RESULT: {
        "required": ["story_id", "status"],
        "allowed": {"type", "story_id", "status"},
        "enums": {"status": {"done", "revised"}},
    },
}


# ---------------------------------------------------------------------------
# validate_worker_result
# ---------------------------------------------------------------------------


def validate_worker_result(obj: object) -> list[str]:
    """Validate a decoded worker result object and return a list of violations.

    An empty list means the object is valid.

    Rules (applied in order):
    1. Must be a dict.
    2. Must have a ``type`` field whose value is a member of :data:`RESULT_TYPES`.
    3. All required fields for the declared type must be present.
    4. Enum-constrained fields must contain a value from the allowed set.
    5. The ``findings`` field in ``REVIEW-RESULT`` must be a list of strings.

    This function does **not** reject extra fields — the result envelope is
    designed to be forward-compatible (consumers ignore unknown fields).
    """
    violations: list[str] = []

    if not isinstance(obj, dict):
        violations.append(
            f"worker result must be a dict; got {type(obj).__name__}"
        )
        return violations

    # --- type field ---
    if "type" not in obj:
        violations.append("missing required field 'type'")
        return violations

    result_type = obj["type"]
    if result_type not in RESULT_TYPES:
        violations.append(
            f"unknown result type {result_type!r}; "
            f"allowed types are {sorted(RESULT_TYPES)}"
        )
        return violations

    schema = _SCHEMAS[result_type]

    # --- required fields ---
    for field in schema["required"]:
        if field not in obj:
            violations.append(
                f"type={result_type!r}: missing required field {field!r}"
            )

    # --- enum constraints ---
    for field, allowed_values in schema["enums"].items():
        if field in obj and obj[field] not in allowed_values:
            violations.append(
                f"type={result_type!r}: field {field!r} must be one of "
                f"{sorted(allowed_values)}; got {obj[field]!r}"
            )

    # --- findings list-of-strings constraint (REVIEW-RESULT only) ---
    if result_type == REVIEW_RESULT and "findings" in obj:
        findings = obj["findings"]
        if not isinstance(findings, list):
            violations.append(
                f"type={result_type!r}: field 'findings' must be a list; "
                f"got {type(findings).__name__}"
            )
        else:
            for i, item in enumerate(findings):
                if not isinstance(item, str):
                    violations.append(
                        f"type={result_type!r}: findings[{i}] must be a string; "
                        f"got {type(item).__name__}"
                    )

    return violations


# ---------------------------------------------------------------------------
# parse_worker_result
# ---------------------------------------------------------------------------


def parse_worker_result(text: str) -> dict:
    """Parse JSON *text* as a worker result object and validate it.

    Parameters
    ----------
    text:
        A JSON string returned by a worker agent.

    Returns
    -------
    dict
        The decoded result dict (guaranteed to pass :func:`validate_worker_result`).

    Raises
    ------
    ValueError
        If *text* is not valid JSON, if the decoded value is not a dict, or if
        :func:`validate_worker_result` returns any violations.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError(
            f"parse_worker_result expects a non-empty string; got {text!r}"
        )

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in worker result text: {exc}") from exc

    violations = validate_worker_result(obj)
    if violations:
        raise ValueError(
            "worker result failed validation:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    return obj

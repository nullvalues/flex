"""context_health.py — phase retry-burden analysis for context health checks.

Public API
----------

- ``phase_retry_burden(db_path, phase)`` — sum of estimated retry-context output
  tokens for reviewer FAIL rows in a single phase.
- ``rolling_phase_median(db_path, current_phase, lookback_phases)`` — median
  retry burden across the N most recent prior phases.
- ``check_context_health(db_path, current_phase, lookback_phases)`` — structured
  health report with a human-readable message and recommendation label.

All three functions are safe when the DB does not exist.  No exceptions propagate
to callers.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from pathlib import Path

try:
    from skills.pairmode.scripts import context_budget
    from skills.pairmode.scripts.context_model import (
        TRACK_ORCHESTRATOR,
        TRACK_STORY_SPEND,
        track_label,
    )
except ImportError:  # flat import via hook/CLI sys.path
    import context_budget  # type: ignore[no-redef]
    from context_model import (  # type: ignore[no-redef]
        TRACK_ORCHESTRATOR,
        TRACK_STORY_SPEND,
        track_label,
    )

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _open_conn(db_path: Path):
    """Return a sqlite3 connection, or None if the DB does not exist."""
    resolved = Path(db_path).resolve()
    if not resolved.exists():
        return None
    try:
        return sqlite3.connect(str(resolved))
    except Exception:
        return None


def _prior_phases(db_path: Path, current_phase: str, lookback_phases: int) -> list[str]:
    """Return up to *lookback_phases* distinct phase values preceding *current_phase*.

    Phases are ordered by their first-occurrence timestamp (ascending).  The
    *current_phase* is always excluded.  Returns an empty list when the DB is
    absent or has no other phase rows.
    """
    conn = _open_conn(db_path)
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT phase
              FROM attempts
             WHERE phase IS NOT NULL
               AND phase != ?
             GROUP BY phase
             ORDER BY MIN(ts) ASC
            """,
            (current_phase,),
        )
        rows = cur.fetchall()
        all_phases = [row[0] for row in rows]
        # Return the most recent *lookback_phases* prior phases.
        return all_phases[-lookback_phases:] if len(all_phases) > lookback_phases else all_phases
    except Exception:
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def phase_retry_burden(db_path: Path, phase: str) -> int:
    """Return the sum of estimated retry-context output tokens for *phase*.

    Counts only ``agent_role = 'reviewer'`` rows with ``outcome = 'FAIL'`` and at
    least one token column present (``tokens_out IS NOT NULL OR tokens_total IS NOT
    NULL``).  When ``tokens_out`` is NULL the estimate uses
    ``CAST(tokens_total * 0.15 AS INTEGER)``.

    Returns ``0`` when no matching rows exist or when the DB is absent.
    Never raises.
    """
    conn = _open_conn(db_path)
    if conn is None:
        return 0
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT SUM(COALESCE(tokens_out, CAST(tokens_total * 0.15 AS INTEGER)))
              FROM attempts
             WHERE agent_role = 'reviewer'
               AND outcome = 'FAIL'
               AND phase = ?
               AND (tokens_out IS NOT NULL OR tokens_total IS NOT NULL)
            """,
            (phase,),
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            return 0
        return int(row[0])
    except Exception:
        return 0
    finally:
        conn.close()


def rolling_phase_median(
    db_path: Path,
    current_phase: str,
    lookback_phases: int = 10,
) -> tuple[float | None, int]:
    """Return ``(median, sample_size)`` of retry-burden across prior phases.

    Prior phases with zero FAIL reviewer rows contribute ``0`` — they are
    included in the median, not skipped.  This correctly captures healthy
    phases (no retries) in the baseline.

    Returns ``(None, 0)`` when fewer than 3 prior phases exist.
    Never raises on missing DB.
    """
    prior = _prior_phases(db_path, current_phase, lookback_phases)
    if len(prior) < 3:
        return (None, 0)

    burdens: list[int] = []
    for p in prior:
        burdens.append(phase_retry_burden(db_path, p))

    sample_size = len(burdens)
    median = statistics.median(burdens)
    return (float(median), sample_size)


def _read_state_for_headroom(project_dir: "Path | None") -> dict:
    """Read ``.companion/state.json`` for :func:`orchestrator_headroom`.

    Returns ``{}`` on any error (absent file, malformed JSON, non-dict root,
    or ``project_dir`` being ``None``) — the same reader pattern this module
    already uses for the effort.db path, kept local so ``orchestrator_headroom``
    stays a pure function of a ``state`` dict for testability (§ B1).
    """
    if project_dir is None:
        return {}
    try:
        state_path = Path(project_dir) / ".companion" / "state.json"
        if not state_path.exists():
            return {}
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def orchestrator_headroom(state: dict, flex_factor: float = 1.0) -> dict:
    """Return a pure orchestrator-track headroom report over *state*.

    Reads only ``state.json`` keys belonging to the orchestrator track
    (INFRA-321 § A1/B1) — it opens no database, never writes, and never
    raises. A malformed or empty ``state`` yields ``tokens=None`` and
    ``recommendation="insufficient_data"``.

    Reuses ``context_budget.derive_expected_step_tokens``,
    ``context_budget.effective_ceiling`` and ``context_budget._is_stale``
    rather than re-deriving any of them — this is the single verdict source
    a pause decision may be computed from (DP7).
    """
    if not isinstance(state, dict):
        state = {}

    tokens = None
    raw = state.get("context_current_tokens")
    if raw is not None:
        try:
            v = int(raw)
            if v > 0:
                tokens = v
        except (TypeError, ValueError):
            tokens = None

    threshold = int(state.get("context_budget_threshold", 130000) or 130000)
    overrun_pct = float(state.get("context_budget_overrun_pct", 0.10) or 0.10)
    ceiling = context_budget.effective_ceiling(threshold, overrun_pct, flex_factor)

    expected_step_tokens, expected_step_provenance = (
        context_budget.derive_expected_step_tokens(state)
    )

    stale = context_budget._is_stale(state)

    headroom = None
    steps_remaining = None
    if tokens is not None:
        headroom = ceiling - tokens
        if expected_step_tokens and expected_step_tokens > 0:
            steps_remaining = headroom // expected_step_tokens

    if stale or tokens is None:
        recommendation = "insufficient_data"
    elif steps_remaining is None:
        recommendation = "insufficient_data"
    elif steps_remaining >= 3:
        recommendation = "normal"
    elif steps_remaining >= 1:
        recommendation = "elevated"
    else:
        recommendation = "high"

    label = track_label(TRACK_ORCHESTRATOR)
    if recommendation == "insufficient_data":
        message = f"{label}: insufficient data (stale or no measurement recorded)"
    elif recommendation == "normal":
        message = (
            f"{label}: {tokens:,} / {ceiling:,} tokens, "
            f"~{steps_remaining} steps of headroom remain"
        )
    elif recommendation == "elevated":
        message = (
            f"{label}: {tokens:,} / {ceiling:,} tokens, "
            f"ELEVATED — ~{steps_remaining} step(s) of headroom remain, consider /clear"
        )
    else:  # high
        message = (
            f"{label}: {tokens:,} / {ceiling:,} tokens, "
            f"HIGH — < 1 step of headroom remains, recommend /clear"
        )

    return {
        "track": TRACK_ORCHESTRATOR,
        "tokens": tokens,
        "ceiling": ceiling,
        "expected_step_tokens": expected_step_tokens,
        "expected_step_provenance": expected_step_provenance,
        "headroom": headroom,
        "steps_remaining": steps_remaining,
        "stale": stale,
        "recommendation": recommendation,
        "message": message,
    }


def check_context_health(
    db_path: Path,
    current_phase: str,
    lookback_phases: int = 10,
    state: "dict | None" = None,
    project_dir: "Path | None" = None,
) -> dict:
    """Return a structured context health report for *current_phase*.

    INFRA-321: this report is now two explicitly-tracked sub-objects rather
    than a single flat dict — the top-level ``recommendation``/``message`` are
    the ORCHESTRATOR track's verdict (the only track a pause/`/clear` decision
    may be computed from, DP7); ``story_spend`` is informational only and
    never drives the top-level verdict.

    ``state`` (optional) is the state dict to derive ``orchestrator`` from —
    when ``None``, it is read from ``project_dir/.companion/state.json`` (or
    ``db_path``'s grandparent when ``project_dir`` is not given, matching this
    module's existing effort.db-relative reader pattern). Passing ``state``
    directly makes this callable purely in tests, with no filesystem I/O.

    Returned shape::

        {
          "phase": "<phase>",
          "orchestrator": {...orchestrator_headroom(...)...},
          "story_spend": {"track": TRACK_STORY_SPEND, "retry_burden": N,
                           "phase_median": M, "ratio": R, "sample_size": K,
                           "informational": True, "message": "<captioned>"},
          "recommendation": "<orchestrator.recommendation>",  # by identity
          "message": "<orchestrator.message>; story spend: <story_spend.message>",
        }

    Never raises on missing DB or missing state.json.
    """
    retry_burden = phase_retry_burden(db_path, current_phase)
    phase_median, sample_size = rolling_phase_median(db_path, current_phase, lookback_phases)

    # Compute ratio.  Set to None when there is no meaningful denominator —
    # this covers both the no-prior-phases case (phase_median is None) and the
    # zero-median case (all prior phases had zero retry burden).
    if phase_median is None or phase_median == 0.0:
        ratio: float | None = None
    else:
        ratio = retry_burden / phase_median

    # Retry-churn banding — the number is a legitimate reviewer-churn signal
    # (INFRA-321 § B4); it was only ever wearing the wrong ("headroom") hat.
    if ratio is None:
        churn = "insufficient_data"
    elif ratio < 2.0:
        churn = "normal"
    elif ratio < 4.0:
        churn = "elevated"
    else:
        churn = "high"

    spend_label = track_label(TRACK_STORY_SPEND)
    if churn == "insufficient_data":
        spend_message = (
            f"{spend_label}: no data yet (retry burden: {retry_burden:,} tokens, "
            f"<3 prior phases recorded)"
        )
    elif churn == "normal":
        spend_message = (
            f"{spend_label}: retry churn: normal ({retry_burden:,} tokens, "
            f"{ratio:.1f}× median, n={sample_size})"  # noqa: RUF001
        )
    elif churn == "elevated":
        spend_message = (
            f"{spend_label}: retry churn: ELEVATED ({retry_burden:,} tokens, "
            f"{ratio:.1f}× median, n={sample_size})"
        )
    else:  # high
        spend_message = (
            f"{spend_label}: retry churn: HIGH ({retry_burden:,} tokens, "
            f"{ratio:.1f}× median, n={sample_size})"
        )

    story_spend = {
        "track": TRACK_STORY_SPEND,
        "retry_burden": retry_burden,
        "phase_median": phase_median,
        "ratio": ratio,
        "sample_size": sample_size,
        "informational": True,
        "message": spend_message,
    }

    if state is None:
        resolved_dir = project_dir if project_dir is not None else Path(db_path).resolve().parent.parent
        state = _read_state_for_headroom(resolved_dir)

    orchestrator = orchestrator_headroom(state)

    return {
        "phase": current_phase,
        "orchestrator": orchestrator,
        "story_spend": story_spend,
        # By identity, not re-derivation (§ B3) — the top-level verdict is
        # the orchestrator track's verdict, full stop.
        "recommendation": orchestrator["recommendation"],
        "message": f"{orchestrator['message']}; story spend: {story_spend['message']}",
    }


def _cli_main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the exit code.

    Separated from the ``if __name__ == "__main__"`` block so that tests can
    call it directly (with mocked dependencies) without spawning a subprocess.
    """
    import argparse
    import sys
    from pathlib import Path as _Path

    # Allow imports of sibling scripts (effort_db) when invoked directly.
    import os as _os
    _scripts_dir = _os.path.dirname(_os.path.abspath(__file__))
    _repo_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_scripts_dir)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

    from skills.pairmode.scripts.effort_db import resolve_effort_db_path  # noqa: E402

    parser = argparse.ArgumentParser(
        description="context_health CLI — phase retry-burden health check"
    )
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser(
        "check",
        help="Check context health for a phase and print the result message.",
    )
    check_parser.add_argument(
        "--phase", required=True, help="Phase ID to evaluate (e.g. '45')"
    )
    check_parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args(argv)

    if args.command == "check":
        project_dir = _Path(args.project_dir)
        db_path = resolve_effort_db_path(project_dir)
        result = check_context_health(
            db_path=db_path, current_phase=args.phase, project_dir=project_dir
        )
        print(result["message"])
        # B5: exit 1 gates ONLY on the orchestrator track's recommendation —
        # a phase with high retry churn and a healthy orchestrator exits 0.
        if result["recommendation"] in ("elevated", "high"):
            return 1
        return 0
    else:
        parser.print_help()
        return 1


# exit 0 = healthy, 1 = unhealthy
if __name__ == "__main__":
    import sys
    sys.exit(_cli_main())

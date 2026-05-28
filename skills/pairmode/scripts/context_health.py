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

import sqlite3
import statistics
from pathlib import Path

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


def check_context_health(
    db_path: Path,
    current_phase: str,
    lookback_phases: int = 10,
) -> dict:
    """Return a structured context health report for *current_phase*.

    Keys returned:
    - ``phase`` (str) — the phase evaluated.
    - ``retry_burden`` (int) — output-token count for this phase's FAIL reviewer rows.
    - ``phase_median`` (float | None) — median across prior phases; None < 3 prior.
    - ``ratio`` (float | None) — ``retry_burden / phase_median``; None when
      phase_median is None or 0.0 (to avoid ZeroDivisionError and meaningless ratios).
    - ``recommendation`` (str) — one of ``"insufficient_data"``, ``"normal"``,
      ``"elevated"``, or ``"high"``.
    - ``sample_size`` (int) — number of prior phases included in the median.
    - ``message`` (str) — human-readable summary.

    Recommendation thresholds (evaluated after setting ratio):

    1. ``ratio is None``              → ``"insufficient_data"``
    2. ``ratio < 2.0``                → ``"normal"``
    3. ``2.0 <= ratio < 4.0``         → ``"elevated"``
    4. ``ratio >= 4.0``               → ``"high"``

    Note: ratio is set to None whenever phase_median is None *or* phase_median
    is 0.0, so both the "no prior phases" and "all prior phases had zero retry
    burden" cases map to ``"insufficient_data"``.  A zero-median baseline is not
    a meaningful signal — there is nothing to compare against.

    Never raises on missing DB.
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

    # Recommendation — gated on ratio, NOT on phase_median.  This correctly
    # handles the zero-median case: when phase_median == 0.0, ratio is None,
    # so we still land in "insufficient_data" rather than falling through to
    # a TypeError on ratio < 2.0.
    if ratio is None:
        recommendation = "insufficient_data"
    elif ratio < 2.0:
        recommendation = "normal"
    elif ratio < 4.0:
        recommendation = "elevated"
    else:
        recommendation = "high"

    # Human-readable message.
    if recommendation == "insufficient_data":
        message = (
            f"no data yet (retry burden: {retry_burden:,} tokens, "
            f"<3 prior phases recorded)"
        )
    elif recommendation == "normal":
        message = (
            f"normal ({retry_burden:,} tokens, {ratio:.1f}× median, "  # noqa: RUF001
            f"n={sample_size})"
        )
    elif recommendation == "elevated":
        message = (
            f"ELEVATED ({retry_burden:,} tokens, {ratio:.1f}× median, "
            f"n={sample_size}) — consider /clear before next phase"
        )
    else:  # high
        message = (
            f"HIGH ({retry_burden:,} tokens, {ratio:.1f}× median, "
            f"n={sample_size}) — recommend /clear before next phase"
        )

    return {
        "phase": current_phase,
        "retry_burden": retry_burden,
        "phase_median": phase_median,
        "ratio": ratio,
        "recommendation": recommendation,
        "sample_size": sample_size,
        "message": message,
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
        db_path = resolve_effort_db_path(_Path(args.project_dir))
        result = check_context_health(db_path=db_path, current_phase=args.phase)
        print(result["message"])
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

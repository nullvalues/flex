"""context_budget_check.py — Check accumulated context token budget for a phase.

Reads `.companion/effort.db` and `.companion/state.json` from the given
project directory. Sums `tokens_total` for all attempts in the specified phase
and compares against a threshold.

Usage:
    PATH=$HOME/.local/bin:$PATH uv run python scripts/context_budget_check.py \
        --project-dir . \
        --phase <PHASE_ID>

Exit codes:
    0  — status=ok  (sum <= threshold)
    1  — status=over (sum > threshold)
    2  — usage/IO error (missing DB, malformed args, etc.)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_THRESHOLD = 120000


def _resolve_db_path(project_dir: Path) -> Path:
    """Resolve the effort DB path from state.json or use the default."""
    state_path = project_dir / ".companion" / "state.json"
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        configured = data.get("effort_db_path")
        if configured:
            p = Path(configured)
            if not p.is_absolute():
                p = project_dir / p
            return p
    return project_dir / ".companion" / "effort.db"


def _load_threshold_from_state(project_dir: Path) -> int | None:
    """Return context_budget_threshold from state.json, or None if absent/invalid."""
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    val = data.get("context_budget_threshold")
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _sum_tokens_for_phase(db_path: Path, phase: str) -> int:
    """Sum tokens_total for all attempts in the given phase. NULL tokens count as 0."""
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(COALESCE(tokens_total, 0)), 0) FROM attempts WHERE phase = ?",
            (phase,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check accumulated context token budget for a phase.",
        prog="context_budget_check.py",
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project root directory. Reads .companion/effort.db and .companion/state.json.",
    )
    parser.add_argument(
        "--phase",
        required=True,
        help="Phase identifier to sum tokens for (e.g. '1', '1.5').",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help=(
            "Override the token threshold. "
            "Priority: --threshold > state.json context_budget_threshold > 120000 (default)."
        ),
    )

    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir).resolve()

    # Resolve the DB path
    db_path = _resolve_db_path(project_dir)

    # Check DB existence
    if not db_path.exists():
        print(
            f"ERROR: effort.db not found at {db_path}",
            file=sys.stderr,
        )
        return 2

    # Resolve threshold: --threshold arg > state.json > built-in default
    if args.threshold is not None:
        threshold = args.threshold
    else:
        state_threshold = _load_threshold_from_state(project_dir)
        threshold = state_threshold if state_threshold is not None else _DEFAULT_THRESHOLD

    # Query the DB
    try:
        token_sum = _sum_tokens_for_phase(db_path, args.phase)
    except sqlite3.Error as exc:
        print(f"ERROR: failed to query effort.db: {exc}", file=sys.stderr)
        return 2

    status = "ok" if token_sum <= threshold else "over"

    # Machine-parseable stdout line
    print(
        f"context_budget phase={args.phase} tokens={token_sum} threshold={threshold} status={status}"
    )

    if status == "over":
        print(
            f"CONTEXT BUDGET EXCEEDED — phase {args.phase} has accumulated "
            f"{token_sum} tokens of recorded subagent work (threshold: {threshold}).\n"
            "Orchestrator MUST surface a proceed-vs-pause prompt to the user before "
            "spawning the next builder.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

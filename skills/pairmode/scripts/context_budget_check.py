"""context_budget_check.py — Check accumulated STORY-SPEND for a phase.

INFRA-321: this CLI measures the story-spend track (TRACK_STORY_SPEND) —
recorded subagent cost summed from effort.db — and renders a verdict about
that track only. It is NOT a context-headroom / orchestrator-window signal;
see `skills/pairmode/scripts/context_health.py`'s `orchestrator_headroom()`
(or the `flex-build context-health` CLI) for that. Reads `.companion/effort.db`
and `.companion/state.json` from the given project directory. Sums
`tokens_total` for all attempts in the specified phase and compares against a
STORY-SPEND threshold — resolved per § A3: --threshold > state.json
`story_spend_threshold` > the module default. It never falls back to
`context_budget_threshold`, which is an orchestrator-track key.

Usage:
    PATH=$HOME/.local/bin:$PATH uv run python scripts/context_budget_check.py \
        --project-dir . \
        --phase <PHASE_ID>

Exit codes (unchanged by INFRA-321 — only the rendered message changed):
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

try:
    from skills.pairmode.scripts.context_model import (
        STORY_SPEND_THRESHOLD_DEFAULT,
        STORY_SPEND_THRESHOLD_KEY,
    )
except ImportError:  # flat import via CLI sys.path
    from context_model import (  # type: ignore[no-redef]
        STORY_SPEND_THRESHOLD_DEFAULT,
        STORY_SPEND_THRESHOLD_KEY,
    )

_DEFAULT_THRESHOLD = STORY_SPEND_THRESHOLD_DEFAULT


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
    """Return the STORY-SPEND threshold from state.json, or None if absent/invalid.

    INFRA-321 § A3: reads ``story_spend_threshold`` — never
    ``context_budget_threshold``, which is an orchestrator-track key. A
    state.json carrying only ``context_budget_threshold`` (no
    ``story_spend_threshold``) must resolve to the module default here, not
    to the orchestrator's threshold value.
    """
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    val = data.get(STORY_SPEND_THRESHOLD_KEY)
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
            "Override the story-spend token threshold. "
            f"Priority: --threshold > state.json {STORY_SPEND_THRESHOLD_KEY} > "
            f"{STORY_SPEND_THRESHOLD_DEFAULT} (default). Never falls back to "
            "context_budget_threshold (an orchestrator-track key)."
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

    # Resolve threshold: --threshold arg > state.json story_spend_threshold >
    # built-in default (§ A3). threshold_source makes the absence of a
    # configured story_spend_threshold visible rather than silent.
    if args.threshold is not None:
        threshold = args.threshold
        threshold_source = "cli"
    else:
        state_threshold = _load_threshold_from_state(project_dir)
        if state_threshold is not None:
            threshold = state_threshold
            threshold_source = "state"
        else:
            threshold = _DEFAULT_THRESHOLD
            threshold_source = "default"

    # Query the DB
    try:
        token_sum = _sum_tokens_for_phase(db_path, args.phase)
    except sqlite3.Error as exc:
        print(f"ERROR: failed to query effort.db: {exc}", file=sys.stderr)
        return 2

    status = "ok" if token_sum <= threshold else "over"

    # Machine-parseable stdout line. INFRA-321: names the track explicitly and
    # surfaces threshold provenance so a silent default cannot pass as a
    # configured one (the original conflation stayed invisible this way).
    print(
        f"story_spend track=story-spend phase={args.phase} tokens={token_sum} "
        f"threshold={threshold} threshold_source={threshold_source} status={status}"
    )

    if status == "over":
        print(
            f"STORY-SPEND OVER THRESHOLD — phase {args.phase} has accumulated "
            f"{token_sum} tokens of recorded subagent work (threshold: {threshold}, "
            f"source: {threshold_source}). This is NOT a context-headroom signal — "
            "it measures cost already spent in subagent windows, never the "
            "orchestrator's own window occupancy. See `flex-build context-health` "
            "(context_health.orchestrator_headroom) for the orchestrator track.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

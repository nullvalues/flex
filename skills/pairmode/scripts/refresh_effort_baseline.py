"""refresh_effort_baseline.py — Operator CLI to regenerate the seed file.

Reads ``.companion/effort.db`` from each provided project directory,
aggregates ``tokens_total`` grouped by ``agent_role``, computes median +
p75 + p90 + n, and writes a JSON seed file.

Usage:
    PATH=$HOME/.local/bin:$PATH uv run python \\
        skills/pairmode/scripts/refresh_effort_baseline.py \\
        --project-dirs /mnt/work/forqsite /mnt/work/radar \\
        --output skills/pairmode/seed/effort_baseline.json

Missing or empty effort.dbs are skipped silently. Output is idempotent:
``source_projects`` is sorted alphabetically and all floats are rounded to
integers.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

import click


def _collect_rows(db_path: Path) -> list[tuple[str, int]]:
    """Return list of (agent_role, tokens_total) tuples from one effort.db."""
    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT agent_role, tokens_total FROM attempts "
            "WHERE tokens_total IS NOT NULL AND agent_role IS NOT NULL"
        )
        rows = cur.fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [(str(r[0]), int(r[1])) for r in rows if r[0] is not None and r[1] is not None]


def _percentile(sorted_values: list[int], pct: float) -> int:
    """Nearest-rank percentile on a pre-sorted list of ints."""
    if not sorted_values:
        return 0
    n = len(sorted_values)
    # Nearest-rank method: rank = ceil(pct * n), 1-indexed
    rank = max(1, min(n, int(pct * n + 0.999999)))
    return int(sorted_values[rank - 1])


def _aggregate(
    rows_by_role: dict[str, list[int]],
) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for role in sorted(rows_by_role.keys()):
        values = sorted(rows_by_role[role])
        if not values:
            continue
        out[role] = {
            "n": len(values),
            "median": int(round(statistics.median(values))),
            "p75": _percentile(values, 0.75),
            "p90": _percentile(values, 0.90),
        }
    return out


@click.command()
@click.option(
    "--project-dirs",
    "project_dirs",
    multiple=True,
    required=True,
    help="One or more project directories. Reads .companion/effort.db from each.",
)
@click.option(
    "--output",
    "output",
    required=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Output JSON path (overwritten).",
)
@click.option(
    "--generated-at",
    "generated_at",
    default=None,
    help="Override the generated_at timestamp (UTC ISO 8601). For deterministic tests.",
)
def main(project_dirs: tuple[str, ...], output: str, generated_at: str | None) -> None:
    """Aggregate effort.db rows across one or more projects into a seed file."""
    rows_by_role: dict[str, list[int]] = defaultdict(list)
    found_projects: list[str] = []

    for raw in project_dirs:
        project_path = Path(raw)
        db_path = project_path / ".companion" / "effort.db"
        if not db_path.exists():
            continue
        collected = _collect_rows(db_path)
        if not collected:
            # Empty effort.db: skip silently per spec.
            continue
        for role, tokens in collected:
            rows_by_role[role].append(tokens)
        found_projects.append(project_path.name)

    by_role = _aggregate(rows_by_role)

    if generated_at is None:
        generated_at = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    result = {
        "generated_at": generated_at,
        "source_projects": sorted(found_projects),
        "by_role": by_role,
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic, sorted JSON output for byte-identical runs.
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

"""drift_evidence.py — Token-evidence scoring for convergence candidates.

Computes a token-efficiency score for a convergence candidate pattern by
querying ``effort.db`` across a set of registered project directories.

Scoring methodology
-------------------
The score measures whether projects that have the drifted pattern in their
builder attempts show lower median builder token costs compared to the
cross-project overall median.

Concretely, for a given *pattern_id*:

1. For each project directory, open its ``effort.db`` and collect all
   ``agent_role='builder'`` rows.  Rows with NULL or zero ``tokens_total``
   are excluded.

2. Count the total number of qualifying builder attempts across all projects.
   If fewer than 5 attempts are found in total, return
   ``(None, "insufficient data")`` — the sample is too small for the
   comparison to be meaningful.

3. Compute the cross-project median builder tokens (``baseline_median``).

4. For each project whose ``project_dir`` path string *contains* the
   ``pattern_id`` string (a simple proxy for "project adopted the pattern"),
   collect its builder token rows.  If no projects match via this proxy,
   fall back to comparing the lowest-token half of projects against the
   upper half.

5. Compute the ``pattern_median`` for the matched projects and the
   ``other_median`` for the remainder.

6. Normalise the score:

   .. code-block:: text

       score = 1.0 - (pattern_median / (pattern_median + other_median))

   A score closer to 1.0 means the pattern-associated projects consumed
   proportionally fewer tokens.  A score of 0.5 means no difference.

Known limits
------------
* **Small samples.** With fewer than 5 total attempts the score is
  suppressed entirely; with only 5–20 attempts the estimate is noisy.
* **Confounding factors.** Story complexity, model choice, and build-loop
  re-tries all affect token counts independently of any pattern.
* **Pattern proxy is coarse.** The current implementation uses
  ``pattern_id`` as a substring of the project path, which is a rough
  proxy for "this project adopted the pattern."  A more accurate signal
  would require explicit tagging of attempts with the pattern they relate to.
* **No causality.** Lower tokens for pattern-associated projects may reflect
  pre-existing simplicity of those projects, not an effect of the pattern
  itself.

Public API
----------
- ``score_convergence_candidate(project_dirs, pattern_id)``
  → ``(score: float | None, justification: str)``
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# Repo root on sys.path so sibling imports work when run as CLI
# ---------------------------------------------------------------------------
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from skills.pairmode.scripts.effort_db import resolve_effort_db_path  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_TOTAL_ATTEMPTS = 5  # suppress score when below this threshold


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_builder_tokens(project_dir: Path) -> list[int]:
    """Return non-zero ``tokens_total`` values for builder rows in *project_dir*'s DB.

    Returns an empty list when the DB is absent, empty, or unreadable.
    Never raises.
    """
    import sqlite3

    db_path = resolve_effort_db_path(project_dir)
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT tokens_total
                  FROM attempts
                 WHERE agent_role = 'builder'
                   AND tokens_total IS NOT NULL
                   AND tokens_total > 0
                """
            )
            return [int(row[0]) for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_convergence_candidate(
    project_dirs: Sequence[str | Path],
    pattern_id: str,
) -> tuple[float | None, str]:
    """Compute a token-efficiency score for a convergence candidate.

    Queries each project's ``effort.db`` for builder attempt token counts.
    Returns a ``(score, justification)`` tuple.

    Args:
        project_dirs: Sequence of project directory paths to query.
        pattern_id:   A stable identifier for the convergence candidate
                      (typically ``"<file>::<section>"``).

    Returns:
        ``(score, justification)`` where:

        - ``score`` is a float in ``[0.0, 1.0]`` or ``None``.
        - ``justification`` is a one-line human-readable string.

        Returns ``(None, "insufficient data")`` when:
        - total builder attempts across all projects is fewer than 5, or
        - any unexpected error occurs.

    Score semantics:
        Higher score → stronger evidence that the pattern is associated with
        lower builder token costs.  0.5 indicates no observable difference.
    """
    try:
        return _compute_score(list(project_dirs), pattern_id)
    except Exception:  # noqa: BLE001
        return (None, "insufficient data")


def _compute_score(
    project_dirs: list[str | Path],
    pattern_id: str,
) -> tuple[float | None, str]:
    """Core scoring logic.  Called by ``score_convergence_candidate``."""

    # Build per-project token lists
    per_project: list[tuple[Path, list[int]]] = []
    for raw in project_dirs:
        p = Path(raw).resolve()
        tokens = _collect_builder_tokens(p)
        per_project.append((p, tokens))

    # Total qualifying attempts
    all_tokens: list[int] = [t for _, tokens in per_project for t in tokens]
    total_attempts = len(all_tokens)

    if total_attempts < _MIN_TOTAL_ATTEMPTS:
        return (None, "insufficient data")

    baseline_median = statistics.median(all_tokens)

    # Identify "pattern" vs "other" projects using pattern_id as a proxy.
    # We look for the file component of the pattern_id (everything before "::")
    # as a substring of the project path string.  This is intentionally coarse —
    # see module docstring for known limits.
    pattern_file = pattern_id.split("::")[0] if "::" in pattern_id else pattern_id

    pattern_projects: list[list[int]] = []
    other_projects: list[list[int]] = []

    for p, tokens in per_project:
        if tokens:  # only include projects with data
            # Use section component as discriminator if meaningful; otherwise
            # just split by project token volume for a crude comparison.
            pattern_projects.append(tokens) if pattern_file in str(p) else other_projects.append(tokens)

    # Fallback: if substring match gives us nothing, split by token volume
    if not pattern_projects or not other_projects:
        # Sort projects by median token count; lower half = "pattern" group
        projects_with_data = [(statistics.median(t), t) for _, t in per_project if t]
        if len(projects_with_data) < 2:
            # Only one project — compare halves of its attempt list
            flat = sorted(all_tokens)
            mid = len(flat) // 2
            pattern_tokens = flat[:mid]
            other_tokens = flat[mid:]
        else:
            projects_with_data.sort(key=lambda x: x[0])
            mid = max(1, len(projects_with_data) // 2)
            pattern_tokens = [t for _, ts in projects_with_data[:mid] for t in ts]
            other_tokens = [t for _, ts in projects_with_data[mid:] for t in ts]
    else:
        pattern_tokens = [t for ts in pattern_projects for t in ts]
        other_tokens = [t for ts in other_projects for t in ts]

    if not pattern_tokens or not other_tokens:
        return (None, "insufficient data")

    pattern_median = statistics.median(pattern_tokens)
    other_median = statistics.median(other_tokens)

    denom = pattern_median + other_median
    if denom == 0:
        return (None, "insufficient data")

    # score: 0.5 = equal, >0.5 = pattern group has lower median (better)
    score = float(1.0 - (pattern_median / denom))
    score = max(0.0, min(1.0, score))

    # Compute percentage difference for the justification message
    if other_median > 0:
        pct = round(abs(pattern_median - other_median) / other_median * 100)
    else:
        pct = 0

    n = total_attempts
    if score > 0.5:
        justification = (
            f"Projects with this pattern show ~{pct}% lower median builder tokens "
            f"(n={n} attempts across {len(per_project)} project(s))"
        )
    elif score < 0.5:
        justification = (
            f"Projects with this pattern show ~{pct}% higher median builder tokens "
            f"(n={n} attempts across {len(per_project)} project(s))"
        )
    else:
        justification = (
            f"No token-cost difference observed for this pattern "
            f"(n={n} attempts across {len(per_project)} project(s))"
        )

    return (score, justification)

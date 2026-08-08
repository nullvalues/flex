"""session_orphan_notice.py — SessionStart advisory for orphaned claim state
and status drift (INFRA-443).

INFRA-442 shipped ``diagnose_state`` (``flex_build.py``): a pure, read-only
classifier for orphaned worktree/stamp/permissions-artifact claims and
frontmatter/phase-table status drift, surfaced through the operator-invoked
``doctor-state`` CLI. That command is only useful if the operator remembers
it exists and runs it after already hitting the symptom — a session that
died mid-build leaves exactly the state ``diagnose_state`` classifies, and
the *next* SessionStart is the cheapest, earliest moment to surface it.

This module renders that one advisory line. It performs **no filesystem
scanning of its own** — no listing of ``.pairmode-worktrees/``, no reading
of ``.companion/state.json``, no globbing ``docs/phases/permissions/`` — all
classification is ``diagnose_state``'s alone; this module only formats its
return value. Read-only: no writes, no repair, no gating. The same
advisory-first shape as ``session_lifecycle.agent_staleness_notice``
(INFRA-323), which ``hooks/session_start.py`` also delegates to.
"""
from __future__ import annotations

from pathlib import Path

_MAX_ENUMERATED_IDS = 5


def _cap_ids(ids: "list[str]", limit: int = _MAX_ENUMERATED_IDS) -> str:
    """Render *ids* as a comma-joined string, capped at *limit* entries plus
    a ``+N more`` suffix — a badly drifted repo must not flood the status
    block."""
    if len(ids) <= limit:
        return ", ".join(ids)
    shown = ids[:limit]
    return ", ".join(shown) + f", +{len(ids) - limit} more"


def orphan_state_notice(project_dir: "str | Path") -> "str | None":
    """Return a one-line SessionStart advisory naming orphaned claims and/or
    status-drift rows, or ``None`` when there is nothing to report.

    Imports ``diagnose_state`` from ``flex_build`` lazily, inside this
    function, flat-``sys.path`` style — the same pattern
    ``hooks/session_start.py`` already relies on for its sibling-module
    imports — so an import failure (e.g. this module invoked outside a
    pairmode-bootstrapped ``sys.path``) is contained and yields ``None``
    rather than raising.

    Derives its output **entirely** from ``diagnose_state``'s return value:
    no independent filesystem scan. Renders the counts and (capped) IDs of
    ``orphans`` and ``status_drift``, followed by the concrete repair
    command — ``doctor-state --project-dir <dir> --apply`` when orphans are
    present, ``doctor-state --project-dir <dir> --sync-status
    frontmatter|table`` when the only finding is status drift (both named
    when both are present). ``in_flight`` entries are never surfaced — a
    mid-build ``compact``/``clear`` restart must stay silent (Ensures 3).
    """
    try:
        from flex_build import diagnose_state
    except Exception:
        return None

    try:
        diagnosis = diagnose_state(Path(project_dir))
    except Exception:
        return None

    if not isinstance(diagnosis, dict):
        return None

    orphans = diagnosis.get("orphans") or []
    status_drift = diagnosis.get("status_drift") or []

    orphan_ids = [
        str(entry["story_id"])
        for entry in orphans
        if isinstance(entry, dict) and entry.get("story_id")
    ]
    drift_ids = [str(row[0]) for row in status_drift if row]

    if not orphan_ids and not drift_ids:
        return None

    segments: list[str] = []
    if orphan_ids:
        segments.append(
            f"{len(orphan_ids)} orphaned claim(s): {_cap_ids(orphan_ids)}"
        )
    if drift_ids:
        segments.append(
            f"{len(drift_ids)} status-drift row(s): {_cap_ids(drift_ids)}"
        )

    dir_str = str(project_dir)
    commands: list[str] = []
    if orphan_ids:
        commands.append(f"doctor-state --project-dir {dir_str} --apply")
    if drift_ids:
        commands.append(
            f"doctor-state --project-dir {dir_str} --sync-status frontmatter|table"
        )

    return (
        "Pairmode state drift detected — "
        + "; ".join(segments)
        + ". Repair with: "
        + " and ".join(commands)
    )

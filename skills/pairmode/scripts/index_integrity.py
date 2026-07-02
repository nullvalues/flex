"""
index_integrity.py — Pure-read graph invariant checker for the flex project index.

Computes four graph invariants and returns structured violations:

  1. Status drift — a story with a feat(story-<ID>) commit in git log but status
     not 'complete' or 'deferred'.
  2. Cross-link consistency — four sub-checks:
     (a) Every phase row in docs/phases/index.md has a corresponding phase file.
     (b) Every story's phase frontmatter names an existing phase doc.
     (c) Every era's phase table matches the index truth for phase status.
     (d) Deferred/backlog phases are treated as inactive (CER-056).
  3. Orphan story files — a docs/stories/<RAIL>/<ID>.md not referenced in any
     phase doc's Stories table.
  4. Deferred without section — a story marked 'deferred' whose phase doc lacks
     a ## Deferred stories section naming it.

Reuses:
  - next_story._git_log_oneline / _has_story_commit (commit-authority helpers)
  - flex_build._parse_index_phases / _parse_phase_stories_with_status / _is_aggregate_range
    (lazy import to avoid circular dependency — flex_build imports this module)

Pure-read: no write_text, json.dump, or file mutations anywhere in this module.

RESOLVER-010 / HARNESS008-main.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

# Ensure sibling modules are importable when invoked as a script or imported.
sys.path.insert(0, str(Path(__file__).parent))

# Reuse commit-authority helpers from next_story.py (HARNESS001 requirement).
from next_story import _git_log_oneline  # noqa: E402
from next_story import _has_story_commit  # noqa: E402
from schema_validator import _parse_frontmatter  # noqa: E402


# ---------------------------------------------------------------------------
# Public data type
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    """A single graph-invariant violation."""

    kind: str  # "status-drift" | "cross-link" | "orphan-story" | "deferred-without-section"
    ids: list[str] = field(default_factory=list)
    path: str = ""
    reason: str = ""

    def __eq__(self, other: object) -> bool:  # needed for list comparison in tests
        if not isinstance(other, Violation):
            return NotImplemented
        return (self.kind, self.ids, self.path, self.reason) == (
            other.kind, other.ids, other.path, other.reason
        )


# ---------------------------------------------------------------------------
# Public helper (imported by RESOLVER-011)
# ---------------------------------------------------------------------------


def is_phase_inactive(status: str) -> bool:
    """Return True for statuses that represent inactive phases (CER-056).

    Inactive statuses: 'complete', 'deferred', 'backlog'.
    Active statuses (anything else): 'active', 'planned', '', etc.
    """
    return status in ("complete", "deferred", "backlog")


# ---------------------------------------------------------------------------
# Era phase table parser
# ---------------------------------------------------------------------------

_DEFERRED_SECTION_RE = re.compile(
    r"^##\s+Deferred stories\s*$", re.MULTILINE | re.IGNORECASE
)


def _parse_era_phase_table(era_text: str) -> list[tuple[str, str]]:
    """Parse phase rows from an era doc's Phases table.

    Searches for pipe tables that have both a 'Phase' (or 'Phase key' / 'Phase ref')
    column and a 'Status' column.  Returns [(phase_ref, status)].
    Skips aggregate-range rows (e.g. '1–7').

    Lazily imports _is_aggregate_range from flex_build to avoid circular imports.
    """
    # Lazy import — flex_build imports index_integrity at module level,
    # so we must not import flex_build at index_integrity's module level.
    from flex_build import _is_aggregate_range  # noqa: PLC0415

    rows: list[tuple[str, str]] = []
    in_table = False
    header_seen = False
    separator_seen = False
    phase_col_idx: int = -1
    status_col_idx: int = -1

    for line in era_text.splitlines():
        stripped = line.strip()

        if not stripped.startswith("|"):
            if in_table and stripped:
                # End of this table — reset for next table.
                in_table = False
                header_seen = False
                separator_seen = False
                phase_col_idx = -1
                status_col_idx = -1
            continue

        in_table = True
        parts = [p.strip() for p in stripped.split("|")]
        # parts[0] is '' (before first |), parts[-1] is '' (after last |)

        if not header_seen:
            # Detect Phase and Status column positions.
            for i, p in enumerate(parts):
                pl = p.lower()
                if pl in ("phase", "phase ref", "phase key"):
                    phase_col_idx = i
                if pl == "status":
                    status_col_idx = i
            if phase_col_idx >= 0 and status_col_idx >= 0:
                header_seen = True
            else:
                # Not a phase-status table; reset.
                in_table = False
                phase_col_idx = -1
                status_col_idx = -1
            continue

        if not separator_seen:
            separator_seen = True
            continue

        if len(parts) <= max(phase_col_idx, status_col_idx):
            continue

        phase_ref = parts[phase_col_idx].strip()
        if not phase_ref or _is_aggregate_range(phase_ref):
            continue

        status = parts[status_col_idx].strip().lower()
        rows.append((phase_ref, status))

    return rows


# ---------------------------------------------------------------------------
# Main checker — pure read
# ---------------------------------------------------------------------------


def check_index(project_dir: Path) -> list[Violation]:
    """Run all four graph-invariant checks and return a list of Violation objects.

    Pure-read: makes no writes to any file.

    Lazily imports flex_build helpers to avoid circular imports.
    """
    # Lazy imports — flex_build imports this module at module level.
    from flex_build import _is_aggregate_range  # noqa: F401,PLC0415 (needed via era parser)
    from flex_build import _parse_index_phases  # noqa: PLC0415
    from flex_build import _parse_phase_stories_with_status  # noqa: PLC0415

    violations: list[Violation] = []

    phases_dir = project_dir / "docs" / "phases"
    stories_dir = project_dir / "docs" / "stories"

    # --- Parse the phase index ---
    index_path = project_dir / "docs" / "phases" / "index.md"
    index_rows: list[tuple[str, str]] = []
    index_phase_status: dict[str, str] = {}

    if index_path.exists():
        try:
            index_text = index_path.read_text(encoding="utf-8")
            index_rows = _parse_index_phases(index_text)
            index_phase_status = {ref: status for ref, status in index_rows}
        except OSError:
            pass

    # --- Collect all story files ---
    all_story_files: list[Path] = []
    if stories_dir.exists():
        all_story_files = sorted(stories_dir.rglob("*.md"))

    # --- Git log (single call; reused for check 1) ---
    git_log = _git_log_oneline(project_dir)

    # =========================================================================
    # Check 1: Status drift
    # A story with a feat(story-<ID>) commit in git log but status not
    # 'complete' or 'deferred'.
    # =========================================================================
    for story_file in all_story_files:
        try:
            text = story_file.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text) or {}
        story_id = (fm.get("id") or story_file.stem).strip()
        status = (fm.get("status") or "").lower().strip()

        if _has_story_commit(story_id, git_log) and status not in ("complete", "deferred"):
            violations.append(
                Violation(
                    kind="status-drift",
                    ids=[story_id],
                    path=str(story_file.relative_to(project_dir)),
                    reason=(
                        f"commit feat(story-{story_id}) exists but status is "
                        f"{status!r} (expected 'complete' or 'deferred')"
                    ),
                )
            )

    # =========================================================================
    # Check 2: Cross-link consistency
    # =========================================================================

    # 2a: Every phase row in index.md has a corresponding phase-<key>.md
    for phase_ref, _status in index_rows:
        phase_file = phases_dir / f"phase-{phase_ref}.md"
        if not phase_file.exists():
            violations.append(
                Violation(
                    kind="cross-link",
                    ids=[phase_ref],
                    path=str((phases_dir / f"phase-{phase_ref}.md").relative_to(project_dir)),
                    reason=(
                        f"index lists phase-{phase_ref} but "
                        f"docs/phases/phase-{phase_ref}.md does not exist"
                    ),
                )
            )

    # 2b: Every story's phase frontmatter names an existing phase doc
    for story_file in all_story_files:
        try:
            text = story_file.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text) or {}
        story_id = (fm.get("id") or story_file.stem).strip()
        phase_id = fm.get("phase")
        if phase_id is None:
            continue
        # _parse_frontmatter already strips quotes.
        phase_id_str = str(phase_id).strip()
        if not phase_id_str:
            continue
        phase_file = phases_dir / f"phase-{phase_id_str}.md"
        if not phase_file.exists():
            violations.append(
                Violation(
                    kind="cross-link",
                    ids=[story_id],
                    path=str(story_file.relative_to(project_dir)),
                    reason=(
                        f"story {story_id} phase frontmatter references "
                        f"phase-{phase_id_str}.md which does not exist"
                    ),
                )
            )

    # 2c: Era phase tables match index truth for phase status
    eras_dir = project_dir / "docs" / "eras"
    if eras_dir.exists():
        for era_file in sorted(eras_dir.glob("*.md")):
            try:
                era_text = era_file.read_text(encoding="utf-8")
            except OSError:
                continue
            era_rows = _parse_era_phase_table(era_text)
            for phase_ref, era_status in era_rows:
                if phase_ref not in index_phase_status:
                    # Era references a phase not in the index — skip (not our job here).
                    continue
                index_status = index_phase_status[phase_ref]
                if era_status != index_status:
                    violations.append(
                        Violation(
                            kind="cross-link",
                            ids=[phase_ref],
                            path=str(era_file.relative_to(project_dir)),
                            reason=(
                                f"era doc shows phase-{phase_ref} as {era_status!r} "
                                f"but index says {index_status!r}"
                            ),
                        )
                    )

    # =========================================================================
    # Check 3: Orphan story files
    # A docs/stories/<RAIL>/<ID>.md not referenced in any phase doc's Stories table.
    # =========================================================================
    referenced_story_ids: set[str] = set()
    if phases_dir.exists():
        for phase_file in sorted(phases_dir.glob("phase-*.md")):
            try:
                phase_text = phase_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for sid, _title, _status in _parse_phase_stories_with_status(phase_text):
                referenced_story_ids.add(sid)

    for story_file in all_story_files:
        try:
            text = story_file.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text) or {}
        story_id = (fm.get("id") or story_file.stem).strip()
        if story_id not in referenced_story_ids:
            violations.append(
                Violation(
                    kind="orphan-story",
                    ids=[story_id],
                    path=str(story_file.relative_to(project_dir)),
                    reason=(
                        f"story {story_id} not referenced in any phase doc's Stories table"
                    ),
                )
            )

    # =========================================================================
    # Check 4: Deferred without section
    # A story marked 'deferred' whose phase doc lacks a ## Deferred stories
    # section naming that story.
    # =========================================================================
    for story_file in all_story_files:
        try:
            text = story_file.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text) or {}
        story_id = (fm.get("id") or story_file.stem).strip()
        status = (fm.get("status") or "").lower().strip()
        if status != "deferred":
            continue

        phase_id = fm.get("phase")
        if phase_id is None:
            continue
        phase_id_str = str(phase_id).strip()
        if not phase_id_str:
            continue

        phase_file = phases_dir / f"phase-{phase_id_str}.md"
        if not phase_file.exists():
            # Already caught by cross-link 2b.
            continue

        try:
            phase_text = phase_file.read_text(encoding="utf-8")
        except OSError:
            continue

        m = _DEFERRED_SECTION_RE.search(phase_text)
        if not m:
            violations.append(
                Violation(
                    kind="deferred-without-section",
                    ids=[story_id],
                    path=str(phase_file.relative_to(project_dir)),
                    reason=(
                        f"story {story_id} is deferred but phase-{phase_id_str}.md "
                        f"has no ## Deferred stories section"
                    ),
                )
            )
            continue

        # Section exists — verify it names this story ID.
        section_text = phase_text[m.end():]
        next_heading = re.search(r"^##\s+", section_text, re.MULTILINE)
        if next_heading:
            section_text = section_text[: next_heading.start()]

        if story_id not in section_text:
            violations.append(
                Violation(
                    kind="deferred-without-section",
                    ids=[story_id],
                    path=str(phase_file.relative_to(project_dir)),
                    reason=(
                        f"story {story_id} is deferred but not named in the "
                        f"## Deferred stories section of phase-{phase_id_str}.md"
                    ),
                )
            )

    return violations

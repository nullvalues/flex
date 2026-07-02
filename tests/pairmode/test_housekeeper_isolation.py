"""
tests/pairmode/test_housekeeper_isolation.py

Consolidated hermetic isolation suite for the housekeeper (check_index) and
resolver read-model (infer_position) — RESOLVER-011 / CER-056.

Matrix coverage
---------------
- One fixture per violation class (status drift, broken cross-link, orphan
  file, deferred-without-section): each flags exactly that violation and no
  other.
- Clean tree → no violations (check_index returns []).
- CER-056 fixture: a project with a ``deferred`` phase (trailing entry in the
  index after an active phase) is treated as inactive by **both**
  ``check_index`` (no spurious violations) and ``infer_position`` (the active
  phase is returned, not the deferred one).

No network. No live git-history dependence — all git log calls are
monkeypatched; synthetic project trees only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Import wiring
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).parent
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
for _d in (_TESTS_DIR, _SCRIPTS_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from index_integrity import Violation, check_index  # noqa: E402
from next_action import infer_position  # noqa: E402
from resolver_fixtures import make_resolver_project  # noqa: E402


# ---------------------------------------------------------------------------
# Shared git-log patcher
# ---------------------------------------------------------------------------


def _patch_git_log(monkeypatch: Any, log_output: str = "") -> None:
    """Monkeypatch next_story._git_log_oneline to return a fixed string."""
    import next_story as _ns  # type: ignore[import]
    monkeypatch.setattr(_ns, "_git_log_oneline", lambda _p: log_output)


# ---------------------------------------------------------------------------
# Fixture builder helpers
# ---------------------------------------------------------------------------


def _write_story(
    project: Path,
    story_id: str,
    *,
    status: str = "planned",
    phase_ref: str = "1",
) -> None:
    """Write (or overwrite) a story file with the given status and phase ref."""
    rail = story_id.split("-", 1)[0]
    story_dir = project / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / f"{story_id}.md").write_text(
        f"---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"status: {status}\n"
        f"phase: '{phase_ref}'\n"
        f"primary_files: []\n"
        f"---\n\n"
        f"## Ensures\n\n- It works.\n- Tests pass.\n- No regressions.\n"
        f"- All inputs validated.\n- Output format correct.\n",
        encoding="utf-8",
    )


def _make_cer056_project(tmp_path: Path) -> Path:
    """Build a two-phase project that exercises the CER-056 fix.

    The index lists an active phase (1) first, followed by a deferred phase
    (2).  Old code would return ``phase-2.md`` (last non-complete).  Fixed
    code must return ``phase-1.md`` (last non-inactive per is_phase_inactive).
    """
    # Use make_resolver_project to scaffold the active phase (phase ref "1").
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "phase_ref": "1",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
        },
    )

    # Write a deferred phase doc (phase-2.md) with a proper deferred section.
    deferred_phase = project / "docs" / "phases" / "phase-2.md"
    deferred_phase.write_text(
        "# Phase 2\n\n"
        "## Stories\n\n"
        "| ID | Title | Status |\n"
        "|----|-------|--------|\n"
        "| TEST-002 | Deferred story | deferred |\n\n"
        "## Deferred stories\n\n"
        "TEST-002 was deferred.\n",
        encoding="utf-8",
    )

    # Write the deferred story file.
    story_dir = project / "docs" / "stories" / "TEST"
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "TEST-002.md").write_text(
        "---\n"
        "id: TEST-002\n"
        "rail: TEST\n"
        "status: deferred\n"
        "phase: '2'\n"
        "primary_files: []\n"
        "---\n\n"
        "Deferred story.\n",
        encoding="utf-8",
    )

    # Overwrite the phase index: active phase (1) first, deferred phase (2) second.
    # This is the layout that triggers the CER-056 bug in unfixed code.
    index_path = project / "docs" / "phases" / "index.md"
    index_path.write_text(
        "# Phase Index\n\n"
        "| Phase | Title | Status | Tag |\n"
        "|-------|-------|--------|-----|\n"
        "| 1 | Active Phase | active | |\n"
        "| 2 | Deferred Phase | deferred | |\n",
        encoding="utf-8",
    )

    return project


# ---------------------------------------------------------------------------
# 1. Clean tree — no violations
# ---------------------------------------------------------------------------


def test_clean_tree_no_violations(tmp_path: Path, monkeypatch: Any) -> None:
    """A well-formed project with no commits and one planned story → no violations."""
    _patch_git_log(monkeypatch, "")
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    assert check_index(project) == []


# ---------------------------------------------------------------------------
# 2. Status-drift isolation — exactly one violation, no others
# ---------------------------------------------------------------------------


def test_status_drift_flags_only_that_class(tmp_path: Path, monkeypatch: Any) -> None:
    """Planned story with a feat(story-<ID>) commit → only status-drift violation.

    Uses a real commit in the isolated synthetic git repo so that
    index_integrity._git_log_oneline (module-level import) picks it up without
    needing a separate monkeypatch.  The synthetic repo is hermetic — no
    dependence on the live flex-harness git history.
    """
    _patch_git_log(monkeypatch, "")  # ensure infer_position calls see no commits
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            # Real commit in the synthetic repo so check_index detects it.
            "git_commits": ["feat(story-TEST-001): implement"],
            "phase_ref": "1",
        },
    )
    violations = check_index(project)
    drift = [v for v in violations if v.kind == "status-drift"]
    other = [v for v in violations if v.kind != "status-drift"]
    assert len(drift) == 1, f"Expected 1 status-drift, got: {drift}"
    assert "TEST-001" in drift[0].ids
    assert other == [], f"Unexpected violations of other classes: {other}"


# ---------------------------------------------------------------------------
# 3. Broken cross-link isolation — exactly one violation, no others
# ---------------------------------------------------------------------------


def test_cross_link_flags_only_that_class(tmp_path: Path, monkeypatch: Any) -> None:
    """Index row with no corresponding phase file → only cross-link violation."""
    _patch_git_log(monkeypatch, "")
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    # Add a ghost phase row to the index (no matching phase-ghost-main.md).
    index_path = project / "docs" / "phases" / "index.md"
    index_path.write_text(
        index_path.read_text(encoding="utf-8")
        + "| ghost-main | Ghost Phase | active | |\n",
        encoding="utf-8",
    )
    violations = check_index(project)
    cross = [v for v in violations if v.kind == "cross-link"]
    other = [v for v in violations if v.kind != "cross-link"]
    assert any("ghost-main" in v.ids for v in cross), (
        f"Expected cross-link for ghost-main, got: {violations}"
    )
    assert other == [], f"Unexpected violations of other classes: {other}"


# ---------------------------------------------------------------------------
# 4. Orphan file isolation — exactly one violation, no others
# ---------------------------------------------------------------------------


def test_orphan_file_flags_only_that_class(tmp_path: Path, monkeypatch: Any) -> None:
    """Story file not in any phase Stories table → only orphan-story violation."""
    _patch_git_log(monkeypatch, "")
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    # Add an orphan story not mentioned in any phase.
    orphan_dir = project / "docs" / "stories" / "TEST"
    (orphan_dir / "TEST-999.md").write_text(
        "---\nid: TEST-999\nrail: TEST\nstatus: planned\nphase: '1'\n---\n",
        encoding="utf-8",
    )
    violations = check_index(project)
    orphans = [v for v in violations if v.kind == "orphan-story"]
    other = [v for v in violations if v.kind != "orphan-story"]
    assert any("TEST-999" in v.ids for v in orphans), (
        f"Expected orphan-story for TEST-999, got: {violations}"
    )
    assert other == [], f"Unexpected violations of other classes: {other}"


# ---------------------------------------------------------------------------
# 5. Deferred-without-section isolation — exactly one violation, no others
# ---------------------------------------------------------------------------


def test_deferred_without_section_flags_only_that_class(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Deferred story with no ## Deferred stories section → only that violation."""
    _patch_git_log(monkeypatch, "")
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "deferred", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    # Overwrite story to status: deferred (make_resolver_project writes planned).
    _write_story(project, "TEST-001", status="deferred", phase_ref="1")

    violations = check_index(project)
    deferred_v = [v for v in violations if v.kind == "deferred-without-section"]
    other = [v for v in violations if v.kind != "deferred-without-section"]
    assert any("TEST-001" in v.ids for v in deferred_v), (
        f"Expected deferred-without-section for TEST-001, got: {violations}"
    )
    assert other == [], f"Unexpected violations of other classes: {other}"


# ---------------------------------------------------------------------------
# 6. CER-056 fixture — check_index treats deferred phase as inactive
# ---------------------------------------------------------------------------


def test_cer056_check_index_deferred_phase_no_spurious_violations(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Properly documented deferred phase → check_index emits no violations."""
    _patch_git_log(monkeypatch, "")
    project = _make_cer056_project(tmp_path)

    violations = check_index(project)
    assert violations == [], (
        f"Expected no violations for a clean two-phase project, got: {violations}"
    )


# ---------------------------------------------------------------------------
# 7. CER-056 fixture — infer_position returns active phase, not deferred
# ---------------------------------------------------------------------------


def test_cer056_infer_position_returns_active_not_deferred_phase(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """infer_position must return the active phase (1), not the trailing deferred (2).

    The CER-056 layout has an active phase first (index row 1) and a deferred
    phase second (index row 2).  Old code selected the last non-complete row,
    which is the deferred phase.  Fixed code uses is_phase_inactive and selects
    the last non-inactive row (the active phase).
    """
    _patch_git_log(monkeypatch, "")
    project = _make_cer056_project(tmp_path)

    pos = infer_position(project)

    active_phase = pos["active_phase_file"]
    assert active_phase is not None, "infer_position returned no active phase"

    # Must point to phase-1.md (active), not phase-2.md (deferred).
    assert Path(str(active_phase)).name == "phase-1.md", (
        f"Expected active_phase_file to be phase-1.md, got: {active_phase}"
    )

    # The next story must be from the active phase (TEST-001), not deferred (TEST-002).
    assert pos["next_story_id"] == "TEST-001", (
        f"Expected next_story_id TEST-001, got: {pos['next_story_id']}"
    )

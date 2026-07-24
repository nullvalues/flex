"""
tests/pairmode/test_index_integrity.py

Tests for skills/pairmode/scripts/index_integrity.py (RESOLVER-010).

One fixture per violation class that flags exactly that violation.
A clean tree produces no violations.
A deferred phase fixture is treated as inactive (is_phase_inactive).
No network, no live git-history dependence — synthetic project trees only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure both the scripts directory and the tests/pairmode directory are importable.
_TESTS_DIR = Path(__file__).parent
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
for _d in (_TESTS_DIR, _SCRIPTS_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from index_integrity import Violation, check_index, is_phase_inactive  # noqa: E402
from resolver_fixtures import make_resolver_project  # noqa: E402


# ---------------------------------------------------------------------------
# Utilities
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


def _add_deferred_section(phase_path: Path, story_id: str) -> None:
    """Append a ## Deferred stories section naming story_id to a phase doc."""
    existing = phase_path.read_text(encoding="utf-8")
    phase_path.write_text(
        existing + f"\n## Deferred stories\n\n{story_id} was deferred.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# is_phase_inactive
# ---------------------------------------------------------------------------


def test_is_phase_inactive_complete() -> None:
    assert is_phase_inactive("complete") is True


def test_is_phase_inactive_deferred() -> None:
    assert is_phase_inactive("deferred") is True


def test_is_phase_inactive_backlog() -> None:
    assert is_phase_inactive("backlog") is True


def test_is_phase_inactive_active() -> None:
    assert is_phase_inactive("active") is False


def test_is_phase_inactive_planned() -> None:
    assert is_phase_inactive("planned") is False


def test_is_phase_inactive_empty() -> None:
    assert is_phase_inactive("") is False


# ---------------------------------------------------------------------------
# Clean tree → zero violations
# ---------------------------------------------------------------------------


def test_clean_tree_no_violations(tmp_path: Path) -> None:
    """A well-formed project with no commits and one planned story → no violations."""
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
# Check 1: Status drift
# ---------------------------------------------------------------------------


def test_status_drift_planned_with_commit(tmp_path: Path) -> None:
    """Story with feat(story-<ID>) commit but status 'planned' → status-drift."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": ["feat(story-TEST-001): implement"],
            "phase_ref": "1",
        },
    )
    violations = check_index(project)
    drift = [v for v in violations if v.kind == "status-drift"]
    assert len(drift) == 1, f"Expected 1 drift violation, got: {drift}"
    assert "TEST-001" in drift[0].ids


def test_status_drift_only_that_violation(tmp_path: Path) -> None:
    """Status-drift fixture flags only status-drift, not other kinds."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": ["feat(story-TEST-001): implement"],
            "phase_ref": "1",
        },
    )
    violations = check_index(project)
    non_drift = [v for v in violations if v.kind != "status-drift"]
    assert non_drift == [], f"Unexpected non-drift violations: {non_drift}"


def test_status_drift_complete_status_not_flagged(tmp_path: Path) -> None:
    """Story with commit and status 'complete' is NOT flagged as drift."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": ["feat(story-TEST-001): implement"],
            "phase_ref": "1",
        },
    )
    # Overwrite story file to have status: complete.
    _write_story(project, "TEST-001", status="complete", phase_ref="1")
    violations = check_index(project)
    drift = [v for v in violations if v.kind == "status-drift"]
    assert drift == [], f"Unexpected drift for complete story: {drift}"


def test_status_drift_deferred_status_not_flagged(tmp_path: Path) -> None:
    """Story with commit and status 'deferred' is NOT flagged as drift."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": ["feat(story-TEST-001): implement"],
            "phase_ref": "1",
        },
    )
    _write_story(project, "TEST-001", status="deferred", phase_ref="1")
    violations = check_index(project)
    drift = [v for v in violations if v.kind == "status-drift"]
    assert drift == [], f"Unexpected drift for deferred story: {drift}"


def test_status_drift_no_commit_no_violation(tmp_path: Path) -> None:
    """Story with status 'planned' and no commit → no drift."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    violations = check_index(project)
    drift = [v for v in violations if v.kind == "status-drift"]
    assert drift == []


# ---------------------------------------------------------------------------
# Check 2a: Cross-link — index row with no phase file
# ---------------------------------------------------------------------------


def test_cross_link_missing_phase_file(tmp_path: Path) -> None:
    """Index row with no corresponding phase-<key>.md → cross-link violation."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    # Inject a ghost phase row into index.md (no matching phase file exists).
    index_path = project / "docs" / "phases" / "index.md"
    index_text = index_path.read_text(encoding="utf-8")
    index_path.write_text(
        index_text + "| ghost-main | Ghost Phase | active | |\n", encoding="utf-8"
    )

    violations = check_index(project)
    cross = [v for v in violations if v.kind == "cross-link"]
    assert any(
        "ghost-main" in v.ids for v in cross
    ), f"Expected cross-link for ghost-main, got: {violations}"


def test_cross_link_missing_phase_file_only_that_violation(tmp_path: Path) -> None:
    """cross-link (2a) fixture flags only that cross-link, no other kinds."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    index_path = project / "docs" / "phases" / "index.md"
    index_text = index_path.read_text(encoding="utf-8")
    index_path.write_text(
        index_text + "| ghost-main | Ghost Phase | active | |\n", encoding="utf-8"
    )

    violations = check_index(project)
    non_cross = [v for v in violations if v.kind != "cross-link"]
    assert non_cross == [], f"Unexpected non-cross violations: {non_cross}"


# ---------------------------------------------------------------------------
# Check 2b: Cross-link — story phase frontmatter → non-existent phase doc
# ---------------------------------------------------------------------------


def test_cross_link_story_phase_nonexistent(tmp_path: Path) -> None:
    """Story's phase frontmatter pointing to non-existent phase → cross-link."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    # Overwrite story to reference a non-existent phase.
    _write_story(project, "TEST-001", status="planned", phase_ref="999-ghost")

    violations = check_index(project)
    cross = [v for v in violations if v.kind == "cross-link"]
    assert any(
        "TEST-001" in v.ids for v in cross
    ), f"Expected cross-link for TEST-001, got: {violations}"


# ---------------------------------------------------------------------------
# Check 2c: Cross-link — era table status mismatch
# ---------------------------------------------------------------------------


def _write_era_with_phase_status(eras_dir: Path, phase_ref: str, status: str) -> None:
    """Write a minimal era doc with a Phases table claiming phase_ref has status."""
    eras_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\nid: '001'\nname: Test Era\nstatus: complete\n---\n\n"
        "## Phases\n\n"
        "| Phase | Title | Status |\n"
        "|-------|-------|--------|\n"
        f"| {phase_ref} | Test Phase | {status} |\n"
    )
    (eras_dir / "001-test.md").write_text(content, encoding="utf-8")


def test_cross_link_era_status_mismatch(tmp_path: Path) -> None:
    """Era doc claiming different phase status from index → cross-link violation."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "complete",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    eras_dir = project / "docs" / "eras"
    # Era says "active" but index says "complete".
    _write_era_with_phase_status(eras_dir, "1", "active")

    violations = check_index(project)
    cross = [v for v in violations if v.kind == "cross-link"]
    assert any(
        "1" in v.ids and "era" in v.reason for v in cross
    ), f"Expected era cross-link for phase 1, got: {violations}"


def test_cross_link_era_status_match_no_violation(tmp_path: Path) -> None:
    """Era doc with matching phase status → no era cross-link violation."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "complete",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    eras_dir = project / "docs" / "eras"
    # Era status matches index status.
    _write_era_with_phase_status(eras_dir, "1", "complete")

    violations = check_index(project)
    era_cross = [v for v in violations if v.kind == "cross-link" and "era" in v.reason]
    assert era_cross == [], f"Unexpected era cross-link violations: {era_cross}"


def test_era_table_without_status_column_ignored(tmp_path: Path) -> None:
    """Era table lacking a Status column (e.g. Phase key/Title/Rail/Intent) is not parsed."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    eras_dir = project / "docs" / "eras"
    eras_dir.mkdir(parents=True, exist_ok=True)
    # Table with Phase key/Title/Rail/Intent — no Status column.
    content = (
        "---\nid: '003'\nname: Harness\nstatus: active\n---\n\n"
        "## Phases\n\n"
        "| Phase key | Title | Rail | Intent |\n"
        "|-----------|-------|------|--------|\n"
        "| 1 | Test Phase | TEST | Some intent |\n"
    )
    (eras_dir / "003-test.md").write_text(content, encoding="utf-8")

    violations = check_index(project)
    era_cross = [v for v in violations if v.kind == "cross-link" and "era" in v.reason]
    assert era_cross == [], f"Unexpected era cross-link violations: {era_cross}"


# ---------------------------------------------------------------------------
# Check 3: Orphan story files
# ---------------------------------------------------------------------------


def test_orphan_story_not_in_phase(tmp_path: Path) -> None:
    """Story file not in any phase doc's Stories table → orphan-story violation."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    # Add an orphan story file not mentioned in any phase.
    orphan_dir = project / "docs" / "stories" / "TEST"
    (orphan_dir / "TEST-999.md").write_text(
        "---\nid: TEST-999\nrail: TEST\nstatus: planned\nphase: '1'\n---\n",
        encoding="utf-8",
    )

    violations = check_index(project)
    orphans = [v for v in violations if v.kind == "orphan-story"]
    assert any(
        "TEST-999" in v.ids for v in orphans
    ), f"Expected orphan for TEST-999, got: {violations}"


def test_orphan_story_only_that_violation(tmp_path: Path) -> None:
    """Orphan fixture flags only orphan-story, not other kinds."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    orphan_dir = project / "docs" / "stories" / "TEST"
    (orphan_dir / "TEST-999.md").write_text(
        "---\nid: TEST-999\nrail: TEST\nstatus: planned\nphase: '1'\n---\n",
        encoding="utf-8",
    )

    violations = check_index(project)
    non_orphan = [v for v in violations if v.kind != "orphan-story"]
    assert non_orphan == [], f"Unexpected non-orphan violations: {non_orphan}"


def test_referenced_story_not_flagged_as_orphan(tmp_path: Path) -> None:
    """Story referenced in a phase doc is NOT flagged as orphan."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    violations = check_index(project)
    orphans = [v for v in violations if v.kind == "orphan-story"]
    assert not any(
        "TEST-001" in v.ids for v in orphans
    ), f"TEST-001 should not be an orphan"


# ---------------------------------------------------------------------------
# Check 4: Deferred without section
# ---------------------------------------------------------------------------


def test_deferred_without_section(tmp_path: Path) -> None:
    """Deferred story with no ## Deferred stories section in phase doc → violation."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "deferred", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    # Overwrite the story to actually have status: deferred.
    _write_story(project, "TEST-001", status="deferred", phase_ref="1")
    # Phase doc has no ## Deferred stories section.

    violations = check_index(project)
    deferred_v = [v for v in violations if v.kind == "deferred-without-section"]
    assert len(deferred_v) >= 1, f"Expected deferred-without-section, got: {violations}"
    assert any("TEST-001" in v.ids for v in deferred_v)


def test_deferred_without_section_only_that_violation(tmp_path: Path) -> None:
    """Deferred-without-section fixture flags only that kind."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "deferred", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    _write_story(project, "TEST-001", status="deferred", phase_ref="1")

    violations = check_index(project)
    non_deferred = [v for v in violations if v.kind != "deferred-without-section"]
    assert non_deferred == [], f"Unexpected non-deferred violations: {non_deferred}"


def test_deferred_with_section_naming_story_no_violation(tmp_path: Path) -> None:
    """Deferred story named in ## Deferred stories section → no violation."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "deferred", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    _write_story(project, "TEST-001", status="deferred", phase_ref="1")

    phase_path = project / "docs" / "phases" / "phase-1.md"
    _add_deferred_section(phase_path, "TEST-001")

    violations = check_index(project)
    deferred_v = [v for v in violations if v.kind == "deferred-without-section"]
    assert deferred_v == [], f"Unexpected deferred violations: {deferred_v}"


def test_deferred_section_exists_but_does_not_name_story(tmp_path: Path) -> None:
    """## Deferred stories section exists but omits the story ID → violation."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "deferred", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    _write_story(project, "TEST-001", status="deferred", phase_ref="1")

    # Add a deferred section that names a DIFFERENT story.
    phase_path = project / "docs" / "phases" / "phase-1.md"
    existing = phase_path.read_text(encoding="utf-8")
    phase_path.write_text(
        existing + "\n## Deferred stories\n\nTEST-002 was deferred.\n",
        encoding="utf-8",
    )

    violations = check_index(project)
    deferred_v = [v for v in violations if v.kind == "deferred-without-section"]
    assert any(
        "TEST-001" in v.ids for v in deferred_v
    ), f"Expected deferred-without-section for TEST-001, got: {violations}"


# ---------------------------------------------------------------------------
# Deferred phase treated as inactive (CER-056)
# ---------------------------------------------------------------------------


def test_deferred_phase_inactive_helper() -> None:
    """is_phase_inactive returns True for 'deferred' — CER-056 helper contract."""
    assert is_phase_inactive("deferred") is True


def test_deferred_phase_no_spurious_violations(tmp_path: Path) -> None:
    """Project with a deferred phase and a properly deferred story → no spurious violations."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "deferred",
            "stories": [("TEST-001", "deferred", "code", [])],
            "git_commits": [],
            "phase_ref": "1",
        },
    )
    _write_story(project, "TEST-001", status="deferred", phase_ref="1")

    # Add the required ## Deferred stories section.
    phase_path = project / "docs" / "phases" / "phase-1.md"
    _add_deferred_section(phase_path, "TEST-001")

    violations = check_index(project)
    # Expect no status-drift (no commits), no deferred-without-section (section present).
    drift_v = [v for v in violations if v.kind == "status-drift"]
    deferred_v = [v for v in violations if v.kind == "deferred-without-section"]
    assert drift_v == [], f"Unexpected drift violations: {drift_v}"
    assert deferred_v == [], f"Unexpected deferred violations: {deferred_v}"


def test_backlog_phase_inactive() -> None:
    """is_phase_inactive returns True for 'backlog' — CER-056."""
    assert is_phase_inactive("backlog") is True

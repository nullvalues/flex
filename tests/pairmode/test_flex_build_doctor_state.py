"""Tests for flex_build.py doctor-state subcommand (INFRA-442).

Covers the pure classifier `diagnose_state` and the thin printing/repair
command over it: report-mode zero-write default, `--apply` full teardown of
an orphan (F1/CER-236 regression), `--apply` recovery from the exact
post-`clear-stale-stories --apply` residue (F2/CER-237 regression), a fresh
in-flight stamp surviving `--apply` untouched, status-drift cross-check and
`--sync-status` resolution (F3/CER-238), and the residue/exit-code contract.

Ensures 2 and 3 use a real `git worktree add`-created worktree (not a bare
`mkdir`) — the whole point of the F2 regression is that `git worktree
remove` actually runs and a retry's `create-story-worktree` then succeeds.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import flex_build as flex_build_mod  # type: ignore[import]  # noqa: E402
from flex_build import diagnose_state, flex_build  # type: ignore[import]  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _init_git_repo(project: Path) -> None:
    """Initialise *project* as a git repo with one commit on the default branch."""
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(project),
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(project), check=True)
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"], cwd=str(project), check=True
    )
    (project / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(project), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=str(project), check=True)


def _git(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(project), capture_output=True, text=True
    )


def _write_story(
    project: Path,
    story_id: str,
    *,
    phase: str = "146",
    status: str = "planned",
) -> Path:
    rail = story_id.split("-", 1)[0]
    story_dir = project / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"
    story_path.write_text(
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"phase: '{phase}'\n"
        "story_class: code\n"
        f"status: {status}\n"
        "primary_files: []\n"
        "touches: []\n"
        "---\n\n"
        "## Acceptance criterion\n\n_(fill in)_\n",
        encoding="utf-8",
    )
    return story_path


def _write_phase_doc(project: Path, phase: str, rows: list[tuple[str, str, str]]) -> Path:
    """Write a minimal phase doc with a Stories table.

    *rows* is a list of (story_id, title, status) tuples.
    """
    phases_dir = project / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_path = phases_dir / f"{phase}-doctor-state-test.md"
    lines = [f"# Phase {phase}", "", "## Stories", "", "| Story | Title | Status |", "| --- | --- | --- |"]
    for story_id, title, status in rows:
        lines.append(f"| {story_id} | {title} | {status} |")
    phase_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return phase_path


def _write_phase_doc_std(project: Path, phase: str, rows: list[tuple[str, str, str]]) -> Path:
    """Write a minimal phase doc at the **production** naming convention
    (``docs/phases/phase-<ref>.md``, matching `resolve_current_phase` /
    `_active_phase_candidates`), unlike `_write_phase_doc`'s test-only
    ``<phase>-doctor-state-test.md`` name. INFRA-445's index-driven
    allow-list keys off this exact filename, so the new closed-phase-scoping
    tests need this variant.
    """
    phases_dir = project / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_path = phases_dir / f"phase-{phase}.md"
    lines = [f"# Phase {phase}", "", "## Stories", "", "| Story | Title | Status |", "| --- | --- | --- |"]
    for story_id, title, status in rows:
        lines.append(f"| {story_id} | {title} | {status} |")
    phase_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return phase_path


def _write_phase_index(project: Path, rows: list[tuple[str, str]]) -> Path:
    """Write ``docs/phases/index.md`` with a minimal Phase table.

    *rows* is a list of ``(phase_ref, status)`` tuples — mirrors the real
    index's ``| Phase | Title | Status | Tag |`` columns (title/tag are
    filler; only ``phase_ref``/``status`` are load-bearing for
    `_parse_index_phases`).
    """
    phases_dir = project / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index",
        "",
        "| Phase | Title | Status | Tag |",
        "|-------|-------|--------|-----|",
    ]
    for phase_ref, status in rows:
        lines.append(f"| {phase_ref} | Phase {phase_ref} title | {status} | tag-{phase_ref} |")
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path


def _write_permissions_artifact(project: Path, story_id: str) -> Path:
    perm_dir = project / "docs" / "phases" / "permissions"
    perm_dir.mkdir(parents=True, exist_ok=True)
    path = perm_dir / f"{story_id}.json"
    path.write_text(json.dumps({"story_id": story_id, "allowed_paths": []}), encoding="utf-8")
    return path


def _write_state(project: Path, state: dict) -> None:
    companion = project / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _read_state(project: Path) -> dict:
    state_path = project / ".companion" / "state.json"
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def _make_real_worktree(project: Path, story_id: str) -> Path:
    """Create a real `git worktree add`-created worktree + branch for
    *story_id*, mirroring `create-story-worktree`'s own convention
    (`.pairmode-worktrees/<ID>/` on branch `pairmode/<ID>`).
    """
    wt_rel = Path(".pairmode-worktrees") / story_id
    wt_abs = project / wt_rel
    wt_abs.parent.mkdir(parents=True, exist_ok=True)
    branch = f"pairmode/{story_id}"
    result = _git(project, "worktree", "add", "-b", branch, str(wt_rel), "HEAD")
    assert result.returncode == 0, result.stderr
    return wt_abs


def _run_doctor(project: Path, *extra_args: str):
    runner = CliRunner()
    args = ["doctor-state", "--project-dir", str(project), *extra_args]
    return runner.invoke(flex_build, args, catch_exceptions=False)


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    _init_git_repo(project)
    return project


# ---------------------------------------------------------------------------
# Ensures 1 — report mode, zero writes, [would] repair lines
# ---------------------------------------------------------------------------


def test_report_mode_zero_writes_all_artifacts_named(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-001"
    _write_story(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")

    wt = _make_real_worktree(project, story_id)
    stale_set_at = "2020-01-01T00:00:00Z"
    _write_state(
        project,
        {
            "current_stories": {story_id: {"id": story_id, "set_at": stale_set_at}},
            "current_story": {"id": story_id, "set_at": stale_set_at},
        },
    )
    artifact = _write_permissions_artifact(project, story_id)

    before_state = _read_state(project)
    before_perm = artifact.read_bytes()

    result = _run_doctor(project)

    assert result.exit_code == 0, result.output
    assert wt.is_dir(), "report mode removed the worktree"
    assert _git(project, "branch", "--list", f"pairmode/{story_id}").stdout.strip() != ""
    assert _read_state(project) == before_state, "report mode wrote state.json"
    assert artifact.exists() and artifact.read_bytes() == before_perm

    assert f"[would] repair {story_id}" in result.output
    assert "worktree" in result.output
    assert "current_stories stamp" in result.output
    assert "current_story mirror" in result.output
    assert "permissions artifact" in result.output


# ---------------------------------------------------------------------------
# Ensures 2 — F1 regression: full teardown under --apply
# ---------------------------------------------------------------------------


def test_apply_full_teardown_of_orphan_f1_regression(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-002"
    _write_story(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")

    wt = _make_real_worktree(project, story_id)
    stale_set_at = "2020-01-01T00:00:00Z"
    _write_state(
        project,
        {
            "current_stories": {story_id: {"id": story_id, "set_at": stale_set_at}},
            "current_story": {"id": story_id, "set_at": stale_set_at},
        },
    )
    _write_permissions_artifact(project, story_id)

    result = _run_doctor(project, "--apply")

    assert result.exit_code == 0, result.output
    assert not wt.exists(), "worktree directory still exists"
    assert _git(project, "branch", "--list", f"pairmode/{story_id}").stdout.strip() == ""
    state = _read_state(project)
    assert story_id not in state.get("current_stories", {})
    assert not (project / "docs" / "phases" / "permissions" / f"{story_id}.json").exists()

    sys.path.insert(0, str(_SCRIPTS_DIR))
    from flex_build import claimed_story_ids  # noqa: E402

    assert claimed_story_ids(project) == set()


# ---------------------------------------------------------------------------
# Ensures 3 — F2 regression: recovery from exact post-clear-stale-stories
# residue (worktree/branch/permissions present, NO state.json stamps at all)
# ---------------------------------------------------------------------------


def test_apply_recovers_from_partial_clear_stale_stories_residue_f2(
    tmp_path: Path,
) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-003"
    _write_story(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")

    wt = _make_real_worktree(project, story_id)
    _write_permissions_artifact(project, story_id)
    # No .companion/state.json at all — the exact post-`clear-stale-stories
    # --apply` shape.

    result = _run_doctor(project, "--apply")

    assert result.exit_code == 0, result.output
    assert not wt.exists(), "F2: worktree directory survived doctor-state --apply"
    assert _git(project, "branch", "--list", f"pairmode/{story_id}").stdout.strip() == ""
    assert not (project / "docs" / "phases" / "permissions" / f"{story_id}.json").exists()

    # A subsequent create-story-worktree must now succeed.
    retry = CliRunner().invoke(
        flex_build,
        ["create-story-worktree", "--story-id", story_id, "--project-dir", str(project)],
        catch_exceptions=False,
    )
    assert retry.exit_code == 0, retry.output


# ---------------------------------------------------------------------------
# Ensures 4 — fresh entry retained, reported on an in-flight line
# ---------------------------------------------------------------------------


def test_fresh_entry_retained_and_reported_in_flight(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-004"
    _write_story(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")

    wt = _make_real_worktree(project, story_id)
    from datetime import datetime, timezone

    fresh_set_at = datetime.now(timezone.utc).isoformat()
    _write_state(
        project,
        {
            "current_stories": {story_id: {"id": story_id, "set_at": fresh_set_at}},
            "current_story": {"id": story_id, "set_at": fresh_set_at},
        },
    )
    artifact = _write_permissions_artifact(project, story_id)

    result = _run_doctor(project, "--apply")

    assert result.exit_code == 0, result.output
    assert wt.is_dir(), "--apply removed a fresh in-flight worktree"
    state = _read_state(project)
    assert story_id in state.get("current_stories", {})
    assert artifact.exists()
    assert f"in-flight {story_id}" in result.output
    assert f"[would] repair {story_id}" not in result.output
    assert f"[apply] repaired {story_id}" not in result.output


# ---------------------------------------------------------------------------
# Ensures 5 — F3 status-drift cross-check, reported in both modes,
# resolved only via --sync-status
# ---------------------------------------------------------------------------


def test_status_drift_reported_in_report_mode_not_applied(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-005"
    _write_story(project, story_id, phase="146", status="complete")
    _write_phase_doc(project, "146", [(story_id, "Some story", "planned")])
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story + phase")

    result = _run_doctor(project)

    assert result.exit_code == 0, result.output
    assert f"status-drift {story_id} frontmatter=complete table=planned" in result.output

    story_text = (project / "docs" / "stories" / "DOC" / f"{story_id}.md").read_text()
    assert "status: complete" in story_text
    phase_text = (project / "docs" / "phases" / "146-doctor-state-test.md").read_text()
    assert "| planned |" in phase_text


def test_status_drift_reported_but_not_applied_under_bare_apply(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-006"
    _write_story(project, story_id, phase="146", status="complete")
    _write_phase_doc(project, "146", [(story_id, "Some story", "planned")])
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story + phase")

    result = _run_doctor(project, "--apply")

    assert result.exit_code == 0, result.output
    assert f"status-drift {story_id} frontmatter=complete table=planned" in result.output
    phase_text = (project / "docs" / "phases" / "146-doctor-state-test.md").read_text()
    assert "| planned |" in phase_text, "--apply alone silently picked a winner"
    story_text = (project / "docs" / "stories" / "DOC" / f"{story_id}.md").read_text()
    assert "status: complete" in story_text


def test_sync_status_frontmatter_wins_writes_table(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-007"
    _write_story(project, story_id, phase="146", status="complete")
    _write_phase_doc(project, "146", [(story_id, "Some story", "planned")])
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story + phase")

    result = _run_doctor(project, "--sync-status", "frontmatter")

    assert result.exit_code == 0, result.output
    phase_text = (project / "docs" / "phases" / "146-doctor-state-test.md").read_text()
    assert "| complete |" in phase_text
    story_text = (project / "docs" / "stories" / "DOC" / f"{story_id}.md").read_text()
    assert "status: complete" in story_text


def test_sync_status_table_wins_writes_frontmatter(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-008"
    _write_story(project, story_id, phase="146", status="complete")
    _write_phase_doc(project, "146", [(story_id, "Some story", "planned")])
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story + phase")

    result = _run_doctor(project, "--sync-status", "table")

    assert result.exit_code == 0, result.output
    story_text = (project / "docs" / "stories" / "DOC" / f"{story_id}.md").read_text()
    assert "status: planned" in story_text
    phase_text = (project / "docs" / "phases" / "146-doctor-state-test.md").read_text()
    assert "| planned |" in phase_text


# ---------------------------------------------------------------------------
# Ensures 6 — diagnose_state is pure, total, and never raises on absent dirs
# ---------------------------------------------------------------------------


def test_diagnose_state_pure_no_writes(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-009"
    _write_story(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")
    wt = _make_real_worktree(project, story_id)
    artifact = _write_permissions_artifact(project, story_id)
    _write_state(
        project,
        {"current_stories": {story_id: {"id": story_id, "set_at": "2020-01-01T00:00:00Z"}}},
    )

    before_state = _read_state(project)
    before_perm = artifact.read_bytes()

    diagnosis = diagnose_state(project)

    assert wt.is_dir()
    assert artifact.exists() and artifact.read_bytes() == before_perm
    assert _read_state(project) == before_state
    assert any(o["story_id"] == story_id for o in diagnosis["orphans"])


def test_diagnose_state_empty_lists_when_dirs_absent(tmp_path: Path) -> None:
    project = tmp_path / "empty_proj"
    project.mkdir()

    diagnosis = diagnose_state(project)

    assert diagnosis == {"orphans": [], "in_flight": [], "status_drift": []}


def test_diagnose_state_max_age_hours_override(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-010"
    _write_story(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")
    _make_real_worktree(project, story_id)

    from datetime import datetime, timedelta, timezone

    set_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _write_state(
        project,
        {"current_stories": {story_id: {"id": story_id, "set_at": set_at}}},
    )

    # Default cutoff (24h): a 2h-old stamp is fresh -> in_flight.
    diagnosis_default = diagnose_state(project)
    assert any(e["story_id"] == story_id for e in diagnosis_default["in_flight"])
    assert not any(o["story_id"] == story_id for o in diagnosis_default["orphans"])

    # Tighter 1h cutoff: the same 2h-old stamp is now stale -> orphan.
    diagnosis_tight = diagnose_state(project, max_age_hours=1.0)
    assert not any(e["story_id"] == story_id for e in diagnosis_tight["in_flight"])
    assert any(o["story_id"] == story_id for o in diagnosis_tight["orphans"])


# ---------------------------------------------------------------------------
# Ensures 7 — residue leaves remaining artifacts untouched, exits 1
# ---------------------------------------------------------------------------


def test_residue_leaves_artifacts_untouched_and_exits_1(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-011"
    _write_story(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")

    wt = _make_real_worktree(project, story_id)
    stale_set_at = "2020-01-01T00:00:00Z"
    _write_state(
        project,
        {"current_stories": {story_id: {"id": story_id, "set_at": stale_set_at}}},
    )
    artifact = _write_permissions_artifact(project, story_id)

    # Make an uncommitted change inside the worktree so `git worktree
    # remove --force` still succeeds... instead, simulate a removal
    # failure by deleting the branch out from under the worktree link so
    # `git worktree remove` fails (dangling administrative files).
    # Simplest reliable failure: lock the worktree.
    lock_result = _git(project, "worktree", "lock", str(Path(".pairmode-worktrees") / story_id))
    assert lock_result.returncode == 0, lock_result.stderr

    result = _run_doctor(project, "--apply")

    assert result.exit_code == 1, result.output
    assert wt.is_dir(), "residue path removed the worktree anyway"
    state = _read_state(project)
    assert story_id in state.get("current_stories", {}), (
        "residue path cleared the stamp despite the worktree surviving"
    )
    assert artifact.exists(), "residue path cleared the permissions artifact"
    assert "still exists" in result.output


def test_report_mode_exit_0_and_apply_exit_0_on_clean_repair(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    story_id = "DOC-012"
    _write_story(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")
    _make_real_worktree(project, story_id)
    _write_state(
        project,
        {"current_stories": {story_id: {"id": story_id, "set_at": "2020-01-01T00:00:00Z"}}},
    )

    report = _run_doctor(project)
    assert report.exit_code == 0

    apply_result = _run_doctor(project, "--apply")
    assert apply_result.exit_code == 0, apply_result.output


# ---------------------------------------------------------------------------
# INFRA-445 — active-phase scoping (checkpoint-security remediation)
# ---------------------------------------------------------------------------
#
# The live BUILD-024..028/BUILD-001 shapes: a closed/checkpointed phase's
# residual claim artifacts and stale frontmatter/table drift must stop being
# reported as if they were live signal, while the same shapes in a still-open
# phase must keep being reported exactly as before this story.


def test_closed_phase_stale_permissions_artifact_not_orphan(tmp_path: Path) -> None:
    """Ensures 1: closed-phase stale permissions artifact, no state.json
    stamp (the live BUILD-024..028 shape) — `orphans` carries no entry."""
    project = _make_project(tmp_path)
    story_id = "DOC-021"
    _write_story(project, story_id, phase="90", status="complete")
    _write_phase_doc_std(project, "90", [(story_id, "Some story", "complete")])
    _write_phase_index(project, [("90", "complete")])
    _write_permissions_artifact(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "closed phase residue")

    diagnosis = diagnose_state(project)

    assert not any(o["story_id"] == story_id for o in diagnosis["orphans"])


def test_open_phase_stale_permissions_artifact_still_orphan(tmp_path: Path) -> None:
    """Regression control for Ensures 1: the identical shape in a phase
    still open by the index's own Status column stays a reported orphan."""
    project = _make_project(tmp_path)
    story_id = "DOC-022"
    _write_story(project, story_id, phase="91", status="complete")
    _write_phase_doc_std(project, "91", [(story_id, "Some story", "complete")])
    _write_phase_index(project, [("91", "active")])
    _write_permissions_artifact(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "open phase residue")

    diagnosis = diagnose_state(project)

    assert any(o["story_id"] == story_id for o in diagnosis["orphans"])


def test_closed_phase_status_drift_excluded(tmp_path: Path) -> None:
    """Ensures 2: closed-phase frontmatter/table mismatch (the live
    BUILD-001 shape) — `status_drift` carries no entry for that pair.

    **Forbidden proxy check**: the scoping must live in `diagnose_state`
    itself, not merely in `orphan_state_notice`'s rendering — this test
    calls `diagnose_state` directly.
    """
    project = _make_project(tmp_path)
    story_id = "DOC-023"
    _write_story(project, story_id, phase="92", status="complete")
    _write_phase_doc_std(project, "92", [(story_id, "Some story", "planned")])
    _write_phase_index(project, [("92", "complete")])
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "closed phase drift")

    diagnosis = diagnose_state(project)

    assert not any(row[0] == story_id for row in diagnosis["status_drift"])


def test_open_phase_status_drift_still_detected(tmp_path: Path) -> None:
    """Regression control for Ensures 2: the identical mismatch in a phase
    still open by the index's own Status column is still reported."""
    project = _make_project(tmp_path)
    story_id = "DOC-024"
    _write_story(project, story_id, phase="93", status="complete")
    _write_phase_doc_std(project, "93", [(story_id, "Some story", "planned")])
    _write_phase_index(project, [("93", "active")])
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "open phase drift")

    diagnosis = diagnose_state(project)

    assert (story_id, "complete", "planned") in diagnosis["status_drift"]


def test_unusual_own_status_not_narrowed_by_closed_phase(tmp_path: Path) -> None:
    """Ensures 3: a story whose own frontmatter status is not one of
    complete/merged/deferred/backlog is classified exactly as before, even
    when its phase is closed — the fix narrows what counts as closed, it
    does not add a new closed-status value."""
    project = _make_project(tmp_path)
    story_id = "DOC-025"
    _write_story(project, story_id, phase="94", status="draft")
    _write_phase_doc_std(project, "94", [(story_id, "Some story", "complete")])
    _write_phase_index(project, [("94", "complete")])
    _write_permissions_artifact(project, story_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "unusual own status")

    diagnosis = diagnose_state(project)

    assert any(o["story_id"] == story_id for o in diagnosis["orphans"])


def test_malformed_candidate_ids_excluded_everywhere(
    tmp_path: Path, monkeypatch
) -> None:
    """Ensures 4: a malformed `current_stories` key / `current_story` mirror
    ID (shell-metacharacter and path-traversal shapes) is excluded from the
    candidate set entirely — absent from `orphans`/`in_flight`/
    `status_drift`, and under `--apply` never reaches
    `_teardown_story_worktree`/`clear_permissions_artifact` (asserted via
    monkeypatch spies, not by inspecting the classification alone)."""
    project = _make_project(tmp_path)
    good_id = "DOC-026"
    _write_story(project, good_id)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "add story")

    bad_keyed_id = "; rm -rf /"
    bad_mirror_id = "../../etc"
    stale_set_at = "2020-01-01T00:00:00Z"
    _write_state(
        project,
        {
            "current_stories": {bad_keyed_id: {"id": bad_keyed_id, "set_at": stale_set_at}},
            "current_story": {"id": bad_mirror_id, "set_at": stale_set_at},
        },
    )

    diagnosis = diagnose_state(project)
    all_ids = (
        [o["story_id"] for o in diagnosis["orphans"]]
        + [e["story_id"] for e in diagnosis["in_flight"]]
        + [row[0] for row in diagnosis["status_drift"]]
    )
    assert bad_keyed_id not in all_ids
    assert bad_mirror_id not in all_ids

    teardown_calls: list[str] = []
    clear_calls: list[str] = []

    def _spy_teardown(pp, sid):
        teardown_calls.append(sid)
        return []

    def _spy_clear(sid, pp):
        clear_calls.append(sid)

    monkeypatch.setattr(flex_build_mod, "_teardown_story_worktree", _spy_teardown)
    monkeypatch.setattr(flex_build_mod, "clear_permissions_artifact", _spy_clear)

    result = _run_doctor(project, "--apply")

    assert result.exit_code == 0, result.output
    assert bad_keyed_id not in teardown_calls
    assert bad_keyed_id not in clear_calls
    assert bad_mirror_id not in teardown_calls
    assert bad_mirror_id not in clear_calls


def test_status_drift_scan_never_opens_closed_phase_files(
    tmp_path: Path, monkeypatch
) -> None:
    """Ensures 5: a file-access spy wrapping `Path.read_text` records zero
    reads against closed phases' `.md` files during the status-drift scan,
    given N closed phases and one open phase.

    **Forbidden proxy check**: reading every phase file and discarding
    closed ones from the result is not acceptable — the scoping must select
    which files to open *before* opening them (this is what actually bounds
    the SessionStart hook's cost as project history accumulates).
    """
    project = _make_project(tmp_path)
    closed_refs = ["95", "96", "97"]
    open_ref = "98"

    for ref in closed_refs:
        sid = f"DOC-1{ref}"
        _write_story(project, sid, phase=ref, status="complete")
        _write_phase_doc_std(project, ref, [(sid, "Some story", "complete")])

    open_sid = "DOC-198"
    _write_story(project, open_sid, phase=open_ref, status="complete")
    _write_phase_doc_std(project, open_ref, [(open_sid, "Some story", "planned")])

    index_rows = [(ref, "complete") for ref in closed_refs] + [(open_ref, "active")]
    _write_phase_index(project, index_rows)
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "closed+open phases for file-access spy")

    closed_paths = {
        (project / "docs" / "phases" / f"phase-{ref}.md").resolve() for ref in closed_refs
    }
    read_paths: list[Path] = []
    real_read_text = Path.read_text

    def _spy_read_text(self, *args, **kwargs):
        read_paths.append(self.resolve())
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _spy_read_text)

    diagnosis = diagnose_state(project)

    opened_closed = closed_paths & set(read_paths)
    assert not opened_closed, f"closed-phase files opened: {opened_closed}"
    assert (open_sid, "complete", "planned") in diagnosis["status_drift"]

"""Tests for flex_build.py permissions-gc subcommand (INFRA-290).

Covers the pure classification helper ``collectable_permission_artifacts``
and the thin CLI printer over it: dry-run lists but does not delete; --apply
deletes collectable artifacts; every retention whitelist rule (worktree
claim, current_stories claim, current_story mirror claim, non-story-ID
filename) survives --apply; a missing permissions directory exits 0 with
the zero summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from click.testing import CliRunner

# Make sibling scripts importable via direct path insertion.
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from flex_build import (  # type: ignore[import]  # noqa: E402
    collectable_permission_artifacts,
    flex_build,
)


def _make_project(tmp_path: Path) -> Path:
    """Deep-enough project root (depth guard) with a permissions dir."""
    project = tmp_path / "proj"
    (project / "docs" / "phases" / "permissions").mkdir(parents=True)
    return project


def _write_artifact(project: Path, name: str) -> Path:
    path = project / "docs" / "phases" / "permissions" / name
    path.write_text(json.dumps({"story_id": name.rsplit(".", 1)[0]}), encoding="utf-8")
    return path


def _write_state(project: Path, state: dict) -> None:
    companion = project / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _run_gc(project: Path, *, apply: bool = False):
    runner = CliRunner()
    args = ["permissions-gc", "--project-dir", str(project)]
    if apply:
        args.append("--apply")
    return runner.invoke(flex_build, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# F2: report by default, delete only with --apply
# ---------------------------------------------------------------------------


def test_dryrun_lists_but_does_not_delete(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    artifact = _write_artifact(project, "BUILD-001.json")

    result = _run_gc(project, apply=False)

    assert result.exit_code == 0
    assert artifact.exists(), "dry-run deleted an artifact"
    assert "[would] delete docs/phases/permissions/BUILD-001.json" in result.output
    assert "permissions-gc: 1 collectable, 0 retained" in result.output


def test_apply_deletes_collectable_artifact(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    artifact = _write_artifact(project, "BUILD-001.json")

    result = _run_gc(project, apply=True)

    assert result.exit_code == 0
    assert not artifact.exists(), "--apply did not delete a collectable artifact"
    assert "[apply] deleted docs/phases/permissions/BUILD-001.json" in result.output
    assert "permissions-gc: 1 collectable, 0 retained" in result.output


# ---------------------------------------------------------------------------
# F3: retention whitelist — each rule survives --apply, with a printed reason
# ---------------------------------------------------------------------------


def test_worktree_claimed_artifact_survives_apply(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    artifact = _write_artifact(project, "BUILD-002.json")
    (project / ".pairmode-worktrees" / "BUILD-002").mkdir(parents=True)

    result = _run_gc(project, apply=True)

    assert result.exit_code == 0
    assert artifact.exists(), "worktree-claimed artifact was deleted"
    assert "permissions-gc: 0 collectable, 1 retained" in result.output
    assert "retained docs/phases/permissions/BUILD-002.json" in result.output
    assert "in-flight claim" in result.output


def test_current_stories_claimed_artifact_survives_apply(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    artifact = _write_artifact(project, "BUILD-003.json")
    _write_state(
        project,
        {"current_stories": {"BUILD-003": {"id": "BUILD-003", "set_at": "2026-07-28T00:00:00Z"}}},
    )

    result = _run_gc(project, apply=True)

    assert result.exit_code == 0
    assert artifact.exists(), "current_stories-claimed artifact was deleted"
    assert "permissions-gc: 0 collectable, 1 retained" in result.output
    assert "current_stories" in result.output


def test_current_story_mirror_claimed_artifact_survives_apply(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    artifact = _write_artifact(project, "BUILD-004.json")
    # Legacy flat-mirror-only state (pre-INFRA-281 shape, no keyed record).
    _write_state(
        project,
        {"current_story": {"id": "BUILD-004", "set_at": "2026-07-28T00:00:00Z"}},
    )

    result = _run_gc(project, apply=True)

    assert result.exit_code == 0
    assert artifact.exists(), "current_story-mirror-claimed artifact was deleted"
    assert "permissions-gc: 0 collectable, 1 retained" in result.output


def test_non_story_id_filename_survives_apply(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    artifact = _write_artifact(project, "notes.json")

    result = _run_gc(project, apply=True)

    assert result.exit_code == 0
    assert artifact.exists(), "non-story-ID artifact was deleted"
    assert "permissions-gc: 0 collectable, 1 retained" in result.output
    assert "does not parse as a story ID" in result.output


# ---------------------------------------------------------------------------
# F4: pure and total
# ---------------------------------------------------------------------------


def test_missing_permissions_dir_exits_zero_with_zero_summary(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()

    result = _run_gc(project, apply=False)

    assert result.exit_code == 0
    assert "permissions-gc: 0 collectable, 0 retained" in result.output


def test_missing_state_json_is_tolerated(tmp_path: Path) -> None:
    """No .companion/state.json — artifacts with no other claim are collectable."""
    project = _make_project(tmp_path)
    _write_artifact(project, "BUILD-005.json")

    collectable, retained = collectable_permission_artifacts(project)

    assert [p.name for p in collectable] == ["BUILD-005.json"]
    assert retained == []


def test_helper_classification_mixed(tmp_path: Path) -> None:
    """The helper classifies a mixed directory without touching any file."""
    project = _make_project(tmp_path)
    _write_artifact(project, "BUILD-010.json")   # collectable
    _write_artifact(project, "BUILD-011.json")   # worktree-claimed
    _write_artifact(project, "README.json")      # non-story-ID
    (project / ".pairmode-worktrees" / "BUILD-011").mkdir(parents=True)

    collectable, retained = collectable_permission_artifacts(project)

    assert [p.name for p in collectable] == ["BUILD-010.json"]
    assert sorted(p.name for p, _ in retained) == ["BUILD-011.json", "README.json"]
    # Pure read: everything still on disk.
    for name in ("BUILD-010.json", "BUILD-011.json", "README.json"):
        assert (project / "docs" / "phases" / "permissions" / name).exists()

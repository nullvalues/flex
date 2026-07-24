"""RELEASE-007 fold-preparation invariants.

Asserts deterministically:
  (a) _version.py == "0.3.0" (version finalized)
  (b) Signal-1 detection works on a synthetic scripts-bound project tree
  (c) runbook contains the Signal-1 verification step (CER-059b)
  (d) RELEASE-002 reconciliation AC present; status-flip guard xfail pre-fold
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
_RUNBOOK = _REPO_ROOT / "docs" / "harness-cutover-runbook.md"
_RELEASE_002 = _REPO_ROOT / "docs" / "stories" / "RELEASE" / "RELEASE-002.md"


# ---------------------------------------------------------------------------
# (a) Version finalize
# ---------------------------------------------------------------------------

class TestVersionFinalize:
    def test_pairmode_version_is_0_3_0(self) -> None:
        from skills.pairmode.scripts._version import PAIRMODE_VERSION
        assert PAIRMODE_VERSION == "0.3.0", (
            f"PAIRMODE_VERSION is {PAIRMODE_VERSION!r} — should be '0.3.0' after fold preparation"
        )


# ---------------------------------------------------------------------------
# (b) Signal-1 detection — synthetic scripts-bound project tree (CER-059a)
#
# Diagnosis: the zero-Signal-1-hit in fleet-snapshot.md is accurate.
# Old-template projects embed scripts paths in shell commands, not as a
# `pairmode_scripts_dir` key-value line.  `_check_signal1` is correct but
# the detection fires only for projects that declare `pairmode_scripts_dir`
# explicitly.  Post-sync (after `pairmode sync --apply` migrates a project
# to the thin loop), the new CLAUDE.build.md will carry this declaration and
# Signal-1 will fire.  The runbook Signal-1 verification step (CER-059b)
# covers re-detection after each project sync.
# ---------------------------------------------------------------------------

class TestSignal1Detection:
    def test_signal1_detects_scripts_bound_project(self, tmp_path: pathlib.Path) -> None:
        """A synthetic project with pairmode_scripts_dir under _SCRIPTS_DIR is detected."""
        build_md = tmp_path / "CLAUDE.build.md"
        build_md.write_text(
            f"# Build\npairmode_scripts_dir = {_SCRIPTS_DIR}\n",
            encoding="utf-8",
        )

        from skills.pairmode.scripts.fleet_discovery import _check_signal1
        hit, val = _check_signal1(tmp_path)
        assert hit, f"Signal-1 not detected; _check_signal1 returned ({hit}, {val!r})"
        assert val is not None

    def test_signal1_absent_without_declaration(self, tmp_path: pathlib.Path) -> None:
        """A project whose CLAUDE.build.md uses only inline uv-run paths returns no Signal-1."""
        build_md = tmp_path / "CLAUDE.build.md"
        build_md.write_text(
            f"PATH=$HOME/.local/bin:$PATH uv run python {_SCRIPTS_DIR}/flex_build.py next-action\n",
            encoding="utf-8",
        )

        from skills.pairmode.scripts.fleet_discovery import _check_signal1
        hit, val = _check_signal1(tmp_path)
        assert not hit, (
            "Signal-1 should be absent for old-template inline paths (no pairmode_scripts_dir key)"
        )

    def test_signal1_detects_relative_path(self, tmp_path: pathlib.Path) -> None:
        """A project with a relative pairmode_scripts_dir resolving under _SCRIPTS_DIR is detected."""
        sub = tmp_path / "project"
        sub.mkdir()
        # write a relative path that resolves to _SCRIPTS_DIR
        rel = pathlib.Path(pathlib.os.path.relpath(_SCRIPTS_DIR, sub))
        build_md = sub / "CLAUDE.build.md"
        build_md.write_text(f"pairmode_scripts_dir = {rel}\n", encoding="utf-8")

        from skills.pairmode.scripts.fleet_discovery import _check_signal1
        hit, val = _check_signal1(sub)
        assert hit, f"Signal-1 not detected for relative path; got ({hit}, {val!r})"


# ---------------------------------------------------------------------------
# (c) Runbook Signal-1 verification step (CER-059b)
# ---------------------------------------------------------------------------

class TestRunbookSignal1Step:
    def test_runbook_contains_signal1_verification_step(self) -> None:
        text = _RUNBOOK.read_text(encoding="utf-8")
        assert "Signal-1 verification step" in text, (
            "Runbook is missing the Signal-1 verification step (CER-059b)"
        )
        assert "re-run" in text and "binding: scripts" in text or "Signal 1" in text, (
            "Signal-1 verification step text appears incomplete in runbook"
        )


# ---------------------------------------------------------------------------
# (d) RELEASE-002 reconciliation AC (CER-059c)
#
# Pre-fold: RELEASE-002 is `deferred` on main, `complete` on harness.
# The fold merge brings the harness version to main; this guard becomes a
# live check once the fold tag v0.3.0 exists.
# ---------------------------------------------------------------------------

def _fold_tag_exists() -> bool:
    result = subprocess.run(
        ["git", "tag", "-l", "v0.3.0"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    return "v0.3.0" in result.stdout


class TestRelease002Reconciliation:
    def test_release_002_reconciliation_ac_present(self) -> None:
        """The RELEASE-002 story file exists and has a status field."""
        text = _RELEASE_002.read_text(encoding="utf-8")
        assert "status:" in text, "RELEASE-002 story file missing status frontmatter"
        assert "RELEASE-002" in text, "RELEASE-002 story file appears to be wrong file"

    @pytest.mark.xfail(
        not _fold_tag_exists(),
        reason="RELEASE-002 status flip (deferred→complete on main) verified post-fold only",
        strict=False,
    )
    def test_release_002_not_deferred_post_fold(self) -> None:
        """After the fold, RELEASE-002 must not be deferred on main."""
        text = _RELEASE_002.read_text(encoding="utf-8")
        assert 'status: deferred' not in text, (
            "RELEASE-002 is still `deferred` — fold merge should have reconciled this to `complete`"
        )

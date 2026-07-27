"""Tests for skills/pairmode/scripts/fleet_discovery.py."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

# Make the scripts dir importable
import sys

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_discovery as fd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_build_md(project_dir: Path, scripts_dir_value: str) -> None:
    """Write a minimal CLAUDE.build.md with the given pairmode_scripts_dir."""
    (project_dir / "CLAUDE.build.md").write_text(
        f"# Build file\n\npairmode_scripts_dir = {scripts_dir_value}\n",
        encoding="utf-8",
    )


def _make_state_json(project_dir: Path, version: str = "0.2.0") -> None:
    """Write a .companion/state.json with pairmode_version."""
    companion = project_dir / ".companion"
    companion.mkdir(exist_ok=True)
    (companion / "state.json").write_text(
        json.dumps({"pairmode_version": version}),
        encoding="utf-8",
    )


def _record_mtimes(project_dir: Path) -> dict[str, float]:
    """Record modification times of all files under project_dir."""
    mtimes = {}
    for p in project_dir.rglob("*"):
        if p.is_file():
            mtimes[str(p)] = p.stat().st_mtime
    return mtimes


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fleet(tmp_path: Path) -> dict:
    """Create a 3-project fixture fleet and return metadata."""
    # The "real" scripts dir that _THIS_SCRIPTS_DIR points to (monkeypatched below)
    fake_flex_root = tmp_path / "fake_flex"
    fake_scripts = fake_flex_root / "skills" / "pairmode" / "scripts"
    fake_scripts.mkdir(parents=True)

    # Project A: Signal 1 only (scripts path binding)
    proj_a = tmp_path / "project_a"
    proj_a.mkdir()
    _make_build_md(proj_a, str(fake_scripts))

    # Project B: Signal 2 only (pairmode_version binding)
    proj_b = tmp_path / "project_b"
    proj_b.mkdir()
    _make_state_json(proj_b, "0.2.0")

    # Project C: both signals
    proj_c = tmp_path / "project_c"
    proj_c.mkdir()
    _make_build_md(proj_c, str(fake_scripts))
    _make_state_json(proj_c, "0.1.0")

    # Project D: no signals (not reported)
    proj_d = tmp_path / "project_d"
    proj_d.mkdir()
    (proj_d / "CLAUDE.build.md").write_text("# No pairmode_scripts_dir here\n")

    return {
        "fake_flex_root": fake_flex_root,
        "fake_scripts": fake_scripts,
        "proj_a": proj_a,
        "proj_b": proj_b,
        "proj_c": proj_c,
        "proj_d": proj_d,
        "candidates": [proj_a, proj_b, proj_c, proj_d],
    }


# ---------------------------------------------------------------------------
# Monkeypatching helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_scripts_dir(fleet: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point _THIS_SCRIPTS_DIR and _FLEX_ROOT at the fake checkout."""
    monkeypatch.setattr(fd, "_THIS_SCRIPTS_DIR", fleet["fake_scripts"])
    monkeypatch.setattr(fd, "_FLEX_ROOT", fleet["fake_flex_root"])


# ---------------------------------------------------------------------------
# Detection logic tests
# ---------------------------------------------------------------------------

class TestSignal1:
    def test_matches_scripts_dir(self, fleet: dict) -> None:
        matched, value = fd._check_signal1(fleet["proj_a"])
        assert matched is True
        assert value is not None
        assert str(fleet["fake_scripts"]) in value or value.strip() == str(fleet["fake_scripts"])

    def test_no_match_for_project_d(self, fleet: dict) -> None:
        matched, value = fd._check_signal1(fleet["proj_d"])
        assert matched is False
        assert value is None

    def test_no_match_when_no_build_md(self, tmp_path: Path) -> None:
        proj = tmp_path / "empty_project"
        proj.mkdir()
        matched, value = fd._check_signal1(proj)
        assert matched is False
        assert value is None


class TestSignal2:
    def test_matches_pairmode_version(self, fleet: dict) -> None:
        matched, version = fd._check_signal2(fleet["proj_b"])
        assert matched is True
        assert version == "0.2.0"

    def test_no_match_for_project_a(self, fleet: dict) -> None:
        matched, version = fd._check_signal2(fleet["proj_a"])
        assert matched is False
        assert version is None

    def test_no_match_when_no_state_json(self, tmp_path: Path) -> None:
        proj = tmp_path / "no_state"
        proj.mkdir()
        matched, version = fd._check_signal2(proj)
        assert matched is False
        assert version is None

    def test_no_match_when_state_json_missing_key(self, tmp_path: Path) -> None:
        proj = tmp_path / "no_version"
        proj.mkdir()
        companion = proj / ".companion"
        companion.mkdir()
        (companion / "state.json").write_text(json.dumps({"other_key": "value"}))
        matched, version = fd._check_signal2(proj)
        assert matched is False


class TestDiscover:
    def test_signal1_only(self, fleet: dict) -> None:
        results = fd.discover([fleet["proj_a"]])
        assert len(results) == 1
        r = results[0]
        assert r["signal1"] is True
        assert r["signal2"] is False
        assert r["binding"] == "scripts"

    def test_signal2_only(self, fleet: dict) -> None:
        results = fd.discover([fleet["proj_b"]])
        assert len(results) == 1
        r = results[0]
        assert r["signal1"] is False
        assert r["signal2"] is True
        assert r["binding"] == "version"

    def test_both_signals(self, fleet: dict) -> None:
        results = fd.discover([fleet["proj_c"]])
        assert len(results) == 1
        r = results[0]
        assert r["signal1"] is True
        assert r["signal2"] is True
        assert r["binding"] == "both"

    def test_no_signal_not_reported(self, fleet: dict) -> None:
        results = fd.discover([fleet["proj_d"]])
        assert len(results) == 0

    def test_full_fleet(self, fleet: dict) -> None:
        results = fd.discover(fleet["candidates"])
        paths = {r["path"] for r in results}
        assert str(fleet["proj_a"].resolve()) in paths
        assert str(fleet["proj_b"].resolve()) in paths
        assert str(fleet["proj_c"].resolve()) in paths
        # proj_d must NOT be reported
        assert str(fleet["proj_d"].resolve()) not in paths

    def test_nonexistent_candidate_skipped(self, fleet: dict, tmp_path: Path) -> None:
        ghost = tmp_path / "does_not_exist"
        results = fd.discover([ghost])
        assert results == []


# ---------------------------------------------------------------------------
# Read-only assertion
# ---------------------------------------------------------------------------

class TestReadOnly:
    def test_discover_does_not_modify_fixture_files(self, fleet: dict, tmp_path: Path) -> None:
        """Verify the tool is read-only: fixture files unchanged after a run."""
        before = _record_mtimes(tmp_path)
        fd.discover(fleet["candidates"])
        after = _record_mtimes(tmp_path)
        # Only check files that existed before; discover should not create new files in fleet
        for path, mtime in before.items():
            assert after.get(path) == mtime, (
                f"File was modified during discover(): {path}"
            )

    def test_check_signal1_does_not_write(self, fleet: dict, tmp_path: Path) -> None:
        before = _record_mtimes(tmp_path)
        fd._check_signal1(fleet["proj_a"])
        after = _record_mtimes(tmp_path)
        for path, mtime in before.items():
            assert after.get(path) == mtime

    def test_check_signal2_does_not_write(self, fleet: dict, tmp_path: Path) -> None:
        before = _record_mtimes(tmp_path)
        fd._check_signal2(fleet["proj_b"])
        after = _record_mtimes(tmp_path)
        for path, mtime in before.items():
            assert after.get(path) == mtime


# ---------------------------------------------------------------------------
# Snapshot writer
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_written_to_flex_repo(self, fleet: dict, tmp_path: Path) -> None:
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover(fleet["candidates"])
        fd._write_snapshot(results, dest)
        assert dest.exists()
        content = dest.read_text()
        assert "Fleet Snapshot" in content
        assert "hard gate" in content.lower() or "pre-fold" in content.lower()

    def test_snapshot_contains_project_paths(self, fleet: dict) -> None:
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover(fleet["candidates"])
        fd._write_snapshot(results, dest)
        content = dest.read_text()
        for r in results:
            assert r["path"] in content

    def test_snapshot_mentions_both_signals(self, fleet: dict) -> None:
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover([fleet["proj_c"]])  # proj_c has both
        fd._write_snapshot(results, dest)
        content = dest.read_text()
        assert "Signal 1" in content or "scripts path" in content.lower()
        assert "Signal 2" in content or "pairmode_version" in content.lower()

    def test_snapshot_does_not_write_to_scanned_project(self, fleet: dict, tmp_path: Path) -> None:
        """Snapshot goes to flex repo, NOT to any scanned project."""
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        before = {
            k: v for k, v in _record_mtimes(tmp_path).items()
            # Exclude files under fake_flex_root itself (that's the flex repo)
            if not k.startswith(str(fleet["fake_flex_root"]))
        }
        results = fd.discover(fleet["candidates"])
        fd._write_snapshot(results, dest)
        after = _record_mtimes(tmp_path)
        for path, mtime in before.items():
            assert after.get(path) == mtime, (
                f"Scanned project file was modified by _write_snapshot: {path}"
            )

# ---------------------------------------------------------------------------
# INFRA-269: duplicate hook registration check (CER-081, DP8)
# ---------------------------------------------------------------------------

def _write_hook_settings(project_dir: Path, hooks: dict) -> Path:
    settings_dir = project_dir / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"
    settings_path.write_text(json.dumps({"hooks": hooks}, indent=2) + "\n", encoding="utf-8")
    return settings_path


@pytest.fixture()
def project_with_duplicate_hooks(fleet: dict) -> Path:
    """A project bound via Signal 2 that also carries a doubled PreToolUse
    hook registration (a stale + a correct entry for pre_tool_use.py)."""
    proj = fleet["proj_c"]  # already has both signals from the base fixture
    _write_hook_settings(proj, {
        "PreToolUse": [
            {"matcher": "Task", "hooks": [
                {"type": "command", "command": "uv run python /mnt/work/flex/hooks/pre_tool_use.py"},
            ]},
            {"matcher": "Task", "hooks": [
                {"type": "command", "command": "uv run python /mnt/work/flex-harness/hooks/pre_tool_use.py"},
            ]},
        ]
    })
    return proj


class TestCheckDuplicateHooks:
    def test_check_duplicate_hooks_finds_doubled_event(self, project_with_duplicate_hooks: Path) -> None:
        dups = fd._check_duplicate_hooks(project_with_duplicate_hooks)
        assert len(dups) == 1
        dup = dups[0]
        assert dup["event"] == "PreToolUse"
        assert dup["basename"] == "pre_tool_use.py"
        assert len(dup["commands"]) == 2

    def test_check_duplicate_hooks_empty_for_clean_project(self, tmp_path: Path) -> None:
        proj = tmp_path / "clean_project"
        proj.mkdir()
        _write_hook_settings(proj, {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
            ]
        })
        assert fd._check_duplicate_hooks(proj) == []

    def test_check_duplicate_hooks_empty_for_missing_settings(self, tmp_path: Path) -> None:
        proj = tmp_path / "no_settings"
        proj.mkdir()
        assert fd._check_duplicate_hooks(proj) == []

    def test_check_duplicate_hooks_empty_for_unparseable_settings(self, tmp_path: Path) -> None:
        proj = tmp_path / "bad_settings"
        (proj / ".claude").mkdir(parents=True)
        (proj / ".claude" / "settings.json").write_text("{not valid json", encoding="utf-8")
        assert fd._check_duplicate_hooks(proj) == []

    def test_check_duplicate_hooks_does_not_write(self, project_with_duplicate_hooks: Path, tmp_path: Path) -> None:
        before = _record_mtimes(tmp_path)
        fd._check_duplicate_hooks(project_with_duplicate_hooks)
        after = _record_mtimes(tmp_path)
        for path, mtime in before.items():
            assert after.get(path) == mtime, (
                f"File was modified by _check_duplicate_hooks: {path}"
            )
        # No new files created under the project either.
        assert set(after.keys()) == set(before.keys())


class TestDiscoverDuplicateHooksKey:
    def test_discover_includes_duplicate_hooks_key(self, fleet: dict) -> None:
        results = fd.discover(fleet["candidates"])
        assert results, "expected at least one discovered project"
        for r in results:
            assert "duplicate_hooks" in r
            assert "path" in r
            assert "signal1" in r
            assert "signal1_value" in r
            assert "signal2" in r
            assert "signal2_value" in r
            assert "binding" in r

    def test_discover_reports_duplicate_hooks_for_affected_project(
        self, project_with_duplicate_hooks: Path, fleet: dict
    ) -> None:
        results = fd.discover(fleet["candidates"])
        matching = [r for r in results if r["path"] == str(project_with_duplicate_hooks.resolve())]
        assert len(matching) == 1
        assert matching[0]["duplicate_hooks"], "expected non-empty duplicate_hooks for the affected project"


class TestJsonAndTextOutputDuplicateHooks:
    def _candidate_dir_argv(self, fleet: dict) -> list[str]:
        argv: list[str] = []
        for c in fleet["candidates"]:
            argv += ["--candidate-dir", str(c)]
        return argv

    def test_json_output_includes_duplicate_hooks(self, fleet: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            fd.cli, [*self._candidate_dir_argv(fleet), "--json", "--no-snapshot"], catch_exceptions=False
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "flex_root" in payload
        assert "fleet" in payload
        for entry in payload["fleet"]:
            assert "duplicate_hooks" in entry

    def test_text_output_reports_duplicate_hooks(
        self, project_with_duplicate_hooks: Path, fleet: dict
    ) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            fd.cli, [*self._candidate_dir_argv(fleet), "--no-snapshot"], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "DUPLICATE HOOKS" in result.output
        assert "Projects with duplicate hooks:" in result.output

    def test_cli_exit_status_unchanged_with_duplicates(
        self, project_with_duplicate_hooks: Path, fleet: dict
    ) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            fd.cli, [*self._candidate_dir_argv(fleet), "--no-snapshot"], catch_exceptions=False
        )
        assert result.exit_code == 0, (
            "discovery reports duplicates but must not fail the CLI (audit-hooks enforces)"
        )


class TestSnapshotDuplicateHooksSection:
    def test_snapshot_has_duplicate_hooks_section(
        self, project_with_duplicate_hooks: Path, fleet: dict
    ) -> None:
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover(fleet["candidates"])
        fd._write_snapshot(results, dest)
        content = dest.read_text()
        assert "## Duplicate hook registrations (CER-081)" in content
        assert "## Pre-fold gate notice (DP8)" in content

    def test_snapshot_reports_none_found_when_clean(self, fleet: dict) -> None:
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover(fleet["candidates"])
        fd._write_snapshot(results, dest)
        content = dest.read_text()
        assert "no duplicate" in content.lower() or "none found" in content.lower()

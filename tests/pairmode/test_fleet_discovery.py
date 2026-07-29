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


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path_factory) -> Path:
    """INFRA-288: _check_duplicate_hooks now reads the merged hook view,
    which includes plugin hooks.json files discovered under the *home*
    directory. Every test runs against a fake, empty home so the operator's
    real ~/.claude/plugins can never leak into fixture expectations."""
    fake_home = tmp_path_factory.mktemp("fake-home")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("FLEX_PLUGIN_HOOKS", raising=False)
    return fake_home


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
    def test_write_snapshot_writes_requested_destination(self, fleet: dict, tmp_path: Path) -> None:
        """_write_snapshot writes wherever it is told (INFRA-295): the caller
        owns destination policy, this function has no refusal branch."""
        dest = tmp_path / "somewhere" / "fleet-snapshot.md"
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
        """No scanned project is ever written by _write_snapshot (the
        default-target rule for where the snapshot goes is destination
        policy owned by the caller, per INFRA-295 — this test only asserts
        the guarantee _write_snapshot itself still holds)."""
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
# INFRA-295: default snapshot destination refuses to write into the scripts
# checkout when the invoking repo is not that checkout.
# ---------------------------------------------------------------------------

class TestDefaultSnapshotDestination:
    def test_predicate_true_inside_flex_root(self, fleet: dict) -> None:
        assert fd._invoking_repo_is_scripts_checkout(
            fleet["fake_flex_root"], fleet["fake_flex_root"]
        ) is True

    def test_predicate_true_nested_under_flex_root(self, fleet: dict) -> None:
        nested = fleet["fake_flex_root"] / "some" / "subdir"
        nested.mkdir(parents=True)
        assert fd._invoking_repo_is_scripts_checkout(
            nested, fleet["fake_flex_root"]
        ) is True

    def test_predicate_false_outside_flex_root(self, fleet: dict, tmp_path: Path) -> None:
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        assert fd._invoking_repo_is_scripts_checkout(
            elsewhere, fleet["fake_flex_root"]
        ) is False

    def test_resolver_returns_default_when_inside(self, fleet: dict) -> None:
        dest = fd._default_snapshot_destination(
            fleet["fake_flex_root"], fleet["fake_flex_root"]
        )
        assert dest == fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"

    def test_resolver_returns_none_when_outside(self, fleet: dict, tmp_path: Path) -> None:
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        dest = fd._default_snapshot_destination(elsewhere, fleet["fake_flex_root"])
        assert dest is None


class TestCliSnapshotRefusal:
    def _candidate_dir_argv(self, fleet: dict) -> list[str]:
        argv: list[str] = []
        for c in fleet["candidates"]:
            argv += ["--candidate-dir", str(c)]
        return argv

    def test_refusal_writes_no_snapshot_file(
        self, fleet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        runner = CliRunner()
        result = runner.invoke(
            fd.cli, self._candidate_dir_argv(fleet), catch_exceptions=False
        )
        assert result.exit_code == 0
        for candidate_root in (fleet["fake_flex_root"], elsewhere):
            for p in candidate_root.rglob("fleet-snapshot.md"):
                pytest.fail(f"snapshot file unexpectedly written: {p}")

    def test_refusal_exit_code_and_message(
        self, fleet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        runner = CliRunner()
        result = runner.invoke(
            fd.cli, self._candidate_dir_argv(fleet), catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "--snapshot" in result.stderr
        assert "--no-snapshot" in result.stderr
        assert str(fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md") in result.stderr

    def test_refusal_under_json_stdout_still_parses(
        self, fleet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        runner = CliRunner()
        result = runner.invoke(
            fd.cli, [*self._candidate_dir_argv(fleet), "--json"], catch_exceptions=False
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "fleet" in payload
        assert "--snapshot" in result.stderr
        assert "--no-snapshot" in result.stderr

    def test_in_repo_default_still_writes(
        self, fleet: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        monkeypatch.chdir(fleet["fake_flex_root"])

        runner = CliRunner()
        result = runner.invoke(
            fd.cli, self._candidate_dir_argv(fleet), catch_exceptions=False
        )
        assert result.exit_code == 0
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        assert dest.exists()

    def test_explicit_snapshot_honoured_from_foreign_cwd(
        self, fleet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        explicit_dest = fleet["fake_flex_root"] / "docs" / "explicit-snapshot.md"
        runner = CliRunner()
        result = runner.invoke(
            fd.cli,
            [*self._candidate_dir_argv(fleet), "--snapshot", str(explicit_dest)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert explicit_dest.exists()


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
        assert "Projects with actionable duplicate hooks:" in result.output
        assert (
            "Projects with plugin-internal duplicate hooks (non-actionable):"
            in result.output
        )

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


@pytest.fixture()
def project_with_plugin_internal_only(fleet: dict, _isolated_home: Path) -> Path:
    """A project bound via Signal 2 whose only duplicate-hook group is
    plugin-internal (non-actionable, CER-110): a single plugin registers the
    same basename twice under the *same* (matcher, predicate) — the
    negative-control shape from Ensures 8, which does survive refinement
    (unlike the two false-positive shapes, which collapse to no group at
    all)."""
    proj = fleet["proj_b"]
    command = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/session-start.sh"'
    doc = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {"type": "command", "command": command},
                        {"type": "command", "command": command},
                    ]
                }
            ]
        }
    }
    plugin_file = (
        _isolated_home / ".claude" / "plugins" / "some-plugin" / "hooks" / "hooks.json"
    )
    plugin_file.parent.mkdir(parents=True)
    plugin_file.write_text(json.dumps(doc), encoding="utf-8")
    return proj


class TestActionableAndPluginInternalCounts:
    """CER-110 Ensures 6/7: fleet_discovery reports both counts, per-project
    lines land on the correct category, and a plugin-internal-only project
    contributes 0 to the actionable count."""

    def _candidate_dir_argv(self, fleet: dict) -> list[str]:
        argv: list[str] = []
        for c in fleet["candidates"]:
            argv += ["--candidate-dir", str(c)]
        return argv

    def test_actionable_count_excludes_plugin_internal_only_project(
        self, project_with_plugin_internal_only: Path, fleet: dict
    ) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            fd.cli,
            [*self._candidate_dir_argv(fleet), "--no-snapshot"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Projects with actionable duplicate hooks: 0" in result.output
        # The plugin file lives under the fake home, so every bound project
        # (proj_a, proj_b, proj_c) sees it — the count reflects all three.
        assert (
            "Projects with plugin-internal duplicate hooks (non-actionable): 3"
            in result.output
        )
        assert "plugin-internal duplicate hooks:" in result.output
        assert "DUPLICATE HOOKS" not in result.output

    def test_both_counts_reported_when_actionable_present(
        self, project_with_duplicate_hooks: Path, fleet: dict
    ) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            fd.cli,
            [*self._candidate_dir_argv(fleet), "--no-snapshot"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Projects with actionable duplicate hooks: 1" in result.output
        assert (
            "Projects with plugin-internal duplicate hooks (non-actionable): 0"
            in result.output
        )

    def test_duplicate_hooks_key_still_carries_every_group(
        self, project_with_plugin_internal_only: Path, fleet: dict
    ) -> None:
        results = fd.discover(fleet["candidates"])
        matching = [
            r
            for r in results
            if r["path"] == str(project_with_plugin_internal_only.resolve())
        ]
        assert len(matching) == 1
        assert matching[0]["duplicate_hooks"], "group must not be silently dropped"
        assert all(
            dh["actionable"] is False for dh in matching[0]["duplicate_hooks"]
        )


class TestSnapshotActionableSubheadings:
    def test_snapshot_has_both_subheadings(
        self, project_with_duplicate_hooks: Path, fleet: dict
    ) -> None:
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover(fleet["candidates"])
        fd._write_snapshot(results, dest)
        content = dest.read_text()
        assert "### Actionable" in content
        assert "### Plugin-internal (non-actionable, CER-110)" in content

    def test_snapshot_actionable_empty_note_when_only_plugin_internal(
        self, project_with_plugin_internal_only: Path, fleet: dict
    ) -> None:
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover(fleet["candidates"])
        fd._write_snapshot(results, dest)
        content = dest.read_text()
        assert "_No actionable duplicate hook registrations found._" in content


class TestSignal1AbsenceReason:
    """CER-059(a): signal1_absence_reason classifies why Signal 1 is absent."""

    def test_none_when_signal1_matched(self, fleet: dict) -> None:
        reason, detail = fd.signal1_absence_reason(fleet["proj_a"])
        assert reason is None
        assert detail is None

    def test_no_build_md(self, tmp_path: Path) -> None:
        proj = tmp_path / "no_build_md_project"
        proj.mkdir()
        reason, detail = fd.signal1_absence_reason(proj)
        assert reason == fd.SIGNAL1_ABSENT_NO_BUILD_MD
        assert detail is None

    def test_no_declaration(self, fleet: dict) -> None:
        # proj_d has a CLAUDE.build.md with no pairmode_scripts_dir and no
        # inline mention of this checkout's identity.
        reason, detail = fd.signal1_absence_reason(fleet["proj_d"])
        assert reason == fd.SIGNAL1_ABSENT_NO_DECLARATION
        assert detail is None

    def test_inline_only(self, fleet: dict, tmp_path: Path) -> None:
        """A project whose CLAUDE.build.md embeds this checkout's scripts path
        only inline (no key-value pairmode_scripts_dir declaration)."""
        proj = tmp_path / "inline_bound_project"
        proj.mkdir()
        (proj / "CLAUDE.build.md").write_text(
            f"# Build\n\nRun: uv run python {fd._THIS_SCRIPTS_DIR}/flex_build.py next-action\n",
            encoding="utf-8",
        )
        reason, detail = fd.signal1_absence_reason(proj)
        assert reason == fd.SIGNAL1_ABSENT_INLINE_ONLY
        assert detail == str(fd._THIS_SCRIPTS_DIR)

        # And _check_signal1 (unwidened contract) still reports absent.
        matched, value = fd._check_signal1(proj)
        assert matched is False
        assert value is None

    def test_foreign_checkout(self, fleet: dict, tmp_path: Path) -> None:
        """A pairmode_scripts_dir declaration that resolves under neither this
        checkout's scripts dir nor its flex root."""
        other_checkout = tmp_path / "some_other_flex" / "skills" / "pairmode" / "scripts"
        other_checkout.mkdir(parents=True)
        proj = tmp_path / "foreign_bound_project"
        proj.mkdir()
        (proj / "CLAUDE.build.md").write_text(
            f"# Build\n\npairmode_scripts_dir = {other_checkout}\n",
            encoding="utf-8",
        )
        reason, detail = fd.signal1_absence_reason(proj)
        assert reason == fd.SIGNAL1_ABSENT_FOREIGN_CHECKOUT
        assert detail == str(other_checkout)

    def test_does_not_write(self, fleet: dict, tmp_path: Path) -> None:
        before = _record_mtimes(tmp_path)
        fd.signal1_absence_reason(fleet["proj_a"])
        fd.signal1_absence_reason(fleet["proj_d"])
        after = _record_mtimes(tmp_path)
        for path, mtime in before.items():
            assert after.get(path) == mtime
        # No new files created either.
        assert set(after.keys()) == set(before.keys())

    def test_never_raises_on_unreadable_build_md(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        proj = tmp_path / "unreadable_project"
        proj.mkdir()
        (proj / "CLAUDE.build.md").write_text("pairmode_scripts_dir = /x\n", encoding="utf-8")

        real_read_text = Path.read_text

        def _boom(self, *a, **kw):
            if self.name == "CLAUDE.build.md":
                raise OSError("simulated read failure")
            return real_read_text(self, *a, **kw)

        monkeypatch.setattr(Path, "read_text", _boom)
        reason, detail = fd.signal1_absence_reason(proj)
        assert reason == fd.SIGNAL1_ABSENT_NO_BUILD_MD
        assert detail is None


# ---------------------------------------------------------------------------
# B4/B5/B6/B7 — discover()/CLI/snapshot carry the absence reason
# ---------------------------------------------------------------------------

class TestDiscoverSignal1AbsentReason:
    def test_matched_signal1_has_none_reason(self, fleet: dict) -> None:
        results = fd.discover([fleet["proj_a"]])
        r = results[0]
        assert r["signal1_absent_reason"] is None
        assert r["signal1_absent_detail"] is None

    def test_existing_classifications_unperturbed(self, fleet: dict) -> None:
        """B5: pre-existing bindings keep their exact classification strings."""
        assert fd.discover([fleet["proj_a"]])[0]["binding"] == "scripts"
        assert fd.discover([fleet["proj_b"]])[0]["binding"] == "version"
        assert fd.discover([fleet["proj_c"]])[0]["binding"] == "both"

    def test_no_signal_no_declaration_still_skipped(self, fleet: dict) -> None:
        """proj_d fires neither signal and its reason is no-declaration — still skipped."""
        results = fd.discover([fleet["proj_d"]])
        assert results == []

    def test_inline_only_project_now_included(self, fleet: dict, tmp_path: Path) -> None:
        proj = tmp_path / "inline_bound_project"
        proj.mkdir()
        (proj / "CLAUDE.build.md").write_text(
            f"# Build\n\nRun: uv run python {fd._THIS_SCRIPTS_DIR}/flex_build.py next-action\n",
            encoding="utf-8",
        )
        results = fd.discover([proj])
        assert len(results) == 1
        r = results[0]
        assert r["signal1"] is False
        assert r["signal2"] is False
        assert r["binding"] == "inline"
        assert r["signal1_absent_reason"] == fd.SIGNAL1_ABSENT_INLINE_ONLY

    def test_foreign_checkout_project_now_included(self, fleet: dict, tmp_path: Path) -> None:
        other_checkout = tmp_path / "some_other_flex" / "skills" / "pairmode" / "scripts"
        other_checkout.mkdir(parents=True)
        proj = tmp_path / "foreign_bound_project"
        proj.mkdir()
        (proj / "CLAUDE.build.md").write_text(
            f"# Build\n\npairmode_scripts_dir = {other_checkout}\n",
            encoding="utf-8",
        )
        results = fd.discover([proj])
        assert len(results) == 1
        r = results[0]
        assert r["signal1"] is False
        assert r["signal2"] is False
        assert r["binding"] == "foreign"
        assert r["signal1_absent_reason"] == fd.SIGNAL1_ABSENT_FOREIGN_CHECKOUT


class TestCliSignal1AbsentReason:
    def test_text_output_includes_reason(self, fleet: dict, tmp_path: Path) -> None:
        from click.testing import CliRunner

        proj = tmp_path / "inline_bound_project"
        proj.mkdir()
        (proj / "CLAUDE.build.md").write_text(
            f"# Build\n\nRun: uv run python {fd._THIS_SCRIPTS_DIR}/flex_build.py next-action\n",
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            fd.cli, ["--candidate-dir", str(proj), "--no-snapshot"], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "signal1 (scripts path): absent" in result.output
        assert fd.SIGNAL1_ABSENT_INLINE_ONLY in result.output

    def test_json_output_includes_new_keys(self, fleet: dict) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            fd.cli, ["--candidate-dir", str(fleet["proj_b"]), "--json", "--no-snapshot"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        entry = payload["fleet"][0]
        assert "signal1_absent_reason" in entry
        assert "signal1_absent_detail" in entry


class TestSnapshotSignal1AbsentReason:
    def test_snapshot_appends_reason_as_suffix(self, fleet: dict, tmp_path: Path) -> None:
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover([fleet["proj_b"]])  # signal1 absent, no-declaration path
        fd._write_snapshot(results, dest)
        content = dest.read_text()
        assert "Signal 1 (scripts path):** absent" in content

    def test_snapshot_reason_text_present_for_inline(self, fleet: dict, tmp_path: Path) -> None:
        proj = tmp_path / "inline_bound_project"
        proj.mkdir()
        (proj / "CLAUDE.build.md").write_text(
            f"# Build\n\nRun: uv run python {fd._THIS_SCRIPTS_DIR}/flex_build.py next-action\n",
            encoding="utf-8",
        )
        dest = fleet["fake_flex_root"] / "docs" / "fleet-snapshot.md"
        results = fd.discover([proj])
        fd._write_snapshot(results, dest)
        content = dest.read_text()
        assert "Signal 1 (scripts path):** absent" in content
        assert fd.SIGNAL1_ABSENT_INLINE_ONLY in content


# ---------------------------------------------------------------------------
# D4 — legacy state.json (no provenance sidecar) reads correctly
# ---------------------------------------------------------------------------

class TestLegacyStateCompat:
    def test_read_registered_projects_handles_pre_infra270_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_flex_root = tmp_path / "legacy_flex"
        (fake_flex_root / ".companion").mkdir(parents=True)
        (fake_flex_root / ".companion" / "state.json").write_text(
            json.dumps({"registered_projects": ["/mnt/work/coherra", "/mnt/work/caddy"]}),
            encoding="utf-8",
        )
        monkeypatch.setattr(fd, "_FLEX_ROOT", fake_flex_root)
        projects = fd._read_registered_projects()
        assert [str(p) for p in projects] == ["/mnt/work/coherra", "/mnt/work/caddy"]


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
        assert "no actionable duplicate" in content.lower()
        assert "no plugin-internal duplicate" in content.lower()


# ---------------------------------------------------------------------------
# INFRA-288 (CER-104): merged-view duplicate detection
# ---------------------------------------------------------------------------


class TestMergedViewDuplicateHooks:
    def _project_with_settings_entry(self, root: Path) -> Path:
        proj = root / "proj"
        (proj / ".claude").mkdir(parents=True)
        (proj / ".claude" / "settings.json").write_text(
            json.dumps({
                "hooks": {
                    "PostToolUse": [
                        {"matcher": "Task|Agent", "hooks": [
                            {"type": "command",
                             "command": "uv run python /mnt/work/flex/hooks/post_tool_use.py"},
                        ]},
                    ]
                }
            }),
            encoding="utf-8",
        )
        return proj

    def _install_plugin_hook(self, fake_home: Path) -> Path:
        plugin_file = (
            fake_home / ".claude" / "plugins" / "marketplace" / "flex"
            / "hooks" / "hooks.json"
        )
        plugin_file.parent.mkdir(parents=True)
        plugin_file.write_text(
            json.dumps({
                "hooks": {
                    "PostToolUse": [
                        {"matcher": "Task|Agent", "hooks": [
                            {"type": "command",
                             "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"},
                        ]},
                    ]
                }
            }),
            encoding="utf-8",
        )
        return plugin_file

    def test_settings_vs_plugin_pair_is_reported(
        self, tmp_path: Path, _isolated_home: Path
    ) -> None:
        """B7: the CER-104 shape pre-INFRA-288 code reported as []."""
        proj = self._project_with_settings_entry(tmp_path)
        self._install_plugin_hook(_isolated_home)

        dups = fd._check_duplicate_hooks(proj)
        assert len(dups) == 1
        assert dups[0]["event"] == "PostToolUse"
        assert dups[0]["basename"] == "post_tool_use.py"
        assert dups[0]["commands"] == [
            "uv run python /mnt/work/flex/hooks/post_tool_use.py",
            "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py",
        ]
        assert dups[0]["sources"] == ["settings", "plugin"]

    def test_settings_local_entry_is_seen(self, tmp_path: Path) -> None:
        proj = self._project_with_settings_entry(tmp_path)
        (proj / ".claude" / "settings.local.json").write_text(
            json.dumps({
                "hooks": {
                    "PostToolUse": [
                        {"matcher": "Task|Agent", "hooks": [
                            {"type": "command",
                             "command": "uv run python /elsewhere/hooks/post_tool_use.py"},
                        ]},
                    ]
                }
            }),
            encoding="utf-8",
        )
        dups = fd._check_duplicate_hooks(proj)
        assert len(dups) == 1
        assert dups[0]["sources"] == ["settings", "settings.local"]

    def test_settings_only_project_unchanged(self, tmp_path: Path) -> None:
        """C3: with no settings.local.json and no plugin install, the result
        is what the settings-only detector returned before."""
        proj = self._project_with_settings_entry(tmp_path)
        assert fd._check_duplicate_hooks(proj) == []

    def test_still_read_only(self, tmp_path: Path, _isolated_home: Path) -> None:
        proj = self._project_with_settings_entry(tmp_path)
        plugin_file = self._install_plugin_hook(_isolated_home)
        settings_before = (proj / ".claude" / "settings.json").read_bytes()
        plugin_before = plugin_file.read_bytes()
        fd._check_duplicate_hooks(proj)
        assert (proj / ".claude" / "settings.json").read_bytes() == settings_before
        assert plugin_file.read_bytes() == plugin_before

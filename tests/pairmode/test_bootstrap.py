"""Tests for skills/pairmode/scripts/bootstrap.py."""

from __future__ import annotations

import json
import pathlib

from click.testing import CliRunner

from skills.pairmode.scripts.bootstrap import (
    bootstrap,
    AGENT_FILES,
    DEFAULT_DENY,
    PAIRMODE_VERSION,
    _merge_deny_list,
    _glob_prefix,
    _is_subsumed,
)


# ---------------------------------------------------------------------------
# Fixture helpers for spec-based scenarios
# ---------------------------------------------------------------------------

def _make_spec_structure(
    tmp_path: pathlib.Path,
    modules: dict[str, dict],
    module_paths: list[dict] | None = None,
) -> None:
    """Write a minimal .companion + spec structure into tmp_path.

    modules: mapping of module_name → spec.json dict
    module_paths: list of {"name": ..., "paths": [...]} dicts for modules.json
    """
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(exist_ok=True)

    config_dir = tmp_path / "_config"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.json"
    spec_location = tmp_path / "_spec"
    config_path.write_text(json.dumps({"spec_location": str(spec_location)}), encoding="utf-8")

    (companion_dir / "product.json").write_text(
        json.dumps({"project_name": "testproject", "config": str(config_path)}),
        encoding="utf-8",
    )

    specs_dir = spec_location / "openspec" / "specs"
    for module_name, spec_data in modules.items():
        module_dir = specs_dir / module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "spec.json").write_text(json.dumps(spec_data), encoding="utf-8")

    if module_paths is not None:
        (companion_dir / "modules.json").write_text(
            json.dumps(module_paths), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_bootstrap(tmp_path: pathlib.Path, extra_args: list[str] | None = None) -> object:
    """Invoke bootstrap CLI inside *tmp_path* with non-interactive defaults."""
    runner = CliRunner()
    base_args = [
        "--project-dir", str(tmp_path),
        "--project-name", "testproject",
        "--stack", "Python / pytest",
        "--build-command", "uv run pytest",
    ]
    args = base_args + (extra_args or [])
    result = runner.invoke(bootstrap, args, catch_exceptions=False)
    return result


EXPECTED_DEST_PATHS = [
    "CLAUDE.md",
    "CLAUDE.build.md",
    ".claude/agents/builder.md",
    ".claude/agents/reviewer.md",
    ".claude/agents/loop-breaker.md",
    ".claude/agents/security-auditor.md",
    ".claude/agents/intent-reviewer.md",
    "docs/architecture.md",
    "docs/checkpoints.md",
    "docs/phases/index.md",
    "docs/phases/phase-1.md",
    "docs/cer/backlog.md",
]


# ---------------------------------------------------------------------------
# Core scaffold tests
# ---------------------------------------------------------------------------

class TestBootstrapCreatesFiles:
    def test_all_scaffold_files_created(self, tmp_path):
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        for rel in EXPECTED_DEST_PATHS:
            dest = tmp_path / rel
            assert dest.exists(), f"Expected {rel} to be created, but it was not.\nCLI output:\n{result.output}"

    def test_scaffold_files_are_non_empty(self, tmp_path):
        run_bootstrap(tmp_path)
        for rel in EXPECTED_DEST_PATHS:
            dest = tmp_path / rel
            assert dest.stat().st_size > 0, f"{rel} is empty"

    def test_project_name_rendered_in_claude_md(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "testproject" in content

    def test_stack_rendered_in_claude_md(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "Python / pytest" in content

    def test_build_command_rendered_in_claude_build_md(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "CLAUDE.build.md").read_text()
        assert "uv run pytest" in content

    def test_agent_builder_frontmatter(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / ".claude/agents/builder.md").read_text()
        assert "name: builder" in content

    def test_agent_reviewer_frontmatter(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / ".claude/agents/reviewer.md").read_text()
        assert "name: reviewer" in content

    def test_agent_loop_breaker_frontmatter(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / ".claude/agents/loop-breaker.md").read_text()
        assert "name: loop-breaker" in content

    def test_agent_security_auditor_frontmatter(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / ".claude/agents/security-auditor.md").read_text()
        assert "name: security-auditor" in content

    def test_agent_intent_reviewer_frontmatter(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / ".claude/agents/intent-reviewer.md").read_text()
        assert "name: intent-reviewer" in content

    def test_docs_architecture_has_project_name(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "docs/architecture.md").read_text()
        assert "testproject" in content

    def test_docs_phases_index_created(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "docs/phases/index.md").read_text()
        assert "testproject" in content

    def test_docs_phases_phase1_created(self, tmp_path):
        run_bootstrap(tmp_path)
        assert (tmp_path / "docs/phases/phase-1.md").exists()

    def test_docs_checkpoints_created(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "docs/checkpoints.md").read_text()
        assert "testproject" in content


# ---------------------------------------------------------------------------
# settings.json deny list tests
# ---------------------------------------------------------------------------

class TestDenyListMerge:
    def test_settings_json_created_when_absent(self, tmp_path):
        run_bootstrap(tmp_path)
        settings_path = tmp_path / ".claude" / "settings.json"
        assert settings_path.exists()

    def test_settings_json_has_permissions_deny(self, tmp_path):
        run_bootstrap(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        assert "permissions" in data
        assert "deny" in data["permissions"]

    def test_all_default_deny_entries_present(self, tmp_path):
        run_bootstrap(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        deny = data["permissions"]["deny"]
        for entry in DEFAULT_DENY:
            assert entry in deny, f"Missing deny entry: {entry}"

    def test_merge_does_not_remove_existing_deny_entries(self, tmp_path):
        # Pre-create settings.json with an existing deny entry
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {"permissions": {"deny": ["Edit(some/existing/file.py)"]}}
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        run_bootstrap(tmp_path)

        data = json.loads(settings_path.read_text())
        deny = data["permissions"]["deny"]
        assert "Edit(some/existing/file.py)" in deny

    def test_merge_does_not_duplicate_deny_entries(self, tmp_path):
        # Pre-create settings.json with one of the default deny entries already present
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {"permissions": {"deny": [DEFAULT_DENY[0]]}}
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        run_bootstrap(tmp_path)

        data = json.loads(settings_path.read_text())
        deny = data["permissions"]["deny"]
        assert deny.count(DEFAULT_DENY[0]) == 1

    def test_glob_subsumption_removes_specific_entry(self, tmp_path):
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        # Start with a specific entry
        existing = {"permissions": {"deny": ["Edit(hooks/stop.py)"]}}
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        # Merge a glob that subsumes it
        _merge_deny_list(settings_path, ["Edit(hooks/**)"])

        deny = json.loads(settings_path.read_text())["permissions"]["deny"]
        assert "Edit(hooks/**)" in deny
        assert "Edit(hooks/stop.py)" not in deny, "specific entry should be removed when subsumed"

    def test_glob_subsumption_does_not_remove_unrelated_entries(self, tmp_path):
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {"permissions": {"deny": ["Edit(other/file.py)", "Write(hooks/stop.py)"]}}
        settings_path.write_text(json.dumps(existing), encoding="utf-8")

        _merge_deny_list(settings_path, ["Edit(hooks/**)"])

        deny = json.loads(settings_path.read_text())["permissions"]["deny"]
        assert "Edit(other/file.py)" in deny, "unrelated entry must be kept"
        # Write(hooks/stop.py) is not subsumed by Edit(hooks/**) (different tool)
        assert "Write(hooks/stop.py)" in deny


class TestGlobHelpers:
    def test_glob_prefix_on_glob(self):
        assert _glob_prefix("Edit(hooks/**)") == ("Edit", "hooks/")

    def test_glob_prefix_on_non_glob(self):
        assert _glob_prefix("Edit(hooks/stop.py)") is None

    def test_is_subsumed_true(self):
        assert _is_subsumed("Edit(hooks/stop.py)", [("Edit", "hooks/")])

    def test_is_subsumed_false_different_tool(self):
        assert not _is_subsumed("Write(hooks/stop.py)", [("Edit", "hooks/")])

    def test_is_subsumed_false_different_prefix(self):
        assert not _is_subsumed("Edit(other/file.py)", [("Edit", "hooks/")])


# ---------------------------------------------------------------------------
# state.json tests
# ---------------------------------------------------------------------------

class TestStateJson:
    def test_state_json_created(self, tmp_path):
        run_bootstrap(tmp_path)
        state_path = tmp_path / ".companion" / "state.json"
        assert state_path.exists()

    def test_state_json_has_pairmode_version(self, tmp_path):
        run_bootstrap(tmp_path)
        data = json.loads((tmp_path / ".companion/state.json").read_text())
        assert "pairmode_version" in data
        assert data["pairmode_version"] == PAIRMODE_VERSION

    def test_state_json_preserves_existing_fields(self, tmp_path):
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"some_key": "some_value"}), encoding="utf-8")

        run_bootstrap(tmp_path)

        data = json.loads(state_path.read_text())
        assert data.get("some_key") == "some_value"
        assert data["pairmode_version"] == PAIRMODE_VERSION


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_produces_output(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                "--dry-run",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "dry-run" in result.output.lower() or "dry run" in result.output.lower()

    def test_dry_run_writes_no_scaffold_files(self, tmp_path):
        runner = CliRunner()
        runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                "--dry-run",
            ],
            catch_exceptions=False,
        )
        for rel in EXPECTED_DEST_PATHS:
            assert not (tmp_path / rel).exists(), f"{rel} should not exist after dry run"

    def test_dry_run_does_not_write_settings_json(self, tmp_path):
        runner = CliRunner()
        runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                "--dry-run",
            ],
            catch_exceptions=False,
        )
        assert not (tmp_path / ".claude" / "settings.json").exists()

    def test_dry_run_does_not_write_state_json(self, tmp_path):
        runner = CliRunner()
        runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                "--dry-run",
            ],
            catch_exceptions=False,
        )
        assert not (tmp_path / ".companion" / "state.json").exists()


# ---------------------------------------------------------------------------
# Existing-file protection tests
# ---------------------------------------------------------------------------

class TestExistingFileProtection:
    def test_existing_file_is_skipped_when_user_declines(self, tmp_path):
        # First bootstrap to create files
        run_bootstrap(tmp_path)

        # Modify the file to detect an overwrite
        (tmp_path / "CLAUDE.md").write_text("custom content", encoding="utf-8")

        # Second run — simulate user saying "n" to all overwrite prompts
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
            ],
            input="n\n" * 20,  # decline all overwrite prompts
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        # File should still have the custom content (not overwritten)
        assert (tmp_path / "CLAUDE.md").read_text() == "custom content"

    def test_existing_file_is_overwritten_when_user_confirms(self, tmp_path):
        run_bootstrap(tmp_path)

        # Change CLAUDE.md
        (tmp_path / "CLAUDE.md").write_text("custom content", encoding="utf-8")

        runner = CliRunner()
        runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
            ],
            input="y\n" * 20,  # confirm all overwrites
            catch_exceptions=False,
        )
        # CLAUDE.md should now have the rendered template content again
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "testproject" in content
        assert "custom content" not in content


# ---------------------------------------------------------------------------
# product.json integration test
# ---------------------------------------------------------------------------

class TestProductJsonIntegration:
    def test_project_name_loaded_from_product_json(self, tmp_path):
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        product = {"project_name": "from_product_json"}
        (companion_dir / "product.json").write_text(json.dumps(product), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                # No --project-name provided — should come from product.json
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "from_product_json" in content


# ---------------------------------------------------------------------------
# Build command inference tests
# ---------------------------------------------------------------------------

class TestBuildCommandInference:
    def test_infers_uv_run_pytest_from_pyproject_toml(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                # No --build-command — should infer from pyproject.toml
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        content = (tmp_path / "CLAUDE.build.md").read_text()
        assert "uv run pytest" in content

    def test_infers_pnpm_from_pnpm_lockfile(self, tmp_path):
        (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 6\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "TypeScript / Next.js",
                # No --build-command
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        content = (tmp_path / "CLAUDE.build.md").read_text()
        assert "pnpm build" in content


# ---------------------------------------------------------------------------
# --help smoke test
# ---------------------------------------------------------------------------

def test_help_succeeds():
    runner = CliRunner()
    result = runner.invoke(bootstrap, ["--help"])
    assert result.exit_code == 0
    assert "project-dir" in result.output


# ---------------------------------------------------------------------------
# sys.path guard test (subprocess, no PYTHONPATH in env)
# ---------------------------------------------------------------------------

def test_bootstrap_help_via_subprocess_no_pythonpath(tmp_path):
    """Verify bootstrap.py --help works without PYTHONPATH set externally.

    The sys.path guard inside bootstrap.py must handle the import path
    insertion on its own, so no PYTHONPATH env var is required.
    """
    import os
    import subprocess
    import sys

    bootstrap_path = str(
        pathlib.Path(__file__).parent.parent.parent
        / "skills" / "pairmode" / "scripts" / "bootstrap.py"
    )

    # Strip PYTHONPATH from the environment to ensure the guard does all the work
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    result = subprocess.run(
        [sys.executable, bootstrap_path, "--help"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"bootstrap.py --help failed without PYTHONPATH.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "project-dir" in result.stdout


# ---------------------------------------------------------------------------
# Spec-derived scenarios
# ---------------------------------------------------------------------------

class TestSpecDerivedChecklist:
    """When a spec is present, checklist_items come from the spec derivation."""

    def test_no_spec_checklist_items_is_empty_list(self, tmp_path):
        """Without a spec, derived_checklist is [] (universal items come from templates)."""
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        # Templates still render — we just verify bootstrap succeeds cleanly
        assert (tmp_path / "CLAUDE.md").exists()

    def test_reviewer_checklist_contains_only_universal_items(self, tmp_path):
        """Reviewer checklist uses only universal items; spec non-negotiables are NOT injected."""
        _make_spec_structure(
            tmp_path,
            modules={
                "auth": {
                    "module": "auth",
                    "non_negotiables": ["Auth must never call billing directly — events only"],
                    "business_rules": ["All payments must be idempotent"],
                }
            },
        )
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        content = (tmp_path / ".claude/agents/reviewer.md").read_text()
        # Spec text must NOT appear in reviewer checklist (L005 fix)
        assert "Auth must never call billing directly" not in content
        assert "All payments must be idempotent" not in content
        # Universal items must still be present
        assert "PROTECTED FILES" in content
        assert "STORY SCOPE" in content
        assert "BUILD GATE" in content


class TestSpecDerivedDenyList:
    """When a spec is present with matching paths, deny list is spec-derived."""

    def test_spec_derived_deny_entries_in_settings_json(self, tmp_path):
        """With spec + module paths, settings.json gets spec-derived deny patterns."""
        _make_spec_structure(
            tmp_path,
            modules={
                "auth-and-security": {
                    "module": "auth-and-security",
                    "non_negotiables": ["Auth must never call billing directly — events only"],
                    "business_rules": [],
                }
            },
            module_paths=[
                {"name": "auth-and-security", "paths": ["src/services/auth"]}
            ],
        )
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        deny = data["permissions"]["deny"]
        assert "Edit(src/services/auth/**)" in deny
        assert "Write(src/services/auth/**)" in deny

    def test_spec_derived_deny_replaces_static_defaults(self, tmp_path):
        """When spec yields deny rules, DEFAULT_DENY static entries are NOT written."""
        _make_spec_structure(
            tmp_path,
            modules={
                "auth-and-security": {
                    "module": "auth-and-security",
                    "non_negotiables": ["Auth must never call billing directly — events only"],
                    "business_rules": [],
                }
            },
            module_paths=[
                {"name": "auth-and-security", "paths": ["src/services/auth"]}
            ],
        )
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        deny = data["permissions"]["deny"]
        # Static default entries should NOT be present when spec-derived rules replace them
        for static_entry in DEFAULT_DENY:
            assert static_entry not in deny, f"Static entry {static_entry!r} should not be present when spec-derived deny is active"

    def test_no_spec_falls_back_to_default_deny(self, tmp_path):
        """Without a spec, settings.json gets the DEFAULT_DENY static entries."""
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        deny = data["permissions"]["deny"]
        for entry in DEFAULT_DENY:
            assert entry in deny, f"Missing default deny entry: {entry}"

    def test_spec_no_matching_paths_falls_back_to_default_deny(self, tmp_path):
        """Spec present but no triggered deny rules → fall back to DEFAULT_DENY."""
        _make_spec_structure(
            tmp_path,
            modules={
                "auth-and-security": {
                    "module": "auth-and-security",
                    "non_negotiables": ["Auth must never call billing directly — events only"],
                    "business_rules": [],
                }
            },
            # no module_paths — modules.json absent
        )
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        deny = data["permissions"]["deny"]
        for entry in DEFAULT_DENY:
            assert entry in deny


class TestDenyRationaleJson:
    """settings.deny-rationale.json is always written alongside settings.json."""

    def test_rationale_file_created(self, tmp_path):
        run_bootstrap(tmp_path)
        rationale_path = tmp_path / ".claude" / "settings.deny-rationale.json"
        assert rationale_path.exists()

    def test_rationale_has_required_keys(self, tmp_path):
        run_bootstrap(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.deny-rationale.json").read_text())
        assert data["generated_by"] == "anchor:pairmode"
        assert data["pairmode_version"] == PAIRMODE_VERSION
        assert isinstance(data["rules"], list)

    def test_rationale_rules_empty_without_spec(self, tmp_path):
        """No spec → rationale rules list is empty (static deny has no rationale)."""
        run_bootstrap(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.deny-rationale.json").read_text())
        assert data["rules"] == []

    def test_rationale_rules_populated_with_spec(self, tmp_path):
        """With spec-derived deny rules, rationale file lists them with pattern/module/non_negotiable."""
        _make_spec_structure(
            tmp_path,
            modules={
                "auth-and-security": {
                    "module": "auth-and-security",
                    "non_negotiables": ["Auth must never call billing directly — events only"],
                    "business_rules": [],
                }
            },
            module_paths=[
                {"name": "auth-and-security", "paths": ["src/services/auth"]}
            ],
        )
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        data = json.loads((tmp_path / ".claude/settings.deny-rationale.json").read_text())
        assert len(data["rules"]) > 0
        rule = data["rules"][0]
        assert "pattern" in rule
        assert "module" in rule
        assert "non_negotiable" in rule
        assert rule["module"] == "auth-and-security"
        assert "Auth must never call billing directly" in rule["non_negotiable"]

    def test_dry_run_does_not_write_rationale_file(self, tmp_path):
        runner = CliRunner()
        runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                "--dry-run",
            ],
            catch_exceptions=False,
        )
        assert not (tmp_path / ".claude" / "settings.deny-rationale.json").exists()


# ---------------------------------------------------------------------------
# pairmode_context.json tests
# ---------------------------------------------------------------------------

class TestPairmodeContextJson:
    """bootstrap writes .companion/pairmode_context.json with the template context."""

    def test_context_file_created(self, tmp_path):
        run_bootstrap(tmp_path)
        context_path = tmp_path / ".companion" / "pairmode_context.json"
        assert context_path.exists(), "pairmode_context.json should be created"

    def test_context_file_has_project_name(self, tmp_path):
        run_bootstrap(tmp_path)
        data = json.loads((tmp_path / ".companion" / "pairmode_context.json").read_text())
        assert data["project_name"] == "testproject"

    def test_context_file_has_stack(self, tmp_path):
        run_bootstrap(tmp_path)
        data = json.loads((tmp_path / ".companion" / "pairmode_context.json").read_text())
        assert data["stack"] == "Python / pytest"

    def test_context_file_has_required_keys(self, tmp_path):
        run_bootstrap(tmp_path)
        data = json.loads((tmp_path / ".companion" / "pairmode_context.json").read_text())
        required_keys = [
            "project_name", "project_description", "stack", "build_command",
            "test_command", "migration_command", "domain_model", "domain_isolation_rule",
            "checklist_items", "protected_paths", "non_negotiables",
            "module_structure", "layer_rules",
        ]
        for key in required_keys:
            assert key in data, f"pairmode_context.json missing key: {key}"

    def test_dry_run_does_not_write_context_file(self, tmp_path):
        runner = CliRunner()
        runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                "--dry-run",
            ],
            catch_exceptions=False,
        )
        assert not (tmp_path / ".companion" / "pairmode_context.json").exists()


# ---------------------------------------------------------------------------
# Agent file skip-by-default tests (Story 7.0 / L003)
# ---------------------------------------------------------------------------

AGENT_DEST_PATHS = [dest_rel for dest_rel, _ in AGENT_FILES]


class TestAgentFileSkipByDefault:
    """Agent files in .claude/agents/ are project-owned after first bootstrap."""

    def _run_bootstrap_decline_all(self, tmp_path: pathlib.Path, extra_args: list[str] | None = None) -> object:
        """Run bootstrap declining all overwrite prompts (for non-agent scaffold files)."""
        runner = CliRunner()
        base_args = [
            "--project-dir", str(tmp_path),
            "--project-name", "testproject",
            "--stack", "Python / pytest",
            "--build-command", "uv run pytest",
        ]
        args = base_args + (extra_args or [])
        return runner.invoke(bootstrap, args, input="n\n" * 20, catch_exceptions=False)

    def test_agent_files_skipped_when_already_exist(self, tmp_path):
        """Second bootstrap without --force-agents must not overwrite existing agent files."""
        # First run — creates all files
        run_bootstrap(tmp_path)

        # Mark each agent file with sentinel content
        for rel in AGENT_DEST_PATHS:
            (tmp_path / rel).write_text("# project-owned sentinel", encoding="utf-8")

        # Second run — no --force-agents; decline prompts for non-agent files
        result = self._run_bootstrap_decline_all(tmp_path)
        assert result.exit_code == 0, result.output

        # All agent files should still have the sentinel content
        for rel in AGENT_DEST_PATHS:
            content = (tmp_path / rel).read_text(encoding="utf-8")
            assert content == "# project-owned sentinel", (
                f"{rel} was overwritten on second bootstrap without --force-agents"
            )

    def test_skip_message_printed_for_existing_agent_files(self, tmp_path):
        """Bootstrap should print a 'skipped (project-owned)' message for each skipped agent file."""
        run_bootstrap(tmp_path)

        result = self._run_bootstrap_decline_all(tmp_path)
        assert result.exit_code == 0, result.output
        assert "skipped (project-owned)" in result.output

    def test_skip_message_mentions_force_agents(self, tmp_path):
        """The skip message must tell the user to use --force-agents."""
        run_bootstrap(tmp_path)

        result = self._run_bootstrap_decline_all(tmp_path)
        assert "--force-agents" in result.output

    def test_agent_files_overwritten_with_force_agents(self, tmp_path):
        """--force-agents causes existing agent files to be overwritten."""
        run_bootstrap(tmp_path)

        # Mark each agent file with sentinel content
        for rel in AGENT_DEST_PATHS:
            (tmp_path / rel).write_text("# project-owned sentinel", encoding="utf-8")

        # Second run with --force-agents; decline prompts for non-agent files
        result = self._run_bootstrap_decline_all(tmp_path, extra_args=["--force-agents"])
        assert result.exit_code == 0, result.output

        # All agent files should have been overwritten (sentinel gone, project_name present)
        for rel in AGENT_DEST_PATHS:
            content = (tmp_path / rel).read_text(encoding="utf-8")
            assert "# project-owned sentinel" not in content, (
                f"{rel} was not overwritten despite --force-agents"
            )

    def test_non_agent_scaffold_files_always_written(self, tmp_path):
        """CLAUDE.md and docs/ files follow normal prompt-based overwrite logic (not agent skip)."""
        run_bootstrap(tmp_path)

        # Modify CLAUDE.md
        (tmp_path / "CLAUDE.md").write_text("custom content", encoding="utf-8")

        # Second run — agent files skipped, but CLAUDE.md prompts for overwrite.
        # Simulate user saying "y" to overwrite CLAUDE.md.
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
            ],
            input="y\n" * 20,
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # CLAUDE.md should have been overwritten (user said y)
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "testproject" in content
        assert "custom content" not in content

    def test_agent_files_created_on_first_bootstrap(self, tmp_path):
        """On first bootstrap (no prior files), agent files are always written."""
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        for rel in AGENT_DEST_PATHS:
            assert (tmp_path / rel).exists(), f"Agent file {rel} not created on first bootstrap"

    def test_force_agents_flag_in_help(self):
        """--force-agents flag must appear in help output."""
        runner = CliRunner()
        result = runner.invoke(bootstrap, ["--help"])
        assert result.exit_code == 0
        assert "force-agents" in result.output


# ---------------------------------------------------------------------------
# CER backlog bootstrap tests (Story 7.3)
# ---------------------------------------------------------------------------

class TestCerBacklogBootstrap:
    """Bootstrap writes docs/cer/backlog.md to new projects."""

    def test_bootstrap_writes_cer_backlog(self, tmp_path):
        result = run_bootstrap(tmp_path)
        assert result.exit_code == 0, result.output
        assert (tmp_path / "docs/cer/backlog.md").exists(), (
            "Bootstrap must write docs/cer/backlog.md"
        )

    def test_cer_backlog_is_non_empty(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "docs/cer/backlog.md").read_text(encoding="utf-8")
        assert content.strip()

    def test_cer_backlog_has_project_name(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "docs/cer/backlog.md").read_text(encoding="utf-8")
        assert "testproject" in content

    def test_cer_backlog_has_four_quadrant_headings(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "docs/cer/backlog.md").read_text(encoding="utf-8")
        assert "## Do Now" in content
        assert "## Do Later" in content
        assert "## Do Much Later" in content
        assert "## Do Never" in content

    def test_cer_backlog_rendered_with_empty_entries(self, tmp_path):
        """Bootstrap renders backlog with cer_entries=[] — none placeholder rows appear."""
        run_bootstrap(tmp_path)
        content = (tmp_path / "docs/cer/backlog.md").read_text(encoding="utf-8")
        assert "*(none)*" in content


# ---------------------------------------------------------------------------
# Story 8.4: phase-title / phase-goal / non-TTY what/why warning
# ---------------------------------------------------------------------------

class TestPhaseTitleAndGoal:
    """Bootstrap --phase-title and --phase-goal populate docs/phases/phase-1.md."""

    def test_phase_title_in_phase1_md(self, tmp_path):
        """--phase-title 'My Phase' causes phase-1.md to contain 'My Phase'."""
        result = run_bootstrap(tmp_path, extra_args=["--phase-title", "My Phase"])
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs/phases/phase-1.md").read_text(encoding="utf-8")
        assert "My Phase" in content

    def test_phase_goal_in_phase1_md(self, tmp_path):
        """--phase-goal text is rendered into phase-1.md."""
        result = run_bootstrap(tmp_path, extra_args=["--phase-goal", "Ship the MVP"])
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs/phases/phase-1.md").read_text(encoding="utf-8")
        assert "Ship the MVP" in content

    def test_no_phase_title_non_tty_no_crash(self, tmp_path):
        """Without --phase-title in non-TTY, phase-1.md renders with empty/placeholder title."""
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                # no --phase-title
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "docs/phases/phase-1.md").exists()

    def test_phase_title_also_rendered_in_index(self, tmp_path):
        """--phase-title is reflected in docs/phases/index.md as well."""
        result = run_bootstrap(tmp_path, extra_args=["--phase-title", "Launch Phase"])
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs/phases/index.md").read_text(encoding="utf-8")
        assert "Launch Phase" in content


class TestNonTtyWhatWhyWarning:
    """Non-TTY bootstrap emits a warning when what/why are blank."""

    def test_warning_on_stderr_when_no_what(self, tmp_path):
        """In non-TTY (CliRunner), omitting --what produces a warning on stderr."""
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                # no --what or --why
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # CliRunner mixes stderr into output by default; warning should appear there.
        assert "warning: non-interactive mode" in result.output
        assert "docs/brief.md" in result.output

    def test_no_warning_when_what_provided(self, tmp_path):
        """In non-TTY, providing --what and --why suppresses the warning."""
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                "--what", "something useful",
                "--why", "because reasons",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "warning: non-interactive mode" not in result.output

    def test_what_value_appears_in_brief_md(self, tmp_path):
        """--what value is rendered into docs/brief.md."""
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "testproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
                "--what", "something useful",
                "--why", "because reasons",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs/brief.md").read_text(encoding="utf-8")
        assert "something useful" in content


# ---------------------------------------------------------------------------
# Story 9.4: DEFAULT_DENY scope tests for docs/phases and docs/brief.md
# ---------------------------------------------------------------------------

class TestDefaultDenyScopeDocs:
    """DEFAULT_DENY must protect docs/phases/** and docs/brief.md but not operational files."""

    def test_edit_docs_phases_glob_in_default_deny(self):
        assert "Edit(docs/phases/**)" in DEFAULT_DENY

    def test_write_docs_phases_glob_in_default_deny(self):
        assert "Write(docs/phases/**)" in DEFAULT_DENY

    def test_edit_docs_brief_in_default_deny(self):
        assert "Edit(docs/brief.md)" in DEFAULT_DENY

    def test_write_docs_brief_in_default_deny(self):
        assert "Write(docs/brief.md)" in DEFAULT_DENY

    def test_blanket_edit_docs_not_in_default_deny(self):
        assert "Edit(docs/**)" not in DEFAULT_DENY

    def test_blanket_write_docs_not_in_default_deny(self):
        assert "Write(docs/**)" not in DEFAULT_DENY

    def test_edit_checkpoints_not_in_default_deny(self):
        """docs/checkpoints.md is an operational file — must not be denied."""
        assert "Edit(docs/checkpoints.md)" not in DEFAULT_DENY

    def test_edit_cer_backlog_not_in_default_deny(self):
        """docs/cer/backlog.md is an operational file — must not be denied."""
        assert "Edit(docs/cer/backlog.md)" not in DEFAULT_DENY

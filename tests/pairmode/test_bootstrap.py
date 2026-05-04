"""Tests for skills/pairmode/scripts/bootstrap.py."""

from __future__ import annotations

import json
import pathlib

from click.testing import CliRunner

from skills.pairmode.scripts.bootstrap import bootstrap, DEFAULT_DENY, PAIRMODE_VERSION


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
    "docs/phase-prompts.md",
    "docs/checkpoints.md",
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

    def test_docs_phase_prompts_created(self, tmp_path):
        run_bootstrap(tmp_path)
        content = (tmp_path / "docs/phase-prompts.md").read_text()
        assert "testproject" in content

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

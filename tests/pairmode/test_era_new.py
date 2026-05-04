"""Tests for skills/pairmode/scripts/era_new.py."""

from __future__ import annotations

import pathlib

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.era_new import era_new


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(args: list[str]) -> "click.testing.Result":
    """Invoke era_new with the given arguments."""
    runner = CliRunner()
    return runner.invoke(era_new, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEraFileCreated:
    """Era file is created at the correct path with the correct ID."""

    def test_creates_era_file_at_correct_path(self, tmp_path: pathlib.Path) -> None:
        result = invoke(["--name", "Ideology capture", "--project-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        era_file = tmp_path / "docs" / "eras" / "001-ideology-capture.md"
        assert era_file.exists(), f"Expected {era_file} to exist"

    def test_output_contains_era_id_and_name(self, tmp_path: pathlib.Path) -> None:
        result = invoke(["--name", "Foundation", "--project-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "001" in result.output
        assert "Foundation" in result.output

    def test_frontmatter_contains_id_name_status(self, tmp_path: pathlib.Path) -> None:
        invoke(["--name", "My Era", "--project-dir", str(tmp_path)])
        era_file = tmp_path / "docs" / "eras" / "001-my-era.md"
        content = era_file.read_text()
        assert "id: 001" in content
        assert "name: My Era" in content
        assert "status: active" in content


class TestIdIncrement:
    """ID increments correctly for subsequent eras."""

    def test_second_era_gets_002(self, tmp_path: pathlib.Path) -> None:
        invoke(["--name", "First Era", "--project-dir", str(tmp_path)])
        result = invoke(["--name", "Second Era", "--project-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        era_file = tmp_path / "docs" / "eras" / "002-second-era.md"
        assert era_file.exists(), "Expected 002-second-era.md to exist"
        assert "002" in result.output

    def test_third_era_gets_003(self, tmp_path: pathlib.Path) -> None:
        for name in ("Alpha", "Beta", "Gamma"):
            invoke(["--name", name, "--project-dir", str(tmp_path)])
        era_file = tmp_path / "docs" / "eras" / "003-gamma.md"
        assert era_file.exists()


class TestDirCreation:
    """docs/eras/ is created if it does not exist."""

    def test_creates_eras_dir_when_absent(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        assert not eras_dir.exists()
        result = invoke(["--name", "New Era", "--project-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert eras_dir.is_dir()

    def test_idempotent_when_dir_exists(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        eras_dir.mkdir(parents=True)
        result = invoke(["--name", "Existing dir era", "--project-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        era_file = eras_dir / "001-existing-dir-era.md"
        assert era_file.exists()


class TestGoalOption:
    """--goal populates the Strategic intent section."""

    def test_goal_appears_in_strategic_intent(self, tmp_path: pathlib.Path) -> None:
        goal_text = "Establish the foundational architecture for the product."
        result = invoke(
            ["--name", "Foundation", "--goal", goal_text, "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        era_file = tmp_path / "docs" / "eras" / "001-foundation.md"
        content = era_file.read_text()
        assert goal_text in content
        assert "## Strategic intent" in content

    def test_no_goal_shows_placeholder(self, tmp_path: pathlib.Path) -> None:
        invoke(["--name", "Placeholder Era", "--project-dir", str(tmp_path)])
        era_file = tmp_path / "docs" / "eras" / "001-placeholder-era.md"
        content = era_file.read_text()
        assert "## Strategic intent" in content
        assert "_(fill in)_" in content


class TestBodySectionStubs:
    """Era file contains required section stubs."""

    def test_rails_table_header_present(self, tmp_path: pathlib.Path) -> None:
        invoke(["--name", "Rail Era", "--project-dir", str(tmp_path)])
        era_file = tmp_path / "docs" / "eras" / "001-rail-era.md"
        content = era_file.read_text()
        assert "## Rails" in content
        assert "| Rail |" in content

    def test_phases_table_header_present(self, tmp_path: pathlib.Path) -> None:
        invoke(["--name", "Phase Era", "--project-dir", str(tmp_path)])
        era_file = tmp_path / "docs" / "eras" / "001-phase-era.md"
        content = era_file.read_text()
        assert "## Phases" in content
        assert "| Phase |" in content


class TestPathTraversalGuard:
    """Too-shallow project_dir causes non-zero exit."""

    def test_shallow_path_exits_nonzero(self, tmp_path: pathlib.Path) -> None:
        shallow = pathlib.Path("/tmp")
        if len(shallow.resolve().parts) < 3:
            runner = CliRunner()
            result = runner.invoke(
                era_new,
                ["--name", "Test Era", "--project-dir", str(shallow)],
                catch_exceptions=False,
            )
            assert result.exit_code != 0
        else:
            pytest.skip("/tmp resolves to >= 3 parts on this system")

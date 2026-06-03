"""Tests for skills/pairmode/scripts/phase_new.py."""

from __future__ import annotations

import json
import pathlib

from click.testing import CliRunner

from skills.pairmode.scripts.phase_new import (
    phase_new,
    _read_phase_title,
    _append_index_row,
    _create_index,
    _detect_active_era,
    _update_era_phases_table,
)
from skills.pairmode.scripts.schema_validator import (
    validate_phase_manifest,
    VALID_PHASE_CLASSES,
    DEFAULT_PHASE_CLASS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(args: list[str], input: str | None = None) -> "click.testing.Result":
    runner = CliRunner()
    return runner.invoke(phase_new, args, input=input, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFreshProject:
    """Fresh project: creates both phase-1.md and index.md."""

    def test_creates_phase_file(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Getting Started",
                "--goal", "Bootstrap the project",
            ]
        )
        assert result.exit_code == 0, result.output
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        assert phase_file.exists()
        content = phase_file.read_text()
        assert "Getting Started" in content

    def test_creates_index_file(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Getting Started",
                "--goal", "Bootstrap the project",
            ]
        )
        assert result.exit_code == 0, result.output
        index_file = tmp_path / "docs" / "phases" / "index.md"
        assert index_file.exists()
        content = index_file.read_text()
        assert "Getting Started" in content
        assert "phase-1.md" in content
        assert "planned" in content

    def test_goal_in_phase_file(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Alpha",
                "--goal", "Do the alpha things",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "Do the alpha things" in content


class TestIdempotent:
    """Running twice with same phase ID warns and does not overwrite."""

    def test_warns_on_second_run(self, tmp_path: pathlib.Path) -> None:
        args = [
            "--project-dir", str(tmp_path),
            "--phase-id", "1",
            "--title", "Alpha",
            "--goal", "First goal",
        ]
        invoke(args)
        result = invoke(args)
        assert result.exit_code == 0
        assert "already exists" in result.output or "Warning" in result.output

    def test_does_not_overwrite(self, tmp_path: pathlib.Path) -> None:
        args = [
            "--project-dir", str(tmp_path),
            "--phase-id", "1",
            "--title", "Alpha",
            "--goal", "First goal",
        ]
        invoke(args)
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        original = phase_file.read_text()

        # Second run with different title — file must stay unchanged
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Changed Title",
                "--goal", "Different goal",
            ]
        )
        assert phase_file.read_text() == original


class TestPrevPhase:
    """Phase 3 after phases 1 and 2 exist: prev_phase populated from phase-2.md."""

    def test_prev_phase_populated(self, tmp_path: pathlib.Path) -> None:
        # Create phase 1
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Phase One",
                "--goal", "",
            ]
        )
        # Create phase 2
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Phase Two",
                "--goal", "",
            ]
        )
        # Create phase 3
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "3",
                "--title", "Phase Three",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-3.md").read_text()
        # Should reference phase 2 as previous
        assert "Phase Two" in content or "phase-2.md" in content

    def test_no_prev_phase_when_n_is_1(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Solo Phase",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        # No backward nav link expected
        assert "phase-0.md" not in content


class TestDirCreation:
    """docs/phases/ directory is created if it does not exist."""

    def test_creates_phases_dir(self, tmp_path: pathlib.Path) -> None:
        assert not (tmp_path / "docs").exists()
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Hello",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0
        assert (tmp_path / "docs" / "phases").is_dir()
        assert (tmp_path / "docs" / "phases" / "phase-1.md").exists()


class TestPrevPhaseNoHeading:
    """Phase N where N-1 exists but has no # Phase heading: graceful fallback."""

    def test_graceful_fallback(self, tmp_path: pathlib.Path) -> None:
        phases_dir = tmp_path / "docs" / "phases"
        phases_dir.mkdir(parents=True)
        # Write a phase-1.md with no # Phase heading
        (phases_dir / "phase-1.md").write_text(
            "Some content without a phase heading.\n", encoding="utf-8"
        )
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Second Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0
        content = (phases_dir / "phase-2.md").read_text()
        # Should fall back to "Phase 1" rather than crashing
        assert "Phase 1" in content

    def test_read_phase_title_fallback(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "no_heading.md"
        f.write_text("No heading here\n", encoding="utf-8")
        title = _read_phase_title(f, 5)
        assert title == "Phase 5"

    def test_read_phase_title_with_heading(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "phase.md"
        f.write_text("# MyProject — Phase 2: The Real Deal\n\nContent\n", encoding="utf-8")
        title = _read_phase_title(f, 2)
        assert title == "The Real Deal"


class TestProjectNameFromContext:
    """project_name is read from pairmode_context.json when present."""

    def test_project_name_from_context_renders_in_phase_file(
        self, tmp_path: pathlib.Path
    ) -> None:
        # Write context file
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        ctx = {"project_name": "myawesome"}
        (companion_dir / "pairmode_context.json").write_text(
            json.dumps(ctx), encoding="utf-8"
        )

        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "myawesome" in content

    def test_project_name_fallback_when_context_absent(
        self, tmp_path: pathlib.Path
    ) -> None:
        # No .companion directory at all
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "project" in content


class TestCreateIndex:
    """_create_index() threads project_name into the rendered index.md."""

    def test_project_name_in_rendered_index(self, tmp_path: pathlib.Path) -> None:
        index_path = tmp_path / "index.md"
        _create_index(index_path, phase_key="1", phase_title="First Phase", project_name="MyProject")
        content = index_path.read_text()
        assert "MyProject" in content

    def test_default_fallback_renders_without_crash(self, tmp_path: pathlib.Path) -> None:
        index_path = tmp_path / "index.md"
        # Call with default project_name — must not raise
        _create_index(index_path, phase_key="1", phase_title="First Phase")
        assert index_path.exists()
        content = index_path.read_text()
        assert "First Phase" in content


class TestDryRun:
    """--dry-run prints what would be written without writing files."""

    def test_dry_run_no_files_written(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Second Phase",
                "--goal", "Do things",
                "--dry-run",
            ]
        )
        assert result.exit_code == 0, result.output
        # No files should have been written
        assert not (tmp_path / "docs").exists()

    def test_dry_run_output_contains_would_write(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "3",
                "--title", "Third Phase",
                "--goal", "",
                "--dry-run",
            ]
        )
        assert result.exit_code == 0, result.output
        assert "Would write" in result.output

    def test_dry_run_with_existing_index_shows_would_update(
        self, tmp_path: pathlib.Path
    ) -> None:
        # Create index first (non-dry-run)
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First",
                "--goal", "",
            ]
        )
        # Now dry-run for phase 2
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Second",
                "--goal", "",
                "--dry-run",
            ]
        )
        assert result.exit_code == 0, result.output
        assert "Would write" in result.output or "Would update" in result.output
        # phase-2.md must not exist
        assert not (tmp_path / "docs" / "phases" / "phase-2.md").exists()


# ---------------------------------------------------------------------------
# Era detection helpers
# ---------------------------------------------------------------------------

ERA_ACTIVE_CONTENT = """\
---
id: 001
name: Foundation
status: active
---

## Strategic intent

Building the foundation.

## Rails

| Rail | Primary domain |
|------|----------------|

## Phases

| Phase | Title | Status |
|-------|-------|--------|
"""

ERA_COMPLETE_CONTENT = """\
---
id: 001
name: Foundation
status: complete
---

## Phases

| Phase | Title | Status |
|-------|-------|--------|
"""


def _write_era(eras_dir: pathlib.Path, filename: str, content: str) -> pathlib.Path:
    eras_dir.mkdir(parents=True, exist_ok=True)
    p = eras_dir / filename
    p.write_text(content, encoding="utf-8")
    return p


class TestDetectActiveEra:
    """_detect_active_era() helper tests."""

    def test_returns_none_when_no_eras_dir(self, tmp_path: pathlib.Path) -> None:
        result = _detect_active_era(tmp_path)
        assert result is None

    def test_returns_none_when_no_active_era(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_COMPLETE_CONTENT)
        result = _detect_active_era(tmp_path)
        assert result is None

    def test_returns_era_id_for_single_active(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)
        result = _detect_active_era(tmp_path)
        assert result == "001"

    def test_multiple_active_returns_highest(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        active1 = ERA_ACTIVE_CONTENT
        active2 = active1.replace("id: 001", "id: 002").replace("name: Foundation", "name: Second")
        _write_era(eras_dir, "001-foundation.md", active1)
        _write_era(eras_dir, "002-second.md", active2)
        result = _detect_active_era(tmp_path)
        assert result == "002"


class TestUpdateErasPhasesTable:
    """_update_era_phases_table() helper tests."""

    def test_appends_row_to_phases_table(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        era_file = _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)
        _update_era_phases_table(tmp_path, "001", "3", "My Phase")
        content = era_file.read_text()
        assert "| 3 | My Phase | planned |" in content

    def test_no_crash_when_era_not_found(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)
        # Trying to update era 002 which doesn't exist — must not raise
        _update_era_phases_table(tmp_path, "002", "1", "Whatever")

    def test_update_era_phases_table_with_no_frontmatter(self, tmp_path: pathlib.Path) -> None:
        """Era file with body content but no frontmatter block must not crash.

        _update_era_phases_table should gracefully skip or add the row if a
        Phases table is present.  It must never raise an exception.
        """
        eras_dir = tmp_path / "docs" / "eras"
        eras_dir.mkdir(parents=True, exist_ok=True)
        body_only_content = (
            "## Strategic intent\n\nBuilding the foundation.\n\n"
            "## Phases\n\n"
            "| Phase | Title | Status |\n"
            "|-------|-------|--------|\n"
        )
        era_file = eras_dir / "001-foundation.md"
        era_file.write_text(body_only_content, encoding="utf-8")

        # Must not raise regardless of whether it inserts the row
        _update_era_phases_table(tmp_path, "001", "3", "My Phase")
        # Era file still readable after the call
        assert era_file.exists()


class TestEraFrontmatterInPhaseFile:
    """Phase file gets era frontmatter when active era exists."""

    def test_phase_has_era_frontmatter_when_active_era(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)

        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First Phase",
                "--goal", "Do things",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert 'era: "001"' in content

    def test_phase_has_empty_stories_table(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)

        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "First Phase",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        # Stories table header present
        assert "| ID | Title | Status |" in content
        # No extra story rows beyond separator
        assert "|----|-------|--------|" in content

    def test_era_phases_table_updated(self, tmp_path: pathlib.Path) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        era_file = _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)

        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "5",
                "--title", "Fifth Phase",
                "--goal", "",
            ]
        )
        era_content = era_file.read_text()
        assert "| 5 | Fifth Phase | planned |" in era_content

    def test_no_era_frontmatter_when_no_active_era(self, tmp_path: pathlib.Path) -> None:
        # No eras directory at all
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Solo Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "era:" not in content
        # Frontmatter block should be absent — file must not start with ---
        assert not content.startswith("---")


# ---------------------------------------------------------------------------
# Tests: depth guard
# ---------------------------------------------------------------------------


class TestDepthGuard:
    """phase_new depth guard rejects too-shallow project directories."""

    def test_project_dir_root_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            phase_new,
            ["--project-dir", "/", "--phase-id", "1", "--title", "T", "--goal", ""],
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert "too shallow" in result.output.lower()

    def test_project_dir_tmp_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            phase_new,
            ["--project-dir", "/tmp", "--phase-id", "1", "--title", "T", "--goal", ""],
            catch_exceptions=False,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Tests: phase_class field
# ---------------------------------------------------------------------------


class TestPhaseClass:
    """phase_class frontmatter field: written when provided, absent when omitted."""

    def test_phase_class_production_written_to_frontmatter(
        self, tmp_path: pathlib.Path
    ) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Prod Phase",
                "--goal", "",
                "--phase-class", "production",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "phase_class: production" in content

    def test_phase_class_docs_only_written_to_frontmatter(
        self, tmp_path: pathlib.Path
    ) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Docs Phase",
                "--goal", "",
                "--phase-class", "docs-only",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "phase_class: docs-only" in content

    def test_phase_class_pre_pr_written_to_frontmatter(
        self, tmp_path: pathlib.Path
    ) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Pre-PR Phase",
                "--goal", "",
                "--phase-class", "pre-pr",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "phase_class: pre-pr" in content

    def test_phase_class_absent_when_omitted(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Normal Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert "phase_class" not in content

    def test_phase_class_invalid_value_rejected(self, tmp_path: pathlib.Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            phase_new,
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Bad Phase",
                "--goal", "",
                "--phase-class", "invalid-class",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code != 0

    def test_phase_class_with_era_both_in_frontmatter(
        self, tmp_path: pathlib.Path
    ) -> None:
        eras_dir = tmp_path / "docs" / "eras"
        _write_era(eras_dir, "001-foundation.md", ERA_ACTIVE_CONTENT)

        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Mixed Phase",
                "--goal", "",
                "--phase-class", "production",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert 'era: "001"' in content
        assert "phase_class: production" in content
        # Both should be inside the frontmatter block
        assert content.startswith("---")

    def test_phase_class_frontmatter_block_present_without_era(
        self, tmp_path: pathlib.Path
    ) -> None:
        """phase_class alone creates a frontmatter block even when no era exists."""
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Class Only",
                "--goal", "",
                "--phase-class", "docs-only",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-1.md").read_text()
        assert content.startswith("---")
        assert "phase_class: docs-only" in content


class TestPhaseClassValidation:
    """validate_phase_manifest() accepts and rejects phase_class values."""

    def _write_phase_file(
        self,
        path: pathlib.Path,
        era: str = "001",
        phase_class: str | None = None,
    ) -> pathlib.Path:
        lines = ["---", f'era: "{era}"']
        if phase_class is not None:
            lines.append(f"phase_class: {phase_class}")
        lines += ["---", "", "# Phase content"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_valid_production_class_passes(self, tmp_path: pathlib.Path) -> None:
        f = self._write_phase_file(tmp_path / "phase-1.md", phase_class="production")
        errors = validate_phase_manifest(f)
        assert errors == []

    def test_valid_docs_only_class_passes(self, tmp_path: pathlib.Path) -> None:
        f = self._write_phase_file(tmp_path / "phase-1.md", phase_class="docs-only")
        errors = validate_phase_manifest(f)
        assert errors == []

    def test_valid_pre_pr_class_passes(self, tmp_path: pathlib.Path) -> None:
        f = self._write_phase_file(tmp_path / "phase-1.md", phase_class="pre-pr")
        errors = validate_phase_manifest(f)
        assert errors == []

    def test_absent_phase_class_passes(self, tmp_path: pathlib.Path) -> None:
        f = self._write_phase_file(tmp_path / "phase-1.md")
        errors = validate_phase_manifest(f)
        assert errors == []

    def test_invalid_phase_class_returns_error(self, tmp_path: pathlib.Path) -> None:
        f = self._write_phase_file(tmp_path / "phase-1.md", phase_class="unknown")
        errors = validate_phase_manifest(f)
        assert any("phase_class" in e for e in errors)
        assert any("unknown" in e for e in errors)

    def test_valid_phase_classes_constant(self) -> None:
        assert VALID_PHASE_CLASSES == {"production", "docs-only", "pre-pr"}

    def test_default_phase_class_constant(self) -> None:
        assert DEFAULT_PHASE_CLASS == "production"


# ---------------------------------------------------------------------------
# Tests: string phase-id and --suffix flag (INFRA-143)
# ---------------------------------------------------------------------------


class TestSuffixFlag:
    """--suffix produces phase-{id}-{suffix}.md with correct phase_key in content."""

    def test_suffix_produces_correct_filename(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "56",
                "--suffix", "main",
                "--title", "Main Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        phase_file = tmp_path / "docs" / "phases" / "phase-56-main.md"
        assert phase_file.exists(), f"Expected phase-56-main.md but got: {list((tmp_path / 'docs' / 'phases').iterdir())}"

    def test_suffix_phase_key_in_heading(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "56",
                "--suffix", "main",
                "--title", "Main Phase",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-56-main.md").read_text()
        assert "Phase 56-main" in content

    def test_suffix_index_row_uses_full_key(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "56",
                "--suffix", "main",
                "--title", "Main Phase",
                "--goal", "",
            ]
        )
        index_content = (tmp_path / "docs" / "phases" / "index.md").read_text()
        assert "56-main" in index_content
        assert "phase-56-main.md" in index_content

    def test_suffix_cp_checklist_uses_phase_key(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "56",
                "--suffix", "main",
                "--title", "Main Phase",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-56-main.md").read_text()
        assert "CP-56-main" in content


class TestStringPhaseId:
    """--phase-id accepts non-integer strings like PM025."""

    def test_string_id_produces_correct_filename(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "PM025",
                "--title", "PM Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        phase_file = tmp_path / "docs" / "phases" / "phase-PM025.md"
        assert phase_file.exists()

    def test_string_id_with_suffix_produces_correct_filename(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "PM025",
                "--suffix", "main",
                "--title", "PM Main Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        phase_file = tmp_path / "docs" / "phases" / "phase-PM025-main.md"
        assert phase_file.exists()

    def test_string_id_no_prev_phase_lookup(self, tmp_path: pathlib.Path) -> None:
        """String IDs must not attempt prev_phase lookup (no integer arithmetic)."""
        # Create a numeric phase file first to ensure any accidental lookup would find something
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Numeric Phase",
                "--goal", "",
            ]
        )
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "PM025",
                "--title", "String Phase",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-PM025.md").read_text()
        # No backward nav link to any phase file from a string ID
        assert "phase-1.md" not in content

    def test_string_id_index_row_uses_full_key(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "PM025",
                "--suffix", "main",
                "--title", "PM Main Phase",
                "--goal", "",
            ]
        )
        index_content = (tmp_path / "docs" / "phases" / "index.md").read_text()
        assert "PM025-main" in index_content
        assert "phase-PM025-main.md" in index_content


class TestIntegerIdBackwardsCompat:
    """Integer-style phase IDs continue to work exactly as before."""

    def test_integer_id_produces_phase_N_md(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "56",
                "--title", "Numeric Only",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "docs" / "phases" / "phase-56.md").exists()
        assert not (tmp_path / "docs" / "phases" / "phase-56-.md").exists()

    def test_integer_id_prev_phase_still_populated(self, tmp_path: pathlib.Path) -> None:
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Phase One",
                "--goal", "",
            ]
        )
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--title", "Phase Two",
                "--goal", "",
            ]
        )
        content = (tmp_path / "docs" / "phases" / "phase-2.md").read_text()
        assert "Phase One" in content or "phase-1.md" in content

    def test_integer_id_with_suffix_no_prev_phase(self, tmp_path: pathlib.Path) -> None:
        """Integer ID + suffix must not attempt prev_phase lookup."""
        invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "1",
                "--title", "Phase One",
                "--goal", "",
            ]
        )
        result = invoke(
            [
                "--project-dir", str(tmp_path),
                "--phase-id", "2",
                "--suffix", "main",
                "--title", "Phase Two Main",
                "--goal", "",
            ]
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "docs" / "phases" / "phase-2-main.md").read_text()
        # With suffix present, no prev_phase nav should be generated
        assert "phase-1.md" not in content


class TestAppendIndexRow:
    """_append_index_row uses full phase_key in the row and filename link."""

    def test_append_row_with_simple_key(self, tmp_path: pathlib.Path) -> None:
        index_path = tmp_path / "index.md"
        _create_index(index_path, phase_key="1", phase_title="First Phase")
        _append_index_row(index_path, phase_key="PM025-main", phase_title="PM Main")
        content = index_path.read_text()
        assert "PM025-main" in content
        assert "phase-PM025-main.md" in content

    def test_append_row_integer_key(self, tmp_path: pathlib.Path) -> None:
        index_path = tmp_path / "index.md"
        _create_index(index_path, phase_key="1", phase_title="First Phase")
        _append_index_row(index_path, phase_key="2", phase_title="Second Phase")
        content = index_path.read_text()
        assert "phase-2.md" in content

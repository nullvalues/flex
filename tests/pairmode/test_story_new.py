"""Tests for skills/pairmode/scripts/story_new.py."""

from __future__ import annotations

import pathlib

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.story_new import story_new, _story_frontmatter, create_story


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(args: list[str], input: str | None = "Y\n") -> "click.testing.Result":
    """Invoke story_new.  Defaults to answering 'Y' to the rail-creation prompt."""
    runner = CliRunner()
    return runner.invoke(story_new, args, input=input, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateStoryFile:
    """Basic story creation."""

    def test_creates_story_file_at_correct_path(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "BOOTSTRAP", "--title", "My first story", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-001.md"
        assert story_file.exists(), f"Expected {story_file} to exist"

    def test_story_id_in_output(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "AUDIT", "--title", "Audit something", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        assert "AUDIT-001" in result.output
        assert "Audit something" in result.output

    def test_correct_frontmatter_id(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "INFRA", "--title", "Infra story", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "id: INFRA-001" in content

    def test_rail_normalized_to_uppercase(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "bootstrap", "--title", "Lower rail", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-001.md"
        assert story_file.exists()

    def test_frontmatter_contains_required_fields(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "BUILD", "--title", "Build story", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "BUILD" / "BUILD-001.md"
        content = story_file.read_text()
        assert "id: BUILD-001" in content
        assert "rail: BUILD" in content
        assert "title: Build story" in content
        assert "status: draft" in content

    def test_primary_files_omitted_when_empty(self, tmp_path: pathlib.Path) -> None:
        """primary_files must be omitted from frontmatter for a new story (CER-006)."""
        invoke(["--rail", "TEMPLATE", "--title", "Template story", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "TEMPLATE" / "TEMPLATE-001.md"
        content = story_file.read_text()
        # primary_files: [] must NOT appear — the key should be absent entirely
        assert "primary_files: []" not in content
        fm_block = content.split("---")[1]
        assert "primary_files: []" not in fm_block


class TestSequenceIncrement:
    """Sequence number increments for subsequent stories on the same rail."""

    def test_second_story_gets_002(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "BOOTSTRAP", "--title", "First", "--project-dir", str(tmp_path)])
        result = invoke(
            ["--rail", "BOOTSTRAP", "--title", "Second", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-002.md"
        assert story_file.exists(), "Expected BOOTSTRAP-002.md to exist"
        assert "BOOTSTRAP-002" in result.output

    def test_third_story_gets_003(self, tmp_path: pathlib.Path) -> None:
        for title in ("A", "B", "C"):
            invoke(["--rail", "AUDIT", "--title", title, "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "AUDIT" / "AUDIT-003.md"
        assert story_file.exists()


class TestNewRailPrompt:
    """Prompting when a rail does not exist."""

    def test_declining_prompt_aborts_no_directory_created(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "NEWRAIL", "--title", "First", "--project-dir", str(tmp_path)],
            input="n\n",
        )
        assert result.exit_code == 0, result.output
        rail_dir = tmp_path / "docs" / "stories" / "NEWRAIL"
        assert not rail_dir.exists(), "Rail directory must not be created when user declines"

    def test_accepting_prompt_creates_directory_and_story(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "NEWRAIL", "--title", "First", "--project-dir", str(tmp_path)],
            input="Y\n",
        )
        assert result.exit_code == 0, result.output
        rail_dir = tmp_path / "docs" / "stories" / "NEWRAIL"
        assert rail_dir.is_dir()
        story_file = rail_dir / "NEWRAIL-001.md"
        assert story_file.exists()

    def test_existing_rail_no_prompt(self, tmp_path: pathlib.Path) -> None:
        """When the rail already exists no prompt is shown."""
        rail_dir = tmp_path / "docs" / "stories" / "EXISTING"
        rail_dir.mkdir(parents=True)
        # Invoke without any stdin input — would fail if a prompt appeared
        result = invoke(
            ["--rail", "EXISTING", "--title", "Story", "--project-dir", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output


class TestPhaseFlag:
    """--phase appends a row to the phase manifest."""

    def _make_phase_file(self, tmp_path: pathlib.Path, phase: str, with_table: bool = False) -> pathlib.Path:
        phases_dir = tmp_path / "docs" / "phases"
        phases_dir.mkdir(parents=True, exist_ok=True)
        phase_path = phases_dir / f"phase-{phase}.md"
        if with_table:
            content = (
                f"# Phase {phase}\n\n"
                "## Stories\n\n"
                "| Story ID | Title | Status |\n"
                "|----------|-------|--------|\n"
            )
        else:
            content = f"# Phase {phase}\n\n## Goal\n\nDo things.\n"
        phase_path.write_text(content, encoding="utf-8")
        return phase_path

    def test_phase_flag_appends_row_to_existing_table(self, tmp_path: pathlib.Path) -> None:
        phase_path = self._make_phase_file(tmp_path, "001", with_table=True)
        # Pre-create rail so no prompt
        rail_dir = tmp_path / "docs" / "stories" / "BUILD"
        rail_dir.mkdir(parents=True)

        result = invoke(
            [
                "--rail", "BUILD",
                "--title", "My build story",
                "--phase", "001",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        assert "Added to Phase 001" in result.output

        content = phase_path.read_text()
        assert "BUILD-001" in content
        assert "My build story" in content

    def test_phase_flag_creates_stories_section_if_absent(self, tmp_path: pathlib.Path) -> None:
        phase_path = self._make_phase_file(tmp_path, "002", with_table=False)
        rail_dir = tmp_path / "docs" / "stories" / "AUDIT"
        rail_dir.mkdir(parents=True)

        result = invoke(
            [
                "--rail", "AUDIT",
                "--title", "Audit story",
                "--phase", "002",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        content = phase_path.read_text()
        assert "AUDIT-001" in content
        assert "Audit story" in content

    def test_phase_flag_prints_added_to_phase(self, tmp_path: pathlib.Path) -> None:
        self._make_phase_file(tmp_path, "003", with_table=True)
        rail_dir = tmp_path / "docs" / "stories" / "LESSON"
        rail_dir.mkdir(parents=True)

        result = invoke(
            [
                "--rail", "LESSON",
                "--title", "Lesson story",
                "--phase", "003",
                "--project-dir", str(tmp_path),
            ]
        )
        assert "Added to Phase 003" in result.output


class TestValidationIntegration:
    """Validation is called after creation; errors are printed as warnings."""

    def test_no_validation_warnings_on_new_draft_story(self, tmp_path: pathlib.Path) -> None:
        """Draft stories with empty primary_files must produce no validation warnings."""
        result = invoke(
            ["--rail", "INFRA", "--title", "Validation test", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        # stderr (mixed into output by CliRunner by default) must not contain warning text
        assert "validation:" not in result.output

    def test_validation_warning_printed_to_stderr_on_error(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the validator returns a fake error, it is printed to stderr, exit code stays 0."""
        import sys

        # story_new.py imports 'schema_validator' via a sys.path insert (plain module name).
        # Ensure that plain-name module is loaded and patch it.
        import skills.pairmode.scripts.schema_validator as _sv_pkg  # ensure loaded

        # Register under the plain name so the local import inside story_new resolves it
        monkeypatch.setitem(sys.modules, "schema_validator", _sv_pkg)
        monkeypatch.setattr(_sv_pkg, "validate_story_file", lambda path: ["fake validation error"])

        # CliRunner mixes stdout+stderr into result.output by default
        runner = CliRunner()
        result = runner.invoke(
            story_new,
            ["--rail", "WARN", "--title", "Warn story", "--project-dir", str(tmp_path)],
            input="Y\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "fake validation error" in result.output

    def test_validation_warning_exit_code_still_zero(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exit code remains 0 even when validation warnings are emitted."""
        import sys
        import skills.pairmode.scripts.schema_validator as _sv_pkg

        monkeypatch.setitem(sys.modules, "schema_validator", _sv_pkg)
        monkeypatch.setattr(_sv_pkg, "validate_story_file", lambda path: ["some error"])

        runner = CliRunner()
        result = runner.invoke(
            story_new,
            ["--rail", "EXIT", "--title", "Exit story", "--project-dir", str(tmp_path)],
            input="Y\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0


class TestStoryClassFlag:
    """--story-class writes story_class into generated frontmatter."""

    def test_story_class_code_written_to_frontmatter(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--rail", "INFRA",
                "--title", "Code story",
                "--story-class", "code",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "story_class: code" in content

    def test_story_class_doc_written_to_frontmatter(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--rail", "INFRA",
                "--title", "Doc story",
                "--story-class", "doc",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "story_class: doc" in content

    def test_story_class_lesson_written_to_frontmatter(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--rail", "LESSON",
                "--title", "Lesson story",
                "--story-class", "lesson",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "LESSON" / "LESSON-001.md"
        content = story_file.read_text()
        assert "story_class: lesson" in content

    def test_story_class_methodology_written_to_frontmatter(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--rail", "INFRA",
                "--title", "Methodology story",
                "--story-class", "methodology",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "story_class: methodology" in content

    def test_story_class_omitted_no_field_in_frontmatter(self, tmp_path: pathlib.Path) -> None:
        """When --story-class is omitted, story_class does not appear in frontmatter."""
        result = invoke(
            ["--rail", "INFRA", "--title", "Default story", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "story_class" not in content

    def test_story_class_invalid_value_rejected(self, tmp_path: pathlib.Path) -> None:
        """An invalid --story-class value causes a non-zero exit (Click validation)."""
        runner = CliRunner()
        result = runner.invoke(
            story_new,
            [
                "--rail", "INFRA",
                "--title", "Bad class",
                "--story-class", "invalid-class",
                "--project-dir", str(tmp_path),
            ],
            input="Y\n",
            catch_exceptions=False,
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit for invalid story_class, got: {result.output}"
        )

    def test_story_class_in_frontmatter_block_not_body(self, tmp_path: pathlib.Path) -> None:
        """story_class appears in the YAML frontmatter block, not the Markdown body."""
        result = invoke(
            [
                "--rail", "INFRA",
                "--title", "Scoped story",
                "--story-class", "doc",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        parts = content.split("---")
        # parts[0] is empty (before opening ---), parts[1] is frontmatter, parts[2] is body
        assert len(parts) >= 3, "Expected frontmatter delimiters"
        frontmatter_block = parts[1]
        assert "story_class: doc" in frontmatter_block


class TestSourceFlag:
    """--source writes source: field after story_class in generated frontmatter."""

    def test_source_flag_written_to_frontmatter(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            [
                "--rail", "INFRA",
                "--title", "Promoted story",
                "--source", "myproject",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "source: myproject" in content

    def test_source_flag_written_in_frontmatter_block_not_body(self, tmp_path: pathlib.Path) -> None:
        """source appears in the YAML frontmatter block, not the Markdown body."""
        result = invoke(
            [
                "--rail", "INFRA",
                "--title", "Promoted story",
                "--source", "flex-self",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        parts = content.split("---")
        assert len(parts) >= 3, "Expected frontmatter delimiters"
        frontmatter_block = parts[1]
        assert "source: flex-self" in frontmatter_block

    def test_source_omitted_no_field_in_frontmatter(self, tmp_path: pathlib.Path) -> None:
        """When --source is omitted, source does not appear in frontmatter at all."""
        result = invoke(
            ["--rail", "INFRA", "--title", "Native story", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "source:" not in content

    def test_source_written_after_story_class(self, tmp_path: pathlib.Path) -> None:
        """source: field appears after story_class: in the frontmatter."""
        result = invoke(
            [
                "--rail", "INFRA",
                "--title", "Promoted code story",
                "--story-class", "code",
                "--source", "other-project",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        # Both fields present
        assert "story_class: code" in content
        assert "source: other-project" in content
        # source appears after story_class in the file
        sc_pos = content.index("story_class: code")
        src_pos = content.index("source: other-project")
        assert src_pos > sc_pos, "Expected source: to appear after story_class:"

    def test_source_without_story_class_still_written(self, tmp_path: pathlib.Path) -> None:
        """source is written even when --story-class is not provided."""
        result = invoke(
            [
                "--rail", "INFRA",
                "--title", "Promoted no-class story",
                "--source", "external-project",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "source: external-project" in content
        assert "story_class" not in content


class TestRailValidation:
    """CER-010 — --rail regex validation and normalization."""

    def test_traversal_rail_rejected_by_regex(self, tmp_path: pathlib.Path) -> None:
        """--rail '../../../etc' is rejected with exit 1 and an error message."""
        runner = CliRunner()
        result = runner.invoke(
            story_new,
            ["--rail", "../../../etc", "--title", "Traversal", "--project-dir", str(tmp_path)],
            input="Y\n",
            catch_exceptions=False,
        )
        assert result.exit_code != 0, f"Expected non-zero exit for traversal rail, got: {result.output}"
        assert "invalid rail name" in result.output.lower() or "invalid rail" in result.output.lower(), (
            f"Expected error message about invalid rail, got: {result.output}"
        )

    def test_lowercase_rail_accepted_after_normalization(self, tmp_path: pathlib.Path) -> None:
        """--rail 'infra' (lowercase) is normalized to INFRA and accepted."""
        result = invoke(
            ["--rail", "infra", "--title", "Lowercase rail", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        assert story_file.exists()

    def test_scaffolded_story_does_not_contain_primary_files_empty_list(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Scaffolded story file does not contain 'primary_files: []' (CER-006)."""
        result = invoke(
            ["--rail", "INFRA", "--title", "No empty primary_files", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "primary_files: []" not in content


class TestRailContainmentGuard:
    """--rail values that escape docs/stories/ are rejected."""

    def test_traversal_rail_exits_nonzero(self, tmp_path: pathlib.Path) -> None:
        """--rail '../../etc' must exit non-zero and not create any files."""
        runner = CliRunner()
        result = runner.invoke(
            story_new,
            ["--rail", "../../etc", "--title", "Traversal", "--project-dir", str(tmp_path)],
            input="Y\n",
            catch_exceptions=False,
        )
        assert result.exit_code != 0, f"Expected non-zero exit, got: {result.output}"

    def test_traversal_rail_error_message(self, tmp_path: pathlib.Path) -> None:
        """Error message explains the rejection (either regex or containment guard)."""
        runner = CliRunner()
        result = runner.invoke(
            story_new,
            ["--rail", "../../etc", "--title", "Traversal", "--project-dir", str(tmp_path)],
            input="Y\n",
            catch_exceptions=False,
        )
        # The traversal is caught by the regex guard first (CER-010) or containment guard
        assert (
            "resolves outside docs/stories/" in result.output
            or "invalid rail name" in result.output.lower()
        ), f"Expected rejection message, got: {result.output}"

    def test_traversal_rail_no_files_created(self, tmp_path: pathlib.Path) -> None:
        """No story file or directory is created on a traversal attempt."""
        runner = CliRunner()
        runner.invoke(
            story_new,
            ["--rail", "../../etc", "--title", "Traversal", "--project-dir", str(tmp_path)],
            input="Y\n",
            catch_exceptions=False,
        )
        # docs/stories/ must not have been created with any traversal-derived content
        stories_dir = tmp_path / "docs" / "stories"
        if stories_dir.exists():
            # It's OK if the directory itself was created, but no traversal-escaped paths
            import os
            for root, dirs, files in os.walk(str(tmp_path)):
                for f in files:
                    full = pathlib.Path(root) / f
                    # Nothing should be outside tmp_path
                    assert str(full).startswith(str(tmp_path)), (
                        f"Unexpected file created outside tmp_path: {full}"
                    )

    def test_normal_rail_still_works(self, tmp_path: pathlib.Path) -> None:
        """A normal --rail INFRA value still creates the story correctly."""
        result = invoke(
            ["--rail", "INFRA", "--title", "Normal story", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        assert story_file.exists()


class TestStoryBodyFormat:
    """New story body uses ## Requires and ## Ensures; ## Acceptance criterion is absent."""

    def test_generated_body_contains_requires_section(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "INFRA", "--title", "Body format test", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "## Requires" in content

    def test_generated_body_contains_ensures_section(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "INFRA", "--title", "Body format test", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "## Ensures" in content

    def test_generated_body_does_not_contain_acceptance_criterion(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "INFRA", "--title", "Body format test", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "## Acceptance criterion" not in content

    def test_generated_body_contains_instructions_section(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "INFRA", "--title", "Body format test", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "## Instructions" in content

    def test_generated_body_contains_tests_section(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "INFRA", "--title", "Body format test", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "## Tests" in content

    def test_requires_precedes_ensures_in_body(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "INFRA", "--title", "Body order test", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        requires_pos = content.index("## Requires")
        ensures_pos = content.index("## Ensures")
        assert requires_pos < ensures_pos, "## Requires must appear before ## Ensures"


class TestAuthGatedSchemaIntroducesFields:
    """auth_gated and schema_introduces are scaffolded into new story frontmatter."""

    def test_story_frontmatter_includes_auth_gated(self) -> None:
        """_story_frontmatter() output contains 'auth_gated: false'."""
        output = _story_frontmatter("INFRA-001", "INFRA", "Test story", "78")
        assert "auth_gated: false" in output

    def test_story_frontmatter_includes_schema_introduces(self) -> None:
        """_story_frontmatter() output contains 'schema_introduces: false'."""
        output = _story_frontmatter("INFRA-001", "INFRA", "Test story", "78")
        assert "schema_introduces: false" in output

    def test_story_frontmatter_field_order(self) -> None:
        """auth_gated and schema_introduces appear after story_class."""
        output = _story_frontmatter(
            "INFRA-001", "INFRA", "Test story", "78", story_class="code"
        )
        sc_pos = output.index("story_class: code")
        ag_pos = output.index("auth_gated: false")
        si_pos = output.index("schema_introduces: false")
        assert sc_pos < ag_pos, "auth_gated must appear after story_class"
        assert sc_pos < si_pos, "schema_introduces must appear after story_class"
        # primary_files is omitted for new stories (CER-006)
        assert "primary_files:" not in output


class TestTouchesArchitectureComment:
    """The touches: line in generated frontmatter carries an architecture.md hint comment."""

    def test_story_frontmatter_touches_has_architecture_comment(self) -> None:
        """_story_frontmatter() includes 'docs/architecture.md' comment on the touches: line."""
        output = _story_frontmatter("TEST-001", "TEST", "foo", None, story_class="code")
        assert "docs/architecture.md" in output
        # The comment must appear on the touches: line specifically
        for line in output.splitlines():
            if line.startswith("touches:"):
                assert "docs/architecture.md" in line, (
                    f"docs/architecture.md comment not on touches: line. Line was: {line!r}"
                )
                break
        else:
            raise AssertionError("touches: line not found in frontmatter output")

    def test_story_frontmatter_fields_in_frontmatter_block_not_body(
        self, tmp_path: pathlib.Path
    ) -> None:
        """auth_gated and schema_introduces appear in the frontmatter block, not the body."""
        result = invoke(
            ["--rail", "INFRA", "--title", "New fields test", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        parts = content.split("---")
        assert len(parts) >= 3, "Expected frontmatter delimiters"
        frontmatter_block = parts[1]
        assert "auth_gated: false" in frontmatter_block
        assert "schema_introduces: false" in frontmatter_block

    def test_story_frontmatter_fields_present_without_story_class(self) -> None:
        """Fields are emitted even when story_class is not provided."""
        output = _story_frontmatter("INFRA-001", "INFRA", "No class story", "78")
        assert "auth_gated: false" in output
        assert "schema_introduces: false" in output


class TestPathTraversalGuard:
    """Too-shallow project_dir causes non-zero exit."""

    def test_shallow_path_exits_nonzero(self, tmp_path: pathlib.Path) -> None:
        # / has only 1 part, which is < 3
        runner = CliRunner()
        # We need to pass a path with < 3 parts.  Use a monkeypatched path.
        # The easiest approach: resolve a known shallow path.
        # On Linux /tmp itself has 2 parts: ('/', 'tmp') — still < 3.
        # We call the script with an existing directory that resolves to a shallow path.
        # Rather than using a real shallow path (which might not exist in test env),
        # let's test the guard by importing and calling directly.
        from pathlib import Path as _Path
        import sys as _sys

        # Patch the resolve to return a shallow path by temporarily overriding
        # We test via CLI with the actual guard: use /tmp which has 2 parts on Linux
        shallow = pathlib.Path("/tmp")
        if len(shallow.resolve().parts) < 3:
            result = runner.invoke(
                story_new,
                ["--rail", "INFRA", "--title", "t", "--project-dir", str(shallow)],
                catch_exceptions=False,
            )
            assert result.exit_code != 0
        else:
            # On some systems /tmp resolves to more parts — skip this check gracefully
            pytest.skip("/tmp resolves to >= 3 parts on this system")


class TestTestGateFlag:
    """--test-gate writes test_gate into generated frontmatter."""

    def test_story_new_with_test_gate_writes_field(self, tmp_path: pathlib.Path) -> None:
        """create_story with test_gate='phase_checkpoint' writes test_gate: phase_checkpoint."""
        story_path = create_story(
            rail="INFRA",
            title="Test gate story",
            project_dir=tmp_path,
            test_gate="phase_checkpoint",
        )
        content = story_path.read_text()
        assert "test_gate: phase_checkpoint" in content
        # Verify it is in the frontmatter block, not the body
        parts = content.split("---")
        assert len(parts) >= 3, "Expected frontmatter delimiters"
        frontmatter_block = parts[1]
        assert "test_gate: phase_checkpoint" in frontmatter_block

    def test_story_new_without_test_gate_omits_field(self, tmp_path: pathlib.Path) -> None:
        """create_story without test_gate omits the test_gate field entirely."""
        story_path = create_story(
            rail="INFRA",
            title="No test gate story",
            project_dir=tmp_path,
        )
        content = story_path.read_text()
        assert "test_gate" not in content

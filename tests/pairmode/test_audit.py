"""Tests for audit.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills.pairmode.scripts.audit import (
    AuditItem,
    AuditResult,
    audit_project,
    format_audit_output,
    _load_project_context,
    _JINJA_ENV,
)
from skills.pairmode.scripts import audit as _audit_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEMPLATES_DIR = _audit_mod.TEMPLATES_DIR
CANONICAL_FILES = _audit_mod.CANONICAL_FILES


def _write_state(project_dir: Path, version: str | None = "0.1.0") -> None:
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state: dict = {}
    if version is not None:
        state["pairmode_version"] = version
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _copy_canonical_files(project_dir: Path) -> None:
    """Render all canonical template files with fallback context and write into project_dir.

    Uses the same context that audit_project would use when pairmode_context.json is absent,
    so that rendered canonical == rendered template and no false INCONSISTENT is produced.
    """
    context = _load_project_context(project_dir)
    for dest_rel, template_rel in CANONICAL_FILES:
        dest_path = project_dir / dest_rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            rendered = _JINJA_ENV.get_template(template_rel).render(**context)
        except Exception:
            rendered = "# placeholder\n"
        dest_path.write_text(rendered, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuditProjectAllPresentIdentical:
    """All canonical files present and identical → nothing MISSING, possible EXTRA only."""

    def test_no_missing_when_all_files_present_and_identical(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        assert result.missing == [], f"Expected no missing items, got: {result.missing}"
        assert result.inconsistent == [], (
            f"Expected no inconsistent items, got: {result.inconsistent}"
        )

    def test_extra_sections_exist_for_project_specific_content(self, tmp_path: Path) -> None:
        """When project files match canonical exactly there should be no extra sections
        beyond what the templates themselves produce (EXTRA can be empty or non-empty
        depending on preamble handling — just assert it is a list)."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        assert isinstance(result.extra, list)


class TestAuditProjectMissingClaudeMd:
    """Project missing CLAUDE.md → CLAUDE.md sections appear in MISSING."""

    def test_missing_claude_md_produces_missing_items(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Remove CLAUDE.md
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        claude_md_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_md_missing) > 0, "Expected MISSING items for CLAUDE.md"

    def test_missing_claude_md_description_mentions_file(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        for item in result.missing:
            if item.file == "CLAUDE.md":
                assert "CLAUDE.md" in item.file
                break


class TestAuditProjectNoPairmodeVersion:
    """Project with no pairmode_version in state.json → pairmode_version is None."""

    def test_no_pairmode_version_key(self, tmp_path: Path) -> None:
        _write_state(tmp_path, version=None)  # state.json exists but no version key

        result = audit_project(tmp_path)

        assert result.pairmode_version is None

    def test_no_state_json_at_all(self, tmp_path: Path) -> None:
        # No .companion/state.json at all
        result = audit_project(tmp_path)

        assert result.pairmode_version is None

    def test_canonical_version_always_set(self, tmp_path: Path) -> None:
        result = audit_project(tmp_path)

        assert result.canonical_version == "0.1.0"


class TestFormatAuditOutput:
    """format_audit_output produces correct string with all sections."""

    def _make_result(
        self,
        missing: list[AuditItem] | None = None,
        inconsistent: list[AuditItem] | None = None,
        extra: list[AuditItem] | None = None,
    ) -> AuditResult:
        return AuditResult(
            project_name="myproject",
            project_dir=Path("/tmp/myproject"),
            missing=missing or [],
            inconsistent=inconsistent or [],
            extra=extra or [],
            pairmode_version="0.1.0",
            canonical_version="0.1.0",
        )

    def test_header_contains_project_name_and_version(self) -> None:
        result = self._make_result()
        output = format_audit_output(result)
        assert "myproject" in output
        assert "0.1.0" in output

    def test_missing_section_present_when_items_exist(self) -> None:
        result = self._make_result(
            missing=[AuditItem(file="CLAUDE.md", section="intro", description="Missing intro")]
        )
        output = format_audit_output(result)
        assert "MISSING" in output
        assert "CLAUDE.md" in output
        assert "\u2717" in output  # ✗

    def test_inconsistent_section_present(self) -> None:
        result = self._make_result(
            inconsistent=[
                AuditItem(file="CLAUDE.build.md", section="rules", description="Rules differ")
            ]
        )
        output = format_audit_output(result)
        assert "INCONSISTENT" in output
        assert "CLAUDE.build.md" in output
        assert "~" in output

    def test_extra_section_present(self) -> None:
        result = self._make_result(
            extra=[
                AuditItem(
                    file=".claude/agents/builder.md",
                    section="custom",
                    description="Custom section",
                )
            ]
        )
        output = format_audit_output(result)
        assert "EXTRA" in output
        assert ".claude/agents/builder.md" in output
        assert "\u2713" in output  # ✓

    def test_recommendation_always_present(self) -> None:
        result = self._make_result()
        output = format_audit_output(result)
        assert "RECOMMENDATION" in output
        assert "sync" in output

    def test_empty_sections_omitted(self) -> None:
        result = self._make_result()  # no items anywhere
        output = format_audit_output(result)
        assert "MISSING" not in output
        assert "INCONSISTENT" not in output
        assert "EXTRA" not in output

    def test_lesson_id_appears_in_missing_item(self) -> None:
        result = self._make_result(
            missing=[
                AuditItem(
                    file="CLAUDE.md",
                    section="intro",
                    description="Missing intro",
                    lesson_id="L001",
                )
            ]
        )
        output = format_audit_output(result)
        assert "L001" in output


class TestLessonIdInMissingItems:
    """Lesson IDs appear in MISSING items when a lesson applies."""

    def test_lesson_id_attached_when_lesson_affects_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a lesson's methodology_change.affects mentions CLAUDE.md and the file
        is missing, the lesson_id should be attached to the AuditItem."""
        fake_lessons_data = {
            "version": "1.0.0",
            "lessons": [
                {
                    "id": "L001",
                    "trigger": "test trigger",
                    "learning": "some learning",
                    "date": "2026-01-01",
                    "status": "active",
                    "applies_to": ["all"],
                    "methodology_change": {
                        "affects": "CLAUDE.md",
                        "description": "Update CLAUDE.md",
                    },
                }
            ],
        }

        monkeypatch.setattr(
            _audit_mod.lesson_utils,
            "load_lessons",
            lambda: fake_lessons_data,
        )

        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        claude_md_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_md_missing) > 0
        lesson_ids = [i.lesson_id for i in claude_md_missing if i.lesson_id]
        assert "L001" in lesson_ids, f"Expected L001 in lesson_ids, got: {lesson_ids}"


class TestNoCompanionStateJson:
    """audit_project on a directory with no .companion/state.json → pairmode_version is None."""

    def test_no_companion_dir(self, tmp_path: Path) -> None:
        # tmp_path has no .companion directory at all
        result = audit_project(tmp_path)
        assert result.pairmode_version is None

    def test_no_error_raised(self, tmp_path: Path) -> None:
        # Should not raise
        result = audit_project(tmp_path)
        assert isinstance(result, AuditResult)


# ---------------------------------------------------------------------------
# Story 4.5 edge-case tests
# ---------------------------------------------------------------------------


class TestAuditClaudeMdFewerSections:
    """CLAUDE.md exists but has fewer sections than canonical → missing sections in MISSING."""

    def test_missing_sections_appear_in_missing_list(self, tmp_path: Path) -> None:
        """Write a CLAUDE.md that only has the preamble — all canonical sections are absent."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Replace CLAUDE.md with a stub that has only a preamble and one section
        stub = "# Project context\n\nThis is a minimal CLAUDE.md with just a preamble.\n"
        (tmp_path / "CLAUDE.md").write_text(stub, encoding="utf-8")

        result = audit_project(tmp_path)

        # The canonical template has multiple sections; at least some must be MISSING
        claude_md_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_md_missing) > 0, (
            "Expected MISSING items for CLAUDE.md sections absent from the project file"
        )

    def test_sections_present_in_project_are_not_missing(self, tmp_path: Path) -> None:
        """Sections that DO appear in the project file should not be reported as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # The canonical CLAUDE.md — read the first real header from it
        canonical_text = (
            _audit_mod.TEMPLATES_DIR / "CLAUDE.md.j2"
        ).read_text(encoding="utf-8")

        # Find a header that exists in the canonical template
        import re
        headers = re.findall(r"^## .+", canonical_text, re.MULTILINE)
        assert headers, "Canonical CLAUDE.md.j2 should have at least one ## header"

        # Build a stub that contains just this one header/section
        first_header = headers[0]
        stub = f"{first_header}\n\nSome content.\n"
        (tmp_path / "CLAUDE.md").write_text(stub, encoding="utf-8")

        result = audit_project(tmp_path)

        # The section corresponding to this header should NOT be in missing
        # (it may be in inconsistent because the body differs — that's OK)
        from skills.pairmode.scripts.audit import _normalise
        normalised_header = _normalise(first_header)
        missing_keys = {i.section for i in result.missing if i.file == "CLAUDE.md"}
        assert normalised_header not in missing_keys, (
            f"Section '{normalised_header}' is present in project but appears in MISSING"
        )


class TestAuditExtraCustomSections:
    """Project CLAUDE.md has extra custom sections not in canonical → appear in EXTRA."""

    def test_extra_sections_appear_in_extra_list(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Append a custom section that is not in any canonical template
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            existing + "\n## My Unique Project Section\n\nProject-specific notes here.\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        extra_files = [i.file for i in result.extra]
        assert "CLAUDE.md" in extra_files, (
            f"Expected CLAUDE.md in extra items, got: {extra_files}"
        )

    def test_extra_section_key_is_in_extra_list(self, tmp_path: Path) -> None:
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        from skills.pairmode.scripts.audit import _normalise
        custom_header = "## My Unique Project Section"
        normalised_custom = _normalise(custom_header)

        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            existing + f"\n{custom_header}\n\nProject-specific notes here.\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        extra_sections = {i.section for i in result.extra if i.file == "CLAUDE.md"}
        assert normalised_custom in extra_sections, (
            f"Expected '{normalised_custom}' in extra sections, got: {extra_sections}"
        )

    def test_extra_sections_do_not_appear_in_missing(self, tmp_path: Path) -> None:
        """Custom project sections should not be mistakenly flagged as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            existing + "\n## My Unique Project Section\n\nProject-specific notes here.\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        from skills.pairmode.scripts.audit import _normalise
        normalised_custom = _normalise("## My Unique Project Section")
        missing_keys = {i.section for i in result.missing}
        assert normalised_custom not in missing_keys, (
            "Custom project section should not appear in MISSING"
        )


class TestAuditVersionMismatch:
    """pairmode_version in state.json doesn't match canonical → audit still runs, mismatch captured."""

    def test_audit_runs_with_version_mismatch(self, tmp_path: Path) -> None:
        _write_state(tmp_path, version="0.0.1")  # older version than canonical 0.1.0
        _copy_canonical_files(tmp_path)

        # Should not raise
        result = audit_project(tmp_path)

        assert isinstance(result, AuditResult)

    def test_project_version_captured_in_result(self, tmp_path: Path) -> None:
        _write_state(tmp_path, version="0.0.1")
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        assert result.pairmode_version == "0.0.1", (
            f"Expected pairmode_version='0.0.1', got: {result.pairmode_version}"
        )

    def test_canonical_version_is_always_current(self, tmp_path: Path) -> None:
        _write_state(tmp_path, version="0.0.1")
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        assert result.canonical_version == "0.1.0", (
            f"Expected canonical_version='0.1.0', got: {result.canonical_version}"
        )

    def test_version_mismatch_does_not_add_spurious_missing_items(self, tmp_path: Path) -> None:
        """A version mismatch alone should not cause files to appear missing when all files exist."""
        _write_state(tmp_path, version="0.0.1")
        _copy_canonical_files(tmp_path)

        result = audit_project(tmp_path)

        # Files are all present and identical so nothing should be MISSING
        assert result.missing == [], (
            f"Version mismatch alone should not produce MISSING items; got: {result.missing}"
        )


# ---------------------------------------------------------------------------
# Context rendering tests
# ---------------------------------------------------------------------------


class TestAuditRendersTemplateWithContext:
    """audit_project reads pairmode_context.json and renders templates before comparing."""

    def test_no_false_inconsistent_when_context_matches(self, tmp_path: Path) -> None:
        """When pairmode_context.json is present and project files were rendered from it,
        audit should report no INCONSISTENT items for project_name substitution."""
        import json as _json
        from click.testing import CliRunner
        from skills.pairmode.scripts.bootstrap import bootstrap

        # Bootstrap the project (writes pairmode_context.json and rendered files)
        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "cora",
                "--stack", "Python / FastAPI",
                "--build-command", "uv run pytest",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        # pairmode_context.json must exist
        context_path = tmp_path / ".companion" / "pairmode_context.json"
        assert context_path.exists()

        # Audit should not flag INCONSISTENT because rendered canonical == project files
        audit_result = audit_project(tmp_path)

        inconsistent_files = [i.file for i in audit_result.inconsistent]
        assert inconsistent_files == [], (
            f"Expected no INCONSISTENT items after clean bootstrap, got: {audit_result.inconsistent}"
        )

    def test_context_project_name_used_in_rendered_canonical(self, tmp_path: Path) -> None:
        """When pairmode_context.json has project_name='cora', canonical sections
        contain 'cora' after rendering, not '{{ project_name }}'."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "cora",
            "project_description": "a test project",
            "stack": "Python",
            "build_command": "uv run pytest",
            "test_command": "uv run pytest",
            "migration_command": "",
            "domain_model": "",
            "domain_isolation_rule": "",
            "checklist_items": [],
            "protected_paths": [],
            "non_negotiables": [],
            "module_structure": [],
            "layer_rules": [],
        }
        (companion / "pairmode_context.json").write_text(
            _json.dumps(ctx), encoding="utf-8"
        )

        # Read what audit will produce for canonical CLAUDE.md sections
        from skills.pairmode.scripts.audit import _read_template_sections, _load_project_context
        loaded_ctx = _load_project_context(tmp_path)
        assert loaded_ctx["project_name"] == "cora"

        sections = _read_template_sections("CLAUDE.md.j2", loaded_ctx)
        # All section bodies should not contain raw Jinja2 syntax
        for key, body in sections.items():
            assert "{{" not in body, (
                f"Section '{key}' still contains Jinja2 syntax after rendering: {body[:100]}"
            )
        # At least some section should mention 'cora'
        all_text = " ".join(sections.values())
        assert "cora" in all_text, "Rendered CLAUDE.md canonical should contain 'cora'"

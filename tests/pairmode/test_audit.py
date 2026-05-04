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
    _is_separator_key,
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
    Also creates Phase 7 existence-check files so they are not flagged as MISSING.
    """
    from skills.pairmode.scripts import audit as _audit_mod_inner

    context, _ = _load_project_context(project_dir)
    for dest_rel, template_rel in CANONICAL_FILES:
        dest_path = project_dir / dest_rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            rendered = _JINJA_ENV.get_template(template_rel).render(**context)
        except Exception:
            rendered = "# placeholder\n"
        dest_path.write_text(rendered, encoding="utf-8")

    # Also create Phase 7 existence-check files so they are not flagged MISSING
    for dest_rel, _template_rel, _desc in _audit_mod_inner.EXISTENCE_CHECK_FILES:
        dest_path = project_dir / dest_rel
        if not dest_path.exists():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text("# placeholder\n", encoding="utf-8")


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
        loaded_ctx, ctx_found = _load_project_context(tmp_path)
        assert ctx_found is True
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


# ---------------------------------------------------------------------------
# Story 6.1 — context_missing behaviour
# ---------------------------------------------------------------------------


class TestContextMissingFlag:
    """When pairmode_context.json is absent, context_missing=True and inconsistent is empty."""

    def test_context_missing_true_when_no_context_file(self, tmp_path: Path) -> None:
        """audit_project returns context_missing=True when pairmode_context.json is absent."""
        result = audit_project(tmp_path)
        assert result.context_missing is True

    def test_inconsistent_empty_when_context_missing(self, tmp_path: Path) -> None:
        """No INCONSISTENT items are produced when pairmode_context.json is absent."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Modify a canonical file so body differs — without context, this must not raise INCONSISTENT
        (tmp_path / "CLAUDE.md").write_text(
            "## Session modes\n\nDifferent content here.\n", encoding="utf-8"
        )

        result = audit_project(tmp_path)

        assert result.context_missing is True
        assert result.inconsistent == [], (
            f"Expected no INCONSISTENT when context is missing, got: {result.inconsistent}"
        )

    def test_context_missing_false_when_context_file_present(self, tmp_path: Path) -> None:
        """context_missing=False when pairmode_context.json is present and valid."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "testproject",
            "project_description": "",
            "stack": "",
            "build_command": "",
            "test_command": "",
            "migration_command": "",
            "domain_model": "",
            "domain_isolation_rule": "",
            "checklist_items": [],
            "protected_paths": [],
            "non_negotiables": [],
            "module_structure": [],
            "layer_rules": [],
        }
        (companion / "pairmode_context.json").write_text(_json.dumps(ctx), encoding="utf-8")

        result = audit_project(tmp_path)

        assert result.context_missing is False

    def test_missing_still_populated_when_context_missing(self, tmp_path: Path) -> None:
        """MISSING items are reported even when pairmode_context.json is absent."""
        # Remove CLAUDE.md so it counts as MISSING
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        assert result.context_missing is True
        claude_md_missing = [i for i in result.missing if i.file == "CLAUDE.md"]
        assert len(claude_md_missing) > 0, (
            "Expected MISSING items for CLAUDE.md even when context is absent"
        )

    def test_extra_still_populated_when_context_missing(self, tmp_path: Path) -> None:
        """EXTRA items are reported even when pairmode_context.json is absent."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Append a project-specific section
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(
            existing + "\n## My Unique Extra Section\n\nProject-specific.\n",
            encoding="utf-8",
        )

        result = audit_project(tmp_path)

        assert result.context_missing is True
        extra_files = [i.file for i in result.extra]
        assert "CLAUDE.md" in extra_files, (
            "Expected EXTRA items for CLAUDE.md even when context is absent"
        )


class TestFormatAuditOutputContextMissing:
    """format_audit_output emits warning when context_missing=True."""

    def _make_result_no_context(
        self,
        missing: list[AuditItem] | None = None,
        extra: list[AuditItem] | None = None,
    ) -> AuditResult:
        return AuditResult(
            project_name="myproject",
            project_dir=Path("/tmp/myproject"),
            missing=missing or [],
            inconsistent=[],
            extra=extra or [],
            pairmode_version="0.1.0",
            canonical_version="0.1.0",
            context_missing=True,
        )

    def test_warning_present_when_context_missing(self) -> None:
        result = self._make_result_no_context()
        output = format_audit_output(result)
        assert "WARNING: No pairmode_context.json found" in output

    def test_warning_mentions_inconsistent_disabled(self) -> None:
        result = self._make_result_no_context()
        output = format_audit_output(result)
        assert "INCONSISTENT comparison disabled" in output

    def test_warning_mentions_bootstrap(self) -> None:
        result = self._make_result_no_context()
        output = format_audit_output(result)
        assert "bootstrap" in output

    def test_inconsistent_section_absent_when_context_missing(self) -> None:
        result = self._make_result_no_context()
        output = format_audit_output(result)
        # The INCONSISTENT section header should not appear as a standalone line
        # (The warning itself contains the word INCONSISTENT, but the section header does not)
        lines = output.splitlines()
        assert "INCONSISTENT" not in lines, (
            "INCONSISTENT section header should not appear as a line when context is missing"
        )

    def test_missing_section_still_shown_when_context_missing(self) -> None:
        result = self._make_result_no_context(
            missing=[AuditItem(file="CLAUDE.md", section="intro", description="Missing")]
        )
        output = format_audit_output(result)
        assert "MISSING" in output
        assert "CLAUDE.md" in output

    def test_extra_section_still_shown_when_context_missing(self) -> None:
        result = self._make_result_no_context(
            extra=[AuditItem(file="CLAUDE.md", section="custom", description="Custom")]
        )
        output = format_audit_output(result)
        assert "EXTRA" in output
        assert "CLAUDE.md" in output

    def test_no_warning_when_context_present(self) -> None:
        result = AuditResult(
            project_name="myproject",
            project_dir=Path("/tmp/myproject"),
            context_missing=False,
        )
        output = format_audit_output(result)
        assert "WARNING: No pairmode_context.json found" not in output


# ---------------------------------------------------------------------------
# Story 6.2 — separator-key filtering
# ---------------------------------------------------------------------------


class TestIsSeparatorKey:
    """Unit tests for the _is_separator_key helper."""

    def test_plain_triple_dash_is_separator(self) -> None:
        assert _is_separator_key("---") is True

    def test_quad_dash_is_separator(self) -> None:
        assert _is_separator_key("----") is True

    def test_dash_with_suffix_zero_is_separator(self) -> None:
        assert _is_separator_key("---__0") is True

    def test_dash_with_suffix_one_is_separator(self) -> None:
        assert _is_separator_key("---__1") is True

    def test_section_header_is_not_separator(self) -> None:
        assert _is_separator_key("## session modes") is False

    def test_preamble_key_is_not_separator(self) -> None:
        assert _is_separator_key("__preamble__0") is False


class TestSeparatorKeysFilteredFromOutput:
    """Integration: separator-keyed sections never appear in MISSING, EXTRA, or INCONSISTENT."""

    def _make_project_with_separators(self, project_dir: Path) -> None:
        """Write a CLAUDE.md that contains --- separators between sections."""
        content = (
            "## Session modes\n\nSome content.\n\n"
            "---\n\n"
            "## Build rules\n\nOther content.\n"
        )
        (project_dir / "CLAUDE.md").write_text(content, encoding="utf-8")

    def test_separator_keys_not_in_inconsistent(self, tmp_path: Path) -> None:
        """Project file with --- separators must not produce INCONSISTENT items
        whose section key matches the separator pattern."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "testproject",
            "project_description": "",
            "stack": "",
            "build_command": "",
            "test_command": "",
            "migration_command": "",
            "domain_model": "",
            "domain_isolation_rule": "",
            "checklist_items": [],
            "protected_paths": [],
            "non_negotiables": [],
            "module_structure": [],
            "layer_rules": [],
        }
        (companion / "pairmode_context.json").write_text(_json.dumps(ctx), encoding="utf-8")

        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Append a separator to CLAUDE.md to simulate the pattern
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(existing + "\n---\n\nExtra text after separator.\n", encoding="utf-8")

        result = audit_project(tmp_path)

        separator_inconsistent = [
            i for i in result.inconsistent if _is_separator_key(i.section)
        ]
        assert separator_inconsistent == [], (
            f"Separator-keyed sections must not appear in INCONSISTENT: {separator_inconsistent}"
        )

    def test_separator_keys_not_in_missing(self, tmp_path: Path) -> None:
        """No MISSING item should have a separator-pattern section key."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        (tmp_path / "CLAUDE.md").unlink()

        result = audit_project(tmp_path)

        separator_missing = [i for i in result.missing if _is_separator_key(i.section)]
        assert separator_missing == [], (
            f"Separator-keyed sections must not appear in MISSING: {separator_missing}"
        )

    def test_separator_keys_not_in_extra(self, tmp_path: Path) -> None:
        """No EXTRA item should have a separator-pattern section key."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Append a raw --- separator to CLAUDE.md
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(existing + "\n---\n\nExtra text.\n", encoding="utf-8")

        result = audit_project(tmp_path)

        separator_extra = [i for i in result.extra if _is_separator_key(i.section)]
        assert separator_extra == [], (
            f"Separator-keyed sections must not appear in EXTRA: {separator_extra}"
        )

    def test_legitimate_section_differences_still_reported(self, tmp_path: Path) -> None:
        """A real ## section difference is still reported as INCONSISTENT
        even after the separator-key filter is applied."""
        import json as _json

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        ctx = {
            "project_name": "testproject",
            "project_description": "",
            "stack": "",
            "build_command": "",
            "test_command": "",
            "migration_command": "",
            "domain_model": "",
            "domain_isolation_rule": "",
            "checklist_items": [],
            "protected_paths": [],
            "non_negotiables": [],
            "module_structure": [],
            "layer_rules": [],
        }
        (companion / "pairmode_context.json").write_text(_json.dumps(ctx), encoding="utf-8")

        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Overwrite CLAUDE.md so that one real section body differs
        from skills.pairmode.scripts.audit import _normalise
        canonical_text = (
            _audit_mod.TEMPLATES_DIR / "CLAUDE.md.j2"
        ).read_text(encoding="utf-8")
        import re as _re
        headers = _re.findall(r"^## .+", canonical_text, _re.MULTILINE)
        assert headers, "CLAUDE.md.j2 must have at least one ## header"

        first_header = headers[0]
        # Write a version where the first section has completely different content
        claude_md = tmp_path / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8")
        # Replace content under the first header with something clearly different
        altered = _re.sub(
            rf"({_re.escape(first_header)}\n+)(.+?)(\n##|\Z)",
            lambda m: m.group(1) + "COMPLETELY DIFFERENT CONTENT\n" + m.group(3),
            existing,
            count=1,
            flags=_re.DOTALL,
        )
        claude_md.write_text(altered, encoding="utf-8")

        result = audit_project(tmp_path)

        # There should be at least one INCONSISTENT item for CLAUDE.md
        inconsistent_claude = [i for i in result.inconsistent if i.file == "CLAUDE.md"]
        assert len(inconsistent_claude) > 0, (
            "Expected INCONSISTENT items for modified CLAUDE.md section, got none"
        )


# ---------------------------------------------------------------------------
# Story 7.7 — Phase 7 file-existence checks
# ---------------------------------------------------------------------------


class TestAuditPhase7FileExistenceChecks:
    """audit_project reports MISSING for docs/brief.md, docs/phases/index.md,
    and docs/cer/backlog.md when absent."""

    def test_docs_brief_md_missing_when_absent(self, tmp_path: Path) -> None:
        """docs/brief.md absent → reported as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        # Remove the placeholder created by _copy_canonical_files to simulate absence
        brief = tmp_path / "docs" / "brief.md"
        if brief.exists():
            brief.unlink()

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/brief.md" in missing_files, (
            f"Expected docs/brief.md in missing files, got: {missing_files}"
        )

    def test_docs_phases_index_md_missing_when_absent(self, tmp_path: Path) -> None:
        """docs/phases/index.md absent → reported as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        index = tmp_path / "docs" / "phases" / "index.md"
        if index.exists():
            index.unlink()

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/phases/index.md" in missing_files, (
            f"Expected docs/phases/index.md in missing files, got: {missing_files}"
        )

    def test_docs_cer_backlog_md_missing_when_absent(self, tmp_path: Path) -> None:
        """docs/cer/backlog.md absent → reported as MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)
        backlog = tmp_path / "docs" / "cer" / "backlog.md"
        if backlog.exists():
            backlog.unlink()

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/cer/backlog.md" in missing_files, (
            f"Expected docs/cer/backlog.md in missing files, got: {missing_files}"
        )

    def test_no_missing_when_all_three_present(self, tmp_path: Path) -> None:
        """When all three Phase 7 files are present, none are reported MISSING."""
        _write_state(tmp_path)
        _copy_canonical_files(tmp_path)

        # Create the three Phase 7 files
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "brief.md").write_text("# Brief\n", encoding="utf-8")
        (tmp_path / "docs" / "phases").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "phases" / "index.md").write_text("# Index\n", encoding="utf-8")
        (tmp_path / "docs" / "cer").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "cer" / "backlog.md").write_text("# Backlog\n", encoding="utf-8")

        result = audit_project(tmp_path)

        missing_files = {i.file for i in result.missing}
        assert "docs/brief.md" not in missing_files, "docs/brief.md should not be MISSING"
        assert "docs/phases/index.md" not in missing_files, (
            "docs/phases/index.md should not be MISSING"
        )
        assert "docs/cer/backlog.md" not in missing_files, (
            "docs/cer/backlog.md should not be MISSING"
        )

"""Tests for _build_template_context and _render_build_template in pairmode_sync.py.

Verifies that:
- _build_template_context() returns a pairmode_scripts_dir key whose value is the
  absolute path to flex's scripts directory.
- The rendered build template contains no literal 'skills/pairmode/scripts' substrings
  and does contain the absolute scripts path.
"""

from __future__ import annotations

import json
import pathlib
import sys

# Add scripts dir for direct import
_SCRIPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from pairmode_sync import (  # noqa: E402
    _build_template_context,
    _merge_body_sections,
    _render_build_template,
    sync_agents,
)

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
EXPECTED_SCRIPTS_DIR = str(_REPO_ROOT / "skills" / "pairmode" / "scripts")


class TestBuildTemplateContext:
    """Tests for _build_template_context()."""

    def test_pairmode_scripts_dir_key_present(self, tmp_path: pathlib.Path) -> None:
        """_build_template_context must include pairmode_scripts_dir in its return value."""
        ctx = _build_template_context(tmp_path)
        assert "pairmode_scripts_dir" in ctx, (
            "pairmode_scripts_dir key missing from _build_template_context() return value"
        )

    def test_pairmode_scripts_dir_is_absolute(self, tmp_path: pathlib.Path) -> None:
        """pairmode_scripts_dir must be an absolute path."""
        ctx = _build_template_context(tmp_path)
        scripts_dir = ctx["pairmode_scripts_dir"]
        assert pathlib.Path(scripts_dir).is_absolute(), (
            f"pairmode_scripts_dir is not absolute: {scripts_dir!r}"
        )

    def test_pairmode_scripts_dir_ends_with_scripts_suffix(self, tmp_path: pathlib.Path) -> None:
        """pairmode_scripts_dir must end with 'skills/pairmode/scripts'."""
        ctx = _build_template_context(tmp_path)
        scripts_dir = ctx["pairmode_scripts_dir"]
        assert scripts_dir.endswith("skills/pairmode/scripts"), (
            f"pairmode_scripts_dir does not end with 'skills/pairmode/scripts': {scripts_dir!r}"
        )

    def test_domain_isolation_rule_from_pairmode_context(self, tmp_path: pathlib.Path) -> None:
        """_build_template_context returns domain_isolation_rule from pairmode_context.json."""
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        pairmode_ctx = {"domain_isolation_rule": "no raw SQL"}
        (companion_dir / "pairmode_context.json").write_text(
            json.dumps(pairmode_ctx), encoding="utf-8"
        )
        ctx = _build_template_context(tmp_path)
        assert ctx.get("domain_isolation_rule") == "no raw SQL", (
            f"Expected domain_isolation_rule='no raw SQL', got {ctx.get('domain_isolation_rule')!r}"
        )

    def test_protected_paths_from_pairmode_context(self, tmp_path: pathlib.Path) -> None:
        """_build_template_context returns protected_paths from pairmode_context.json."""
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        pairmode_ctx = {"protected_paths": ["src/core/"]}
        (companion_dir / "pairmode_context.json").write_text(
            json.dumps(pairmode_ctx), encoding="utf-8"
        )
        ctx = _build_template_context(tmp_path)
        assert ctx.get("protected_paths") == ["src/core/"], (
            f"Expected protected_paths=['src/core/'], got {ctx.get('protected_paths')!r}"
        )


class TestRenderBuildTemplate:
    """Tests for _render_build_template() with pairmode_scripts_dir in context."""

    def _make_context(self, project_dir: pathlib.Path) -> dict:
        return _build_template_context(project_dir)

    def test_rendered_template_has_no_relative_scripts_path(self, tmp_path: pathlib.Path) -> None:
        """The rendered build template must not contain the bare relative path 'skills/pairmode/scripts'.

        The absolute path (e.g. '/mnt/work/flex/skills/pairmode/scripts') is expected and
        acceptable — we only forbid the relative form that would break on non-/mnt/work/flex machines.
        """
        ctx = self._make_context(tmp_path)
        rendered = _render_build_template(ctx)
        # Check each line: a line containing 'skills/pairmode/scripts' must also contain
        # the absolute scripts dir (meaning it's the absolute form, not the bare relative form).
        absolute_scripts = ctx["pairmode_scripts_dir"]
        for lineno, line in enumerate(rendered.splitlines(), 1):
            if "skills/pairmode/scripts" in line and absolute_scripts not in line:
                raise AssertionError(
                    f"Line {lineno} contains bare relative path 'skills/pairmode/scripts' "
                    f"without the absolute prefix — template substitution incomplete:\n  {line}"
                )

    def test_rendered_template_contains_absolute_scripts_path(self, tmp_path: pathlib.Path) -> None:
        """The rendered build template must contain the absolute scripts directory path."""
        ctx = self._make_context(tmp_path)
        rendered = _render_build_template(ctx)
        expected = ctx["pairmode_scripts_dir"]
        assert expected in rendered, (
            f"Rendered CLAUDE.build.md does not contain the absolute scripts path {expected!r}."
        )


class TestMergeBodySections:
    """Tests for _merge_body_sections()."""

    def test_missing_template_section_is_appended(self) -> None:
        """Sections present in the template body but absent from the target are appended."""
        template_body = (
            "\n"
            "## Contract check\n"
            "\n"
            "Read the story spec's `## Ensures` section.\n"
        )
        target_body = (
            "\n"
            "You are the reviewer.\n"
            "\n"
            "## Review checklist\n"
            "\n"
            "Run every item.\n"
        )

        merged = _merge_body_sections(template_body, target_body)

        # The target's existing section must still be present
        assert "## Review checklist" in merged
        # The new section from the template must have been appended
        assert "## Contract check" in merged
        assert "Read the story spec" in merged

    def test_project_specific_section_preserved(self) -> None:
        """Target sections absent from the template are preserved in the merged result."""
        template_body = (
            "\n"
            "## Contract check\n"
            "\n"
            "Read the story spec's `## Ensures` section.\n"
        )
        target_body = (
            "\n"
            "## Contract check\n"
            "\n"
            "Read the story spec's `## Ensures` section.\n"
            "\n"
            "## Local overrides\n"
            "\n"
            "Project-specific instructions here.\n"
        )

        merged = _merge_body_sections(template_body, target_body)

        # The project-specific section must be preserved
        assert "## Local overrides" in merged
        assert "Project-specific instructions here." in merged
        # The shared section must still be present
        assert "## Contract check" in merged

    def test_existing_section_not_duplicated(self) -> None:
        """When the target already has a section matching a template section, it is not duplicated."""
        contract_check_content = "Read the story spec's `## Ensures` section.\n"
        template_body = f"\n## Contract check\n\n{contract_check_content}"
        target_body = f"\n## Contract check\n\nTarget's version of contract check content.\n"

        merged = _merge_body_sections(template_body, target_body)

        # The section should appear exactly once
        assert merged.count("## Contract check") == 1
        # The target's version should be preserved (not overwritten by the template version)
        assert "Target's version of contract check content." in merged
        assert contract_check_content not in merged


def test_sync_agents_rejects_shallow_path(tmp_path: pathlib.Path) -> None:
    """sync_agents must exit with code 1 when --project-dir resolves to fewer than 3 path components."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(sync_agents, ["--project-dir", "/tmp"])
    assert result.exit_code == 1


def test_sync_agents_renders_with_full_context(tmp_path: pathlib.Path) -> None:
    """sync-agents detects changes when pairmode_context.json provides full context.

    Ensures the false-negative 'No changes to apply.' is gone when a template
    uses {{ build_command }} or {{ protected_paths }} and those values are present
    in pairmode_context.json.
    """
    from click.testing import CliRunner

    # Set up .companion/ with pairmode_context.json
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir()
    pairmode_ctx = {
        "build_command": "make build",
        "test_command": "make test",
        "protected_paths": ["src/core/"],
    }
    (companion_dir / "pairmode_context.json").write_text(
        json.dumps(pairmode_ctx), encoding="utf-8"
    )

    # Create a synthetic agent file and a matching template in a temp templates dir
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    # Write a synthetic existing agent file whose frontmatter differs from what
    # the template will render (so we get a detected change).
    agent_content = """\
---
name: test-agent
description: Old description without build_command
---

## Body section

Some body text.
"""
    (agents_dir / "test-agent.md").write_text(agent_content, encoding="utf-8")

    # Create a synthetic template dir and template that uses build_command and protected_paths
    templates_dir = tmp_path / "templates" / "agents"
    templates_dir.mkdir(parents=True)
    template_content = """\
---
name: test-agent
description: Agent for {{ project_name }} — build: {{ build_command }}
---

## Body section

Protected paths: {% for p in protected_paths %} {{ p }}{% endfor %}
"""
    (templates_dir / "test-agent.md.j2").write_text(template_content, encoding="utf-8")

    # We can't inject our custom templates_dir into sync_agents CLI directly,
    # so test via _collect_changes with a context built from _build_template_context.
    from pairmode_sync import _collect_changes

    ctx = _build_template_context(tmp_path)
    changes = _collect_changes(agents_dir, templates_dir, ctx)

    # The change must be detected — rendering succeeds and context is fully populated.
    # Before this fix, sync-agents used only {"project_name": ...} as context, so templates
    # using {{ build_command }} would raise StrictUndefined and silently no-op, producing
    # "No changes to apply." even when changes existed.
    assert len(changes) == 1, (
        f"Expected 1 change, got {len(changes)}. "
        "build_command and protected_paths from pairmode_context.json may not be in context."
    )

    # The rendered frontmatter must contain the build_command value from pairmode_context.json
    _agent_file, _old, new_content = changes[0]
    assert "make build" in new_content, (
        f"Rendered agent content does not contain 'make build': {new_content!r}"
    )

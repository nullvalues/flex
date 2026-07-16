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
    _seed_context_gate_state,
    pairmode_cli,
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

    def test_pseudo_header_target_matches_template_h2_no_duplicate(self) -> None:
        """A target bold-inline pseudo-header matching a template ## heading is a no-op (INFRA-202)."""
        target_body = (
            "\n"
            "## Review checklist\n"
            "\n"
            "**1. HOOK PERFORMANCE**\n"
            "Do any hook scripts make API calls?\n"
        )
        template_body = (
            "\n"
            "## 1. Hook performance\n"
            "\n"
            "Do any hook scripts make API calls?\n"
        )

        before_count = target_body.lower().count("hook performance")
        merged = _merge_body_sections(template_body, target_body)
        after_count = merged.lower().count("hook performance")

        assert after_count == before_count, (
            "Expected no duplicate 'Hook performance' concept after merge; "
            f"before={before_count} after={after_count}\nmerged:\n{merged}"
        )

    def test_numbering_and_case_differences_still_match(self) -> None:
        """Different numbering/casing between target pseudo-header and template heading still match."""
        target_body = "\n## Review checklist\n\n**7. PROTECTED FILES**\nWere protected files touched?\n"
        template_body = "\n## 1. Protected files\n\nWere protected files touched?\n"

        merged = _merge_body_sections(template_body, target_body)

        assert "## 1. Protected files" not in merged
        assert merged == target_body

    def test_enumerated_subsection_ids_match(self) -> None:
        """Sub-lettered enumerator ids (5b.) normalize to the same concept key."""
        target_body = (
            "\n## Review checklist\n\n"
            "**5b. constraint rationale preservation**\nSome content.\n"
        )
        template_body = "\n## 5b. Constraint rationale preservation\n\nSome content.\n"

        merged = _merge_body_sections(template_body, target_body)

        assert merged == target_body
        assert "## 5b. Constraint rationale preservation" not in merged

    def test_reviewer_md_incident_shape_is_noop(self) -> None:
        """Reproduces the 85a6f52 corruption shape: full checklist must merge as a no-op."""
        target_body = (
            "\n"
            "You are the reviewer.\n"
            "\n"
            "## Review checklist\n"
            "\n"
            "**1. HOOK PERFORMANCE**\n"
            "Hook content.\n"
            "\n"
            "**2. PIPE CONTRACT**\n"
            "Pipe content.\n"
            "\n"
            "**7. PROTECTED FILES**\n"
            "Protected content.\n"
            "\n"
            "## Final output to orchestrator\n"
            "\n"
            "End here.\n"
        )
        template_body = (
            "\n"
            "## 1. Hook performance\n"
            "\n"
            "Hook content.\n"
            "\n"
            "## 2. Pipe contract\n"
            "\n"
            "Pipe content.\n"
            "\n"
            "## 9. Story scope\n"
            "\n"
            "Rail scope content.\n"
            "\n"
            "## 5b. Constraint rationale preservation\n"
            "\n"
            "Constraint content.\n"
            "\n"
            "## 2.5 Story spec\n"
            "\n"
            "Story spec content.\n"
        )

        # Add pseudo-headers matching the remaining template items so this is a
        # true full-checklist no-op reproduction of the incident shape.
        target_body = target_body.replace(
            "**7. PROTECTED FILES**\nProtected content.\n",
            (
                "**7. PROTECTED FILES**\nProtected content.\n\n"
                "**6. STORY SCOPE**\nRail scope content.\n\n"
                "**5b. CONSTRAINT RATIONALE PRESERVATION**\nConstraint content.\n\n"
                "**2.5 STORY SPEC**\nStory spec content.\n"
            ),
        )

        merged = _merge_body_sections(template_body, target_body)

        # Every template concept is already present in the target under some
        # heading style, so the merge must be a true no-op: nothing appended
        # after the terminal section, and the target body is unchanged.
        assert merged == target_body, (
            "Expected a full no-op merge (85a6f52 incident shape); "
            f"merged differs from target:\n{merged}"
        )
        assert merged.split("## Final output to orchestrator")[1].strip() == "End here."
        # Each canonical heading marker for the covered concepts appears exactly
        # once — guards against the tail-duplication shape from commit 85a6f52.
        for marker in [
            "**1. HOOK PERFORMANCE**",
            "**2. PIPE CONTRACT**",
            "**6. STORY SCOPE**",
            "**5b. CONSTRAINT RATIONALE PRESERVATION**",
            "**2.5 STORY SPEC**",
        ]:
            assert merged.count(marker) == 1, (
                f"Marker {marker!r} does not appear exactly once in merged body:\n{merged}"
            )

    def test_genuinely_new_section_still_appended(self) -> None:
        """A template section with no matching concept anywhere in the target is still appended."""
        target_body = "\n## Review checklist\n\n**1. HOOK PERFORMANCE**\nHook content.\n"
        template_body = "\n## Brand new section\n\nSome brand new content.\n"

        merged = _merge_body_sections(template_body, target_body)

        assert "## Brand new section" in merged
        assert "Some brand new content." in merged

    def test_inline_bold_in_prose_is_not_a_pseudo_header(self) -> None:
        """A bold span embedded in a prose sentence must not register as a pseudo-header concept."""
        target_body = "\nThis is **important** context.\n"
        template_body = "\n## Important\n\nSome content.\n"

        merged = _merge_body_sections(template_body, target_body)

        assert "## Important" in merged
        assert "Some content." in merged


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
    changes, render_errors = _collect_changes(agents_dir, templates_dir, ctx)

    # The change must be detected — rendering succeeds and context is fully populated.
    # Before this fix, sync-agents used only {"project_name": ...} as context, so templates
    # using {{ build_command }} would raise StrictUndefined and silently no-op, producing
    # "No changes to apply." even when changes existed.
    assert len(changes) == 1, (
        f"Expected 1 change, got {len(changes)}. "
        "build_command and protected_paths from pairmode_context.json may not be in context."
    )
    assert render_errors == [], f"Expected no render errors, got {render_errors!r}"

    # The rendered frontmatter must contain the build_command value from pairmode_context.json
    _agent_file, _old, new_content = changes[0]
    assert "make build" in new_content, (
        f"Rendered agent content does not contain 'make build': {new_content!r}"
    )


def test_sync_agents_exits_nonzero_on_render_failure(tmp_path: pathlib.Path) -> None:
    """sync-agents must exit 1 and surface the render error when a template fails to render.

    Sets up a synthetic agent file plus a synthetic template that references an
    undefined variable. Invokes the sync_agents CLI via CliRunner, with
    pairmode_sync.TEMPLATES_DIR patched to point at the synthetic templates dir.
    Asserts exit code is 1 and stderr/stdout contains "failed to render".
    """
    import unittest.mock

    from click.testing import CliRunner

    # Create a 4-component temp path (depth guard rejects fewer than 3 components).
    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)

    # Synthetic agent file with a valid frontmatter block
    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "bad-agent.md").write_text(
        "---\nmodel: sonnet\n---\nbody\n", encoding="utf-8"
    )

    # Synthetic templates dir whose template references an undefined variable
    fake_templates = project_dir / "templates"
    fake_templates.mkdir()
    (fake_templates / "bad-agent.md.j2").write_text(
        "---\nmodel: sonnet\nname: {{ project_name }}\n---\n{{ undefined_variable_xyz }}\n",
        encoding="utf-8",
    )

    # Minimal .companion files so _build_template_context succeeds
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({"project_name": "test"}), encoding="utf-8"
    )
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", fake_templates):
        result = runner.invoke(
            sync_agents,
            ["--project-dir", str(project_dir), "--yes"],
        )

    assert result.exit_code == 1, (
        f"Expected exit code 1, got {result.exit_code}. Output:\n{result.output}"
    )
    assert "failed to render" in result.output, (
        f"Expected 'failed to render' in output, got:\n{result.output}"
    )


def test_no_changes_message_only_when_clean(tmp_path: pathlib.Path) -> None:
    """sync-agents prints 'No changes to apply.' only when there are no changes and no errors.

    Sets up a project whose agent file matches what the synthetic template would render,
    so no changes are detected and no errors occur. Asserts exit code 0 and that the
    "No changes to apply." message is in the CLI output.
    """
    import unittest.mock

    from click.testing import CliRunner

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)

    # Synthetic templates dir whose template renders to a deterministic output
    fake_templates = project_dir / "templates"
    fake_templates.mkdir()
    template_text = "---\nmodel: sonnet\nname: clean-agent\n---\n"
    (fake_templates / "clean-agent.md.j2").write_text(template_text, encoding="utf-8")

    # The agent file must equal the rendered template so _collect_changes finds no diff
    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "clean-agent.md").write_text(template_text, encoding="utf-8")

    # Minimal .companion files so _build_template_context succeeds
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({"project_name": "test"}), encoding="utf-8"
    )
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", fake_templates):
        result = runner.invoke(
            sync_agents,
            ["--project-dir", str(project_dir), "--yes"],
        )

    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output:\n{result.output}"
    )
    assert "No changes to apply." in result.output, (
        f"Expected 'No changes to apply.' in output, got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# INFRA-203: empty/missing-variable body-merge render-failure tests
# ---------------------------------------------------------------------------


def test_empty_build_command_in_appended_section_fails_loudly(tmp_path: pathlib.Path) -> None:
    """A body section appended to the target that interpolates an empty build_command fails loudly.

    Reproduces the 85a6f52 corruption shape: build_command is absent from both
    state.json and pairmode_context.json (resolves to "" via
    _build_template_context's fallback), and the template's ## Test run section
    -- absent from the target, so it would be newly appended -- interpolates it.
    Asserts the file lands in render_errors (not changes), the CLI exits 1 with
    "failed to render" on stderr, and the on-disk agent file is unchanged.
    """
    import unittest.mock

    from click.testing import CliRunner

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)

    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    original_content = "---\nmodel: sonnet\nname: reviewer\n---\n\n## Other section\n\nSome text.\n"
    (agents_dir / "reviewer.md").write_text(original_content, encoding="utf-8")

    fake_templates = project_dir / "templates"
    fake_templates.mkdir()
    (fake_templates / "reviewer.md.j2").write_text(
        "---\nmodel: sonnet\nname: reviewer\n---\n\n"
        "## Other section\n\nSome text.\n\n"
        "## Test run\n\nDoes `{{ build_command }}` pass cleanly?\n",
        encoding="utf-8",
    )

    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({"project_name": "test"}), encoding="utf-8"
    )
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", fake_templates):
        result = runner.invoke(
            sync_agents,
            ["--project-dir", str(project_dir), "--yes"],
        )

    assert result.exit_code == 1, (
        f"Expected exit code 1, got {result.exit_code}. Output:\n{result.output}"
    )
    assert "failed to render" in result.output, (
        f"Expected 'failed to render' in output, got:\n{result.output}"
    )
    assert (agents_dir / "reviewer.md").read_text(encoding="utf-8") == original_content, (
        "Agent file on disk must be unchanged when the render fails"
    )


def test_empty_variable_in_existing_section_does_not_fail(tmp_path: pathlib.Path) -> None:
    """An empty build_command inside a section already present in the target is not blocked.

    The same empty build_command as above, but the target already contains an
    equivalent '## Test run' section, so _merge_body_sections would not append
    it. Asserts the file is NOT reported as a render error (Ensures #4).
    """
    import unittest.mock

    from click.testing import CliRunner

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)

    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    original_content = (
        "---\nmodel: sonnet\nname: reviewer\n---\n\n"
        "## Test run\n\nDoes the test suite pass?\n"
    )
    (agents_dir / "reviewer.md").write_text(original_content, encoding="utf-8")

    fake_templates = project_dir / "templates"
    fake_templates.mkdir()
    (fake_templates / "reviewer.md.j2").write_text(
        "---\nmodel: sonnet\nname: reviewer-updated\n---\n\n"
        "## Test run\n\nDoes `{{ build_command }}` pass cleanly?\n",
        encoding="utf-8",
    )

    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({"project_name": "test"}), encoding="utf-8"
    )
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", fake_templates):
        result = runner.invoke(
            sync_agents,
            ["--project-dir", str(project_dir), "--yes"],
        )

    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output:\n{result.output}"
    )
    assert "failed to render" not in result.output, (
        f"Should not report a render error when the empty variable is only inside an "
        f"already-present section, got:\n{result.output}"
    )
    # The frontmatter change (name: reviewer -> reviewer-updated) must still apply.
    new_content = (agents_dir / "reviewer.md").read_text(encoding="utf-8")
    assert "name: reviewer-updated" in new_content


def test_full_render_exception_populates_render_errors(tmp_path: pathlib.Path) -> None:
    """A raised full-template render is surfaced via render_errors, not swallowed to "".

    Uses a targeted mock of _render_full_template raising jinja2.TemplateError
    to exercise the branch directly, since both renders normally share context
    and a natural full-render-only failure is hard to construct.
    """
    import unittest.mock

    import jinja2

    from pairmode_sync import _collect_changes

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)

    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "builder.md").write_text(
        "---\nmodel: sonnet\nname: builder\n---\nbody\n", encoding="utf-8"
    )

    templates_dir = project_dir / "templates"
    templates_dir.mkdir()
    (templates_dir / "builder.md.j2").write_text(
        "---\nmodel: sonnet\nname: builder-updated\n---\nbody\n", encoding="utf-8"
    )

    ctx = {"project_name": "test"}

    with unittest.mock.patch(
        "pairmode_sync._render_full_template",
        side_effect=jinja2.TemplateError("synthetic full-render failure"),
    ):
        changes, render_errors = _collect_changes(agents_dir, templates_dir, ctx)

    assert changes == [], f"Expected no changes when full render raises, got {changes!r}"
    assert len(render_errors) == 1, f"Expected 1 render error, got {render_errors!r}"
    assert render_errors[0][0] == "builder.md"
    assert "synthetic full-render failure" in render_errors[0][1]
    assert (agents_dir / "builder.md").read_text(encoding="utf-8") == (
        "---\nmodel: sonnet\nname: builder\n---\nbody\n"
    ), "Agent file must not be written when the full render raises"


def test_undefined_variable_still_fails_via_frontmatter_path(tmp_path: pathlib.Path) -> None:
    """A truly-undefined body variable still exits 1 via the frontmatter StrictUndefined path.

    Extends coverage equivalent to test_sync_agents_exits_nonzero_on_render_failure
    without weakening it (Ensures #5).
    """
    import unittest.mock

    from click.testing import CliRunner

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)

    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "bad-agent.md").write_text(
        "---\nmodel: sonnet\n---\nbody\n", encoding="utf-8"
    )

    fake_templates = project_dir / "templates"
    fake_templates.mkdir()
    (fake_templates / "bad-agent.md.j2").write_text(
        "---\nmodel: sonnet\nname: {{ project_name }}\n---\n{{ truly_undefined_xyz }}\n",
        encoding="utf-8",
    )

    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({"project_name": "test"}), encoding="utf-8"
    )
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", fake_templates):
        result = runner.invoke(
            sync_agents,
            ["--project-dir", str(project_dir), "--yes"],
        )

    assert result.exit_code == 1
    assert "failed to render" in result.output
    assert not (agents_dir / "bad-agent.md").read_text(encoding="utf-8").startswith(
        "---\nmodel: sonnet\nname:"
    ), "Agent file must remain unwritten (still the original content)"


def test_reviewer_incident_empty_build_command_not_written(tmp_path: pathlib.Path) -> None:
    """Reproduces the 85a6f52 `` Does `` pass cleanly? `` corruption and asserts it never lands.

    A reviewer-shaped fixture whose target lacks the appended checklist section;
    the template's checklist item interpolates an empty build_command into a
    to-be-appended section. Asserts the corrupt line is never written to the
    agent file and the run fails loudly.
    """
    import unittest.mock

    from click.testing import CliRunner

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)

    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    original_content = (
        "---\nname: reviewer\nmodel: sonnet\n---\n\n"
        "## 1. HOOK PERFORMANCE\n\nDo any hooks block?\n"
    )
    (agents_dir / "reviewer.md").write_text(original_content, encoding="utf-8")

    fake_templates = project_dir / "templates"
    fake_templates.mkdir()
    (fake_templates / "reviewer.md.j2").write_text(
        "---\nname: reviewer\nmodel: sonnet\n---\n\n"
        "## 1. HOOK PERFORMANCE\n\nDo any hooks block?\n\n"
        "## 10. BUILD GATE\n\nDoes `{{ build_command }}` pass cleanly?\n",
        encoding="utf-8",
    )

    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({"project_name": "test"}), encoding="utf-8"
    )
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", fake_templates):
        result = runner.invoke(
            sync_agents,
            ["--project-dir", str(project_dir), "--yes"],
        )

    assert result.exit_code == 1, (
        f"Expected exit code 1, got {result.exit_code}. Output:\n{result.output}"
    )
    on_disk = (agents_dir / "reviewer.md").read_text(encoding="utf-8")
    assert "Does `` pass cleanly?" not in on_disk, (
        "The corrupt empty-substitution line must never be written to disk"
    )
    assert on_disk == original_content, "Agent file must remain byte-for-byte unchanged"


# ---------------------------------------------------------------------------
# sync-all tests
# ---------------------------------------------------------------------------


def _make_deep_project_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a project dir with >= 3 path components (depth guard safe)."""
    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)
    return project_dir


def _run_sync_all(args: list[str], subprocess_mock=None):
    """Invoke sync-all via Click's CliRunner with subprocess.run mocked."""
    import unittest.mock
    from click.testing import CliRunner

    runner = CliRunner()
    if subprocess_mock is not None:
        with unittest.mock.patch("pairmode_sync.subprocess.run", subprocess_mock):
            return runner.invoke(pairmode_cli, ["sync-all"] + args, catch_exceptions=False)
    return runner.invoke(pairmode_cli, ["sync-all"] + args, catch_exceptions=False)


def _ok_run(returncode: int = 0):
    """Return a mock subprocess.run that always returns the given returncode."""
    import unittest.mock

    def _run(argv, check=False):
        result = unittest.mock.MagicMock()
        result.returncode = returncode
        return result

    return _run


def _capturing_run(return_codes=None):
    """Return a mock subprocess.run that records calls and returns given codes in order."""
    import unittest.mock

    codes = list(return_codes or [0, 0, 0])
    calls = []

    def _run(argv, check=False):
        calls.append(list(argv))
        rc = codes.pop(0) if codes else 0
        result = unittest.mock.MagicMock()
        result.returncode = rc
        return result

    return _run, calls


def test_sync_all_dry_run_default_skips_sync_py_and_passes_dry_run_to_others(
    tmp_path: pathlib.Path,
) -> None:
    """In default dry-run mode: sync.py is skipped; sync-agents and sync-build get --dry-run."""
    project_dir = _make_deep_project_dir(tmp_path)
    mock_run, calls = _capturing_run([0, 0])

    result = _run_sync_all(["--project-dir", str(project_dir)], mock_run)

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}:\n{result.output}"
    # sync.py not invoked — only two subprocess calls
    assert len(calls) == 2, f"Expected 2 subprocess calls, got {len(calls)}: {calls}"
    # sync-agents must contain --dry-run
    agents_argv = calls[0]
    assert "--dry-run" in agents_argv, f"sync-agents argv missing --dry-run: {agents_argv}"
    assert "sync-agents" in agents_argv, f"Expected sync-agents call, got: {agents_argv}"
    # sync-build must contain --dry-run
    build_argv = calls[1]
    assert "--dry-run" in build_argv, f"sync-build argv missing --dry-run: {build_argv}"
    assert "sync-build" in build_argv, f"Expected sync-build call, got: {build_argv}"
    # stdout should contain all three section headers and the skipped notice
    assert "=== sync (methodology files) ===" in result.output
    assert "=== sync-agents (agent frontmatter) ===" in result.output
    assert "=== sync-build (CLAUDE.build.md) ===" in result.output
    assert "skipped:" in result.output


def test_sync_all_apply_invokes_all_three_in_order(tmp_path: pathlib.Path) -> None:
    """--apply: all three commands invoked in order; no --dry-run; sync-build gets --apply."""
    project_dir = _make_deep_project_dir(tmp_path)
    mock_run, calls = _capturing_run([0, 0, 0])

    result = _run_sync_all(["--project-dir", str(project_dir), "--apply"], mock_run)

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}:\n{result.output}"
    assert len(calls) == 3, f"Expected 3 subprocess calls, got {len(calls)}: {calls}"
    # Order: sync.py, sync-agents, sync-build
    assert "sync.py" in calls[0][-2] or any("sync.py" in a for a in calls[0]), (
        f"First call should be sync.py, got: {calls[0]}"
    )
    assert "sync-agents" in calls[1], f"Second call should be sync-agents, got: {calls[1]}"
    assert "sync-build" in calls[2], f"Third call should be sync-build, got: {calls[2]}"
    # No --dry-run in any argv
    for argv in calls:
        assert "--dry-run" not in argv, f"--dry-run found in argv: {argv}"
    # sync-build should contain --apply
    assert "--apply" in calls[2], f"sync-build argv missing --apply: {calls[2]}"


def test_sync_all_yes_propagates_to_all_in_apply_mode(tmp_path: pathlib.Path) -> None:
    """--apply --yes: all three invocations receive --yes."""
    project_dir = _make_deep_project_dir(tmp_path)
    mock_run, calls = _capturing_run([0, 0, 0])

    result = _run_sync_all(
        ["--project-dir", str(project_dir), "--apply", "--yes"], mock_run
    )

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}:\n{result.output}"
    assert len(calls) == 3
    for argv in calls:
        assert "--yes" in argv, f"--yes missing from argv: {argv}"


def test_sync_all_yes_in_dry_run_propagates_to_sync_agents_and_sync_build(
    tmp_path: pathlib.Path,
) -> None:
    """--yes in dry-run mode: sync.py skipped; sync-agents and sync-build each get --yes and --dry-run."""
    project_dir = _make_deep_project_dir(tmp_path)
    mock_run, calls = _capturing_run([0, 0])

    result = _run_sync_all(["--project-dir", str(project_dir), "--yes"], mock_run)

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}:\n{result.output}"
    assert len(calls) == 2, f"Expected 2 calls (sync.py skipped), got {len(calls)}: {calls}"
    for argv in calls:
        assert "--yes" in argv, f"--yes missing from argv: {argv}"
        assert "--dry-run" in argv, f"--dry-run missing from argv: {argv}"
    assert "skipped:" in result.output


def test_sync_all_halts_on_sync_py_failure(tmp_path: pathlib.Path) -> None:
    """If sync.py exits non-zero in --apply mode, sync-agents and sync-build are not invoked."""
    project_dir = _make_deep_project_dir(tmp_path)
    mock_run, calls = _capturing_run([2])  # sync.py fails with exit 2

    result = _run_sync_all(["--project-dir", str(project_dir), "--apply"], mock_run)

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}:\n{result.output}"
    # Only one subprocess call (sync.py); the chain halted
    assert len(calls) == 1, f"Expected 1 call before halt, got {len(calls)}: {calls}"
    # output (stderr is mixed in) should mention halting chain
    assert "halting chain" in result.output, (
        f"Expected 'halting chain' in output, got: {result.output!r}"
    )


def test_sync_all_halts_on_sync_agents_failure(tmp_path: pathlib.Path) -> None:
    """If sync-agents exits 1, sync-build is not invoked; wrapper exits 1."""
    project_dir = _make_deep_project_dir(tmp_path)
    # apply mode: sync.py (ok=0), sync-agents (fail=1)
    mock_run, calls = _capturing_run([0, 1])

    result = _run_sync_all(["--project-dir", str(project_dir), "--apply"], mock_run)

    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    # sync.py and sync-agents were invoked; sync-build was not
    assert len(calls) == 2, f"Expected 2 calls, got {len(calls)}: {calls}"
    assert "sync-agents" in calls[1], f"Second call should be sync-agents, got: {calls[1]}"


def test_sync_all_halts_on_sync_build_failure(tmp_path: pathlib.Path) -> None:
    """If sync-build exits 3, wrapper exits 3; all three commands were invoked."""
    project_dir = _make_deep_project_dir(tmp_path)
    mock_run, calls = _capturing_run([0, 0, 3])

    result = _run_sync_all(["--project-dir", str(project_dir), "--apply"], mock_run)

    assert result.exit_code == 3, f"Expected exit 3, got {result.exit_code}"
    assert len(calls) == 3, f"Expected 3 calls, got {len(calls)}: {calls}"


def test_sync_all_depth_guard_rejects_shallow_dir(tmp_path: pathlib.Path) -> None:
    """Depth guard must reject shallow paths (< 3 components); no subprocess invoked."""
    import unittest.mock
    from click.testing import CliRunner

    mock_run = unittest.mock.MagicMock()
    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.subprocess.run", mock_run):
        result = runner.invoke(pairmode_cli, ["sync-all", "--project-dir", "/tmp"])

    assert result.exit_code != 0, f"Expected non-zero exit for shallow dir, got 0"
    mock_run.assert_not_called()


def test_sync_all_project_dir_defaults_to_cwd(tmp_path: pathlib.Path) -> None:
    """Without --project-dir, downstream argvs include --project-dir set to resolved cwd."""
    import os
    import unittest.mock
    from click.testing import CliRunner

    # Use a sufficiently deep real directory as CWD
    project_dir = _make_deep_project_dir(tmp_path)
    mock_run, calls = _capturing_run([0, 0])

    runner = CliRunner()
    # Change working directory to project_dir so the default "." resolves there
    orig_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        with unittest.mock.patch("pairmode_sync.subprocess.run", mock_run):
            result = runner.invoke(pairmode_cli, ["sync-all"], catch_exceptions=False)
    finally:
        os.chdir(orig_cwd)

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}:\n{result.output}"
    expected_dir = str(project_dir.resolve())
    for argv in calls:
        assert "--project-dir" in argv, f"--project-dir missing from argv: {argv}"
        idx = argv.index("--project-dir")
        assert argv[idx + 1] == expected_dir, (
            f"Expected --project-dir={expected_dir}, got {argv[idx + 1]}"
        )


def test_sync_all_header_separators_present_in_order(tmp_path: pathlib.Path) -> None:
    """--apply mode: all three === headers appear in the correct order in stdout."""
    project_dir = _make_deep_project_dir(tmp_path)
    mock_run, _ = _capturing_run([0, 0, 0])

    result = _run_sync_all(["--project-dir", str(project_dir), "--apply"], mock_run)

    assert result.exit_code == 0
    headers = [
        "=== sync (methodology files) ===",
        "=== sync-agents (agent frontmatter) ===",
        "=== sync-build (CLAUDE.build.md) ===",
    ]
    positions = [result.output.find(h) for h in headers]
    assert all(p >= 0 for p in positions), (
        f"One or more headers missing from output: {result.output!r}"
    )
    assert positions == sorted(positions), (
        f"Headers not in expected order. Positions: {positions}"
    )


def test_sync_all_registered_on_pairmode_cli() -> None:
    """'sync-all' must be registered as a command on pairmode_cli."""
    assert "sync-all" in pairmode_cli.commands, (
        f"sync-all not found in pairmode_cli.commands: {list(pairmode_cli.commands.keys())}"
    )


# ---------------------------------------------------------------------------
# _seed_context_gate_state tests
# ---------------------------------------------------------------------------


def test_sync_build_apply_seeds_missing_context_gate_state(tmp_path: pathlib.Path) -> None:
    """Both context gate keys absent: seeds all three; emits seeded line."""
    import io
    from click.testing import CliRunner

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps({"pairmode_version": "1.0"}), encoding="utf-8")

    runner = CliRunner()
    # Capture stdout from _seed_context_gate_state directly
    with runner.isolated_filesystem():
        from click.testing import CliRunner as CR
        import io as _io

        output = _io.StringIO()
        import click as _click
        with _click.Context(_click.Command("test")):
            from unittest.mock import patch
            with patch("click.echo", side_effect=lambda msg, **kw: output.write(str(msg) + "\n")):
                _seed_context_gate_state(project_dir, state_path, dry_run=False)

    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert "context_session_reset_at" in written, "context_session_reset_at not seeded"
    assert written["context_current_tokens"] == 25000, (
        f"Expected context_current_tokens=25000, got {written.get('context_current_tokens')}"
    )
    assert "context_current_tokens_recorded_at" in written, (
        "context_current_tokens_recorded_at not seeded"
    )
    # Existing key must be preserved
    assert written.get("pairmode_version") == "1.0", "Existing pairmode_version was lost"
    assert "seeded" in output.getvalue(), f"Expected 'seeded' in output, got: {output.getvalue()!r}"


def test_sync_build_apply_no_seed_when_keys_present(tmp_path: pathlib.Path) -> None:
    """Both context gate keys present: no write to state.json, no seeded output."""
    import io
    from unittest.mock import patch

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    state_path = companion_dir / "state.json"

    original = {
        "context_session_reset_at": "2026-01-01T00:00:00+00:00",
        "context_current_tokens": 50000,
        "context_current_tokens_recorded_at": "2026-01-01T00:00:00+00:00",
    }
    state_path.write_text(json.dumps(original), encoding="utf-8")

    original_mtime = state_path.stat().st_mtime

    output = io.StringIO()
    with patch("click.echo", side_effect=lambda msg, **kw: output.write(str(msg) + "\n")):
        _seed_context_gate_state(project_dir, state_path, dry_run=False)

    # state.json must not have been modified
    assert state_path.stat().st_mtime == original_mtime, "state.json was written when no seed needed"
    assert output.getvalue() == "", f"Expected no output, got: {output.getvalue()!r}"


def test_sync_build_apply_creates_state_json_if_absent(tmp_path: pathlib.Path) -> None:
    """No state.json at all: creates .companion/state.json with only the three context gate keys."""
    import io
    from unittest.mock import patch

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    state_path = companion_dir / "state.json"

    output = io.StringIO()
    with patch("click.echo", side_effect=lambda msg, **kw: output.write(str(msg) + "\n")):
        _seed_context_gate_state(project_dir, state_path, dry_run=False)

    assert state_path.exists(), "state.json was not created"
    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(written.keys()) == {
        "context_session_reset_at",
        "context_current_tokens",
        "context_current_tokens_recorded_at",
    }, f"Expected only three context gate keys, got: {list(written.keys())}"
    assert written["context_current_tokens"] == 25000
    assert "seeded" in output.getvalue()


def test_sync_build_dry_run_emits_warning_not_write(tmp_path: pathlib.Path) -> None:
    """Dry-run with missing keys: warning lines emitted; state.json not written."""
    import io
    from unittest.mock import patch

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps({}), encoding="utf-8")

    original_content = state_path.read_text(encoding="utf-8")

    output = io.StringIO()
    with patch("click.echo", side_effect=lambda msg, **kw: output.write(str(msg) + "\n")):
        _seed_context_gate_state(project_dir, state_path, dry_run=True)

    # state.json must not have been modified
    assert state_path.read_text(encoding="utf-8") == original_content, (
        "state.json was written in dry-run mode"
    )
    out = output.getvalue()
    assert "warning:" in out, f"Expected 'warning:' in output, got: {out!r}"
    assert "context_session_reset_at" in out, f"Expected missing key in warning, got: {out!r}"
    assert "context_current_tokens" in out, f"Expected missing key in warning, got: {out!r}"


def test_sync_build_apply_seeds_only_missing_reset_at(tmp_path: pathlib.Path) -> None:
    """Only context_session_reset_at absent: seeds it; does not alter tokens or recorded_at."""
    import io
    from unittest.mock import patch

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    state_path = companion_dir / "state.json"

    original = {
        "context_current_tokens": 75000,
        "context_current_tokens_recorded_at": "2025-12-01T10:00:00+00:00",
    }
    state_path.write_text(json.dumps(original), encoding="utf-8")

    output = io.StringIO()
    with patch("click.echo", side_effect=lambda msg, **kw: output.write(str(msg) + "\n")):
        _seed_context_gate_state(project_dir, state_path, dry_run=False)

    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert "context_session_reset_at" in written, "context_session_reset_at not seeded"
    # tokens and recorded_at must be preserved
    assert written["context_current_tokens"] == 75000, (
        f"context_current_tokens was altered: {written['context_current_tokens']}"
    )
    assert written["context_current_tokens_recorded_at"] == "2025-12-01T10:00:00+00:00", (
        "context_current_tokens_recorded_at was altered"
    )
    assert "seeded" in output.getvalue()


def test_sync_build_apply_seeds_only_missing_current_tokens(tmp_path: pathlib.Path) -> None:
    """Only context_current_tokens absent: seeds tokens=25000 and recorded_at=now; reset_at untouched."""
    import io
    from unittest.mock import patch

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    state_path = companion_dir / "state.json"

    existing_reset_at = "2026-03-15T08:00:00+00:00"
    original = {
        "context_session_reset_at": existing_reset_at,
    }
    state_path.write_text(json.dumps(original), encoding="utf-8")

    output = io.StringIO()
    with patch("click.echo", side_effect=lambda msg, **kw: output.write(str(msg) + "\n")):
        _seed_context_gate_state(project_dir, state_path, dry_run=False)

    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert written.get("context_current_tokens") == 25000, (
        f"Expected context_current_tokens=25000, got {written.get('context_current_tokens')}"
    )
    assert "context_current_tokens_recorded_at" in written, (
        "context_current_tokens_recorded_at not seeded"
    )
    # reset_at must be preserved (not overwritten)
    assert written["context_session_reset_at"] == existing_reset_at, (
        f"context_session_reset_at was overwritten: {written['context_session_reset_at']}"
    )
    assert "seeded" in output.getvalue()


# ---------------------------------------------------------------------------
# sync-build gate section replacement tests (BUILD-035)
# ---------------------------------------------------------------------------

# Old stub-gate prose that appears in pre-BUILD-035 CLAUDE.build.md files.
# This is the distinctive delegation-language content that the new CLI-call
# sections replace.
_OLD_STUB_GATE_PROSE = """\
### Pre-story stub gate

Run this check **once per story**, after the schema gate, before spawning the builder.

Read `docs/stories/<RAIL>/<RAIL>-NNN.md` and check for:

**Delegation language** -- any of these appearing in the story body:
- "See phase doc"
- "See docs/phases/"
- "See phase-"

**Missing acceptance surface** -- none of these sections present:
- `## Ensures`
- `## Acceptance criterion`
- `## Acceptance criteria`

If delegation language found OR acceptance surface missing, stop and report:

PRE-STORY BLOCK -- Story [RAIL-NNN] is a stub.
"""


def _make_old_gate_build_md(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a CLAUDE.build.md containing the old inline stub-gate prose.

    Returns the Path to the project root dir.
    """
    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)

    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({"pairmode_version": "1.0"}), encoding="utf-8"
    )
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")

    build_file = project_dir / "CLAUDE.build.md"
    build_file.write_text(_OLD_STUB_GATE_PROSE, encoding="utf-8")

    return project_dir


def test_sync_build_dry_run_detects_old_gate_sections(tmp_path: pathlib.Path) -> None:
    """sync-build --dry-run reports a non-empty diff when CLAUDE.build.md has old inline gate prose.

    The old stub-gate section contains delegation-language prose ("See phase doc", etc.)
    that the template replacement removes. After BUILD-035, the rendered template uses
    CLI-call sections instead. A project still holding the old content must show a diff.
    """
    from click.testing import CliRunner

    project_dir = _make_old_gate_build_md(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["sync-build", "--project-dir", str(project_dir), "--dry-run"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (
        f"Expected exit 0 from --dry-run, got {result.exit_code}:\n{result.output}"
    )
    # The diff must be non-empty (old and new content differ)
    assert "---" in result.output or "+++" in result.output, (
        f"Expected a unified diff in output, got:\n{result.output!r}"
    )


def test_sync_build_apply_replaces_old_gate_sections(tmp_path: pathlib.Path) -> None:
    """sync-build --apply --yes rewrites CLAUDE.build.md: contains check-stub, not old prose.

    After applying the template, the written file must:
    - Contain 'check-stub' (the new CLI subcommand name).
    - Not contain the old delegation-language prose ('See phase doc').
    """
    from click.testing import CliRunner

    project_dir = _make_old_gate_build_md(tmp_path)
    build_file = project_dir / "CLAUDE.build.md"

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["sync-build", "--project-dir", str(project_dir), "--apply", "--yes"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (
        f"Expected exit 0 from --apply --yes, got {result.exit_code}:\n{result.output}"
    )

    written = build_file.read_text(encoding="utf-8")

    assert "check-stub" in written, (
        "Expected 'check-stub' CLI call in written CLAUDE.build.md, but not found."
    )
    assert "See phase doc" not in written, (
        "Old delegation-language prose ('See phase doc') still present in written file."
    )

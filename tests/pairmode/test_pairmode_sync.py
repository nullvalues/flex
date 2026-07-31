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

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path_factory) -> pathlib.Path:
    """INFRA-288: audit-hooks now reads the merged hook view, which includes
    plugin hooks.json files discovered under the *home* directory. Every test
    runs against a fake, empty home so the operator's real ~/.claude/plugins
    can never leak into fixture expectations."""
    fake_home = tmp_path_factory.mktemp("fake-home")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("FLEX_PLUGIN_HOOKS", raising=False)
    return fake_home


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

    def test_test_dir_from_pairmode_context(self, tmp_path: pathlib.Path) -> None:
        """_build_template_context returns test_dir from pairmode_context.json (INFRA-240)."""
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        pairmode_ctx = {"test_dir": "spec/"}
        (companion_dir / "pairmode_context.json").write_text(
            json.dumps(pairmode_ctx), encoding="utf-8"
        )
        ctx = _build_template_context(tmp_path)
        assert ctx.get("test_dir") == "spec/", (
            f"Expected test_dir='spec/', got {ctx.get('test_dir')!r}"
        )

    def test_test_dir_defaults_to_tests_slash_when_absent(self, tmp_path: pathlib.Path) -> None:
        """_build_template_context falls back to 'tests/' when no test_dir is declared."""
        ctx = _build_template_context(tmp_path)
        assert ctx.get("test_dir") == "tests/"


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
        """The rendered build template must contain the absolute scripts directory path.

        RELEASE-009: pairmode_scripts_dir is now explicitly embedded in the template.
        """
        ctx = self._make_context(tmp_path)
        rendered = _render_build_template(ctx)
        absolute_scripts = ctx["pairmode_scripts_dir"]
        assert absolute_scripts in rendered, (
            f"Rendered CLAUDE.build.md does not contain absolute scripts path {absolute_scripts!r}"
        )

    def test_rendered_template_has_pairmode_scripts_dir_line(self, tmp_path: pathlib.Path) -> None:
        """Rendered CLAUDE.build.md must contain a 'pairmode_scripts_dir = <path>' line.

        Signal-1 detection in fleet_discovery.py uses _SCRIPTS_DIR_PATTERN which
        matches exactly this key-value form.  RELEASE-009 defect 1.
        """
        import re
        ctx = self._make_context(tmp_path)
        rendered = _render_build_template(ctx)
        pattern = re.compile(r"pairmode_scripts_dir\s*=\s*\S+")
        assert pattern.search(rendered), (
            "Rendered CLAUDE.build.md does not contain a 'pairmode_scripts_dir = <path>' line"
        )

    def test_rendered_template_has_no_bare_flex_build_invocations(self, tmp_path: pathlib.Path) -> None:
        """All flex_build.py invocations in the rendered template must use absolute paths.

        RELEASE-009 defect 2: bare 'flex_build.py' references must not appear.
        """
        ctx = self._make_context(tmp_path)
        rendered = _render_build_template(ctx)
        absolute_scripts = ctx["pairmode_scripts_dir"]
        for lineno, line in enumerate(rendered.splitlines(), 1):
            # A bare invocation is one that contains 'flex_build.py' but NOT
            # the absolute scripts path prefix.
            if "flex_build.py" in line and absolute_scripts not in line:
                raise AssertionError(
                    f"Line {lineno} contains bare 'flex_build.py' without absolute path prefix:\n  {line}"
                )

    def test_rendered_template_does_not_hardcode_harness_branch(self, tmp_path: pathlib.Path) -> None:
        """The rendered template must not contain the literal string 'harness' as a branch name.

        RELEASE-009 defect 3: the tag-push line must use the project's default_branch variable.
        """
        ctx = self._make_context(tmp_path)
        rendered = _render_build_template(ctx)
        # Look for patterns like 'git push origin harness' that hardcode the branch
        import re
        pattern = re.compile(r"git push origin harness")
        assert not pattern.search(rendered), (
            "Rendered CLAUDE.build.md hardcodes 'harness' as the push branch — "
            "should use default_branch variable"
        )

    def test_rendered_template_record_attempt_uses_absolute_path(self, tmp_path: pathlib.Path) -> None:
        """The record-attempt invocation in the rendered template must use the absolute path.

        RELEASE-009 defect 4: record-attempt must be dispatched via the absolute
        flex_build.py path, not a bare subcommand reference.
        """
        ctx = self._make_context(tmp_path)
        rendered = _render_build_template(ctx)
        absolute_scripts = ctx["pairmode_scripts_dir"]
        # The record-attempt line should reference absolute path/flex_build.py record-attempt
        for lineno, line in enumerate(rendered.splitlines(), 1):
            if "record-attempt" in line and "flex_build.py" in line:
                if absolute_scripts not in line:
                    raise AssertionError(
                        f"Line {lineno} has record-attempt via flex_build.py but not absolute path:\n  {line}"
                    )
                return  # found and it's correct
        # Also acceptable: no flex_build.py on the record-attempt line — means it's using
        # record_attempt.py directly or the line format differs; check for absolute path
        for lineno, line in enumerate(rendered.splitlines(), 1):
            if "record-attempt" in line:
                if absolute_scripts not in line:
                    raise AssertionError(
                        f"Line {lineno} has record-attempt without absolute scripts path:\n  {line}"
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
            "\n"
            "## Return\n"
            "\n"
            "Return contract.\n"
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

        # INFRA-293: the template now carries a "## Return" section (matching
        # the real builder.md.j2/reviewer.md.j2 shape) and the target still
        # carries the legacy "## Final output to orchestrator" heading this
        # story's alias mechanic exists to replace. The merge is therefore no
        # longer byte-identical to the target — the pre-INFRA-293 version of
        # this test asserted `merged == target_body` and that the legacy
        # heading survived verbatim, which was the very defect (E6b) this
        # story closes: a stale return contract sitting earlier in the file
        # than an appended canonical one. The legacy section is now replaced
        # in place (position preserved — it stays the terminal section, it is
        # not deleted and re-appended), and every other concept is still a
        # true no-op (nothing else appended, nothing else changed).
        assert merged.count("## Return") == 1
        assert "Final output to orchestrator" not in merged
        assert merged.split("## Return")[1].strip() == "Return contract."
        assert merged.rstrip("\n") == target_body.replace(
            "## Final output to orchestrator\n\nEnd here.",
            "## Return\n\nReturn contract.",
        ).rstrip("\n")
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

    # -----------------------------------------------------------------
    # INFRA-293: legacy-heading alias replacement (§ Ensures B)
    # -----------------------------------------------------------------

    def test_legacy_heading_replaced_in_place_no_duplicate(self) -> None:
        """B3: a target whose only return section is the legacy heading ends
        up with exactly one return section — the template's ``## Return``, at
        the legacy section's original position — and no appended duplicate."""
        target_body = (
            "\nYou are the builder.\n"
            "\n## Some other section\n\nOther content.\n"
            "\n## Final output to orchestrator\n\nBUILD-RESULT: DONE\n"
        )
        template_body = "\n## Return\n\nReturn JSON contract.\n"

        merged = _merge_body_sections(template_body, target_body)

        assert merged.count("## Return") == 1
        assert "Final output to orchestrator" not in merged
        # Position preserved: the replaced section stays after "## Some
        # other section", not appended past the end of the file.
        assert merged.index("## Some other section") < merged.index("## Return")
        assert "Return JSON contract." in merged

    def test_bespoke_section_survives_alias_replacement(self) -> None:
        """B4: a non-aliased, project-specific target section is never
        removed by a sync that also performs an alias replacement."""
        target_body = (
            "\nYou are the builder.\n"
            "\n## Project notes\n\nThis project has bespoke conventions.\n"
            "\n## Final output to orchestrator\n\nBUILD-RESULT: DONE\n"
        )
        template_body = "\n## Return\n\nReturn JSON contract.\n"

        merged = _merge_body_sections(template_body, target_body)

        assert "## Project notes" in merged
        assert "This project has bespoke conventions." in merged
        assert merged.count("## Return") == 1
        assert "Final output to orchestrator" not in merged

    def test_alias_replacement_idempotent_on_rerun(self) -> None:
        """B5: syncing an agent file that already carries `## Return` and no
        legacy heading is a no-op; re-running the merge on its own output
        produces no further change."""
        target_body = (
            "\nYou are the builder.\n"
            "\n## Final output to orchestrator\n\nBUILD-RESULT: DONE\n"
        )
        template_body = "\n## Return\n\nReturn JSON contract.\n"

        first_merge = _merge_body_sections(template_body, target_body)
        second_merge = _merge_body_sections(template_body, first_merge)

        assert second_merge == first_merge
        assert second_merge.count("## Return") == 1
        assert "Final output to orchestrator" not in second_merge

    def test_no_matching_template_section_leaves_legacy_heading_untouched(self) -> None:
        """The alias only fires when the template actually has a section for
        the aliased key; otherwise the legacy target section is preserved
        unchanged (never deleted with nothing to replace it)."""
        target_body = "\n## Final output to orchestrator\n\nBUILD-RESULT: DONE\n"
        template_body = "\n## Unrelated section\n\nUnrelated content.\n"

        merged = _merge_body_sections(template_body, target_body)

        assert "## Final output to orchestrator" in merged
        assert "BUILD-RESULT: DONE" in merged


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
    """sync-build --apply --yes rewrites CLAUDE.build.md with the thin dispatch loop.

    HARNESS-001: the thin dispatch loop template no longer contains check-stub or old
    gate-section prose. After applying, the file must:
    - Contain 'next-action' (the resolver CLI call in the thin dispatch loop).
    - Not contain the old delegation-language prose ('See phase doc').
    """
    import pytest
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

    # HARNESS-001: check-stub is no longer in the thin template; verify dispatch loop instead.
    assert "next-action" in written, (
        "Expected 'next-action' dispatch call in written CLAUDE.build.md, but not found."
    )
    assert "See phase doc" not in written, (
        "Old delegation-language prose ('See phase doc') still present in written file."
    )


# ---------------------------------------------------------------------------
# INFRA-269: audit-hooks subcommand (CER-081)
# ---------------------------------------------------------------------------


def _write_settings(project_dir: pathlib.Path, hooks: dict, extra_top_level: dict | None = None) -> pathlib.Path:
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"hooks": hooks}
    if extra_top_level:
        data.update(extra_top_level)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return settings_path


def test_audit_hooks_registered_on_group() -> None:
    """audit-hooks is registered on pairmode_cli alongside all six pre-existing names."""
    assert "audit-hooks" in pairmode_cli.commands
    for name in (
        "sync-agents",
        "sync-build",
        "sync-all",
        "register",
        "unregister",
        "list-projects",
    ):
        assert name in pairmode_cli.commands, f"{name} missing from pairmode_cli.commands"


def test_audit_hooks_dry_run_writes_nothing_and_exits_1(tmp_path: pathlib.Path) -> None:
    from click.testing import CliRunner

    settings_path = _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /b/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )
    before = settings_path.read_text(encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--dry-run"],
        catch_exceptions=False,
    )

    after = settings_path.read_text(encoding="utf-8")
    assert before == after, "dry-run must not write anything"
    assert result.exit_code == 1, f"Expected exit 1 for duplicates found, got {result.exit_code}"


def test_audit_hooks_clean_project_exits_0(tmp_path: pathlib.Path) -> None:
    """INFRA-319: the command is project-relative-absolute (under tmp_path)
    so this fixture stays clean of the new machine-absolute finding class
    too — a path outside the project dir is exactly what that class flags."""
    from click.testing import CliRunner

    _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": f"uv run python {tmp_path}/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "no duplicate" in result.output.lower()


def test_audit_hooks_apply_removes_duplicates(tmp_path: pathlib.Path) -> None:
    from click.testing import CliRunner

    settings_path = _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /b/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    pre_tool_use_list = data["hooks"]["PreToolUse"]
    all_commands = [
        h["command"] for b in pre_tool_use_list for h in b.get("hooks", [])
    ]
    assert len(all_commands) == 1, f"Expected exactly one surviving entry, got: {all_commands}"
    # No empty blocks left behind.
    assert all(b.get("hooks") for b in pre_tool_use_list)


def test_audit_hooks_apply_keeps_local_plugin_root_entry(tmp_path: pathlib.Path) -> None:
    """--apply prefers the entry whose command path is under this checkout's
    plugin root (the flex root pairmode_sync.py resolves from __file__)."""
    from click.testing import CliRunner

    flex_root = pathlib.Path(__file__).parent.parent.parent
    correct_command = f"uv run python {flex_root / 'hooks' / 'pre_tool_use.py'}"
    stale_command = "uv run python /mnt/work/flex-stale/hooks/pre_tool_use.py"

    settings_path = _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": stale_command},
                ]},
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": correct_command},
                ]},
            ]
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert correct_command in result.output

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    all_commands = [
        h["command"]
        for b in data["hooks"]["PreToolUse"]
        for h in b.get("hooks", [])
    ]
    assert all_commands == [correct_command], (
        f"Expected the plugin_root entry to survive, got: {all_commands}"
    )


def test_audit_hooks_apply_is_idempotent(tmp_path: pathlib.Path) -> None:
    from click.testing import CliRunner

    _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0

    settings_path = tmp_path / ".claude" / "settings.json"
    before = settings_path.read_text(encoding="utf-8")

    result2 = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result2.exit_code == 0
    after = settings_path.read_text(encoding="utf-8")
    assert before == after, "Second --apply run on a clean project must be byte-identical"


def test_audit_hooks_preserves_non_hook_keys(tmp_path: pathlib.Path) -> None:
    from click.testing import CliRunner

    settings_path = _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /b/hooks/pre_tool_use.py"},
                ]},
            ]
        },
        extra_top_level={
            "permissions": {"allow": ["Read(**)"]},
            "some_unknown_key": {"foo": "bar"},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["permissions"] == {"allow": ["Read(**)"]}
    assert data["some_unknown_key"] == {"foo": "bar"}


def test_audit_hooks_no_settings_file_exits_0(tmp_path: pathlib.Path) -> None:
    from click.testing import CliRunner

    settings_path = tmp_path / ".claude" / "settings.json"
    assert not settings_path.exists()

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert not settings_path.exists(), "audit-hooks must not create a settings file"
    assert "no" in result.output.lower() and "settings" in result.output.lower()


# ---------------------------------------------------------------------------
# INFRA-288 (CER-104): merged-view audit-hooks — sources in output, plugin
# entries never written
# ---------------------------------------------------------------------------


def _install_fake_plugin_hook(fake_home: pathlib.Path) -> pathlib.Path:
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
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    return plugin_file


def test_audit_hooks_reports_sources_for_cross_source_duplicate(
    tmp_path: pathlib.Path, _isolated_home: pathlib.Path
) -> None:
    """B8: the per-duplicate line names the sources the group spans."""
    from click.testing import CliRunner

    _write_settings(
        tmp_path,
        {
            "PostToolUse": [
                {"matcher": "Task|Agent", "hooks": [
                    {"type": "command",
                     "command": "uv run python /mnt/work/flex/hooks/post_tool_use.py"},
                ]},
            ]
        },
    )
    _install_fake_plugin_hook(_isolated_home)

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--dry-run"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "DUPLICATE: event=PostToolUse basename=post_tool_use.py" in result.output
    assert "sources=['settings', 'plugin']" in result.output


def test_audit_hooks_apply_keeps_plugin_entry_and_never_writes_plugin_file(
    tmp_path: pathlib.Path, _isolated_home: pathlib.Path
) -> None:
    """B9: --apply removes the settings entry; the plugin hooks.json is
    byte-for-byte unchanged."""
    from click.testing import CliRunner

    settings_path = _write_settings(
        tmp_path,
        {
            "PostToolUse": [
                {"matcher": "Task|Agent", "hooks": [
                    {"type": "command",
                     "command": "uv run python /mnt/work/flex/hooks/post_tool_use.py"},
                ]},
            ]
        },
    )
    plugin_file = _install_fake_plugin_hook(_isolated_home)
    plugin_before = plugin_file.read_bytes()

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0

    assert plugin_file.read_bytes() == plugin_before, (
        "audit-hooks --apply must never write a plugin's hooks.json"
    )

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    remaining = [
        entry.get("command")
        for block in data.get("hooks", {}).get("PostToolUse", [])
        for entry in block.get("hooks", [])
    ]
    assert remaining == [], f"settings-level duplicate must be removed, got {remaining}"


def test_audit_hooks_apply_removes_settings_local_duplicate(
    tmp_path: pathlib.Path, _isolated_home: pathlib.Path
) -> None:
    """B9: a duplicate living in settings.local.json is pruned there too."""
    from click.testing import CliRunner

    settings_path = _write_settings(
        tmp_path,
        {
            "PostToolUse": [
                {"matcher": "Task|Agent", "hooks": [
                    {"type": "command",
                     "command": "uv run python /mnt/work/flex/hooks/post_tool_use.py"},
                ]},
            ]
        },
    )
    settings_local_path = tmp_path / ".claude" / "settings.local.json"
    settings_local_path.write_text(
        json.dumps({
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Task|Agent", "hooks": [
                        {"type": "command",
                         "command": "uv run python /elsewhere/hooks/post_tool_use.py"},
                    ]},
                ]
            },
            "permissions": {"allow": ["Read(**)"]},
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    plugin_file = _install_fake_plugin_hook(_isolated_home)

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0

    local_data = json.loads(settings_local_path.read_text(encoding="utf-8"))
    local_remaining = [
        entry.get("command")
        for block in local_data.get("hooks", {}).get("PostToolUse", [])
        for entry in block.get("hooks", [])
    ]
    assert local_remaining == []
    # Keys outside "hooks" untouched.
    assert local_data["permissions"] == {"allow": ["Read(**)"]}
    # Plugin entry (the keeper) untouched.
    plugin_data = json.loads(plugin_file.read_text(encoding="utf-8"))
    assert plugin_data["hooks"]["PostToolUse"][0]["hooks"][0]["command"] == (
        "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"
    )
    # settings.json entry gone as well.
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert [
        entry.get("command")
        for block in data.get("hooks", {}).get("PostToolUse", [])
        for entry in block.get("hooks", [])
    ] == []


# ---------------------------------------------------------------------------
# CER-110: actionable vs. plugin-internal classification in audit-hooks
# ---------------------------------------------------------------------------


def _install_plugin_internal_duplicate(fake_home: pathlib.Path) -> pathlib.Path:
    """A single plugin registering the same basename twice under the *same*
    (matcher, predicate) — non-actionable, but still a surviving group
    (Ensures 8 negative control)."""
    plugin_file = (
        fake_home / ".claude" / "plugins" / "some-plugin" / "hooks" / "hooks.json"
    )
    plugin_file.parent.mkdir(parents=True)
    command = "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/dup_hook.py"
    plugin_file.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {"type": "command", "command": command},
                                {"type": "command", "command": command},
                            ],
                        }
                    ]
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return plugin_file


def test_audit_hooks_plugin_only_fleet_exits_0_with_plugin_internal_line(
    tmp_path: pathlib.Path, _isolated_home: pathlib.Path
) -> None:
    """A project whose only duplicate-hook groups are plugin-internal
    (non-actionable) prints an informational PLUGIN-INTERNAL: line and exits
    0 rather than 1 — plugin-owned registrations are reported, not gating."""
    from click.testing import CliRunner

    _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )
    _install_plugin_internal_duplicate(_isolated_home)

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--dry-run"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "PLUGIN-INTERNAL: event=PostToolUse basename=dup_hook.py" in result.output
    assert "flex never writes another install's hooks.json" in result.output
    assert "DUPLICATE:" not in result.output


def test_audit_hooks_actionable_duplicate_still_exits_1(
    tmp_path: pathlib.Path, _isolated_home: pathlib.Path
) -> None:
    """A project with both an actionable duplicate and a plugin-internal one
    still exits 1 — the actionable finding gates."""
    from click.testing import CliRunner

    _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /b/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )
    _install_plugin_internal_duplicate(_isolated_home)

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--dry-run"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "DUPLICATE: event=PreToolUse basename=pre_tool_use.py" in result.output
    assert "PLUGIN-INTERNAL: event=PostToolUse basename=dup_hook.py" in result.output


def test_audit_hooks_apply_leaves_plugin_internal_only_settings_byte_identical(
    tmp_path: pathlib.Path, _isolated_home: pathlib.Path
) -> None:
    """--apply on a project whose only group is plugin-internal must not
    touch settings.json at all: the non-actionable group never reaches the
    prune loop."""
    from click.testing import CliRunner

    settings_path = _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )
    _install_plugin_internal_duplicate(_isolated_home)
    before = settings_path.read_bytes()

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert settings_path.read_bytes() == before, (
        "settings.json must be byte-identical when the only group is "
        "plugin-internal"
    )


def test_audit_hooks_reports_cer127_shape_and_clears_when_moved_local(
    tmp_path: pathlib.Path,
) -> None:
    """C5: a committed settings.json holding the exact CER-127 shape
    (stale /mnt/work/flex-harness/hooks/* command) produces one finding with
    reason == "stale-flex-harness"; the same fixture with that entry in
    settings.local.json instead produces zero findings."""
    from click.testing import CliRunner

    settings_path = _write_settings(
        tmp_path,
        {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "uv run python /mnt/work/flex-harness/hooks/user_prompt_submit.py",
                        }
                    ]
                }
            ]
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "MACHINE-ABSOLUTE" in result.output
    assert "reason=stale-flex-harness" in result.output
    assert "to-030" in result.output

    # Move the entry to settings.local.json instead — zero findings.
    settings_local_path = tmp_path / ".claude" / "settings.local.json"
    settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
    settings_local_path.write_text(
        json.dumps(settings_data, indent=2) + "\n", encoding="utf-8"
    )
    settings_path.write_text(json.dumps({"hooks": {}}, indent=2) + "\n", encoding="utf-8")

    result2 = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path)],
        catch_exceptions=False,
    )
    assert result2.exit_code == 0
    assert "MACHINE-ABSOLUTE" not in result2.output


# ---------------------------------------------------------------------------
# INFRA-323: RESTART REQUIRED notice for sync-agents / sync-all / audit-hooks
# ---------------------------------------------------------------------------


def _sync_agents_project(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Build a minimal project + synthetic templates dir with one changed agent."""
    project_dir = tmp_path / "a" / "b" / "proj"
    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "test-agent.md").write_text(
        "---\nname: test-agent\ndescription: old\n---\n\nBody.\n", encoding="utf-8"
    )

    templates_dir = project_dir / "templates"
    templates_dir.mkdir()
    (templates_dir / "test-agent.md.j2").write_text(
        "---\nname: test-agent\ndescription: new for {{ project_name }}\n---\n\nBody.\n",
        encoding="utf-8",
    )

    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({"project_name": "test"}), encoding="utf-8"
    )
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")
    return project_dir, templates_dir


def test_sync_agents_prints_restart_notice_after_writing(tmp_path: pathlib.Path) -> None:
    import unittest.mock
    from click.testing import CliRunner

    project_dir, templates_dir = _sync_agents_project(tmp_path)

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", templates_dir):
        result = runner.invoke(
            sync_agents, ["--project-dir", str(project_dir), "--yes"]
        )

    assert result.exit_code == 0, result.output
    assert "RESTART REQUIRED" in result.output
    assert "test-agent.md" in result.output

    state = json.loads(
        (project_dir / ".companion" / "state.json").read_text(encoding="utf-8")
    )
    assert state.get("agent_surfaces_written_by") == "sync-agents"
    assert state.get("agent_surfaces_written_at")


def test_sync_agents_no_changes_prints_no_notice(tmp_path: pathlib.Path) -> None:
    from click.testing import CliRunner

    project_dir = tmp_path / "a" / "b" / "proj"
    (project_dir / ".claude" / "agents").mkdir(parents=True)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "pairmode_context.json").write_text("{}", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(sync_agents, ["--project-dir", str(project_dir), "--yes"])
    assert result.exit_code == 0, result.output
    assert "No changes to apply." in result.output
    assert "RESTART REQUIRED" not in result.output


def test_sync_agents_dry_run_prints_no_notice(tmp_path: pathlib.Path) -> None:
    import unittest.mock
    from click.testing import CliRunner

    project_dir, templates_dir = _sync_agents_project(tmp_path)

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", templates_dir):
        result = runner.invoke(
            sync_agents, ["--project-dir", str(project_dir), "--dry-run"]
        )

    assert result.exit_code == 0, result.output
    assert "RESTART REQUIRED" not in result.output


def test_sync_agents_declined_confirm_prints_no_notice(tmp_path: pathlib.Path) -> None:
    import unittest.mock
    from click.testing import CliRunner

    project_dir, templates_dir = _sync_agents_project(tmp_path)

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", templates_dir):
        result = runner.invoke(
            sync_agents, ["--project-dir", str(project_dir)], input="n\n"
        )

    assert result.exit_code == 0, result.output
    assert "Aborted." in result.output
    assert "RESTART REQUIRED" not in result.output


def test_sync_agents_stamps_state_json(tmp_path: pathlib.Path) -> None:
    import unittest.mock
    from click.testing import CliRunner

    project_dir, templates_dir = _sync_agents_project(tmp_path)

    runner = CliRunner()
    with unittest.mock.patch("pairmode_sync.TEMPLATES_DIR", templates_dir):
        result = runner.invoke(
            sync_agents, ["--project-dir", str(project_dir), "--yes"]
        )
    assert result.exit_code == 0, result.output

    state = json.loads(
        (project_dir / ".companion" / "state.json").read_text(encoding="utf-8")
    )
    assert "agent_surfaces_written_at" in state
    assert "agent_surfaces_written_by" in state


def test_sync_all_prints_exactly_one_notice_for_the_chain(tmp_path: pathlib.Path) -> None:
    """The chain's sync-agents step (mocked) stamps state.json; sync_all reads
    the stamp back once and prints exactly one notice — never one per child."""
    import unittest.mock

    project_dir = _make_deep_project_dir(tmp_path)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(json.dumps({}), encoding="utf-8")

    def _run(argv, check=False):
        if "sync-agents" in argv:
            # Simulate the real sync-agents subprocess stamping state.json.
            import session_lifecycle
            from state_utils import _atomic_write_json

            state_path = project_dir / ".companion" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            session_lifecycle.stamp_agent_surfaces(
                state, changed=[".claude/agents/builder.md"], action="sync-agents"
            )
            _atomic_write_json(state_path, state)
        result = unittest.mock.MagicMock()
        result.returncode = 0
        return result

    result = _run_sync_all(["--project-dir", str(project_dir), "--apply"], _run)

    assert result.exit_code == 0, result.output
    assert result.output.count("RESTART REQUIRED") == 1, result.output


def test_sync_all_reads_stamp_rather_than_parsing_child_output(
    tmp_path: pathlib.Path,
) -> None:
    """A child that prints RESTART REQUIRED to its own inherited stdout (but
    never touches the stamp) must not trigger sync_all's own notice — the
    aggregation reads the state.json stamp, never child stdout."""
    project_dir = _make_deep_project_dir(tmp_path)
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(json.dumps({}), encoding="utf-8")

    mock_run, _calls = _capturing_run([0, 0, 0])

    result = _run_sync_all(["--project-dir", str(project_dir), "--apply"], mock_run)

    assert result.exit_code == 0, result.output
    assert "RESTART REQUIRED" not in result.output


def test_sync_build_only_prints_no_notice(tmp_path: pathlib.Path) -> None:
    """sync-build alone never emits a restart notice — CLAUDE.build.md is
    read per build-loop invocation, not at session start (§ D22)."""
    from click.testing import CliRunner
    from pairmode_sync import sync_build

    project_dir = tmp_path / "a" / "b" / "proj"
    project_dir.mkdir(parents=True)
    (project_dir / "CLAUDE.build.md").write_text("stub\n", encoding="utf-8")
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(json.dumps({}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        sync_build,
        ["--project-dir", str(project_dir), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert "RESTART REQUIRED" not in result.output


def test_audit_hooks_apply_prints_notice_naming_hook_registration(
    tmp_path: pathlib.Path,
) -> None:
    from click.testing import CliRunner

    _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /b/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(json.dumps({}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path), "--apply", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "RESTART REQUIRED" in result.output
    assert "hook_registration" in result.output


def test_audit_hooks_dry_run_prints_no_notice(tmp_path: pathlib.Path) -> None:
    from click.testing import CliRunner

    _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /a/hooks/pre_tool_use.py"},
                ]},
                {"matcher": "Task", "hooks": [
                    {"type": "command", "command": "uv run python /b/hooks/pre_tool_use.py"},
                ]},
            ]
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        pairmode_cli,
        ["audit-hooks", "--project-dir", str(tmp_path)],
        catch_exceptions=False,
    )
    assert "RESTART REQUIRED" not in result.output

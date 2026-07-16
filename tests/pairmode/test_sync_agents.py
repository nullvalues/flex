"""Tests for skills/pairmode/scripts/pairmode_sync.py."""

from __future__ import annotations

import json
import pathlib
import sys
import textwrap

import pytest
from click.testing import CliRunner

# Add scripts dir for direct import
sys.path.insert(
    0,
    str(pathlib.Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"),
)

from pairmode_sync import (  # noqa: E402
    sync_agents,
    _split_agent_file,
    _extract_frontmatter_block,
    _get_project_name,
    _collect_changes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
TEMPLATES_DIR = _REPO_ROOT / "skills" / "pairmode" / "templates" / "agents"


def _make_project(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a minimal pairmode project structure under tmp_path."""
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".companion").mkdir(parents=True)
    return tmp_path


def _write_state(project_dir: pathlib.Path, state: dict) -> None:
    state_path = project_dir / ".companion" / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")


def _write_agent(project_dir: pathlib.Path, filename: str, content: str) -> pathlib.Path:
    path = project_dir / ".claude" / "agents" / filename
    path.write_text(content, encoding="utf-8")
    return path


def _write_template(templates_dir: pathlib.Path, filename: str, content: str) -> pathlib.Path:
    templates_dir.mkdir(parents=True, exist_ok=True)
    path = templates_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def _invoke(project_dir: pathlib.Path, extra_args: list[str] | None = None):
    runner = CliRunner()
    args = ["--project-dir", str(project_dir)]
    if extra_args:
        args.extend(extra_args)
    return runner.invoke(sync_agents, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


def test_split_agent_file_happy_path():
    """Standard agent file splits into frontmatter + body correctly."""
    content = "---\nname: builder\nmodel: sonnet\n---\n\nBody text here.\n"
    result = _split_agent_file(content)
    assert result is not None
    frontmatter, body = result
    # frontmatter includes the trailing newline of the closing '---' line
    assert frontmatter == "---\nname: builder\nmodel: sonnet\n---\n"
    assert body == "\nBody text here.\n"


def test_split_agent_file_no_frontmatter():
    """File not starting with '---' returns None."""
    content = "Just a plain markdown file.\n"
    assert _split_agent_file(content) is None


def test_split_agent_file_no_closing_delimiter():
    """File starting with '---' but missing closing '---' returns None."""
    content = "---\nname: builder\nno closing delimiter\n"
    assert _split_agent_file(content) is None


def test_extract_frontmatter_block_happy_path():
    """Frontmatter block extracted correctly from rendered template output."""
    rendered = "---\nname: builder\nmodel: sonnet\n---\n\nBody content.\n"
    result = _extract_frontmatter_block(rendered)
    # The block includes lines up to and including the closing '---\n'
    assert result == "---\nname: builder\nmodel: sonnet\n---\n"


def test_extract_frontmatter_block_no_opening():
    """ValueError raised when rendered output does not start with '---'."""
    with pytest.raises(ValueError, match="does not start with"):
        _extract_frontmatter_block("No frontmatter here\n")


def test_extract_frontmatter_block_no_closing():
    """ValueError raised when no closing '---' is found."""
    with pytest.raises(ValueError, match="no closing"):
        _extract_frontmatter_block("---\nname: builder\nno closing\n")


# ---------------------------------------------------------------------------
# Integration tests using CLI runner
# ---------------------------------------------------------------------------


def test_happy_path_frontmatter_updated_body_preserved(tmp_path: pathlib.Path):
    """Core happy path: frontmatter updated from template; body preserved."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"

    # Create a template
    _write_template(
        templates_dir,
        "builder.md.j2",
        "---\nname: builder\ndescription: Agent for {{ project_name }}.\nmodel: sonnet\n---\n",
    )

    # Create an existing agent file with different frontmatter but same body
    old_agent_content = (
        "---\nname: builder\ndescription: Agent for OLD_PROJECT.\nmodel: haiku\n---\n\nBody text.\n"
    )
    agent_file = _write_agent(project_dir, "builder.md", old_agent_content)

    # Patch TEMPLATES_DIR in the module to use our fake dir
    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        _write_state(project_dir, {"project_name": "myproject"})
        result = _invoke(project_dir, ["--yes"])
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0, result.output

    # Check file was updated
    new_content = agent_file.read_text(encoding="utf-8")
    assert "myproject" in new_content
    # Body must be preserved
    assert "Body text." in new_content
    # Old frontmatter value should be gone
    assert "haiku" not in new_content
    assert "OLD_PROJECT" not in new_content


def test_no_matching_template_skips_with_warning(tmp_path: pathlib.Path):
    """Agent file with no matching template is skipped with a warning on stderr."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"
    templates_dir.mkdir()
    # No template for "custom_agent"

    _write_agent(
        project_dir,
        "custom_agent.md",
        "---\nname: custom_agent\n---\n\nBody.\n",
    )

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        result = _invoke(project_dir)
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    # Should exit 0 with "No changes to apply."
    assert result.exit_code == 0, result.output
    assert "No changes to apply." in result.output


def test_no_matching_template_warning_on_stderr(tmp_path: pathlib.Path):
    """Warning about missing template is printed (captured in output by Click runner)."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"
    templates_dir.mkdir()

    _write_agent(
        project_dir,
        "custom_agent.md",
        "---\nname: custom_agent\n---\n\nBody.\n",
    )

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        result = _invoke(project_dir)
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0, result.output
    # Warning appears in combined output (Click mixes stdout/stderr in test runner)
    assert "no template found" in result.output


def test_dry_run_does_not_write(tmp_path: pathlib.Path):
    """--dry-run prints diffs but does not modify any file on disk."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"

    _write_template(
        templates_dir,
        "builder.md.j2",
        "---\nname: builder\ndescription: Agent for {{ project_name }}.\nmodel: sonnet\n---\n",
    )

    old_content = "---\nname: builder\ndescription: Agent for OLD.\nmodel: haiku\n---\n\nBody.\n"
    agent_file = _write_agent(project_dir, "builder.md", old_content)

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        result = _invoke(project_dir, ["--dry-run"])
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0, result.output
    # Diff output should be present
    assert "---" in result.output or "-" in result.output

    # File on disk must remain unchanged
    assert agent_file.read_text(encoding="utf-8") == old_content


def test_yes_flag_writes_without_prompt(tmp_path: pathlib.Path):
    """--yes writes files without prompting for confirmation."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"

    _write_template(
        templates_dir,
        "reviewer.md.j2",
        "---\nname: reviewer\ndescription: Reviewer for {{ project_name }}.\nmodel: sonnet\n---\n",
    )

    old_content = (
        "---\nname: reviewer\ndescription: Reviewer for OLD.\nmodel: haiku\n---\n\nReviewer body.\n"
    )
    agent_file = _write_agent(project_dir, "reviewer.md", old_content)

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        result = _invoke(project_dir, ["--yes"])
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0, result.output

    new_content = agent_file.read_text(encoding="utf-8")
    # File was written (different from original)
    assert new_content != old_content
    # Body preserved
    assert "Reviewer body." in new_content
    # No prompt in output
    assert "Apply these changes?" not in result.output


def test_agent_file_no_frontmatter_warns_and_skips(tmp_path: pathlib.Path):
    """Agent file with no frontmatter block warns and skips; no crash."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"

    _write_template(
        templates_dir,
        "builder.md.j2",
        "---\nname: builder\ndescription: Agent for {{ project_name }}.\nmodel: sonnet\n---\n",
    )

    # Agent file with no frontmatter (no '---')
    no_fm_content = "Just plain markdown without any frontmatter.\nBody text here.\n"
    agent_file = _write_agent(project_dir, "builder.md", no_fm_content)

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        result = _invoke(project_dir)
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0, result.output
    assert "No changes to apply." in result.output

    # File must be unchanged
    assert agent_file.read_text(encoding="utf-8") == no_fm_content


def test_agent_file_no_frontmatter_warning_on_stderr(tmp_path: pathlib.Path):
    """Warning for no-frontmatter file appears in output (Click mixes stdout/stderr)."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"

    _write_template(
        templates_dir,
        "builder.md.j2",
        "---\nname: builder\ndescription: Agent for {{ project_name }}.\nmodel: sonnet\n---\n",
    )

    _write_agent(project_dir, "builder.md", "No frontmatter here.\n")

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        result = _invoke(project_dir)
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0
    assert "no frontmatter" in result.output


def test_no_changes_prints_message_and_exits_0(tmp_path: pathlib.Path):
    """When no files would change, prints 'No changes to apply.' and exits 0."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"

    # Template and agent file with identical frontmatter (after rendering)
    template_content = (
        "---\nname: builder\ndescription: Agent for {{ project_name }}.\nmodel: sonnet\n---\n"
    )
    _write_template(templates_dir, "builder.md.j2", template_content)

    # Agent file already matches what the template would produce
    agent_content = (
        "---\nname: builder\ndescription: Agent for myproject.\nmodel: sonnet\n---\n\nBody.\n"
    )
    _write_agent(project_dir, "builder.md", agent_content)
    _write_state(project_dir, {"project_name": "myproject"})

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        result = _invoke(project_dir)
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0, result.output
    assert "No changes to apply." in result.output


def test_project_name_falls_back_to_dir_name(tmp_path: pathlib.Path):
    """When state.json has no project_name, falls back to project_dir.name."""
    project_dir = _make_project(tmp_path)
    templates_dir = tmp_path / "fake_templates"

    _write_template(
        templates_dir,
        "builder.md.j2",
        "---\nname: builder\ndescription: Agent for {{ project_name }}.\nmodel: sonnet\n---\n",
    )

    old_content = "---\nname: builder\ndescription: Agent for OLD.\nmodel: haiku\n---\n\nBody.\n"
    agent_file = _write_agent(project_dir, "builder.md", old_content)

    # state.json with no project_name
    _write_state(project_dir, {"pairmode_version": "1.0"})

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = templates_dir

    try:
        result = _invoke(project_dir, ["--yes"])
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0, result.output
    new_content = agent_file.read_text(encoding="utf-8")
    # Should use directory name (tmp_path name, set by pytest to something unique)
    assert project_dir.name in new_content


# ---------------------------------------------------------------------------
# CER-019: _get_project_name embedded newline sanitization
# ---------------------------------------------------------------------------


def test_get_project_name_strips_embedded_newlines(tmp_path: pathlib.Path):
    """Embedded newlines in state project_name are stripped (CER-019).

    A project_name of "foo\\nmodel: opus" must return "foomodel: opus",
    not two lines that could inject extra YAML frontmatter keys.
    """
    project_dir = tmp_path
    state = {"project_name": "foo\nmodel: opus"}
    result = _get_project_name(project_dir, state)
    assert result == "foomodel: opus"
    assert "\n" not in result


def test_get_project_name_strips_embedded_carriage_returns(tmp_path: pathlib.Path):
    """Embedded carriage-returns in state project_name are stripped (CER-019)."""
    project_dir = tmp_path
    state = {"project_name": "foo\rmodel: opus"}
    result = _get_project_name(project_dir, state)
    assert result == "foomodel: opus"
    assert "\r" not in result


def test_get_project_name_strips_mixed_newlines(tmp_path: pathlib.Path):
    """Both \\n and \\r embedded in project_name are stripped (CER-019)."""
    project_dir = tmp_path
    state = {"project_name": "my\r\nproject"}
    result = _get_project_name(project_dir, state)
    assert result == "myproject"
    assert "\n" not in result
    assert "\r" not in result


def test_get_project_name_plain_name_unaffected(tmp_path: pathlib.Path):
    """A clean project_name without newlines is returned as-is (minus strip)."""
    project_dir = tmp_path
    state = {"project_name": "  myproject  "}
    result = _get_project_name(project_dir, state)
    assert result == "myproject"


def test_get_project_name_fallback_strips_newlines(tmp_path: pathlib.Path):
    """Fallback to project_dir.name also applies newline stripping (CER-019 consistency)."""
    project_dir = tmp_path
    state = {}
    result = _get_project_name(project_dir, state)
    # project_dir.name on Linux cannot contain '\n', but the sanitization
    # is applied for consistency — verify it produces a clean string.
    assert "\n" not in result
    assert "\r" not in result
    assert result == project_dir.resolve().name


def test_collect_changes_reviewer_shaped_body_no_duplicate_checklist(tmp_path: pathlib.Path):
    """CLI-level regression for INFRA-202 (85a6f52 incident).

    A synthetic reviewer-shaped agent file whose checklist items are expressed
    as ``**N. TITLE**`` pseudo-headers, merged against a synthetic template
    that carries the equivalent items as ``## N. Title`` sections, must not
    produce a ``new_content`` with any duplicated canonical checklist item.
    """
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    templates_dir = tmp_path / "fake_templates"
    templates_dir.mkdir()

    agent_content = (
        "---\n"
        "name: reviewer\n"
        "description: Reviewer for {{ project_name }}.\n"
        "model: sonnet\n"
        "---\n"
        "\n"
        "You are the reviewer.\n"
        "\n"
        "## Review checklist\n"
        "\n"
        "**1. HOOK PERFORMANCE**\n"
        "Hook content.\n"
        "\n"
        "**7. PROTECTED FILES**\n"
        "Protected content.\n"
        "\n"
        "## Final output to orchestrator\n"
        "\n"
        "End here.\n"
    )
    (agents_dir / "reviewer.md").write_text(agent_content, encoding="utf-8")

    template_content = (
        "---\n"
        "name: reviewer\n"
        "description: Reviewer for {{ project_name }}.\n"
        "model: sonnet\n"
        "---\n"
        "\n"
        "You are the reviewer.\n"
        "\n"
        "## Review checklist\n"
        "\n"
        "## 1. Hook performance\n"
        "\n"
        "Hook content.\n"
        "\n"
        "## 9. Protected files\n"
        "\n"
        "Protected content.\n"
        "\n"
        "## Final output to orchestrator\n"
        "\n"
        "End here.\n"
    )
    _write_template(templates_dir, "reviewer.md.j2", template_content)

    context = {"project_name": "myproject"}
    changes, render_errors = _collect_changes(agents_dir, templates_dir, context)

    assert render_errors == []
    if changes:
        _agent_file, _old_content, new_content = changes[0]
        assert new_content.lower().count("hook performance") <= 1
        assert new_content.lower().count("protected files") <= 1


def test_no_agents_dir_returns_no_changes(tmp_path: pathlib.Path):
    """When .claude/agents/ does not exist, 'No changes to apply.' is printed."""
    # No .claude/agents/ directory
    tmp_path.mkdir(exist_ok=True)

    import pairmode_sync as ps
    original_templates_dir = ps.TEMPLATES_DIR
    ps.TEMPLATES_DIR = tmp_path / "fake_templates"

    runner = CliRunner()
    try:
        result = runner.invoke(
            sync_agents,
            ["--project-dir", str(tmp_path)],
            catch_exceptions=False,
        )
    finally:
        ps.TEMPLATES_DIR = original_templates_dir

    assert result.exit_code == 0, result.output
    assert "No changes to apply." in result.output

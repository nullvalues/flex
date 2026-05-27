# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "jinja2"]
# ///
"""
pairmode_sync.py — Re-render agent file frontmatter from canonical templates.

``sync-agents`` walks ``.claude/agents/`` in a target project, finds the
matching Jinja2 template in ``skills/pairmode/templates/agents/`` for each
agent file, renders only the frontmatter block, and replaces the frontmatter
in the target file while preserving the body.

``sync-build`` compares the target project's ``CLAUDE.build.md`` against the
canonical ``CLAUDE.build.md.j2`` template rendered with the project's
``state.json``.  With ``--apply``, it writes the rendered template.

Usage:
    uv run python skills/pairmode/scripts/pairmode_sync.py sync-agents \\
        [--project-dir DIR] [--dry-run] [--yes]

    uv run python skills/pairmode/scripts/pairmode_sync.py sync-build \\
        --project-dir DIR [--dry-run] [--apply] [--yes]
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

# Allow running directly and as a module import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import click
import jinja2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pairmode templates root — parents[1] of this script == skills/pairmode/
_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"

# Path to agent templates directory, relative to this script's location:
#   skills/pairmode/scripts/pairmode_sync.py
#   parents[0] = skills/pairmode/scripts/
#   parents[1] = skills/pairmode/
TEMPLATES_DIR = _TEMPLATES_ROOT / "agents"

# Path to the canonical CLAUDE.build.md Jinja2 template
BUILD_TEMPLATE_PATH = _TEMPLATES_ROOT / "CLAUDE.build.md.j2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_state(project_dir: Path) -> dict:
    """Read .companion/state.json; return empty dict if missing or malformed."""
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_pairmode_context(project_dir: Path) -> dict:
    """Read .companion/pairmode_context.json; return empty dict if missing or malformed."""
    ctx_path = project_dir / ".companion" / "pairmode_context.json"
    if not ctx_path.exists():
        return {}
    try:
        return json.loads(ctx_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _get_project_name(project_dir: Path, state: dict) -> str:
    """Return project_name for template rendering.

    Tries state["project_name"] first; falls back to project_dir.name.
    Strips leading/trailing whitespace and removes embedded newline/carriage-return
    characters to prevent YAML injection when the value is rendered into agent
    file frontmatter (CER-019).
    """
    name = state.get("project_name")
    if isinstance(name, str) and name.strip():
        return name.strip().replace("\n", "").replace("\r", "")
    return project_dir.resolve().name.replace("\n", "").replace("\r", "")


def _render_template_frontmatter(template_path: Path, context: dict) -> str:
    """Render *template_path* with *context* and extract only the frontmatter.

    Returns the frontmatter block including both ``---`` delimiters.
    Raises ``ValueError`` if the rendered output has no frontmatter block.
    """
    loader = jinja2.FileSystemLoader(str(template_path.parent))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)
    rendered = template.render(**context)

    return _extract_frontmatter_block(rendered, source=template_path.name)


def _extract_frontmatter_block(text: str, source: str = "<input>") -> str:
    """Extract the frontmatter block (``---`` … ``---``) from *text*.

    Returns the substring from the first ``---`` to and including the closing
    ``---`` (both delimiters).  Raises ``ValueError`` if the block cannot be
    found.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValueError(f"{source}: rendered output does not start with '---'")

    # Find the closing '---' starting from line index 1
    close_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            close_idx = i
            break

    if close_idx is None:
        raise ValueError(f"{source}: no closing '---' found in rendered frontmatter")

    return "".join(lines[: close_idx + 1])


def _split_agent_file(text: str) -> tuple[str, str] | None:
    """Split an agent file into (frontmatter_block, body).

    The frontmatter block includes both ``---`` delimiters.
    The body is everything after the second ``---`` (including the leading
    newline).

    Returns ``None`` if the file has no valid frontmatter block (no ``---``
    start or no closing ``---``).
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None

    close_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            close_idx = i
            break

    if close_idx is None:
        return None

    frontmatter = "".join(lines[: close_idx + 1])
    body = "".join(lines[close_idx + 1 :])
    return frontmatter, body


def _parse_body_sections(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse a body string into a preamble and a list of (heading_line, content) sections.

    The preamble is all content before the first ``## `` heading.
    Each section is a tuple of (heading_line, content) where:
    - ``heading_line`` is the full line starting with ``## `` (including newline)
    - ``content`` is the text that follows the heading, up to the next ``## `` heading

    Returns (preamble, sections).
    """
    lines = body.splitlines(keepends=True)
    preamble_lines: list[str] = []
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_content_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, "".join(current_content_lines)))
            elif current_content_lines:
                preamble_lines.extend(current_content_lines)
                current_content_lines = []
            else:
                # no content yet — flush preamble_lines from before first heading
                pass
            current_heading = line
            current_content_lines = []
        else:
            current_content_lines.append(line)

    # Flush the last section or remaining preamble content
    if current_heading is not None:
        sections.append((current_heading, "".join(current_content_lines)))
    else:
        preamble_lines.extend(current_content_lines)

    return "".join(preamble_lines), sections


def _merge_body_sections(template_body: str, target_body: str) -> str:
    """Merge new H2 sections from *template_body* into *target_body*, additively.

    Sections present in the template but absent from the target are appended to
    the target.  Sections already present in the target are left untouched.
    Sections in the target that are absent from the template are preserved
    (project-specific additions are never removed).

    Returns the merged target body.
    """
    _template_preamble, template_sections = _parse_body_sections(template_body)
    _target_preamble, target_sections = _parse_body_sections(target_body)

    # Build the set of heading lines already present in the target
    target_headings: set[str] = {heading for heading, _content in target_sections}

    # Collect template sections not present in the target
    sections_to_add: list[tuple[str, str]] = [
        (heading, content)
        for heading, content in template_sections
        if heading not in target_headings
    ]

    if not sections_to_add:
        return target_body

    # Append missing sections to the target body, each preceded by a blank line
    merged = target_body
    # Ensure the body ends with a newline before appending
    if merged and not merged.endswith("\n"):
        merged += "\n"
    for heading, content in sections_to_add:
        merged += "\n" + heading + content

    return merged


def _render_full_template(template_path: Path, context: dict) -> str:
    """Render *template_path* with *context* and return the full rendered output.

    Unlike ``_render_template_frontmatter``, this returns the entire rendered
    file including both frontmatter and body.
    Raises ``ValueError`` if the template cannot be rendered.
    """
    loader = jinja2.FileSystemLoader(str(template_path.parent))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)
    return template.render(**context)


# ---------------------------------------------------------------------------
# sync-build helpers
# ---------------------------------------------------------------------------


def _build_template_context(project_dir: Path) -> dict:
    """Build the Jinja2 context for rendering CLAUDE.build.md.j2.

    Merges state.json and pairmode_context.json, with graceful fallbacks
    for every key the template uses.
    """
    state = _load_state(project_dir)
    pctx = _load_pairmode_context(project_dir)

    # project_name: prefer state.json, then pairmode_context.json, then dir name
    project_name = state.get("project_name") or pctx.get("project_name") or ""
    if not isinstance(project_name, str) or not project_name.strip():
        project_name = project_dir.resolve().name
    else:
        project_name = project_name.strip().replace("\n", "").replace("\r", "")

    return {
        "project_name": project_name,
        "build_command": pctx.get("build_command") or state.get("build_command") or "",
        "test_command": pctx.get("test_command") or state.get("test_command") or "",
        "migration_command": pctx.get("migration_command") or state.get("migration_command") or "",
        "pairmode_scripts_dir": str(Path(__file__).parent),
        "domain_isolation_rule": pctx.get("domain_isolation_rule") or state.get("domain_isolation_rule") or "",
        "protected_paths": pctx.get("protected_paths") or state.get("protected_paths") or [],
    }


def _render_build_template(context: dict) -> str:
    """Render the canonical CLAUDE.build.md.j2 template with *context*.

    Returns the rendered string.
    Raises ``ValueError`` if the template cannot be rendered.
    """
    loader = jinja2.FileSystemLoader(str(BUILD_TEMPLATE_PATH.parent))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.Undefined,  # silently treat missing vars as empty
        keep_trailing_newline=True,
    )
    try:
        template = env.get_template(BUILD_TEMPLATE_PATH.name)
        return template.render(**context)
    except jinja2.TemplateError as exc:
        raise ValueError(f"Failed to render {BUILD_TEMPLATE_PATH.name}: {exc}") from exc


def _depth_guard_sync_build(project_dir: Path) -> None:
    """Reject project_dir paths with fewer than 3 components (containment guard).

    Raises SystemExit(1) when the path is too shallow.
    """
    if not project_dir.is_dir() or len(project_dir.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {project_dir}",
            err=True,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------


def _collect_changes(
    agents_dir: Path,
    templates_dir: Path,
    context: dict,
) -> list[tuple[Path, str, str]]:
    """Return a list of (agent_file, old_content, new_content) for changed files.

    Warnings about skipped files are printed to stderr.
    """
    if not agents_dir.is_dir():
        return []

    changes: list[tuple[Path, str, str]] = []

    for agent_file in sorted(agents_dir.glob("*.md")):
        stem = agent_file.stem  # e.g. "builder"
        template_path = templates_dir / f"{stem}.md.j2"

        if not template_path.exists():
            click.echo(
                f"warning: no template found for {agent_file.name} "
                f"(expected {template_path.name}) — skipping",
                err=True,
            )
            continue

        old_content = agent_file.read_text(encoding="utf-8")

        # Check that the agent file has a frontmatter block
        parts = _split_agent_file(old_content)
        if parts is None:
            click.echo(
                f"warning: {agent_file.name} has no frontmatter block — skipping",
                err=True,
            )
            continue

        old_frontmatter, body = parts

        # Render the new frontmatter from the template
        try:
            new_frontmatter = _render_template_frontmatter(template_path, context)
        except (jinja2.TemplateError, ValueError) as exc:
            click.echo(
                f"warning: failed to render template {template_path.name}: {exc} — skipping",
                err=True,
            )
            continue

        # Render the full template and extract its body for section merging
        try:
            full_rendered = _render_full_template(template_path, context)
            template_parts = _split_agent_file(full_rendered)
            template_body = template_parts[1] if template_parts is not None else ""
        except (jinja2.TemplateError, ValueError):
            # If we can't render the full template, fall back to no body merging
            template_body = ""

        # Merge new H2 sections from the template body into the target body
        merged_body = _merge_body_sections(template_body, body)

        new_content = new_frontmatter + merged_body

        if new_content != old_content:
            changes.append((agent_file, old_content, new_content))

    return changes


def _print_diff(agent_file: Path, old_content: str, new_content: str) -> None:
    """Print a unified diff for the given file change."""
    filename = agent_file.name
    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=filename,
        tofile=filename,
    )
    click.echo("".join(diff), nl=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("sync-agents")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Project root (defaults to current directory).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print diffs without writing any files.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Write files without prompting for confirmation.",
)
def sync_agents(project_dir: str, dry_run: bool, yes: bool) -> None:
    """Re-render agent file frontmatter from canonical pairmode templates.

    For each agent file found in <project-dir>/.claude/agents/, finds the
    matching template in skills/pairmode/templates/agents/ by filename stem,
    renders the template frontmatter, and replaces the frontmatter in the
    target file while preserving the body.

    With --dry-run, prints diffs without writing. With --yes, writes without
    prompting. Otherwise, prompts once before writing all changes.
    """
    project_path = Path(project_dir).resolve()
    _depth_guard_sync_build(project_path)
    agents_dir = project_path / ".claude" / "agents"

    context = _build_template_context(project_path)

    changes = _collect_changes(agents_dir, TEMPLATES_DIR, context)

    if not changes:
        click.echo("No changes to apply.")
        return

    # Print diffs for all changed files
    for agent_file, old_content, new_content in changes:
        _print_diff(agent_file, old_content, new_content)

    if dry_run:
        return

    # Prompt once if needed
    if not yes:
        confirmed = click.confirm("Apply these changes? [y/N]", default=False, prompt_suffix="")
        if not confirmed:
            click.echo("Aborted.")
            return

    # Write all changed files
    for agent_file, _old, new_content in changes:
        agent_file.write_text(new_content, encoding="utf-8")
        click.echo(f"  updated: {agent_file.name}")


@click.command("sync-build")
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Project root containing CLAUDE.build.md.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the diff and exit without writing.",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Write the rendered template to CLAUDE.build.md.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation when --apply is set.",
)
def sync_build(project_dir: str, dry_run: bool, apply: bool, yes: bool) -> None:
    """Compare and optionally update CLAUDE.build.md from the canonical template.

    Renders skills/pairmode/templates/CLAUDE.build.md.j2 with the project's
    state.json variables and diffs the result against the project's current
    CLAUDE.build.md.

    With --dry-run: print the diff and exit 0 without writing.
    With --apply: print the diff, optionally prompt, then write the file.
    Without --apply: print the diff and exit 0 (same as --dry-run).
    With --apply --yes: write without prompting.
    """
    project_path = Path(project_dir).resolve()

    # Containment guard — consistent with all other pairmode entry points
    _depth_guard_sync_build(project_path)

    build_file = project_path / "CLAUDE.build.md"

    # Build template context from state.json + pairmode_context.json
    context = _build_template_context(project_path)

    # Render the canonical template
    try:
        rendered = _render_build_template(context)
    except ValueError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    # Read existing file; treat missing as empty
    if build_file.exists():
        existing = build_file.read_text(encoding="utf-8")
    else:
        existing = ""

    # Compute the unified diff
    diff_lines = list(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            rendered.splitlines(keepends=True),
            fromfile="CLAUDE.build.md",
            tofile="CLAUDE.build.md (rendered)",
        )
    )

    if not diff_lines:
        click.echo("No changes to apply.")
        return

    # Print the diff
    click.echo("".join(diff_lines), nl=False)

    # --dry-run or no --apply: exit without writing
    if dry_run or not apply:
        return

    # --apply path: prompt unless --yes
    if not yes:
        confirmed = click.confirm("Apply? [y/N]", default=False, prompt_suffix="")
        if not confirmed:
            click.echo("Aborted.")
            return

    build_file.write_text(rendered, encoding="utf-8")
    click.echo(f"  updated: {build_file.name}")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group("pairmode")
def pairmode_cli() -> None:
    """pairmode sync subcommands."""


pairmode_cli.add_command(sync_agents)
pairmode_cli.add_command(sync_build)

# Register the register/unregister/list-projects commands from pairmode_register.py
from pairmode_register import register, unregister, list_projects  # noqa: E402

pairmode_cli.add_command(register)
pairmode_cli.add_command(unregister)
pairmode_cli.add_command(list_projects)


if __name__ == "__main__":
    pairmode_cli()

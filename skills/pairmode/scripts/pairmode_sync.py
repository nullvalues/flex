"""
pairmode_sync.py — Re-render agent file frontmatter from canonical templates.

``sync-agents`` walks ``.claude/agents/`` in a target project, finds the
matching Jinja2 template in ``skills/pairmode/templates/agents/`` for each
agent file, renders only the frontmatter block, and replaces the frontmatter
in the target file while preserving the body.

Usage:
    uv run python skills/pairmode/scripts/pairmode_sync.py sync-agents \\
        [--project-dir DIR] [--dry-run] [--yes]
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

# Path to agent templates directory, relative to this script's location:
#   skills/pairmode/scripts/pairmode_sync.py
#   parents[0] = skills/pairmode/scripts/
#   parents[1] = skills/pairmode/
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "agents"


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

        new_content = new_frontmatter + body

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
    agents_dir = project_path / ".claude" / "agents"

    state = _load_state(project_path)
    project_name = _get_project_name(project_path, state)
    context = {"project_name": project_name}

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


if __name__ == "__main__":
    sync_agents()

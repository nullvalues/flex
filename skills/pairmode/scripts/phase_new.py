"""
phase_new.py — Lazy phase scaffolding for pairmode projects.

Creates a new per-phase prompt file and updates docs/phases/index.md.
Running it twice with the same phase ID is idempotent (warns, does not overwrite).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Insert anchor repo root so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import click
import jinja2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_env() -> jinja2.Environment:
    """Return a Jinja2 environment pointing at the canonical templates dir."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )


def _read_phase_title(phase_file: Path, phase_id: int) -> str:
    """Extract the phase title from an existing phase file.

    Tries to match a ``# Phase N: <title>`` heading first, then falls back to
    ``### Story`` heading extraction.  If nothing matches, returns the generic
    fallback ``"Phase N"``.
    """
    try:
        text = phase_file.read_text(encoding="utf-8")
    except OSError:
        return f"Phase {phase_id}"

    # Try: # <project> — Phase N: <title>  OR  # Phase N: <title>
    m = re.search(r"#\s+.*Phase\s+\d+[:\s]+(.+)", text)
    if m:
        return m.group(1).strip()

    # Fallback
    return f"Phase {phase_id}"


def _append_index_row(index_path: Path, phase_id: int, phase_title: str) -> None:
    """Append a new row to the phases table in an existing index.md."""
    content = index_path.read_text(encoding="utf-8")
    row = f"| {phase_id} | {phase_title} | planned | [phase-{phase_id}.md](phase-{phase_id}.md) |"

    # Find the end of the table and append
    lines = content.splitlines(keepends=True)
    new_lines = []
    table_found = False
    inserted = False

    for line in lines:
        new_lines.append(line)
        # Detect table rows (lines starting with |)
        if line.startswith("|") and not inserted:
            table_found = True
        elif table_found and not line.startswith("|") and not inserted:
            # We just left the table — insert before this blank line
            new_lines.insert(-1, row + "\n")
            inserted = True

    if not inserted:
        # Table runs to end of file
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(row + "\n")

    index_path.write_text("".join(new_lines), encoding="utf-8")


def _create_index(index_path: Path, phase_id: int, phase_title: str) -> None:
    """Create a brand-new index.md from the index template."""
    env = _load_env()
    tmpl = env.get_template("docs/phases/index.md.j2")
    phases = [
        {
            "id": phase_id,
            "title": phase_title,
            "status": "planned",
            "file": f"phase-{phase_id}.md",
        }
    ]
    # project_name is unknown here; use a placeholder
    content = tmpl.render(project_name="project", phases=phases)
    index_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("phase_new")
@click.option(
    "--project-dir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Root directory of the target project.",
)
@click.option(
    "--phase-id",
    required=True,
    type=int,
    help="Integer phase number (e.g. 3).",
)
@click.option(
    "--title",
    default=None,
    help="Phase title. Prompted if omitted.",
)
@click.option(
    "--goal",
    default=None,
    help="Phase goal. Prompted if omitted (blank is acceptable).",
)
def phase_new(project_dir: str, phase_id: int, title: str | None, goal: str | None) -> None:
    """Create a new phase-N.md scaffold and update docs/phases/index.md."""
    project_path = Path(project_dir).resolve()
    phases_dir = project_path / "docs" / "phases"

    # 1. Ensure docs/phases/ exists
    phases_dir.mkdir(parents=True, exist_ok=True)

    # 2. Idempotency check
    phase_file = phases_dir / f"phase-{phase_id}.md"
    if phase_file.exists():
        click.echo(
            f"Warning: phase-{phase_id}.md already exists. Skipping (idempotent).",
            err=False,
        )
        return

    # 3. Prompt for missing values
    if title is None:
        title = click.prompt(f"Phase {phase_id} title", default="")
    if goal is None:
        goal = click.prompt(f"Phase {phase_id} goal (blank is OK)", default="")

    # 4. Determine prev_phase
    prev_phase = None
    if phase_id > 1:
        prev_file = phases_dir / f"phase-{phase_id - 1}.md"
        if prev_file.exists():
            prev_title = _read_phase_title(prev_file, phase_id - 1)
            prev_phase = {"id": phase_id - 1, "title": prev_title}

    # 5. Render phase-N.md
    env = _load_env()
    phase_tmpl = env.get_template("docs/phases/phase.md.j2")
    rendered = phase_tmpl.render(
        project_name="project",
        phase_id=phase_id,
        phase_title=title,
        goal=goal,
        prev_phase=prev_phase,
        next_phase=None,
        stories=[],
    )

    # 6. Write phase-N.md
    phase_file.write_text(rendered, encoding="utf-8")
    click.echo(f"Created {phase_file.relative_to(project_path)}")

    # 7. Update or create index.md
    index_path = phases_dir / "index.md"
    if index_path.exists():
        _append_index_row(index_path, phase_id, title or f"Phase {phase_id}")
        click.echo(f"Updated {index_path.relative_to(project_path)}")
    else:
        _create_index(index_path, phase_id, title or f"Phase {phase_id}")
        click.echo(f"Created {index_path.relative_to(project_path)}")


if __name__ == "__main__":
    phase_new()

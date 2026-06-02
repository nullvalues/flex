"""
era_transition.py — Formally close the current active era and open the next one.

Closes the current active era (status → complete, adds closed_at: YYYY-MM-DD),
creates a new era via era_new logic, and reports the result.
"""

from __future__ import annotations

import datetime
import glob
import re
import sys
from pathlib import Path

# Insert repo root so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import click

from era_new import _era_content, _next_era_id, _slugify  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_active_eras(eras_dir: Path) -> list[Path]:
    """Scan docs/eras/*.md for files with status: active; return matching paths."""
    pattern = str(eras_dir / "*.md")
    active: list[Path] = []
    for p in sorted(glob.glob(pattern)):
        path = Path(p)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_era_frontmatter(text)
        if fm and fm.get("status") == "active":
            active.append(path)
    return active


def _parse_era_frontmatter(text: str) -> dict | None:
    """Minimal frontmatter parser for era files (status, id, name fields)."""
    m = re.match(r"^\s*---\s*\n(.*?)\n?---\s*(\n|$)", text, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    result: dict = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        scalar_m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$', line)
        if scalar_m:
            key = scalar_m.group(1)
            value = scalar_m.group(2).strip().strip('"').strip("'")
            result[key] = value
    return result


def _close_era_frontmatter(content: str, today: str) -> str:
    """Set status: complete and add closed_at: DATE in the frontmatter block."""
    # Find the frontmatter block boundaries
    m = re.match(r"^(---\s*\n)(.*?)(\n?---\s*\n)", content, re.DOTALL)
    if not m:
        return content

    open_delim = m.group(1)
    fm_block = m.group(2)
    close_delim = m.group(3)
    remainder = content[m.end():]

    # Replace status: active -> status: complete
    fm_block = re.sub(
        r"^(status\s*:)\s*active\s*$",
        r"\1 complete",
        fm_block,
        flags=re.MULTILINE,
    )

    # Insert closed_at after the status line (only if not already present)
    if "closed_at" not in fm_block:
        fm_block = re.sub(
            r"^(status\s*:.*?)$",
            rf"\1\nclosed_at: {today}",
            fm_block,
            flags=re.MULTILINE,
        )

    return open_delim + fm_block + close_delim + remainder


def _era_display_name(era_path: Path, fm: dict) -> str:
    """Return a human-readable label for the era (id + name)."""
    era_id = fm.get("id", era_path.stem.split("-", 1)[0])
    name = fm.get("name", era_path.stem)
    return f"{era_id} — {name}"


# ---------------------------------------------------------------------------
# Core transition logic (callable from flex_build.py)
# ---------------------------------------------------------------------------


def era_transition_cli(
    project_dir: str,
    name: str | None,
    intent: str,
    yes: bool,
) -> int:
    """
    Execute the era transition.

    Returns 0 on success, 1 on any error.
    Used by flex_build.py as an importable delegate.
    """
    resolved = Path(project_dir).resolve()

    # Path traversal depth guard
    if not resolved.is_dir() or len(resolved.parts) < 3:
        click.echo(
            f"error: --project-dir resolves to a suspicious path: {resolved}",
            err=True,
        )
        return 1

    eras_dir = resolved / "docs" / "eras"
    if not eras_dir.exists():
        click.echo(
            "No active era to close. Use era_new.py to create one.",
            err=True,
        )
        return 1

    # 1. Detect active era(s)
    active_eras = _find_active_eras(eras_dir)

    if not active_eras:
        click.echo("No active era to close. Use era_new.py to create one.")
        return 1

    if len(active_eras) > 1:
        names = [p.name for p in active_eras]
        click.echo(
            f"Multiple active eras found: {names}. Resolve manually before transitioning."
        )
        return 1

    current_era_path = active_eras[0]
    current_content = current_era_path.read_text(encoding="utf-8")
    current_fm = _parse_era_frontmatter(current_content)
    current_id = current_fm.get("id", "???") if current_fm else "???"
    current_name = current_fm.get("name", current_era_path.stem) if current_fm else current_era_path.stem

    # 2. Prompt for new era name / intent (unless --yes + --name provided)
    if yes:
        if not name:
            click.echo(
                "error: --name is required when using --yes mode.",
                err=True,
            )
            return 1
        new_name = name
        new_intent = intent
    else:
        if name is None:
            new_name = click.prompt("New era name")
        else:
            new_name = name

        if intent == "":
            prompted = click.prompt(
                "Strategic intent for new era (Enter to skip)", default=""
            )
            new_intent = prompted
        else:
            new_intent = intent

    # 3. Check that the new era file does not already exist
    next_id = _next_era_id(eras_dir)
    new_slug = _slugify(new_name)
    new_filename = f"{next_id:03d}-{new_slug}.md"
    new_era_path = eras_dir / new_filename

    if new_era_path.exists():
        click.echo(
            f"error: new era file already exists: docs/eras/{new_filename}",
            err=True,
        )
        return 1

    # Containment check for new era path
    try:
        new_era_path.resolve().relative_to(eras_dir.resolve())
    except ValueError:
        click.echo(
            "Invalid era name: resolves outside docs/eras/",
            err=True,
        )
        return 1

    # 4. Close the current active era
    today = datetime.date.today().isoformat()
    updated_content = _close_era_frontmatter(current_content, today)
    current_era_path.write_text(updated_content, encoding="utf-8")

    # 5. Create the new era
    new_era_id = f"{next_id:03d}"
    new_content = _era_content(new_era_id, new_name, new_intent)
    new_era_path.write_text(new_content, encoding="utf-8")

    # 6. Report
    click.echo(f"Era {current_id} closed: {current_name}")
    click.echo(f"Era {new_era_id} opened: {new_name}")
    click.echo(f"New phases will be assigned to Era {new_era_id}.")
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@click.command()
@click.option("--name", default=None, help="New era name (required in --yes mode).")
@click.option("--intent", default="", help="Strategic intent for the new era.")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip interactive prompts; --name must be provided.",
)
def era_transition(
    name: str | None,
    intent: str,
    project_dir: str,
    yes: bool,
) -> None:
    """Formally close the current active era and open the next one."""
    rc = era_transition_cli(
        project_dir=project_dir,
        name=name,
        intent=intent,
        yes=yes,
    )
    sys.exit(rc)


if __name__ == "__main__":
    era_transition()

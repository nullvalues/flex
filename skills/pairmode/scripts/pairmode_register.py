"""
pairmode_register.py — Manage registered_projects in anchor's .companion/state.json.

Provides three CLI subcommands:

``register --project-dir <path>``
    Adds the resolved absolute path to ``registered_projects`` in
    ``.companion/state.json``.  If the path is already registered, prints
    "already registered" and exits 0.

``unregister --project-dir <path>``
    Removes the resolved absolute path from ``registered_projects``.  If the
    path is not found, prints "not registered" and exits 0.

``list-projects``
    Prints the current ``registered_projects`` list (one entry per line), or
    "No projects registered." when the list is empty or absent.

All three commands read and write anchor's own ``.companion/state.json`` (the
file in the current working directory).  Writes are atomic: the new content is
first written to a ``.tmp`` file, then renamed onto the target path.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Allow running directly with: uv run python skills/pairmode/scripts/pairmode_register.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import click


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The .companion directory is always relative to cwd (anchor's own root).
_DEFAULT_COMPANION_DIR = Path(".companion")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _depth_guard(path: Path) -> bool:
    """Return True when *path* has at least 3 components.

    Paths with fewer than 3 parts (e.g. ``/tmp``, ``/a``, ``a/b``) are
    considered suspiciously shallow and are rejected to prevent accidental
    registration of filesystem-root-adjacent paths.

    Args:
        path: A resolved (absolute) Path.

    Returns:
        True when the path is acceptable; False when it should be rejected.
    """
    return len(path.parts) >= 3


def _read_state(companion_dir: Path) -> dict:
    """Read ``state.json`` from *companion_dir*; return empty dict if missing."""
    state_path = companion_dir / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state_atomic(companion_dir: Path, state: dict) -> None:
    """Write *state* to ``state.json`` atomically.

    Writes to a temporary file in the same directory first, then renames it
    over the target path to ensure the file is never partially written.
    """
    state_path = companion_dir / "state.json"
    companion_dir.mkdir(parents=True, exist_ok=True)

    # Write to a temp file in the same directory so the rename is atomic on
    # the same filesystem.
    fd, tmp_path = tempfile.mkstemp(
        dir=str(companion_dir),
        prefix="state_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, str(state_path))
    except Exception:
        # Clean up the temp file on error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@click.command("register")
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Path to the pairmode project to register.",
)
@click.option(
    "--companion-dir",
    default=None,
    hidden=True,
    help="Override path to .companion directory (for testing).",
)
def register(project_dir: str, companion_dir: str | None) -> None:
    """Add a project path to registered_projects in .companion/state.json.

    The path is resolved to an absolute path before registration.  Paths with
    fewer than 3 components are rejected (containment guard).  If the path is
    already registered, prints "already registered" and exits 0.
    """
    resolved = Path(project_dir).resolve()

    if not _depth_guard(resolved):
        click.echo(
            f"error: project-dir resolves to a suspicious path: {resolved}",
            err=True,
        )
        sys.exit(1)

    cdir = Path(companion_dir) if companion_dir else _DEFAULT_COMPANION_DIR

    state = _read_state(cdir)
    projects: list[str] = state.get("registered_projects", [])

    path_str = str(resolved)
    if path_str in projects:
        click.echo("already registered")
        return

    projects.append(path_str)
    state["registered_projects"] = projects
    _write_state_atomic(cdir, state)
    click.echo(f"registered: {path_str}")


@click.command("unregister")
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Path to the pairmode project to unregister.",
)
@click.option(
    "--companion-dir",
    default=None,
    hidden=True,
    help="Override path to .companion directory (for testing).",
)
def unregister(project_dir: str, companion_dir: str | None) -> None:
    """Remove a project path from registered_projects in .companion/state.json.

    The path is resolved to an absolute path before lookup.  If the path is
    not found in the list, prints "not registered" and exits 0.
    """
    resolved = Path(project_dir).resolve()

    cdir = Path(companion_dir) if companion_dir else _DEFAULT_COMPANION_DIR

    state = _read_state(cdir)
    projects: list[str] = state.get("registered_projects", [])

    path_str = str(resolved)
    if path_str not in projects:
        click.echo("not registered")
        return

    projects.remove(path_str)
    state["registered_projects"] = projects
    _write_state_atomic(cdir, state)
    click.echo(f"unregistered: {path_str}")


@click.command("list-projects")
@click.option(
    "--companion-dir",
    default=None,
    hidden=True,
    help="Override path to .companion directory (for testing).",
)
def list_projects(companion_dir: str | None) -> None:
    """Print the registered_projects list from .companion/state.json.

    Prints one entry per line, or "No projects registered." when the list is
    empty or the key is absent.
    """
    cdir = Path(companion_dir) if companion_dir else _DEFAULT_COMPANION_DIR

    state = _read_state(cdir)
    projects: list[str] = state.get("registered_projects", [])

    if not projects:
        click.echo("No projects registered.")
        return

    for path_str in projects:
        click.echo(path_str)


# ---------------------------------------------------------------------------
# Standalone CLI group (for direct invocation)
# ---------------------------------------------------------------------------


@click.group("pairmode-register")
def _register_cli() -> None:
    """pairmode register/unregister/list-projects subcommands."""


_register_cli.add_command(register)
_register_cli.add_command(unregister)
_register_cli.add_command(list_projects)


if __name__ == "__main__":
    _register_cli()

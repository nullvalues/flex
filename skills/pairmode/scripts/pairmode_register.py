"""
pairmode_register.py — Manage registered_projects in flex's .companion/state.json.

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

``audit-projects``
    Read-only. Prints one line per registered path with its recorded
    provenance (``source`` + ``registered_at``, or ``unknown`` for entries
    predating the provenance sidecar), a summary line, and a WARN line for
    any registered path that is missing on disk or lacks a ``.companion/``
    directory (CER-058).

``register``/``unregister`` read and write flex's own
``.companion/state.json`` (the file in the current working directory).
Writes are atomic: the new content is first written to a ``.tmp`` file, then
renamed onto the target path. ``register`` also records a provenance sidecar
entry under ``registered_projects_provenance`` (``--source``, default
``"cli"``) in the same atomic write; ``unregister`` removes the matching
sidecar entry. ``registered_projects`` itself keeps its original flat
``list[str]`` shape — the sidecar is additive.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Allow running directly with: uv run python skills/pairmode/scripts/pairmode_register.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import click


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The .companion directory is always relative to cwd (flex's own root).
_DEFAULT_COMPANION_DIR = Path(".companion")

# CER-058 single-writer invariant: the set of in-repo files permitted to
# assign the `registered_projects` key in .companion/state.json. Enforced by
# tests/pairmode/test_register.py::test_registered_projects_has_a_single_writer,
# which walks skills/ and hooks/ for assignments to the key and asserts the
# set of offending files equals exactly this frozenset. A new writer must
# either route through `register`/`unregister` above, or be added here with a
# recorded reason (and a corresponding architecture.md note) — never silently.
REGISTERED_PROJECTS_WRITERS = frozenset({"skills/pairmode/scripts/pairmode_register.py"})

# Sidecar key recording provenance (source + timestamp) for each entry in
# registered_projects. Additive: registered_projects itself keeps its
# flat list[str] shape (A4). Entries predating this story (CER-058) have no
# recoverable provenance and audit as PROVENANCE_UNKNOWN rather than being
# retroactively invented (A5).
REGISTERED_PROJECTS_PROVENANCE_KEY = "registered_projects_provenance"

# Sentinel source value for a registered_projects entry with no recorded
# provenance sidecar entry — either it predates this story, or it arrived via
# an out-of-band edit of state.json (CER-058's actual finding: no in-repo
# writer bypasses `register`, so an "unknown" entry was not written by any
# code path this repo controls).
PROVENANCE_UNKNOWN = "unknown"


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


def _coerce_sidecar(state: dict) -> dict:
    """Return the registered_projects_provenance sidecar as a dict.

    Tolerant in both directions (a missing key, None, a list, or a string
    where a dict is expected all degrade to {} rather than raise) — register
    is an operator command whose failure mode is a confused operator, and
    unregister must stay usable to clean up exactly the kind of hand-edited
    state that produced CER-058.
    """
    sidecar = state.get(REGISTERED_PROJECTS_PROVENANCE_KEY)
    if isinstance(sidecar, dict):
        return sidecar
    return {}


def _provenance_for(state: dict, path_str: str) -> dict:
    """Return the provenance record for *path_str*, or the unknown sentinel.

    No code path back-fills a fabricated `registered_at` for a historical
    entry (A5) — an entry with no sidecar record (pre-INFRA-270, or an
    out-of-band edit of state.json) genuinely has no recoverable provenance.
    """
    sidecar = _coerce_sidecar(state)
    entry = sidecar.get(path_str)
    if isinstance(entry, dict):
        return entry
    return {"source": PROVENANCE_UNKNOWN, "registered_at": None}


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
@click.option(
    "--source",
    default="cli",
    help="Provenance label recorded for this registration (default: 'cli').",
)
def register(project_dir: str, companion_dir: str | None, source: str) -> None:
    """Add a project path to registered_projects in .companion/state.json.

    The path is resolved to an absolute path before registration.  Paths with
    fewer than 3 components are rejected (containment guard).  If the path is
    already registered, prints "already registered" and exits 0.

    Also records a provenance sidecar entry (source + registered_at) under
    registered_projects_provenance (CER-058, A3) — inside this same
    _write_state_atomic call, not a second write, to preserve the single
    read-mutate-atomic-write shape INFRA-285 hardened against concurrent
    sessions.
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
    # intentional direct write: this IS the canonical register entry point (CER-058)
    state["registered_projects"] = projects

    # Provenance sidecar write rides inside this same read-mutate-write call
    # (no second _write_state_atomic invocation) — see INFRA-285.
    sidecar = _coerce_sidecar(state)
    sidecar[path_str] = {
        "source": source,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    state[REGISTERED_PROJECTS_PROVENANCE_KEY] = sidecar

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

    Also removes the matching registered_projects_provenance sidecar entry,
    if any, in this same write.
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
    # intentional direct write: this IS the canonical unregister entry point (CER-058)
    state["registered_projects"] = projects

    sidecar = _coerce_sidecar(state)
    sidecar.pop(path_str, None)
    state[REGISTERED_PROJECTS_PROVENANCE_KEY] = sidecar

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


@click.command("audit-projects")
@click.option(
    "--companion-dir",
    default=None,
    hidden=True,
    help="Override path to .companion directory (for testing).",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output JSON instead of human-readable text.",
)
def audit_projects(companion_dir: str | None, output_json: bool) -> None:
    """Report registered_projects entries and their recorded provenance.

    CER-058: read-only — never writes state.json. Prints one line per
    registered path (`<path> — source: <source> — registered_at: <iso|->`),
    a summary line, and a WARN line for any registered path that does not
    exist on disk or lacks a .companion/ directory.
    """
    cdir = Path(companion_dir) if companion_dir else _DEFAULT_COMPANION_DIR

    state = _read_state(cdir)
    projects: list[str] = state.get("registered_projects", []) or []

    entries = []
    unknown_count = 0
    warnings: list[str] = []
    for path_str in projects:
        prov = _provenance_for(state, path_str)
        source = prov.get("source", PROVENANCE_UNKNOWN)
        registered_at = prov.get("registered_at")
        if source == PROVENANCE_UNKNOWN:
            unknown_count += 1
        entries.append({"path": path_str, "source": source, "registered_at": registered_at})

        p = Path(path_str)
        if not p.exists():
            warnings.append(f"WARN: {path_str} does not exist on disk")
        elif not (p / ".companion").is_dir():
            warnings.append(f"WARN: {path_str} lacks a .companion/ directory")

    if output_json:
        click.echo(json.dumps({"registered": entries, "unknown_count": unknown_count}, indent=2))
        return

    with_provenance = sum(1 for e in entries if e["source"] != PROVENANCE_UNKNOWN)
    for e in entries:
        registered_at_display = e["registered_at"] if e["registered_at"] else "-"
        click.echo(f"{e['path']} — source: {e['source']} — registered_at: {registered_at_display}")

    click.echo(
        f"{len(entries)} registered, {with_provenance} with recorded provenance, "
        f"{unknown_count} unknown (pre-INFRA-270)"
    )
    for w in warnings:
        click.echo(w)


# ---------------------------------------------------------------------------
# Standalone CLI group (for direct invocation)
# ---------------------------------------------------------------------------


@click.group("pairmode-register")
def _register_cli() -> None:
    """pairmode register/unregister/list-projects/audit-projects subcommands."""


_register_cli.add_command(register)
_register_cli.add_command(unregister)
_register_cli.add_command(list_projects)
_register_cli.add_command(audit_projects)


if __name__ == "__main__":
    _register_cli()

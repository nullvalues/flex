"""
flex_observability.py — CLI for the Flex Observability SPA.

Manages the project registry at ~/.config/flex-observability/registry.json
and launches the Fastify API server.

Subcommands:
    register    -- register a project directory
    unregister  -- remove a project directory from registry
    list        -- show all registered repos
    serve       -- launch the Fastify API server

Registry path override: set FLEX_OBS_REGISTRY_PATH env var (used for testing).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

_COLOUR_ROTATION = [
    "#7aa2f7",
    "#e0af68",
    "#9ece6a",
    "#f7768e",
    "#bb9af7",
    "#7dcfff",
]

_DEFAULT_PORT = 7777
_DEFAULT_HOST = "127.0.0.1"


def _registry_path() -> Path:
    """Return the registry file path, respecting FLEX_OBS_REGISTRY_PATH override."""
    override = os.environ.get("FLEX_OBS_REGISTRY_PATH")
    if override:
        return Path(override)
    return Path.home() / ".config" / "flex-observability" / "registry.json"


def _read_registry(path: Path) -> dict:
    """Read registry JSON; return empty registry dict if file absent or empty."""
    if not path.exists():
        return {"version": 1, "repos": []}
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return {"version": 1, "repos": []}
        return json.loads(text)
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "repos": []}


def _write_registry(path: Path, data: dict) -> None:
    """Write registry atomically via temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def _depth_guard(resolved: Path) -> bool:
    """Return True if path has at least 4 components (depth guard).

    Rejects paths that are too shallow to be real project directories.
    Examples rejected: /a/b (3 parts), /tmp (2 parts).
    Examples accepted: /home/user/project (4 parts), /mnt/work/flex (4 parts).
    """
    return len(resolved.parts) >= 4


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Flex Observability CLI — manage project registry and launch the API server."""


@cli.command()
@click.option("--project-dir", required=True, help="Absolute or relative path to the project directory.")
@click.option("--name", default=None, help="Registry ID for the project. Defaults to last path component.")
@click.option("--color", default=None, help="Hex colour for the project in the SPA (e.g. #7aa2f7).")
def register(project_dir: str, name: str | None, color: str | None) -> None:
    """Register a project directory in the observability registry."""
    resolved = Path(project_dir).resolve()

    if not _depth_guard(resolved):
        click.echo(f"error: path too shallow (fewer than 3 components): {resolved}", err=True)
        sys.exit(1)

    # Default name to last path component
    if not name:
        name = resolved.name

    reg_path = _registry_path()
    registry = _read_registry(reg_path)
    repos: list[dict] = registry.get("repos", [])

    # Idempotency check
    for entry in repos:
        if entry.get("project_dir") == str(resolved):
            click.echo(f"already registered: {resolved}")
            return

    # Assign colour from rotation if not provided
    if not color:
        color = _COLOUR_ROTATION[len(repos) % len(_COLOUR_ROTATION)]

    repos.append({"id": name, "project_dir": str(resolved), "color": color})
    registry["repos"] = repos
    _write_registry(reg_path, registry)
    click.echo(f"registered: {name} → {resolved}")


@cli.command()
@click.option("--project-dir", default=None, help="Project directory to unregister.")
@click.option("--name", default=None, help="Registry ID to unregister.")
def unregister(project_dir: str | None, name: str | None) -> None:
    """Remove a project from the observability registry."""
    if not project_dir and not name:
        click.echo("error: at least one of --project-dir or --name is required.", err=True)
        sys.exit(1)

    resolved_str = str(Path(project_dir).resolve()) if project_dir else None

    reg_path = _registry_path()
    registry = _read_registry(reg_path)
    repos: list[dict] = registry.get("repos", [])

    matched: dict | None = None
    for entry in repos:
        if resolved_str and entry.get("project_dir") == resolved_str:
            matched = entry
            break
        if name and entry.get("id") == name:
            matched = entry
            break

    if not matched:
        click.echo("not registered")
        return

    repos.remove(matched)
    registry["repos"] = repos
    _write_registry(reg_path, registry)
    click.echo(f"unregistered: {matched['id']}")


@cli.command(name="list")
def list_repos() -> None:
    """List all registered project repositories."""
    reg_path = _registry_path()
    registry = _read_registry(reg_path)
    repos: list[dict] = registry.get("repos", [])

    if not repos:
        click.echo("No repos registered.")
        return

    # Table header
    col_id = max(len("ID"), max(len(r.get("id", "")) for r in repos))
    col_dir = max(len("PROJECT_DIR"), max(len(r.get("project_dir", "")) for r in repos))

    header = f"{'ID':<{col_id}}  {'PROJECT_DIR':<{col_dir}}  COLOR"
    click.echo(header)
    for r in repos:
        rid = r.get("id", "")
        rdir = r.get("project_dir", "")
        rcolor = r.get("color", "")
        click.echo(f"{rid:<{col_id}}  {rdir:<{col_dir}}  {rcolor}")


@cli.command()
@click.option("--port", default=None, type=int, help="Port to bind the server on.")
@click.option("--host", default=None, help="Host to bind the server on.")
def serve(port: int | None, host: str | None) -> None:
    """Launch the Flex Observability API server (foreground)."""
    reg_path = _registry_path()
    registry = _read_registry(reg_path)

    # Resolve port and host from registry or defaults
    if port is None:
        port = registry.get("default_port", _DEFAULT_PORT)
    if host is None:
        host = registry.get("bind_host", _DEFAULT_HOST)

    # Locate server.js relative to this script
    # skills/observability/scripts/flex_observability.py
    # parents[0] = scripts/
    # parents[1] = observability/
    server_js = Path(__file__).resolve().parent.parent / "api" / "dist" / "server.js"

    if not server_js.exists():
        click.echo("API server not built. Run:")
        click.echo("  cd skills/observability && pnpm install && pnpm --filter @flex-obs/api build")
        sys.exit(1)

    # Verify node is available
    try:
        subprocess.run(
            ["node", "--version"],
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        click.echo("error: 'node' not found on PATH. Install Node.js to run the server.", err=True)
        sys.exit(1)

    env = os.environ.copy()
    env["FLEX_OBS_PORT"] = str(port)
    env["FLEX_OBS_HOST"] = host
    env["FLEX_OBS_REGISTRY"] = str(reg_path)

    try:
        subprocess.run(["node", str(server_js)], env=env)
    except KeyboardInterrupt:
        click.echo("Server stopped.")
        sys.exit(0)


if __name__ == "__main__":
    cli()

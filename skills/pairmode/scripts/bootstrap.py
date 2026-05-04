"""
bootstrap.py — Pairmode scaffold generator.

Writes pairmode scaffold files from Jinja2 templates into a target project
directory.  Existing files are not overwritten without explicit user
confirmation.
"""

from __future__ import annotations

import json
import pathlib
import sys

import click
import jinja2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAIRMODE_VERSION = "0.1.0"

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"

# Mapping: destination path (relative to project_dir) → template name
# None as the template value means the file is written from a hard-coded
# skeleton string (phase-prompts.md and checkpoints.md are plain skeletons
# that the templates directory already provides as .j2 files).
SCAFFOLD_FILES: list[tuple[str, str]] = [
    ("CLAUDE.md", "CLAUDE.md.j2"),
    ("CLAUDE.build.md", "CLAUDE.build.md.j2"),
    (".claude/agents/builder.md", "agents/builder.md.j2"),
    (".claude/agents/reviewer.md", "agents/reviewer.md.j2"),
    (".claude/agents/loop-breaker.md", "agents/loop-breaker.md.j2"),
    (".claude/agents/security-auditor.md", "agents/security-auditor.md.j2"),
    (".claude/agents/intent-reviewer.md", "agents/intent-reviewer.md.j2"),
    ("docs/architecture.md", "docs/architecture.md.j2"),
    ("docs/phase-prompts.md", "docs/phase-prompts.md.j2"),
    ("docs/checkpoints.md", "docs/checkpoints.md.j2"),
]

# Default deny list written into .claude/settings.json
DEFAULT_DENY: list[str] = [
    "Edit(CLAUDE.md)",
    "Write(CLAUDE.md)",
    "Edit(CLAUDE.build.md)",
    "Write(CLAUDE.build.md)",
    "Edit(.claude/agents/**)",
    "Write(.claude/agents/**)",
    "Edit(docs/architecture.md)",
    "Write(docs/architecture.md)",
]

# Universal checklist items always included in templates
UNIVERSAL_CHECKLIST_ITEMS: list[dict] = [
    {
        "name": "PROTECTED FILES",
        "description": "Were any protected files modified without a stated reason?",
        "severity": "HIGH",
    },
    {
        "name": "STORY SCOPE",
        "description": "Did the builder touch files outside the stated story scope?",
        "severity": "MEDIUM",
    },
    {
        "name": "BUILD GATE",
        "description": "Does the build command pass without errors?",
        "severity": "CRITICAL",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_build_command(project_dir: pathlib.Path) -> str | None:
    """Return a build command inferred from files present in project_dir."""
    if (project_dir / "pnpm-lock.yaml").exists() or (project_dir / "pnpm-workspace.yaml").exists():
        return "pnpm build && pnpm typecheck"
    if (project_dir / "pyproject.toml").exists() or (project_dir / "uv.lock").exists():
        return "uv run pytest"
    return None


def _render_template(template_name: str, context: dict) -> str:
    loader = jinja2.FileSystemLoader(str(TEMPLATES_DIR))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_name)
    return template.render(**context)


def _write_file(
    dest: pathlib.Path,
    content: str,
    dry_run: bool,
) -> bool:
    """
    Write *content* to *dest*.

    Returns True if the file was (or would be, in dry-run mode) written.
    If the file already exists and this is not a dry-run, prompts the user
    for confirmation before overwriting.
    """
    if dry_run:
        click.echo(f"  [dry-run] would write: {dest}")
        return True

    if dest.exists():
        overwrite = click.confirm(
            f"  {dest} already exists. Overwrite?", default=False
        )
        if not overwrite:
            click.echo(f"  skipped: {dest}")
            return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    click.echo(f"  wrote: {dest}")
    return True


def _merge_deny_list(settings_path: pathlib.Path, new_entries: list[str]) -> None:
    """
    Merge *new_entries* into the permissions.deny array in settings_path.

    Creates the file if it does not exist.  Existing entries are preserved;
    duplicates are not added.
    """
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    permissions = data.setdefault("permissions", {})
    deny: list[str] = permissions.get("deny", [])

    for entry in new_entries:
        if entry not in deny:
            deny.append(entry)

    permissions["deny"] = deny
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def _record_state(state_path: pathlib.Path, version: str) -> None:
    """Write pairmode_version into .companion/state.json, creating if absent."""
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    data["pairmode_version"] = version
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _load_product_json(project_dir: pathlib.Path) -> dict:
    """Load .companion/product.json if it exists; return {} otherwise."""
    product_path = project_dir / ".companion" / "product.json"
    if product_path.exists():
        try:
            return json.loads(product_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--project-dir",
    default=".",
    show_default=True,
    help="Target project directory.",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
)
@click.option("--project-name", default=None, help="Project name (prompted if omitted).")
@click.option("--stack", default=None, help="Technology stack (prompted if omitted).")
@click.option(
    "--build-command",
    default=None,
    help="Build/test command (inferred from project files if omitted, else prompted).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be written without writing anything.",
)
def bootstrap(
    project_dir: str,
    project_name: str | None,
    stack: str | None,
    build_command: str | None,
    dry_run: bool,
) -> None:
    """Bootstrap a pairmode scaffold into PROJECT_DIR."""

    project_path = pathlib.Path(project_dir).resolve()

    # ------------------------------------------------------------------
    # 1. Gather values: CLI → product.json → prompt
    # ------------------------------------------------------------------
    product = _load_product_json(project_path)

    if project_name is None:
        project_name = product.get("project_name") or click.prompt("Project name")

    if stack is None:
        stack = click.prompt("Stack (e.g. Python / FastAPI / PostgreSQL)")

    if build_command is None:
        inferred = _infer_build_command(project_path)
        if inferred:
            build_command = inferred
        else:
            build_command = click.prompt(
                "Build command (e.g. pnpm build && pnpm typecheck)"
            )

    # test_command is derived from build_command for now
    test_command = build_command

    # ------------------------------------------------------------------
    # 2. Build template context
    # ------------------------------------------------------------------
    context: dict = {
        "project_name": project_name,
        "project_description": product.get("project_description", ""),
        "stack": stack,
        "build_command": build_command,
        "test_command": test_command,
        "migration_command": "",
        "domain_model": "",
        "checklist_items": [],  # universal items (PROTECTED FILES, STORY SCOPE, BUILD GATE) are hardcoded in templates
        "protected_paths": [],
        "non_negotiables": [],
        # architecture.md.j2 needs these; provide empty defaults
        "module_structure": [],
        "layer_rules": [],
        # agent templates need this
        "domain_isolation_rule": "",
    }

    # ------------------------------------------------------------------
    # 3. Render and write scaffold files
    # ------------------------------------------------------------------
    if dry_run:
        click.echo("Dry run — no files will be written.\n")

    click.echo(f"Bootstrapping pairmode scaffold into {project_path}\n")

    for dest_rel, template_name in SCAFFOLD_FILES:
        dest = project_path / dest_rel
        try:
            content = _render_template(template_name, context)
        except jinja2.TemplateError as exc:
            click.echo(f"  ERROR rendering {template_name}: {exc}", err=True)
            sys.exit(1)
        _write_file(dest, content, dry_run=dry_run)

    # ------------------------------------------------------------------
    # 4. Merge deny list into .claude/settings.json
    # ------------------------------------------------------------------
    settings_path = project_path / ".claude" / "settings.json"
    if dry_run:
        click.echo(f"\n  [dry-run] would merge deny list into: {settings_path}")
    else:
        click.echo(f"\nMerging deny list into {settings_path}")
        _merge_deny_list(settings_path, DEFAULT_DENY)

    # ------------------------------------------------------------------
    # 5. Record pairmode version
    # ------------------------------------------------------------------
    state_path = project_path / ".companion" / "state.json"
    if dry_run:
        click.echo(f"  [dry-run] would record pairmode_version in: {state_path}")
    else:
        click.echo(f"Recording pairmode_version in {state_path}")
        _record_state(state_path, PAIRMODE_VERSION)

    click.echo("\nDone." if not dry_run else "\nDry run complete.")


if __name__ == "__main__":
    bootstrap()

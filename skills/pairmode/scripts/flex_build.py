"""flex_build.py — single click CLI that aggregates the 8 inline Python
blocks that used to be embedded as ``uv run python -c "..."`` heredocs in
``skills/pairmode/templates/CLAUDE.build.md.j2``.

Each subcommand wraps one helper call from the pairmode scripts package
(``model_selector``, ``permission_scope``, ``effort_db``, ``context_health``).
The CLI exists solely so the orchestrator template can shell out to a single
script rather than embed multi-line Python boilerplate.

Story: INFRA-131.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Make sibling modules importable when invoked as a script.
sys.path.insert(0, str(Path(__file__).parent))

import click

from schema_validator import _parse_frontmatter  # noqa: E402
from model_selector import (  # noqa: E402
    select_builder_model,
    select_intent_reviewer_model,
    select_reviewer_model,
    select_security_auditor_model,
)
from permission_scope import (  # noqa: E402
    clear_story_permissions,
    write_story_permissions,
)
from effort_db import check_guardrail, resolve_effort_db_path  # noqa: E402
from context_health import check_context_health  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _story_path(story_id: str, project_dir: Path) -> Path:
    """Return ``docs/stories/<RAIL>/<STORY_ID>.md`` for ``story_id``.

    Rail is the substring before the first ``-`` in ``story_id``.
    """
    rail = story_id.split("-", 1)[0]
    return project_dir / "docs" / "stories" / rail / f"{story_id}.md"


def _read_story_frontmatter(story_path: Path) -> dict:
    """Read and parse YAML frontmatter from a story spec file."""
    text = story_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    return fm or {}


def _read_guardrail_multiplier(project_dir: Path) -> float:
    """Read ``effort_guardrail_multiplier`` from ``.companion/state.json``.

    Defaults to ``3.0`` when state.json is absent, malformed, or missing the
    field.
    """
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return 3.0
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return float(data.get("effort_guardrail_multiplier", 3.0))
    except (json.JSONDecodeError, ValueError, TypeError, OSError):
        return 3.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def flex_build() -> None:
    """flex pairmode build orchestrator helpers (INFRA-131)."""


@flex_build.command("select-builder-model")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-131).")
@click.option(
    "--protected-file",
    "protected_files",
    multiple=True,
    default=(),
    help="Protected file path; may be supplied zero or more times.",
)
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_select_builder_model(
    story_id: str,
    protected_files: tuple[str, ...],
    project_dir: str,
) -> None:
    """Select the builder model for *story_id*; print ``model|reason``."""
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)
    fm = _read_story_frontmatter(story_path)
    story_class = fm.get("story_class") or "code"
    primary_files = fm.get("primary_files") or []
    model, reason = select_builder_model(
        story_class, list(primary_files), list(protected_files)
    )
    click.echo(f"{model}|{reason}")


@flex_build.command("write-permissions")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-131).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_write_permissions(story_id: str, project_dir: str) -> None:
    """Write story-scoped allow rules to ``.claude/settings.local.json``."""
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)
    write_story_permissions(story_path, project_path)


@flex_build.command("check-guardrail")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-131).")
@click.option("--tokens", required=True, type=int, help="Latest attempt token count.")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_guardrail(story_id: str, tokens: int, project_dir: str) -> None:
    """Run the effort guardrail; print the warning to stderr when fired."""
    project_path = Path(project_dir).resolve()
    rail = story_id.split("-", 1)[0]
    multiplier = _read_guardrail_multiplier(project_path)
    db_path = resolve_effort_db_path(project_path)
    result = check_guardrail(
        db_path,
        story_id=story_id,
        rail=rail,
        latest_tokens=tokens,
        multiplier=multiplier,
    )
    if result.get("fired"):
        click.echo(result["message"], err=True)


@flex_build.command("select-reviewer-model")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-131).")
@click.option("--attempt", required=True, type=int, help="Attempt number (1 = first).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_select_reviewer_model(
    story_id: str, attempt: int, project_dir: str
) -> None:
    """Select the reviewer model; print ``model`` then ``reason``."""
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)
    fm = _read_story_frontmatter(story_path)
    story_class = fm.get("story_class") or "code"
    phase_id = fm.get("phase")
    phase_id_str = str(phase_id) if phase_id is not None else None
    model, reason = select_reviewer_model(
        story_class=story_class,
        attempt_number=attempt,
        phase_id=phase_id_str,
        project_dir=project_path,
    )
    click.echo(model)
    click.echo(reason)


@flex_build.command("clear-permissions")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_clear_permissions(project_dir: str) -> None:
    """Clear story-scoped allow rules from ``.claude/settings.local.json``."""
    project_path = Path(project_dir).resolve()
    clear_story_permissions(project_path)


@flex_build.command("select-security-auditor-model")
@click.option("--phase-class", required=True, help="Phase class (e.g. production).")
def cmd_select_security_auditor_model(phase_class: str) -> None:
    """Select the security-auditor model; print ``model``."""
    model, _reason = select_security_auditor_model(phase_class)
    click.echo(model)


@flex_build.command("select-intent-reviewer-model")
@click.option("--phase-class", required=True, help="Phase class (e.g. production).")
def cmd_select_intent_reviewer_model(phase_class: str) -> None:
    """Select the intent-reviewer model; print ``model``."""
    model, _reason = select_intent_reviewer_model(phase_class)
    click.echo(model)


@flex_build.command("context-health")
@click.option("--phase", required=True, help="Phase ID to evaluate.")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_context_health(phase: str, project_dir: str) -> None:
    """Run the context-health check; print the JSON result."""
    project_path = Path(project_dir).resolve()
    db_path = resolve_effort_db_path(project_path)
    result = check_context_health(db_path=db_path, current_phase=phase)
    click.echo(json.dumps(result))


_DELEGATION_RE = re.compile(
    r"see phase doc|see docs/phases/|see phase-",
    re.IGNORECASE,
)
_ACCEPTANCE_RE = re.compile(
    r"^##\s+(?:ensures|acceptance criterion|acceptance criteria)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@flex_build.command("check-stubs")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_stubs(project_dir: str) -> None:
    """Audit all story files for stubs (delegation or missing acceptance surface)."""
    project_path = Path(project_dir).resolve()
    stories_dir = project_path / "docs" / "stories"

    click.echo(f"Scanning docs/stories/ in {project_path}...")
    click.echo("")

    if not stories_dir.exists():
        click.echo("Summary: 0 stubs / 0 total stories")
        sys.exit(0)

    story_files = sorted(stories_dir.rglob("*.md"))

    rows: list[tuple[str, str, str, str]] = []
    for story_file in story_files:
        story_id = story_file.stem
        text = story_file.read_text(encoding="utf-8")

        m = _DELEGATION_RE.search(text)
        if m:
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            matched_line = text[line_start : line_end if line_end != -1 else len(text)].strip()
            if len(matched_line) > 70:
                matched_line = matched_line[:70] + "..."
            rows.append(("STUB", story_id, "delegation", f'"{matched_line}"'))
        elif not _ACCEPTANCE_RE.search(text):
            rows.append(("STUB", story_id, "no-acceptance", "(no ## Ensures or ## Acceptance criterion)"))
        else:
            rows.append(("OK", story_id, "self-contained", ""))

    for status, story_id, reason, detail in rows:
        if status == "STUB":
            click.echo(f"STUB  {story_id:<12}  {reason:<14}  {detail}")
        else:
            click.echo(f"OK    {story_id:<12}  self-contained")

    stub_rows = [(s, sid, r, d) for s, sid, r, d in rows if s == "STUB"]
    stub_count = len(stub_rows)
    total = len(rows)
    delegation_count = sum(1 for _, _, r, _ in stub_rows if r == "delegation")
    no_acceptance_count = sum(1 for _, _, r, _ in stub_rows if r == "no-acceptance")
    pct = int(stub_count / total * 100) if total > 0 else 0

    click.echo("")
    click.echo(f"Summary: {stub_count} stubs / {total} total stories ({pct}%)")
    click.echo(f"  delegation:    {delegation_count}")
    click.echo(f"  no-acceptance: {no_acceptance_count}")

    sys.exit(1 if stub_count > 0 else 0)


if __name__ == "__main__":
    flex_build()

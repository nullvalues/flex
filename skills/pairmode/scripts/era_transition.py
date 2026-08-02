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

# CER-154: detects the era doc's machine-maintained ledger heading. Deliberately
# duplicated from flex_build._is_era_ledger_heading rather than imported —
# importing flex_build into era_transition would add a whole module
# dependency for two tokens (matches this module's existing duplication
# precedent, see _phase_ledger_gate_message below).
_ERA_LEDGER_HEADING_RE = re.compile(r"^##\s+Phases\b", re.MULTILINE)


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


def _phase_ledger_gate_message(era_path: Path, era_text: str) -> "str | None":
    """Return a close-era refusal message when *era_path*'s ``## Phases``
    ledger holds a phase not ``is_phase_inactive`` (INFRA-314, Ensures 2), or
    ``None`` when the gate is clean.

    Reuses ``index_integrity``'s own predicates — ``_parse_era_phase_table``
    (the ledger parser) and ``is_phase_inactive`` (``complete``/``deferred``/
    ``backlog`` — CER-056) — rather than forking a variant "not complete/not
    deferred" check (Requires 3).
    """
    from index_integrity import _parse_era_phase_table, is_phase_inactive  # noqa: PLC0415

    rows = _parse_era_phase_table(era_text)
    undispositioned = [
        (phase_ref, status) for phase_ref, status in rows if not is_phase_inactive(status)
    ]
    if not undispositioned:
        # CER-154: `_parse_era_phase_table` returns `[]` both for "no ##
        # Phases heading at all" (legitimate — a legacy/first era with no
        # ledger yet) and for "a ## Phases heading exists but no row could
        # be parsed from its table" (malformed). The two are
        # indistinguishable to the caller unless this gate tells them
        # apart: a malformed ledger must refuse the close rather than
        # silently proceed as if the era had no ledger at all.
        if not rows and _ERA_LEDGER_HEADING_RE.search(era_text):
            return (
                "era-transition: refused — "
                f"{era_path.name} has a ## Phases heading but no row could "
                "be parsed from its table (CER-154). Fix the ledger table "
                "before retrying; a heading with an unparseable table is "
                "refused rather than treated as having no ledger."
            )
        return None

    listed = "; ".join(f"{ref} (status: {status!r})" for ref, status in undispositioned)
    return (
        "era-transition: refused — "
        f"{len(undispositioned)} undispositioned phase(s) in {era_path.name}'s "
        f"## Phases ledger: {listed}. Each must be resolved before closing the "
        "era: complete it, or formally defer it, before retrying."
    )


def era_transition_cli(
    project_dir: str,
    name: str | None,
    intent: str,
    yes: bool,
    era_id: "str | None" = None,
) -> int:
    """
    Execute the era transition.

    Returns 0 on success, 1 on any error.
    Used by flex_build.py as an importable delegate.

    *era_id* (INFRA-314, Ensures 2) names the era to close explicitly. Two
    eras can be active simultaneously (the live incident this story closes),
    so "the active era" is no longer a safe implicit target: *era_id* is
    optional only while exactly one active era exists (it then defaults to
    that sole era, preserving every existing single-active-era call site
    unchanged); with two or more active eras it is required — closing
    ``active[-1]`` implicitly is the forbidden proxy this story removes.
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

    if era_id is not None:
        matches = []
        for p in active_eras:
            fm = _parse_era_frontmatter(p.read_text(encoding="utf-8")) or {}
            if fm.get("id") == era_id:
                matches.append(p)
        if not matches:
            names = [p.name for p in active_eras]
            click.echo(
                f"error: --era-id {era_id!r} does not match any active era "
                f"(active: {names}).",
                err=True,
            )
            return 1
        current_era_path = matches[0]
    elif len(active_eras) > 1:
        names = [p.name for p in active_eras]
        click.echo(
            f"Multiple active eras found: {names}. Resolve manually before transitioning."
        )
        return 1
    else:
        current_era_path = active_eras[0]

    current_content = current_era_path.read_text(encoding="utf-8")
    current_fm = _parse_era_frontmatter(current_content)
    current_id = current_fm.get("id", "???") if current_fm else "???"
    current_name = current_fm.get("name", current_era_path.stem) if current_fm else current_era_path.stem

    # 1b. Phase-ledger disposition gate (INFRA-314, Ensures 2). Checked before
    # any prompting or write — a refusal here never reaches
    # _close_era_frontmatter and the era file stays byte-identical.
    gate_message = _phase_ledger_gate_message(current_era_path, current_content)
    if gate_message is not None:
        click.echo(gate_message, err=True)
        return 1

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
@click.option(
    "--era-id",
    default=None,
    help=(
        "Explicit ID of the active era to close (INFRA-314). Optional when "
        "exactly one era is active (defaults to it); required when two or "
        "more are active — there is no implicit 'last active era' target."
    ),
)
def era_transition(
    name: str | None,
    intent: str,
    project_dir: str,
    yes: bool,
    era_id: str | None,
) -> None:
    """Formally close the current active era and open the next one."""
    rc = era_transition_cli(
        project_dir=project_dir,
        name=name,
        intent=intent,
        yes=yes,
        era_id=era_id,
    )
    sys.exit(rc)


if __name__ == "__main__":
    era_transition()

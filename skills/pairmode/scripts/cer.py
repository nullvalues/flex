"""
cer.py — CER (Cold-Eyes Review) triage CLI.

Appends a finding to docs/cer/backlog.md in the correct quadrant.
Creates the file if it does not exist.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

# Insert repo root so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import click
import jinja2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

BACKLOG_TEMPLATE = "docs/cer/backlog.md.j2"
BACKLOG_REL_PATH = "docs/cer/backlog.md"

# CLI quadrant names → internal quadrant values used in the template
QUADRANT_MAP = {
    "now": "do_now",
    "later": "do_later",
    "much_later": "do_much_later",
    "never": "do_never",
}

QUADRANT_CHOICES = list(QUADRANT_MAP.keys())

# Regex to match a CER-NNN id
_CER_ID_RE = re.compile(r"\bCER-(\d{3})\b")

# Regex to parse a table row: | ID | finding | source | date | phase [| resolution] |
# We capture the leading pipe-delimited cells.
_TABLE_ROW_RE = re.compile(
    r"^\|\s*(CER-\d{3})\s*\|"  # ID
    r"\s*(.+?)\s*\|"            # finding
    r"\s*(.+?)\s*\|"            # source
    r"\s*(.+?)\s*\|"            # date
    r"\s*(.+?)\s*\|"            # phase
    r"(?:\s*(.+?)\s*\|)?"       # optional resolution (Do Never)
    r"\s*$"
)

# ---------------------------------------------------------------------------
# Jinja2 environment
# ---------------------------------------------------------------------------

_JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    keep_trailing_newline=True,
)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _render_backlog(cer_entries: list[dict], project_name: str = "Project") -> str:
    """Render backlog.md from the template with the given entries."""
    template = _JINJA_ENV.get_template(BACKLOG_TEMPLATE)
    today = date.today().isoformat()
    return template.render(
        project_name=project_name,
        last_updated=today,
        cer_entries=cer_entries,
    )


def _parse_entries_from_backlog(content: str) -> list[dict]:
    """Parse existing CER entries from a rendered backlog.md.

    Returns a list of entry dicts matching the template schema.
    Entries with ID '—' (placeholder rows) are skipped.
    """
    # We need to determine which section each row belongs to.
    # Sections are delimited by '## Do Now', '## Do Later', etc.
    section_to_quadrant = {
        "## Do Now": "do_now",
        "## Do Later": "do_later",
        "## Do Much Later": "do_much_later",
        "## Do Never": "do_never",
    }

    entries: list[dict] = []
    current_quadrant: str | None = None

    for line in content.splitlines():
        stripped = line.strip()

        # Detect section header
        for header, quadrant in section_to_quadrant.items():
            if stripped == header:
                current_quadrant = quadrant
                break
        else:
            # Parse table data row
            if current_quadrant and stripped.startswith("|"):
                m = _TABLE_ROW_RE.match(stripped)
                if m:
                    cer_id = m.group(1)
                    finding = m.group(2).strip()
                    source = m.group(3).strip()
                    entry_date = m.group(4).strip()
                    phase_raw = m.group(5).strip()
                    resolution_raw = m.group(6).strip() if m.group(6) else None

                    # Skip placeholder rows. Defensive: _TABLE_ROW_RE already
                    # excludes placeholder rows by requiring a CER-NNN id in
                    # the first cell, so this branch cannot fire today — it is
                    # a de-duplication of the shared rule, not a behaviour
                    # change (INFRA-294).
                    if is_placeholder_row([cer_id, finding]):
                        continue

                    entry: dict = {
                        "id": cer_id,
                        "finding": finding,
                        "source": source,
                        "date": entry_date,
                        "quadrant": current_quadrant,
                    }
                    if phase_raw and phase_raw != "—":
                        entry["phase"] = phase_raw
                    if resolution_raw and resolution_raw != "—":
                        entry["resolution"] = resolution_raw

                    entries.append(entry)

    return entries


def is_placeholder_row(cells) -> bool:
    """Return True when ``cells`` is the scaffolded empty-state row.

    ``docs/cer/backlog.md.j2`` (the Jinja template every project is
    bootstrapped from) emits a placeholder row — e.g.
    ``| — | *(none)* | — | — | — |`` (Do Now/Do Later/Do Much Later) or the
    six-column ``| — | *(none)* | — | — | — | — |`` (Do Never) — whenever a
    quadrant has no entries. That row is not a finding: reading it as an
    unresolved Do Now item blocked caddy's first 0.3.0 checkpoint
    (`next_action._check_cer_do_now`, INFRA-294) by failing the
    ``cer-do-now`` checkpoint guard forever. This predicate is the single
    shared source of truth for recognising that row, consumed by both
    ``cer._parse_entries_from_backlog`` and
    ``next_action._check_cer_do_now`` so the rule is defined once rather
    than duplicated with independent writers.

    ``cells`` may be any sequence of (possibly unstripped) table cell
    strings; column count is not checked, since the placeholder row appears
    in four-, five-, and six-column shapes across sections and consumer
    repos (e.g. the four-cell row observed in caddy's own backlog).
    """
    stripped = [c.strip() for c in cells]
    if not stripped:
        return False
    if stripped[0] in ("—", "–", "-"):
        return True
    if any(c == "*(none)*" for c in stripped):
        return True
    return False


# Anchored, case-insensitive resolution-marker grammar (INFRA-322/CER-130).
#
# The keyword must *begin* an annotation segment: the start of the scanned
# text, a newline, a `|` cell boundary or a sentence-ending punctuation mark
# followed by one or more spaces/tabs, or an emphasis/bracket opener
# (`*`, `(`, `[`). A `\b` word boundary is NOT sufficient here — a plain
# space is also a word boundary, so `should be RESOLVED` and
# `not resolved yet` would both incorrectly match a `\b`-based test. The
# boundary is therefore consumed inside the match rather than checked with a
# fixed-width lookbehind (which cannot express "punctuation followed by one
# or more spaces").
#
# Deliberately NOT accepted as openers: backtick, double quote, single quote,
# underscore. Each collides with prose that legitimately quotes the keyword
# (e.g. CER-130's own row text: ``if "RESOLVED" not in stripped``) or with
# Python identifier prose (`_RESOLVED_RE`). Where the grammar is uncertain it
# fails closed: an unrecognised ornamentation reads as unresolved, producing
# a visible, correctable block rather than a silent pass.
_RESOLUTION_MARKER_RE = re.compile(
    r"(?:^|\n|[.!?;:—–|)][ \t]+|[*(\[])"  # segment start
    r"[*(\[]*"                            # optional emphasis/bracket openers
    r"(?:RESOLVED|SUPERSEDED)"            # keyword
    r"(?![A-Za-z0-9_])",                  # close boundary (not \b: excludes "_")
    re.IGNORECASE,
)


def is_resolution_marked(text: str) -> bool:
    """Return True when ``text`` contains at least one resolution marker.

    A **resolution marker** is the keyword ``RESOLVED`` or ``SUPERSEDED``
    (ASCII case-insensitive — ``RESOLVED``, ``Resolved`` and ``resolved`` all
    match) beginning an annotation segment: the start of the text, a
    newline, a ``|`` table-cell boundary, a sentence-ending
    ``.``/``!``/``?``/``;``/``:``/em-dash/``)`` followed by one or more
    spaces or tabs, or an emphasis/bracket opener (``*``, ``(``, ``[``) —
    optionally with more than one opener stacked, e.g. ``**RESOLVED**`` or
    ``(RESOLVED``. A keyword that appears mid-clause — preceded by a plain
    space and a word — is NOT a marker.

    Accepted forms (see INFRA-322 § A2 for the full table):
        - ``**RESOLVED Phase 55 — INFRA-1**`` (flex's own bolded convention)
        - ``Resolved cp-34 — INFRA-1`` (plain title-case, consuming-repo
          convention — this is the CER-130 direction-1 case: a
          case-sensitive substring test on ``"RESOLVED"`` blocked this
          form's checkpoint forever)
        - ``| Resolved cp-34 — INFRA-1 |`` (marker right after a `|` cell
          boundary)
        - ``(RESOLVED INFRA-297)``, ``[RESOLVED]``, ``*Resolved*``
        - ``**SUPERSEDED by CER-9**``

    Rejected forms — this is the CER-130 direction-2 case: a bare substring
    test also matched these, silently waving through genuinely unresolved
    rows:
        - ``UNRESOLVED naming gap …`` (``RESOLVED`` preceded by ``UN``, not
          a segment start)
        - ``this should be RESOLVED before cp`` / ``to be resolved in 116``
          / ``not resolved yet`` / ``**Not resolved**`` (mid-clause —
          preceded by a space, not a segment boundary)
        - ``PARTIALLY RESOLVED phase 3`` (mid-clause; a partial resolution
          keeps a Do Now row blocking — BUILD-006 partial-resolution notes
          are progress records, not closures)
        - ```` the `RESOLVED` literal ```` / ``if "RESOLVED" not in
          stripped`` (backtick/double-quote are deliberately not openers,
          so prose or code quoting the literal — including CER-130's own
          row text — is not a marker)
        - ``_RESOLVED_RE`` (underscore is deliberately not an opener; it
          collides with Python identifier prose)

    A lowercase-only fix (``.upper()``/``.lower()`` before a bare substring
    test) was considered and rejected: it repairs direction 1 but *widens*
    direction 2, since ``unresolved``, ``should be resolved`` and
    ``to be resolved`` would all begin matching once case is folded without
    anchoring. Both directions must be fixed by the same anchored grammar.

    Consumed by ``next_action._check_cer_do_now`` (the ``cer-do-now``
    checkpoint guard). Any future consumer of the resolution-marker
    convention must call this predicate rather than re-deriving its own
    test — the same precedent ``is_placeholder_row`` set for the
    placeholder-row rule (INFRA-294).

    Pure: no I/O, no state, no mutation of ``text``. Returns False for
    ``""`` and for any falsy non-``str`` input rather than raising.
    """
    if not text or not isinstance(text, str):
        return False
    return bool(_RESOLUTION_MARKER_RE.search(text))


def _escape_table_cell(text: str) -> str:
    """Escape pipe characters so they don't corrupt markdown table cells."""
    return text.replace("|", "\\|")


def _next_cer_id(entries: list[dict]) -> str:
    """Determine the next sequential CER-NNN id."""
    max_num = 0
    for entry in entries:
        m = _CER_ID_RE.search(entry.get("id", ""))
        if m:
            num = int(m.group(1))
            if num > max_num:
                max_num = num
    return f"CER-{max_num + 1:03d}"


def _load_or_create_backlog(backlog_path: Path) -> list[dict]:
    """Load existing entries from backlog.md, creating the file first if absent.

    Returns the list of existing entries.
    """
    if not backlog_path.exists():
        # Create the file with empty entries
        backlog_path.parent.mkdir(parents=True, exist_ok=True)
        content = _render_backlog(cer_entries=[])
        backlog_path.write_text(content, encoding="utf-8")
        return []

    content = backlog_path.read_text(encoding="utf-8")
    try:
        entries = _parse_entries_from_backlog(content)
    except Exception as exc:
        raise click.ClickException(
            f"Could not parse {backlog_path}: {exc}"
        ) from exc

    if len(content.splitlines()) > 5 and len(entries) == 0:
        click.echo(
            "Warning: backlog.md exists but no table rows were parsed. "
            "The file may have non-standard formatting. "
            "Existing CER IDs may not be detected — verify before appending.",
            err=True,
        )

    return entries


def append_finding(
    project_dir: Path,
    finding: str,
    quadrant: str,
    reviewer: str = "external",
    resolution: str | None = None,
    phase: int | None = None,
) -> dict:
    """Append a new finding to docs/cer/backlog.md and return the new entry dict.

    ``quadrant`` must be one of the internal values: do_now, do_later,
    do_much_later, do_never.
    """
    backlog_path = project_dir / BACKLOG_REL_PATH
    entries = _load_or_create_backlog(backlog_path)

    new_id = _next_cer_id(entries)
    today = date.today().isoformat()

    entry: dict = {
        "id": new_id,
        "finding": _escape_table_cell(finding),
        "source": _escape_table_cell(reviewer),
        "date": today,
        "quadrant": quadrant,
    }
    if phase is not None:
        entry["phase"] = str(phase)
    if resolution:
        entry["resolution"] = resolution

    entries.append(entry)

    # Resolve project name: pairmode_context.json > heading parse > default
    project_name = "Project"
    context_path = project_dir / ".companion" / "pairmode_context.json"
    if context_path.exists():
        import json as _json
        try:
            ctx = _json.loads(context_path.read_text(encoding="utf-8"))
            name_from_ctx = ctx.get("project_name", "").strip()
            if name_from_ctx:
                project_name = name_from_ctx
        except Exception:
            pass
    if project_name == "Project":
        backlog_path_obj = project_dir / BACKLOG_REL_PATH
        if backlog_path_obj.exists():
            first_line = backlog_path_obj.read_text(encoding="utf-8").splitlines()
            if first_line:
                heading = first_line[0].lstrip("# ").split("—")[0].strip()
                if heading:
                    project_name = heading

    rendered = _render_backlog(entries, project_name=project_name)
    backlog_path.write_text(rendered, encoding="utf-8")

    return entry


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------

def _prompt_finding() -> str:
    """Prompt for a multiline finding description; end with a blank line."""
    print("Enter finding (blank line to finish):")
    lines: list[str] = []
    while True:
        line = input()
        if line == "" and lines:
            break
        if line:
            lines.append(line)
    return "\n".join(lines)


def _prompt_quadrant() -> str:
    """Show quadrant choices and return the chosen internal quadrant value."""
    click.echo("\nQuadrant choices:")
    click.echo("  1. now        — Do Now (urgent and important)")
    click.echo("  2. later      — Do Later (important, not urgent)")
    click.echo("  3. much_later — Do Much Later (marginal value)")
    click.echo("  4. never      — Do Never (rejected)")
    choice = click.prompt(
        "Select quadrant",
        type=click.Choice(QUADRANT_CHOICES),
    )
    return QUADRANT_MAP[choice]


def _prompt_resolution() -> str:
    """Prompt for a rejection reason."""
    return click.prompt("Rejection reason (resolution)")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--project-dir",
    "project_dir",
    default=".",
    show_default=True,
    help="Root directory of the project.",
    type=click.Path(file_okay=False, exists=True),
)
@click.option(
    "--reviewer",
    default="external",
    show_default=True,
    help="Reviewer identifier (source of the finding).",
)
@click.option(
    "--finding",
    default=None,
    help="Finding description. If omitted, an interactive prompt is shown.",
)
@click.option(
    "--quadrant",
    default=None,
    type=click.Choice(QUADRANT_CHOICES),
    help="Triage quadrant: now, later, much_later, never.",
)
@click.option(
    "--resolution",
    default=None,
    help="Rejection reason. Required when --quadrant is 'never'.",
)
@click.option(
    "--phase",
    default=None,
    type=int,
    help="Phase number this finding is associated with.",
)
def cli(
    project_dir: str,
    reviewer: str,
    finding: str | None,
    quadrant: str | None,
    resolution: str | None,
    phase: int | None,
) -> None:
    """Triage a cold-eyes review finding into docs/cer/backlog.md."""
    proj = Path(project_dir).resolve()

    if not proj.is_dir() or len(proj.parts) < 3:
        click.echo("Error: --project-dir is too shallow or not a directory.", err=True)
        raise SystemExit(1)

    # --- Non-interactive path ---
    if finding is not None and quadrant is not None:
        internal_quadrant = QUADRANT_MAP[quadrant]
        if internal_quadrant == "do_never" and not resolution:
            raise click.ClickException(
                "--resolution is required when --quadrant is 'never'."
            )
        entry = append_finding(
            project_dir=proj,
            finding=finding,
            quadrant=internal_quadrant,
            reviewer=reviewer,
            resolution=resolution,
            phase=phase,
        )
        click.echo(f"Finding appended: {entry['id']} → {quadrant}")
        return

    # --- Interactive path ---
    if finding is None:
        finding = _prompt_finding()
        if not finding:
            raise click.ClickException("Finding description cannot be empty.")

    if quadrant is None:
        internal_quadrant = _prompt_quadrant()
    else:
        internal_quadrant = QUADRANT_MAP[quadrant]

    if internal_quadrant == "do_never" and not resolution:
        resolution = _prompt_resolution()

    # Confirmation
    click.echo("\n--- Summary ---")
    click.echo(f"  Finding  : {finding}")
    click.echo(f"  Quadrant : {internal_quadrant}")
    click.echo(f"  Reviewer : {reviewer}")
    if phase is not None:
        click.echo(f"  Phase    : {phase}")
    if resolution:
        click.echo(f"  Resolution: {resolution}")
    click.echo(f"  Project  : {proj}")

    if not click.confirm("\nAppend this finding?", default=True):
        click.echo("Aborted.")
        return

    entry = append_finding(
        project_dir=proj,
        finding=finding,
        quadrant=internal_quadrant,
        reviewer=reviewer,
        resolution=resolution,
        phase=phase,
    )
    click.echo(f"Finding appended: {entry['id']} → {quadrant or internal_quadrant}")


if __name__ == "__main__":
    cli()

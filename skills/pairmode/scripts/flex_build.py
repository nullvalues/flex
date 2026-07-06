"""flex_build.py — single click CLI that aggregates the 8 inline Python
blocks that used to be embedded as ``uv run python -c "..."`` heredocs in
``skills/pairmode/templates/CLAUDE.build.md.j2``.

Each subcommand wraps one helper call from the pairmode scripts package
(``model_selector``, ``permission_scope``, ``effort_db``, ``context_health``).
The CLI exists solely so the orchestrator template can shell out to a single
script rather than embed multi-line Python boilerplate.

Commands: select-builder-model, select-reviewer-model,
select-security-auditor-model, select-intent-reviewer-model,
write-permissions, clear-permissions, permissions-create,
check-guardrail, context-health, check-stubs, current-phase,
transition-era, write-attempt-count, read-attempt-count,
clear-attempt-count, story-cost-estimate.

Story: INFRA-131.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make sibling modules importable when invoked as a script.
sys.path.insert(0, str(Path(__file__).parent))

# next_story is imported lazily inside cmd_current_phase to avoid circular
# import issues when the module is loaded in test environments.


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
# Validation constants
# ---------------------------------------------------------------------------

_STORY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d{3}$")

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
    """Read and parse YAML frontmatter from a story spec file.

    Always includes ``flex_factor`` as a float (default 1.0 when the key is
    absent or non-numeric). INFRA-160.
    """
    text = story_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text) or {}
    # Ensure flex_factor is always a float, defaulting to 1.0.
    try:
        flex_factor = float(fm.get("flex_factor", 1.0) or 1.0)
    except (TypeError, ValueError):
        flex_factor = 1.0
    fm["flex_factor"] = flex_factor
    return fm


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


@flex_build.command("permissions-create")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_permissions_create(story_id: str, project_dir: str) -> None:
    """Generate docs/phases/permissions/<STORY_ID>.json from story spec frontmatter."""
    if not _STORY_ID_RE.match(story_id):
        click.echo(f"permissions-create: invalid story_id format: {story_id!r}", err=True)
        sys.exit(1)

    project_path = Path(project_dir).resolve()
    rail = story_id.split("-")[0]
    story_spec_rel = f"docs/stories/{rail}/{story_id}.md"
    story_path = project_path / story_spec_rel

    stories_root = project_path / "docs" / "stories"
    try:
        story_path.resolve().relative_to(stories_root.resolve())
    except ValueError:
        click.echo("permissions-create: story spec path escapes project root", err=True)
        sys.exit(1)

    if not story_path.exists():
        click.echo(f"permissions-create: story spec not found: {story_path}", err=True)
        sys.exit(1)

    try:
        fm = _read_story_frontmatter(story_path)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"permissions-create: failed to parse frontmatter: {exc}", err=True)
        sys.exit(1)

    primary_files: list[str] = fm.get("primary_files") or []
    touches: list[str] = fm.get("touches") or []

    seen: set[str] = set()
    allowed: list[str] = []
    for p in primary_files + touches:
        if p not in seen:
            seen.add(p)
            allowed.append(p)
    if story_spec_rel not in seen:
        allowed.append(story_spec_rel)

    out_dir = project_path / "docs" / "phases" / "permissions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{story_id}.json"

    try:
        out_path.resolve().relative_to(out_dir.resolve())
    except ValueError:
        click.echo("permissions-create: output path escapes permissions dir", err=True)
        sys.exit(1)

    payload = {
        "story_id": story_id,
        "story_spec": story_spec_rel,
        "allowed_paths": allowed,
        "generated_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    click.echo(
        f"permissions: wrote docs/phases/permissions/{story_id}.json ({len(allowed)} paths)"
    )


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


def _depth_guard(project_dir: Path) -> None:
    """Reject paths that are too shallow (fewer than 3 components)."""
    if len(project_dir.resolve().parts) < 3:
        click.echo(
            f"error: --project-dir '{project_dir}' is too shallow (depth guard).",
            err=True,
        )
        sys.exit(1)


def _is_aggregate_range(phase_ref: str) -> bool:
    """Return True when *phase_ref* looks like a legacy aggregate range (e.g. ``1–7`` or ``1-7``).

    An aggregate range has both sides of the separator as integers.  Named
    suffix phases like ``RD077-main`` are NOT ranges and must not be skipped.
    """
    for sep in ("–", "-"):
        if sep in phase_ref:
            left, _, right = phase_ref.partition(sep)
            try:
                int(left)
                int(right)
                return True
            except ValueError:
                pass
    return False


def _parse_index_phases(index_text: str) -> list[tuple[str, str]]:
    """Parse ``docs/phases/index.md`` and return ``[(phase_ref, status)]``.

    ``phase_ref`` is the raw first-column value (e.g. ``52``, ``RD077-main``).
    ``status`` is the third column, lowercased.

    Rows with multi-phase entries like ``1–7`` or ``1-7`` (where both sides of
    the separator are integers) are skipped because they describe legacy
    aggregated phases that have no individual phase file.  Named suffix phases
    like ``RD077-main`` are retained.
    """
    rows: list[tuple[str, str]] = []
    in_table = False
    header_seen = False
    separator_seen = False

    for line in index_text.splitlines():
        stripped = line.strip()

        if not stripped.startswith("|"):
            if in_table and stripped:
                # End of this table — reset and keep scanning for more tables.
                in_table = False
                header_seen = False
                separator_seen = False
            continue

        in_table = True
        parts = [p.strip() for p in stripped.split("|")]
        if len(parts) < 4:
            continue

        if not header_seen:
            header_seen = True
            continue

        if not separator_seen:
            separator_seen = True
            continue

        phase_ref = parts[1].strip()
        # Skip aggregate range rows (e.g. "1–7", "1-7") but keep suffix-keyed
        # phases like "RD077-main".
        if _is_aggregate_range(phase_ref):
            continue

        # Status is the third data column (index 3 after leading empty at 0).
        status = parts[3].strip().lower() if len(parts) > 3 else ""
        rows.append((phase_ref, status))

    return rows


def _is_terminal_status(status: str) -> bool:
    """Return True when *status* represents a terminal (done / closed) phase state.

    Terminal statuses:
    - Exactly ``complete`` or begins with ``complete`` (e.g. ``complete (partial)``).

    Match is case-insensitive; the caller is expected to pass an already-lowercased,
    stripped value (as returned by ``_parse_index_phases``), but we normalise anyway.
    """
    normalised = status.strip().lower()
    return normalised == "complete" or normalised.startswith("complete")


def _is_active_status(status: str) -> bool:
    """Return True when *status* means the phase is eligible as the current active phase.

    Active = not terminal and not deferred.
    ``deferred`` phases are parked; they are never returned as the active phase.
    """
    normalised = status.strip().lower()
    if _is_terminal_status(normalised):
        return False
    if normalised == "deferred":
        return False
    return True


@flex_build.command("current-phase")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_current_phase(project_dir: str) -> None:
    """Print the active phase file path; exit 1 if all stories are complete."""
    # Import lazily to avoid issues in environments where next_story isn't on
    # sys.path at module load time.
    from next_story import find_next_story  # noqa: E402  # type: ignore[import]

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)

    index_path = project_path / "docs" / "phases" / "index.md"

    if index_path.exists():
        index_text = index_path.read_text(encoding="utf-8")
        phase_rows = _parse_index_phases(index_text)

        # Walk rows in index order (build order) and return the FIRST active
        # phase whose phase file exists.  Skip terminal statuses
        # (``complete``, ``complete (partial)``, …) and parked phases
        # (``deferred``).  A planned-but-fileless future row must never mask
        # an earlier active phase that has a file.
        for phase_ref, status in phase_rows:
            if not _is_active_status(status):
                continue
            candidate = project_path / "docs" / "phases" / f"phase-{phase_ref}.md"
            if candidate.exists():
                click.echo(str(candidate.relative_to(project_path)))
                sys.exit(0)
            # Active row but no file yet — keep scanning for an earlier
            # active row that does have a file (fileless-phase guard).

        # Index exists but no active phase with an existing file was found.
        click.echo("No active phase found — all stories complete.", err=True)
        sys.exit(1)

    # No index file — fallback: scan phase files directly for one with an
    # unbuilt story.
    phases_dir = project_path / "docs" / "phases"
    if not phases_dir.exists():
        click.echo("No active phase found — all stories complete.", err=True)
        sys.exit(1)

    # Collect all phase-N.md files and sort descending by N.
    phase_files = sorted(
        phases_dir.glob("phase-*.md"),
        key=lambda p: int(re.search(r"phase-(\d+)\.md", p.name).group(1))  # type: ignore[union-attr]
        if re.search(r"phase-(\d+)\.md", p.name)
        else 0,
        reverse=True,
    )

    for phase_file in phase_files:
        try:
            result = find_next_story(phase_file, project_path)
        except Exception:  # noqa: BLE001
            continue
        if result is not None:
            click.echo(str(phase_file.relative_to(project_path)))
            sys.exit(0)

    click.echo("No active phase found — all stories complete.", err=True)
    sys.exit(1)


@flex_build.command("next-phase")
@click.option(
    "--after",
    "after_phase",
    required=True,
    type=str,
    help="Current phase key (e.g. 59 or RD077-main).",
)
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_next_phase(after_phase: str, project_dir: str) -> None:
    """Print the phase key immediately following *after_phase* in the index.

    Reads ``docs/phases/index.md``, finds the row whose ``phase_ref`` equals
    ``--after``, and prints the ``phase_ref`` of the next row.  Exits 1
    (with empty stdout) when the index is missing, the phase is not found, or
    the matched row is the last in the index.

    The command is read-only and makes no writes.
    """
    project_path = Path(project_dir).resolve()

    index_path = project_path / "docs" / "phases" / "index.md"
    if not index_path.exists():
        sys.exit(1)

    index_text = index_path.read_text(encoding="utf-8")
    phase_rows = _parse_index_phases(index_text)

    for i, (phase_ref, _status) in enumerate(phase_rows):
        if phase_ref == after_phase:
            if i + 1 < len(phase_rows):
                click.echo(phase_rows[i + 1][0])
                sys.exit(0)
            else:
                # Matched row is the last one — no next phase.
                sys.exit(1)

    # Phase not found in index.
    sys.exit(1)


@flex_build.command("mark-phase-complete")
@click.option(
    "--phase",
    "phase_key",
    required=True,
    type=str,
    help="Phase key to mark complete (e.g. 59 or PM037-main).",
)
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_mark_phase_complete(phase_key: str, project_dir: str) -> None:
    """Set the status cell of a phase row in docs/phases/index.md to 'complete'."""
    import tempfile  # noqa: PLC0415

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    index_path = project_path / "docs" / "phases" / "index.md"
    if not index_path.exists():
        click.echo(
            f"mark-phase-complete: index not found: {index_path}", err=True
        )
        raise SystemExit(1)

    text = index_path.read_text(encoding="utf-8")
    rows = _parse_index_phases(text)
    found = any(ref == phase_key for ref, _ in rows)
    if not found:
        click.echo(
            f"mark-phase-complete: phase '{phase_key}' not in index", err=True
        )
        raise SystemExit(1)

    # Check for idempotency: if already complete, exit silently.
    for ref, status in rows:
        if ref == phase_key and status == "complete":
            sys.exit(0)

    # Rewrite the matching row in-place, line by line.
    new_lines: list[str] = []
    replaced = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if not replaced and stripped.startswith("|"):
            # inner cells: drop the leading/trailing empty strings produced by
            # splitting "| a | b | c |" on "|"
            cells = [p.strip() for p in stripped.split("|")[1:-1]]
            # cells[0]=phase, cells[1]=title, cells[2]=status, cells[3:]=rest
            if len(cells) >= 3:
                if cells[0] == phase_key and cells[2] != "complete":
                    cells[2] = "complete"
                    new_row = "| " + " | ".join(cells) + " |\n"
                    new_lines.append(new_row)
                    replaced = True
                    continue
        new_lines.append(line)

    new_text = "".join(new_lines)

    # Atomic write: NamedTemporaryFile in same directory + os.replace.
    dir_ = index_path.parent
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=dir_,
        delete=False,
        suffix=".tmp",
    ) as tf:
        tf.write(new_text)
        tmp_path_str = tf.name

    os.replace(tmp_path_str, index_path)


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


# ---------------------------------------------------------------------------
# Per-story attempt counter (BUILD-022)
# ---------------------------------------------------------------------------


def _attempt_counter_path(project_dir: Path) -> Path:
    return project_dir / ".companion" / "attempt_counter.json"


@flex_build.command("write-attempt-count")
@click.option("--story-id", required=True, help="Story ID (e.g. BUILD-022).")
@click.option("--count", required=True, type=int, help="Attempt count (>=1).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_write_attempt_count(story_id: str, count: int, project_dir: str) -> None:
    """Persist the per-story attempt counter to .companion/attempt_counter.json."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    path = _attempt_counter_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"story_id": story_id, "attempt_count": count}),
        encoding="utf-8",
    )


@flex_build.command("read-attempt-count")
@click.option("--story-id", required=True, help="Story ID (e.g. BUILD-022).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_read_attempt_count(story_id: str, project_dir: str) -> None:
    """Print the persisted attempt count for *story_id* (0 if absent/mismatched)."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    path = _attempt_counter_path(project_path)
    if not path.exists():
        click.echo("0")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        click.echo("0")
        return
    if data.get("story_id") != story_id:
        click.echo("0")
        return
    try:
        click.echo(str(int(data.get("attempt_count", 0))))
    except (TypeError, ValueError):
        click.echo("0")


@flex_build.command("clear-attempt-count")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_clear_attempt_count(project_dir: str) -> None:
    """Delete .companion/attempt_counter.json if present."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    path = _attempt_counter_path(project_path)
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Story cost estimate (INFRA-135)
# ---------------------------------------------------------------------------


_COST_MIN_SAMPLE = 3


def _query_story_cost_samples(
    db_path: Path, rail: str, story_class: str
) -> tuple[list[int], str]:
    """Return ``(tokens_total_values, tier)`` using a waterfall query strategy.

    Tier 1 — specific (rail, story_class): if ≥ ``_COST_MIN_SAMPLE`` PASS rows.
    Tier 2 — all rails, same story_class: if Tier 1 insufficient.
    Tier 3 — all PASS rows (global): if Tier 2 insufficient.
    Tier 4 — ``"insufficient"`` if global < ``_COST_MIN_SAMPLE``.

    Returns a ``(rows, tier)`` tuple where ``tier`` is one of
    ``"rail"``, ``"all-rails"``, ``"global"``, or ``"insufficient"``.
    (INFRA-171)
    """
    import sqlite3

    if not db_path.exists():
        return [], "insufficient"

    def _q(conn: sqlite3.Connection, where: str, *params: object) -> list[int]:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT tokens_total
              FROM attempts
             WHERE {where}
               AND outcome = 'PASS'
               AND tokens_total IS NOT NULL
               AND tokens_total > 0
            """,
            params,
        )
        return [int(row[0]) for row in cur.fetchall()]

    conn = sqlite3.connect(str(db_path))
    try:
        # Tier 1: specific rail + story_class.
        rows = _q(conn, "rail = ? AND story_class = ?", rail, story_class)
        if len(rows) >= _COST_MIN_SAMPLE:
            return rows, "rail"

        # Tier 2: all rails, same story_class.
        rows = _q(conn, "story_class = ?", story_class)
        if len(rows) >= _COST_MIN_SAMPLE:
            return rows, "all-rails"

        # Tier 3: global — all PASS rows.
        rows = _q(conn, "1=1")
        if len(rows) >= _COST_MIN_SAMPLE:
            return rows, "global"

        return rows, "insufficient"
    finally:
        conn.close()


@flex_build.command("story-cost-estimate")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-135).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_story_cost_estimate(story_id: str, project_dir: str) -> None:
    """Print a one-line median PASS-token estimate for (rail, story_class)."""
    import statistics

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    story_path = _story_path(story_id, project_path)
    fm = _read_story_frontmatter(story_path) if story_path.exists() else {}
    rail = (fm.get("rail") or story_id.split("-", 1)[0]).strip()
    story_class = (fm.get("story_class") or "code").strip()

    db_path = resolve_effort_db_path(project_path)
    samples, tier = _query_story_cost_samples(db_path, rail, story_class)
    n = len(samples)

    if tier == "insufficient":
        click.echo(
            f"estimate: insufficient data ({n} PASS attempts on {rail}/{story_class})"
        )
        return

    median = int(statistics.median(samples))

    if tier == "rail":
        click.echo(
            f"estimate: {median} tokens (median of {n} PASS attempts on {rail}/{story_class})"
        )
    elif tier == "all-rails":
        click.echo(
            f"estimate: {median} tokens (median of {n} PASS attempts, all rails, story_class={story_class})"
        )
    else:  # global
        click.echo(
            f"estimate: {median} tokens (median of {n} PASS attempts, global)"
        )


@flex_build.command("set-context-tokens")
@click.option("--tokens", required=True, type=int, help="Token count from /context (must be > 0).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_set_context_tokens(tokens: int, project_dir: str) -> None:
    """Record the current ``/context`` token count into ``.companion/state.json``.

    Writes ``state["context_current_tokens"] = N`` and
    ``state["context_current_tokens_recorded_at"] = <ISO-8601>``.

    This is a manual override / debugging escape hatch. Under normal operation,
    ``post_tool_use.py`` writes ``context_current_tokens`` automatically after
    each Task/Agent completion by reading the JSONL transcript (INFRA-182).
    ``pre_tool_use.py`` reads this value to enforce the context budget gate.
    """
    if tokens <= 0:
        click.echo(
            f"set-context-tokens: --tokens must be > 0 (got {tokens})", err=True
        )
        sys.exit(1)

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    companion = project_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state_path = companion / "state.json"

    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except (json.JSONDecodeError, OSError):
            state = {}
    else:
        state = {}

    now_iso = datetime.now(timezone.utc).isoformat()

    # Scalar write — the sole gate token source for INFRA-182.
    state["context_current_tokens"] = tokens
    state["context_current_tokens_recorded_at"] = now_iso

    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    click.echo(f"context: recorded {tokens:,} tokens")


@flex_build.command("bump-context-tokens")
@click.option("--cost", required=True, type=int, help="Token cost to add (must be > 0).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_bump_context_tokens(cost: int, project_dir: str) -> None:
    """Add --cost to context_current_tokens in state.json (per-story accumulation).

    When ``context_current_tokens`` is absent or invalid, treats the base as 0
    and writes ``cost`` as the new value.  Resets ``context_current_tokens_recorded_at``
    on every successful write so the TTL clock restarts after each bump.

    Silent no-op (exit 0) when ``.companion/state.json`` is absent — consistent
    with ``set-context-tokens`` fail-open behaviour for non-pairmode projects.
    """
    if cost <= 0:
        click.echo(
            f"bump-context-tokens: --cost must be > 0 (got {cost})", err=True
        )
        sys.exit(1)

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    state_path = project_path / ".companion" / "state.json"

    if not state_path.exists():
        return  # non-pairmode project, fail-open

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (json.JSONDecodeError, OSError):
        state = {}

    existing = state.get("context_current_tokens")
    try:
        base = int(existing) if existing and int(existing) > 0 else 0
    except (TypeError, ValueError):
        base = 0

    state["context_current_tokens"] = base + cost
    state["context_current_tokens_recorded_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    click.echo(f"context: bumped by {cost:,} → total {state['context_current_tokens']:,} tokens")


@flex_build.command("check-story-scope")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_story_scope(story_id: str, project_dir: str) -> None:
    """Check declared primary_files/touches for common co-dependency scope misses.

    Applies two heuristics:

    1. Test co-location — a skills/pairmode/scripts/*.py file should have its
       sibling test declared.
    2. Template/live-rendered pair — a *.j2 template should have its rendered
       live counterpart declared.

    Always exits 0.  Prints nothing when no warnings are found.
    """
    # Validate story_id format.
    if not _STORY_ID_RE.match(story_id):
        click.echo(
            f"check-story-scope: invalid story_id format: {story_id!r}", err=True
        )
        sys.exit(1)

    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)

    if not story_path.exists():
        click.echo(
            f"check-story-scope: story spec not found: {story_path}", err=True
        )
        sys.exit(1)

    try:
        fm = _read_story_frontmatter(story_path)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"check-story-scope: failed to parse frontmatter: {exc}", err=True)
        sys.exit(1)

    primary_files: list[str] = fm.get("primary_files") or []
    touches: list[str] = fm.get("touches") or []

    def _norm(s: str) -> str:
        return s.replace("\\", "/").lstrip("./")

    # Build the declared scope set (normalised).
    scope_set: set[str] = set()
    for p in primary_files + touches:
        scope_set.add(_norm(p))

    # Rule 1 — Test co-location.
    for p in primary_files + touches:
        np = _norm(p)
        # Match skills/pairmode/scripts/<name>.py where <name> is not test_* / __init__
        parts = np.split("/")
        if (
            len(parts) == 4
            and parts[0] == "skills"
            and parts[1] == "pairmode"
            and parts[2] == "scripts"
            and parts[3].endswith(".py")
        ):
            basename = parts[3]
            if basename.startswith("test_") or basename == "__init__.py":
                continue
            stem = basename[:-3]  # strip .py
            expected_test = f"tests/pairmode/test_{stem}.py"
            # Check that the test file exists on disk.
            if (project_path / expected_test).exists():
                if _norm(expected_test) not in scope_set:
                    click.echo(
                        f"SCOPE WARNING: {story_id}: scripts/{basename} declared but "
                        f"tests/pairmode/test_{stem}.py not in primary_files/touches"
                    )

    # Rule 2 — Template / live-rendered pair.
    for p in primary_files + touches:
        np = _norm(p)
        # Match skills/pairmode/templates/**/*.j2
        if not (np.startswith("skills/pairmode/templates/") and np.endswith(".j2")):
            continue
        bare = Path(np).name[:-3]  # strip .j2
        # Candidate locations in order:
        # 1. bare at project root
        # 2. skills/pairmode/<bare>
        candidates = [bare, f"skills/pairmode/{bare}"]
        for candidate in candidates:
            if (project_path / candidate).exists():
                if _norm(candidate) not in scope_set:
                    click.echo(
                        f"SCOPE WARNING: {story_id}: {np} declared but "
                        f"{candidate} not in primary_files/touches"
                    )
                # Only emit for the first matching candidate.
                break

    # Rule: architecture.md prompt for code stories with no docs/ touches.
    story_class = fm.get("story_class") or "code"
    if story_class == "code":
        all_files = list(primary_files) + list(touches)
        has_docs_path = any(
            str(p).startswith("docs/") for p in all_files
        )
        if not has_docs_path:
            click.echo(
                "Scope hint: if this story affects documented architecture, "
                "add docs/architecture.md to touches."
            )

    sys.exit(0)


# ---------------------------------------------------------------------------
# Pre-flight gate CLIs (BUILD-034)
# ---------------------------------------------------------------------------

_STUB_DELEGATION_RE = re.compile(
    r"see phase doc|see docs/phases/|see phase-",
    re.IGNORECASE,
)
_STUB_ACCEPTANCE_RE = re.compile(
    r"^##\s+(?:ensures|acceptance criterion|acceptance criteria)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_SCHEMA_MGMT_KEYWORDS = re.compile(
    r"\b(?:management|ui|crud|admin|route|page|command|dashboard)\b",
    re.IGNORECASE,
)
_SCHEMA_EXCEPTION_RE = re.compile(
    r"append-only|junction table|cron-output cache",
    re.IGNORECASE,
)

_AUTH_CLASSIFICATION_RE = re.compile(
    r"^\*\*Classification:\*\*",
    re.MULTILINE,
)


def _story_body(text: str) -> str:
    """Return the body of a story file (after the closing --- of frontmatter)."""
    lines = text.splitlines(keepends=True)
    # Find the second '---' line
    dashes_found = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            dashes_found += 1
            if dashes_found == 2:
                return "".join(lines[i + 1:])
    return text


def _find_phase_file(phase_id: str, project_dir: Path) -> Path | None:
    """Return the path to the phase file for *phase_id*, or None if not found."""
    candidate = project_dir / "docs" / "phases" / f"phase-{phase_id}.md"
    if candidate.exists():
        return candidate
    return None


def _parse_phase_stories_with_status(phase_text: str) -> list[tuple[str, str, str]]:
    """Parse the ## Stories table; return [(story_id, title, status)]."""
    stories_section_re = re.compile(r"^##\s+Stories\s*$", re.MULTILINE)
    m = stories_section_re.search(phase_text)
    if not m:
        return []

    section = phase_text[m.end():]
    rows: list[tuple[str, str, str]] = []
    header_seen = False
    separator_seen = False
    in_table = False

    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        if not stripped.startswith("|"):
            if in_table and stripped:
                break
            continue
        in_table = True
        parts = [p.strip() for p in stripped.split("|")]
        if len(parts) < 4:
            continue
        if not header_seen:
            header_seen = True
            continue
        if not separator_seen:
            separator_seen = True
            continue
        story_id_cell = parts[1].strip()
        title_cell = parts[2].strip() if len(parts) > 2 else ""
        status_cell = parts[3].strip().lower() if len(parts) > 3 else ""
        # Strip Markdown link syntax
        story_id_cell = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", story_id_cell)
        if story_id_cell:
            rows.append((story_id_cell, title_cell, status_cell))
    return rows


@flex_build.command("check-stub")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_stub(story_id: str, project_dir: str) -> None:
    """Check a single story file for stub indicators (delegation language or missing acceptance surface).

    Exits 0 silently on a clean story.
    Exits 1 with a structured block when the story is a stub.
    Exits 2 with a clear error message when the story file cannot be found.
    """
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)

    if not story_path.exists():
        click.echo(
            f"check-stub: story file not found: {story_path}", err=True
        )
        sys.exit(2)

    text = story_path.read_text(encoding="utf-8")
    body = _story_body(text)

    reasons: list[str] = []

    # Check for delegation language in the body.
    m = _STUB_DELEGATION_RE.search(body)
    if m:
        line_start = body.rfind("\n", 0, m.start()) + 1
        line_end = body.find("\n", m.end())
        matched_line = body[line_start: line_end if line_end != -1 else len(body)].strip()
        if len(matched_line) > 80:
            matched_line = matched_line[:80] + "..."
        reasons.append(f'Delegation language found: "{matched_line}"')

    # Check for acceptance surface.
    if not _STUB_ACCEPTANCE_RE.search(text):
        reasons.append(
            "No acceptance surface found (missing ## Ensures, ## Acceptance criterion, "
            "or ## Acceptance criteria)."
        )

    if reasons:
        click.echo(f"PRE-STORY BLOCK — Story [{story_id}] is a stub.")
        for reason in reasons:
            click.echo(reason)
        click.echo("Action required: fill in the story spec before building.")
        click.echo('When resolved, say: "Continue building"')
        sys.exit(1)

    # Silent pass.
    sys.exit(0)


@flex_build.command("check-schema-gate")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_schema_gate(story_id: str, project_dir: str) -> None:
    """Check whether a schema-introducing story has a management surface in the phase.

    Exits 0 silently when schema_introduces is absent/false, or when a management
    surface story or documented exception is present.
    Exits 1 with a structured block when schema_introduces is true and neither
    condition is satisfied.
    Exits 2 with a clear error message when the story file cannot be found.
    """
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)

    if not story_path.exists():
        click.echo(
            f"check-schema-gate: story file not found: {story_path}", err=True
        )
        sys.exit(2)

    text = story_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text) or {}

    schema_introduces_raw = fm.get("schema_introduces")
    # _parse_frontmatter returns strings; coerce "true"/"false" as booleans.
    if isinstance(schema_introduces_raw, bool):
        schema_introduces = schema_introduces_raw
    elif isinstance(schema_introduces_raw, str):
        schema_introduces = schema_introduces_raw.lower() == "true"
    else:
        schema_introduces = False

    if not schema_introduces:
        sys.exit(0)

    # schema_introduces is True — look for management surface or exception phrase.
    body = _story_body(text)

    # Check for exception phrase in story body.
    if _SCHEMA_EXCEPTION_RE.search(body):
        sys.exit(0)

    # Load phase manifest to check remaining unbuilt stories.
    phase_id = fm.get("phase")
    if phase_id is not None:
        phase_id_str = str(phase_id).strip()
        phase_file = _find_phase_file(phase_id_str, project_path)
        if phase_file is not None:
            phase_text = phase_file.read_text(encoding="utf-8")
            phase_stories = _parse_phase_stories_with_status(phase_text)
            for sid, title, status in phase_stories:
                if status == "complete":
                    continue
                if _SCHEMA_MGMT_KEYWORDS.search(title):
                    sys.exit(0)
                # Also check the story file's title if we can read it.
                candidate_path = _story_path(sid, project_path)
                if candidate_path.exists():
                    candidate_fm = _parse_frontmatter(
                        candidate_path.read_text(encoding="utf-8")
                    ) or {}
                    candidate_title = candidate_fm.get("title") or ""
                    if _SCHEMA_MGMT_KEYWORDS.search(candidate_title):
                        sys.exit(0)

    click.echo(
        f"PRE-STORY BLOCK — Story [{story_id}] introduces a schema object with no management surface."
    )
    click.echo("Options:")
    click.echo("1. Add a management UI story to the phase spec before building.")
    click.echo(
        "2. Note an explicit exception in the story spec (append-only, junction table,"
    )
    click.echo("   or cron-output cache) if one of those categories applies.")
    sys.exit(1)


@flex_build.command("check-auth-gate")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_auth_gate(story_id: str, project_dir: str) -> None:
    """Check whether an auth-gated story has a recorded auth model classification.

    Exits 0 silently when auth_gated is absent/false, or when docs/architecture.md
    contains a **Classification:** line.
    Exits 1 with a structured block when auth_gated is true and no classification
    is recorded.
    Exits 2 with a clear error message when the story file cannot be found.
    """
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)

    if not story_path.exists():
        click.echo(
            f"check-auth-gate: story file not found: {story_path}", err=True
        )
        sys.exit(2)

    text = story_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text) or {}

    auth_gated_raw = fm.get("auth_gated")
    # _parse_frontmatter returns strings; coerce "true"/"false" as booleans.
    if isinstance(auth_gated_raw, bool):
        auth_gated = auth_gated_raw
    elif isinstance(auth_gated_raw, str):
        auth_gated = auth_gated_raw.lower() == "true"
    else:
        auth_gated = False

    if not auth_gated:
        sys.exit(0)

    # auth_gated is True — check docs/architecture.md for **Classification:** line.
    arch_path = project_path / "docs" / "architecture.md"
    if arch_path.exists():
        arch_text = arch_path.read_text(encoding="utf-8")
        if _AUTH_CLASSIFICATION_RE.search(arch_text):
            sys.exit(0)

    click.echo(
        f"AUTH GATE — Story [{story_id}] is auth-gated but no classification is recorded."
    )
    click.echo(
        "Load ~/.claude/policies/auth-coexistence.md and classify the auth model"
    )
    click.echo(
        "(RBAC / ABAC / both), then record it in docs/architecture.md before building."
    )
    sys.exit(1)


@flex_build.command("transition-era")
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
def cmd_transition_era(
    name: str | None,
    intent: str,
    project_dir: str,
    yes: bool,
) -> None:
    """Formally close the current active era and open the next one."""
    from era_transition import era_transition_cli  # noqa: PLC0415

    sys.exit(
        era_transition_cli(
            project_dir=project_dir,
            name=name,
            intent=intent,
            yes=yes,
        )
    )


if __name__ == "__main__":
    flex_build()

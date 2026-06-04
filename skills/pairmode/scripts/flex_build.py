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
import re
import sys
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


def _parse_index_phases(index_text: str) -> list[tuple[str, str]]:
    """Parse ``docs/phases/index.md`` and return ``[(phase_ref, status)]``.

    ``phase_ref`` is the raw first-column value (e.g. ``52`` or ``1–7``).
    ``status`` is the third column, lowercased.

    Rows with multi-phase entries like ``1–7`` are skipped because they
    describe legacy aggregated phases that have no individual phase file.
    """
    rows: list[tuple[str, str]] = []
    in_table = False
    header_seen = False
    separator_seen = False

    for line in index_text.splitlines():
        stripped = line.strip()

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

        phase_ref = parts[1].strip()
        # Skip aggregate rows (e.g. "1–7", "1-7")
        if "–" in phase_ref or ("-" in phase_ref and not phase_ref.isdigit()):
            try:
                int(phase_ref)
            except ValueError:
                continue

        # Status is the third data column (index 3 after leading empty at 0).
        status = parts[3].strip().lower() if len(parts) > 3 else ""
        rows.append((phase_ref, status))

    return rows


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

        # Walk rows in order and keep track of the last phase that is not
        # 'complete'. The last such row wins (most recent active phase).
        active_phase_ref: str | None = None
        for phase_ref, status in phase_rows:
            if status != "complete":
                active_phase_ref = phase_ref

        if active_phase_ref is not None:
            candidate = project_path / "docs" / "phases" / f"phase-{active_phase_ref}.md"
            if candidate.exists():
                click.echo(str(candidate.relative_to(project_path)))
                sys.exit(0)

        # Index exists but all phases are complete (or the active phase file is
        # missing) — authoritative signal that no active phase remains.
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
) -> list[int]:
    """Return tokens_total values for PASS rows matching (rail, story_class)."""
    import sqlite3

    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tokens_total
              FROM attempts
             WHERE rail = ?
               AND story_class = ?
               AND outcome = 'PASS'
               AND tokens_total IS NOT NULL
               AND tokens_total > 0
            """,
            (rail, story_class),
        )
        return [int(row[0]) for row in cur.fetchall()]
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
    samples = _query_story_cost_samples(db_path, rail, story_class)
    n = len(samples)

    if n < _COST_MIN_SAMPLE:
        click.echo(
            f"estimate: insufficient data ({n} PASS attempts on {rail}/{story_class})"
        )
        return

    median = int(statistics.median(samples))
    click.echo(
        f"estimate: {median} tokens (median of {n} PASS attempts on {rail}/{story_class})"
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

    Writes ``state["context_current_tokens"] = N``. The pre_tool_use hook reads
    this value (via ``context_budget.read_context_tokens_from_state``) to decide
    whether to block a Task spawn (INFRA-148).
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

    state["context_current_tokens"] = tokens
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    click.echo(f"context: recorded {tokens:,} tokens")


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

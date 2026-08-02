"""record_attempt.py — append one row to the effort-tracking sqlite DB.

Invoked by the orchestrator after every Agent tool call when
``effort_tracking`` is enabled in ``.companion/state.json``.

No-op (exits 0) when:
- ``state.json`` is absent.
- ``effort_tracking`` is missing or false in ``state.json``.

In both no-op cases a single line is written to stderr for visibility so
that the orchestrator log shows the recording was attempted but skipped.
"""

from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

# Insert repo root and scripts dir for sibling imports when run as CLI.
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import click

from schema_validator import _parse_frontmatter
from skills.pairmode.scripts import effort_db as _effort_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string with timezone."""

    return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()


def _read_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--story-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help=(
        "Path to a story file with YAML frontmatter. "
        "Auto-fills --story-id, --phase, --rail, --story-class from frontmatter fields "
        "(id, phase, rail, story_class). Explicit flags take precedence."
    ),
)
@click.option("--story-id", default=None, help="Story ID, e.g. INFRA-028.")
@click.option("--phase", default=None, help="Phase number as string.")
@click.option("--rail", default=None, help="Rail name (INFRA, BUILD, ...).")
@click.option(
    "--agent-role",
    required=True,
    help="Agent role (builder, reviewer, intent-reviewer, security-auditor, "
    "loop-breaker, seed-miner, seed-reconcile, sidebar-extractor).",
)
@click.option("--model", default=None, help="Claude model identifier.")
@click.option(
    "--attempt-number",
    type=int,
    default=1,
    show_default=True,
    help="1 for first try, 2 for retry, etc.",
)
@click.option(
    "--usage-block",
    default=None,
    help="Parse <usage>…</usage> block from file or stdin (- for stdin).",
)
@click.option("--tokens-total", type=int, default=None)
@click.option("--tokens-in", type=int, default=None)
@click.option("--tokens-out", type=int, default=None)
@click.option("--cache-read-tokens", type=int, default=None)
@click.option("--cache-write-tokens", type=int, default=None)
@click.option("--duration-ms", type=int, default=None)
@click.option(
    "--outcome",
    default=None,
    help="PASS | FAIL | PARTIAL (free-form; recommended values).",
)
@click.option("--notes", default=None, help="Free-form note.")
@click.option(
    "--story-class",
    default=None,
    help="Story class (code, doc, lesson, methodology). NULL for pre-INFRA-045 builds.",
)
@click.option(
    "--model-selection-reason",
    default=None,
    help=(
        "Reason for model selection: auto-downgrade, auto-baseline, "
        "prompted-upgrade, user-override. NULL for pre-INFRA-050 builds."
    ),
)
@click.option(
    "--ts",
    default=None,
    help="ISO-8601 UTC timestamp; auto-filled with current UTC if omitted.",
)
@click.option(
    "--project-dir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root used to resolve .companion/state.json and the DB.",
)
@click.option(
    "--db-path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Override the effort DB path. Otherwise resolved from state.json.",
)
@click.option(
    "--allow-duplicate",
    is_flag=True,
    default=False,
    help=(
        "Override the default collision-refusal for a deliberate manual "
        "reconciliation (INFRA-345). Without this flag, a call whose "
        "(story_id, agent_role, attempt_number) triple already has an "
        "existing row in the effort database is refused."
    ),
)
def record_attempt(
    story_file: str | None,
    story_id: str | None,
    phase: str | None,
    rail: str | None,
    agent_role: str,
    model: str | None,
    attempt_number: int,
    usage_block: str | None,
    tokens_total: int | None,
    tokens_in: int | None,
    tokens_out: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
    duration_ms: int | None,
    outcome: str | None,
    notes: str | None,
    story_class: str | None,
    model_selection_reason: str | None,
    ts: str | None,
    project_dir: str,
    db_path: str | None,
    allow_duplicate: bool,
) -> None:
    """Append one attempt row.  No-op when effort tracking is disabled."""

    # ---------------------------------------------------------------------------
    # Parse --usage-block and fill in any numeric fields not set explicitly
    # ---------------------------------------------------------------------------
    if usage_block is not None:
        try:
            if usage_block == "-":
                raw = sys.stdin.read()
            else:
                raw = Path(usage_block).read_text(encoding="utf-8")

            # Extract content between <usage> and </usage>
            usage_match = re.search(r"<usage>(.*?)</usage>", raw, re.DOTALL)
            if usage_match is None:
                click.echo(
                    "warning: could not parse usage block: no <usage>…</usage> found",
                    err=True,
                )
            else:
                block_text = usage_match.group(1)

                # Mapping: XML tag name → (local var name, CLI flag name)
                _TAG_MAP = {
                    "total_tokens": "tokens_total",
                    "input_tokens": "tokens_in",
                    "output_tokens": "tokens_out",
                    "cache_read_tokens": "cache_read_tokens",
                    "cache_write_tokens": "cache_write_tokens",
                    "duration_ms": "duration_ms",
                }

                parsed: dict[str, int] = {}
                for tag, _var in _TAG_MAP.items():
                    m = re.search(
                        r"<" + tag + r">\s*(\d+)\s*</" + tag + r">",
                        block_text,
                    )
                    if m:
                        parsed[tag] = int(m.group(1))

                # Apply parsed values only when the explicit flag was not supplied
                if tokens_total is None and "total_tokens" in parsed:
                    tokens_total = parsed["total_tokens"]
                if tokens_in is None and "input_tokens" in parsed:
                    tokens_in = parsed["input_tokens"]
                if tokens_out is None and "output_tokens" in parsed:
                    tokens_out = parsed["output_tokens"]
                if cache_read_tokens is None and "cache_read_tokens" in parsed:
                    cache_read_tokens = parsed["cache_read_tokens"]
                if cache_write_tokens is None and "cache_write_tokens" in parsed:
                    cache_write_tokens = parsed["cache_write_tokens"]
                if duration_ms is None and "duration_ms" in parsed:
                    duration_ms = parsed["duration_ms"]

        except OSError as exc:
            click.echo(
                f"warning: could not parse usage block: {exc}",
                err=True,
            )

    # ---------------------------------------------------------------------------
    # Auto-fill from --story-file frontmatter (explicit flags take precedence)
    # ---------------------------------------------------------------------------
    if story_file is not None:
        story_path = Path(story_file)
        try:
            text = story_path.read_text(encoding="utf-8")
        except OSError as exc:
            click.echo(f"error: cannot read story file: {exc}", err=True)
            sys.exit(1)

        fm = _parse_frontmatter(text)
        if fm is None:
            click.echo(
                f"error: no valid YAML frontmatter found in {story_file}",
                err=True,
            )
            sys.exit(1)

        # story_id from frontmatter 'id' field (required when --story-id not given)
        if story_id is None:
            fm_id = fm.get("id")
            if not fm_id:
                click.echo(
                    "error: frontmatter missing required 'id' field and --story-id not supplied",
                    err=True,
                )
                sys.exit(1)
            story_id = str(fm_id)

        # phase, rail, story_class — fill from frontmatter if not set by explicit flag
        if phase is None and fm.get("phase") is not None:
            phase = str(fm["phase"])
        if rail is None and fm.get("rail") is not None:
            rail = str(fm["rail"])
        if story_class is None:
            fm_class = fm.get("story_class")
            story_class = str(fm_class) if fm_class else "code"

    # story_id must be set by now (either explicit or from story_file)
    if story_id is None:
        click.echo("error: --story-id is required when --story-file is not supplied", err=True)
        sys.exit(1)

    project_path = Path(project_dir).resolve()
    state_path = project_path / ".companion" / "state.json"
    state = _read_state(state_path)

    if not state.get("effort_tracking"):
        click.echo(
            "effort_tracking disabled — no record written",
            err=True,
        )
        sys.exit(0)

    try:
        resolved_db = _effort_db.resolve_db_path_arg(project_path, db_path)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)

    # Auto-fill ts if omitted.
    if not ts:
        ts = _utc_now_iso()

    # Normalise outcome to uppercase (prevents 'pass'/'fail' case drift).
    if outcome is not None:
        outcome = outcome.upper()

    # Ensure schema exists (idempotent).
    _effort_db.init_db(resolved_db)

    # Duplicate guard (INFRA-345): refuse to write a second row for a triple
    # that already has one, unless --allow-duplicate was passed. Queries the
    # effort database itself so a collision against a hook-written row is
    # caught, not just against other CLI-written rows.
    if not allow_duplicate:
        existing_rows = _effort_db.query_by_story(resolved_db, story_id)
        colliding = [
            row
            for row in existing_rows
            if row.get("agent_role") == agent_role and row.get("attempt_number") == attempt_number
        ]
        if colliding:
            existing_id = colliding[0].get("id")
            click.echo(
                f"error: attempt row already exists for {story_id}/{agent_role}/attempt "
                f"{attempt_number} (row id {existing_id}) — pass --allow-duplicate to "
                "insert anyway",
                err=True,
            )
            sys.exit(1)

    _effort_db.insert_attempt(
        resolved_db,
        story_id=story_id,
        phase=phase,
        rail=rail,
        agent_role=agent_role,
        model=model,
        attempt_number=attempt_number,
        tokens_total=tokens_total,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        duration_ms=duration_ms,
        outcome=outcome,
        notes=notes,
        ts=ts,
        story_class=story_class,
        model_selection_reason=model_selection_reason,
    )

    click.echo(f"recorded attempt for {story_id} (agent={agent_role}, attempt={attempt_number})")


if __name__ == "__main__":
    record_attempt()

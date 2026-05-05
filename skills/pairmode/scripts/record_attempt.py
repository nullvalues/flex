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
import sys
from pathlib import Path

# Insert anchor repo root and scripts dir for sibling imports when run as CLI.
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import click

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
@click.option("--story-id", required=True, help="Story ID, e.g. INFRA-028.")
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
@click.option("--tokens-total", type=int, default=None)
@click.option("--tokens-in", type=int, default=None)
@click.option("--tokens-out", type=int, default=None)
@click.option("--cache-read-tokens", type=int, default=None)
@click.option("--cache-write-tokens", type=int, default=None)
@click.option("--tool-uses", type=int, default=None)
@click.option("--duration-ms", type=int, default=None)
@click.option(
    "--outcome",
    default=None,
    help="PASS | FAIL | PARTIAL (free-form; recommended values).",
)
@click.option("--notes", default=None, help="Free-form note.")
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
def record_attempt(
    story_id: str,
    phase: str | None,
    rail: str | None,
    agent_role: str,
    model: str | None,
    attempt_number: int,
    tokens_total: int | None,
    tokens_in: int | None,
    tokens_out: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
    tool_uses: int | None,
    duration_ms: int | None,
    outcome: str | None,
    notes: str | None,
    ts: str | None,
    project_dir: str,
    db_path: str | None,
) -> None:
    """Append one attempt row.  No-op when effort tracking is disabled."""

    project_path = Path(project_dir).resolve()
    state_path = project_path / ".companion" / "state.json"
    state = _read_state(state_path)

    if not state.get("effort_tracking"):
        click.echo(
            "effort_tracking disabled — no record written",
            err=True,
        )
        sys.exit(0)

    if db_path is not None:
        resolved_db = Path(db_path)
        if not resolved_db.is_absolute():
            resolved_db = project_path / resolved_db
    else:
        resolved_db = _effort_db.resolve_effort_db_path(project_path)

    # Auto-fill ts if omitted.
    if not ts:
        ts = _utc_now_iso()

    # Ensure schema exists (idempotent).
    _effort_db.init_db(resolved_db)

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
        tool_uses=tool_uses,
        duration_ms=duration_ms,
        outcome=outcome,
        notes=notes,
        ts=ts,
    )

    click.echo(f"recorded attempt for {story_id} (agent={agent_role}, attempt={attempt_number})")


if __name__ == "__main__":
    record_attempt()

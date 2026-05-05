"""pairmode_effort.py — reporting CLI for the pairmode effort-tracking DB.

Produces four reports against ``.companion/effort.db``:

- ``rollup``    — tokens per phase, per rail, per model; rails ranked by total.
- ``rework``    — stories with ``attempt_number`` above a threshold.
- ``expensive`` — top N stories by total tokens with role breakdown.
- ``models``    — tokens, attempts, and PASS rate per (model, role) pair.

Token counts are the primary metric in every report. Dollar projections are
optional decoration applied via ``--dollars <pricing.json>``: anchor neither
ships nor maintains rates, so a missing or stale pricing file never breaks
the underlying token data.

Output defaults to plain-text columns; ``--json`` emits a list of row dicts.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Insert anchor repo root and scripts dir for sibling imports when run as CLI.
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import click

from skills.pairmode.scripts import effort_db as _effort_db


# ---------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------


# Token-rate keys recognised in pricing.json. Rates are USD per million tokens.
_PRICING_KEYS = ("input", "output", "cache_read", "cache_write")


def _load_pricing(pricing_path: str | None) -> dict[str, dict[str, float]] | None:
    """Load and validate a pricing.json file.

    Returns ``None`` when *pricing_path* is ``None`` (no projection requested).
    Exits with a non-zero status when the path is supplied but does not exist
    or cannot be parsed — this is a user-facing error: they explicitly asked
    for a dollar projection and the input is malformed.
    """

    if pricing_path is None:
        return None

    p = Path(pricing_path)
    if not p.exists():
        click.echo(
            f"error: --dollars file not found: {pricing_path}",
            err=True,
        )
        sys.exit(2)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        click.echo(
            f"error: --dollars file is not valid JSON: {pricing_path} ({exc})",
            err=True,
        )
        sys.exit(2)
    if not isinstance(data, dict):
        click.echo(
            f"error: --dollars file must be a JSON object: {pricing_path}",
            err=True,
        )
        sys.exit(2)
    return data


def _project_dollars(
    pricing: dict[str, dict[str, float]] | None,
    *,
    model: str | None,
    tokens_in: int | None,
    tokens_out: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
    tokens_total: int | None,
) -> float:
    """Project token counts to USD using *pricing*.

    If the model is not present in *pricing*, returns ``0.0``. The pricing
    schema reports USD per million tokens; the projection therefore divides
    by 1_000_000 after multiplying.

    When token-level breakdown columns (``tokens_in``/``tokens_out``/cache)
    are NULL but ``tokens_total`` is set, the total is projected at the
    ``input`` rate as a conservative best-effort fallback.
    """

    if not pricing or not model:
        return 0.0
    rates = pricing.get(model)
    if not rates:
        return 0.0

    in_rate = float(rates.get("input", 0) or 0)
    out_rate = float(rates.get("output", 0) or 0)
    cr_rate = float(rates.get("cache_read", 0) or 0)
    cw_rate = float(rates.get("cache_write", 0) or 0)

    have_breakdown = any(
        v not in (None, 0)
        for v in (tokens_in, tokens_out, cache_read_tokens, cache_write_tokens)
    )

    if have_breakdown:
        total_usd = (
            (tokens_in or 0) * in_rate
            + (tokens_out or 0) * out_rate
            + (cache_read_tokens or 0) * cr_rate
            + (cache_write_tokens or 0) * cw_rate
        )
    else:
        # Fallback: project the total at the input rate so users still get
        # a directional figure when only ``tokens_total`` is captured.
        total_usd = (tokens_total or 0) * in_rate

    return total_usd / 1_000_000.0


# ---------------------------------------------------------------------------
# DB resolution
# ---------------------------------------------------------------------------


def _resolve_db(project_dir: str, db_path: str | None) -> Path:
    project_path = Path(project_dir).resolve()
    if db_path is not None:
        resolved = Path(db_path)
        if not resolved.is_absolute():
            resolved = project_path / resolved
        return resolved
    return _effort_db.resolve_effort_db_path(project_path)


def _connect_or_none(db: Path) -> sqlite3.Connection | None:
    """Return a sqlite connection, or ``None`` if the DB has no rows yet.

    A missing file is treated identically to an empty DB — both are reported
    as "no effort data yet" by the caller.
    """

    if not db.exists():
        return None
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='attempts'"
        )
        if cur.fetchone() is None:
            conn.close()
            return None
        cur.execute("SELECT COUNT(*) FROM attempts")
        if cur.fetchone()[0] == 0:
            conn.close()
            return None
    except sqlite3.Error:
        conn.close()
        return None
    return conn


def _no_data_message() -> None:
    click.echo(
        "no effort data yet — enable effort_tracking and build something",
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _emit(rows: list[dict[str, Any]], columns: list[str], as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(rows, default=_json_default))
        return

    if not rows:
        click.echo("(no rows)")
        return

    # Compute simple fixed-width text columns. Each value is stringified.
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(_render_cell(row.get(col))))

    header = "  ".join(col.ljust(widths[col]) for col in columns)
    click.echo(header)
    click.echo("  ".join("-" * widths[col] for col in columns))
    for row in rows:
        click.echo(
            "  ".join(_render_cell(row.get(col)).ljust(widths[col]) for col in columns)
        )


def _render_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"not serialisable: {type(obj)!r}")


# ---------------------------------------------------------------------------
# Report queries
# ---------------------------------------------------------------------------


def _query_rollup(
    conn: sqlite3.Connection,
    *,
    phase: str | None,
    rail: str | None,
) -> list[dict[str, Any]]:
    """Tokens per (phase, rail, model) with attempt counts.

    Rows are ordered so that the rail with the largest total token spend
    appears first; within a rail, phase/model break ties.
    """

    sql = (
        "SELECT phase, rail, model, "
        "COALESCE(SUM(tokens_total), 0) AS total_tokens, "
        "COUNT(*) AS attempts, "
        "COALESCE(SUM(tokens_in), 0) AS sum_in, "
        "COALESCE(SUM(tokens_out), 0) AS sum_out, "
        "COALESCE(SUM(cache_read_tokens), 0) AS sum_cache_read, "
        "COALESCE(SUM(cache_write_tokens), 0) AS sum_cache_write "
        "FROM attempts WHERE 1=1"
    )
    params: list[Any] = []
    if phase is not None:
        sql += " AND phase = ?"
        params.append(phase)
    if rail is not None:
        sql += " AND rail = ?"
        params.append(rail)
    sql += " GROUP BY phase, rail, model"

    cur = conn.cursor()
    cur.execute(sql, params)
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    # Compute per-rail totals to rank rails.
    rail_totals: dict[str | None, int] = {}
    for row in rows:
        rail_totals[row["rail"]] = rail_totals.get(row["rail"], 0) + int(
            row["total_tokens"] or 0
        )

    rows.sort(
        key=lambda r: (
            -rail_totals.get(r["rail"], 0),
            r["rail"] or "",
            r["phase"] or "",
            -int(r["total_tokens"] or 0),
            r["model"] or "",
        )
    )
    return rows


def _query_rework(
    conn: sqlite3.Connection,
    *,
    threshold: int,
) -> list[dict[str, Any]]:
    """Stories whose maximum ``attempt_number`` exceeds *threshold*.

    A *threshold* of 1 means "any retry counts" — story has at least one
    attempt with ``attempt_number > 1``.
    """

    cur = conn.cursor()
    cur.execute(
        "SELECT story_id, MAX(attempt_number) AS max_attempt "
        "FROM attempts GROUP BY story_id HAVING max_attempt > ?",
        (threshold,),
    )
    candidate_stories = [row[0] for row in cur.fetchall()]

    rows: list[dict[str, Any]] = []
    for story_id in candidate_stories:
        cur.execute(
            "SELECT "
            "COUNT(*) AS attempts, "
            "COALESCE(SUM(tokens_total), 0) AS total_tokens, "
            "COALESCE(SUM(CASE WHEN agent_role='builder' THEN tokens_total ELSE 0 END), 0) "
            "  AS builder_tokens, "
            "COALESCE(SUM(CASE WHEN agent_role='reviewer' THEN tokens_total ELSE 0 END), 0) "
            "  AS reviewer_tokens "
            "FROM attempts WHERE story_id = ?",
            (story_id,),
        )
        row = cur.fetchone()
        rows.append(
            {
                "story_id": story_id,
                "attempts": int(row[0] or 0),
                "total_tokens": int(row[1] or 0),
                "builder_tokens": int(row[2] or 0),
                "reviewer_tokens": int(row[3] or 0),
            }
        )

    rows.sort(key=lambda r: -r["total_tokens"])
    return rows


def _query_expensive(
    conn: sqlite3.Connection,
    *,
    top: int,
) -> list[dict[str, Any]]:
    """Top *top* stories by ``SUM(tokens_total)`` with per-role breakdown."""

    cur = conn.cursor()
    cur.execute(
        "SELECT story_id, COALESCE(SUM(tokens_total), 0) AS total_tokens "
        "FROM attempts GROUP BY story_id "
        "ORDER BY total_tokens DESC LIMIT ?",
        (top,),
    )
    story_totals = cur.fetchall()

    rows: list[dict[str, Any]] = []
    for story_id, total_tokens in story_totals:
        cur.execute(
            "SELECT agent_role, COALESCE(SUM(tokens_total), 0) "
            "FROM attempts WHERE story_id = ? GROUP BY agent_role "
            "ORDER BY agent_role",
            (story_id,),
        )
        breakdown_pairs = cur.fetchall()
        # Render breakdown as a stable, human-readable string.
        breakdown_str = ", ".join(
            f"{role or 'unknown'}={int(tok or 0)}" for role, tok in breakdown_pairs
        )
        breakdown_dict = {
            (role or "unknown"): int(tok or 0) for role, tok in breakdown_pairs
        }
        rows.append(
            {
                "story_id": story_id,
                "role_breakdown": breakdown_str,
                "role_breakdown_dict": breakdown_dict,
                "total_tokens": int(total_tokens or 0),
            }
        )
    return rows


def _query_models(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Tokens, attempts, and PASS rate per (model, agent_role) pair."""

    cur = conn.cursor()
    cur.execute(
        "SELECT model, agent_role, "
        "COUNT(*) AS attempts, "
        "COALESCE(SUM(tokens_total), 0) AS total_tokens, "
        "SUM(CASE WHEN outcome='PASS' THEN 1 ELSE 0 END) AS pass_count, "
        "SUM(CASE WHEN outcome='FAIL' THEN 1 ELSE 0 END) AS fail_count "
        "FROM attempts GROUP BY model, agent_role "
        "ORDER BY total_tokens DESC"
    )
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    for row in rows:
        attempts = int(row.get("attempts") or 0)
        pass_count = int(row.get("pass_count") or 0)
        # PASS rate over *attempts*: a non-PASS, non-FAIL outcome (NULL,
        # PARTIAL) is neither a pass nor an explicit fail. We report the
        # fraction of attempts that explicitly passed; this matches the
        # methodology framing where unknowns are not credited as passes.
        row["pass_rate_pct"] = (
            round(100.0 * pass_count / attempts, 2) if attempts else 0.0
        )
        row["pass_count"] = pass_count
        row["fail_count"] = int(row.get("fail_count") or 0)
        row["total_tokens"] = int(row.get("total_tokens") or 0)
        row["attempts"] = attempts
    return rows


# ---------------------------------------------------------------------------
# Aggregate-row helpers
# ---------------------------------------------------------------------------


def _attach_rollup_dollars(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    pricing: dict[str, dict[str, float]] | None,
    *,
    phase_filter: str | None,
    rail_filter: str | None,
) -> None:
    """Add a ``dollars_estimate`` field to each rollup row when *pricing* is set.

    Each rollup row is grouped by ``(phase, rail, model)``; we re-query the
    underlying breakdown for that group so the projection uses the column-level
    breakdown rather than a single aggregate.
    """

    if pricing is None:
        return

    for row in rows:
        cur = conn.cursor()
        sql = (
            "SELECT "
            "COALESCE(SUM(tokens_total), 0), "
            "COALESCE(SUM(tokens_in), 0), "
            "COALESCE(SUM(tokens_out), 0), "
            "COALESCE(SUM(cache_read_tokens), 0), "
            "COALESCE(SUM(cache_write_tokens), 0) "
            "FROM attempts WHERE 1=1"
        )
        params: list[Any] = []
        if row["phase"] is None:
            sql += " AND phase IS NULL"
        else:
            sql += " AND phase = ?"
            params.append(row["phase"])
        if row["rail"] is None:
            sql += " AND rail IS NULL"
        else:
            sql += " AND rail = ?"
            params.append(row["rail"])
        if row["model"] is None:
            sql += " AND model IS NULL"
        else:
            sql += " AND model = ?"
            params.append(row["model"])
        if phase_filter is not None:
            sql += " AND phase = ?"
            params.append(phase_filter)
        if rail_filter is not None:
            sql += " AND rail = ?"
            params.append(rail_filter)
        cur.execute(sql, params)
        total, tin, tout, cr, cw = cur.fetchone()
        row["dollars_estimate"] = round(
            _project_dollars(
                pricing,
                model=row["model"],
                tokens_in=int(tin or 0),
                tokens_out=int(tout or 0),
                cache_read_tokens=int(cr or 0),
                cache_write_tokens=int(cw or 0),
                tokens_total=int(total or 0),
            ),
            6,
        )


def _attach_per_story_dollars(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    pricing: dict[str, dict[str, float]] | None,
) -> None:
    """Add a ``dollars_estimate`` field to per-story rows.

    Per-story rows can span multiple models; the projection sums the estimates
    over the (story_id, model) sub-groups so each row's model rates apply to
    only its own tokens.
    """

    if pricing is None:
        return

    for row in rows:
        story_id = row["story_id"]
        cur = conn.cursor()
        cur.execute(
            "SELECT model, "
            "COALESCE(SUM(tokens_total), 0), "
            "COALESCE(SUM(tokens_in), 0), "
            "COALESCE(SUM(tokens_out), 0), "
            "COALESCE(SUM(cache_read_tokens), 0), "
            "COALESCE(SUM(cache_write_tokens), 0) "
            "FROM attempts WHERE story_id = ? GROUP BY model",
            (story_id,),
        )
        total_usd = 0.0
        for model, total, tin, tout, cr, cw in cur.fetchall():
            total_usd += _project_dollars(
                pricing,
                model=model,
                tokens_in=int(tin or 0),
                tokens_out=int(tout or 0),
                cache_read_tokens=int(cr or 0),
                cache_write_tokens=int(cw or 0),
                tokens_total=int(total or 0),
            )
        row["dollars_estimate"] = round(total_usd, 6)


def _attach_models_dollars(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    pricing: dict[str, dict[str, float]] | None,
) -> None:
    if pricing is None:
        return
    for row in rows:
        model = row.get("model")
        agent_role = row.get("agent_role")
        cur = conn.cursor()
        sql = (
            "SELECT "
            "COALESCE(SUM(tokens_total), 0), "
            "COALESCE(SUM(tokens_in), 0), "
            "COALESCE(SUM(tokens_out), 0), "
            "COALESCE(SUM(cache_read_tokens), 0), "
            "COALESCE(SUM(cache_write_tokens), 0) "
            "FROM attempts WHERE 1=1"
        )
        params: list[Any] = []
        if model is None:
            sql += " AND model IS NULL"
        else:
            sql += " AND model = ?"
            params.append(model)
        if agent_role is None:
            sql += " AND agent_role IS NULL"
        else:
            sql += " AND agent_role = ?"
            params.append(agent_role)
        cur.execute(sql, params)
        total, tin, tout, cr, cw = cur.fetchone()
        row["dollars_estimate"] = round(
            _project_dollars(
                pricing,
                model=model,
                tokens_in=int(tin or 0),
                tokens_out=int(tout or 0),
                cache_read_tokens=int(cr or 0),
                cache_write_tokens=int(cw or 0),
                tokens_total=int(total or 0),
            ),
            6,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Reporting CLI for pairmode effort tracking."""


_COMMON_OPTIONS = [
    click.option(
        "--project-dir",
        default=".",
        show_default=True,
        type=click.Path(file_okay=False, dir_okay=True),
        help="Project root used to resolve .companion/state.json and the DB.",
    ),
    click.option(
        "--db-path",
        default=None,
        type=click.Path(dir_okay=False),
        help="Override the effort DB path.",
    ),
    click.option(
        "--dollars",
        "dollars",
        default=None,
        type=click.Path(dir_okay=False),
        help="Optional pricing.json for a USD projection column.",
    ),
    click.option(
        "--json",
        "as_json",
        is_flag=True,
        default=False,
        help="Emit JSON instead of a text table.",
    ),
]


def _common(func):
    for opt in reversed(_COMMON_OPTIONS):
        func = opt(func)
    return func


@cli.command("rollup")
@click.option("--phase", default=None, help="Filter to a single phase.")
@click.option("--rail", default=None, help="Filter to a single rail.")
@_common
def rollup_cmd(
    phase: str | None,
    rail: str | None,
    project_dir: str,
    db_path: str | None,
    dollars: str | None,
    as_json: bool,
) -> None:
    """Token rollup per (phase, rail, model); rails ranked by total tokens."""

    db = _resolve_db(project_dir, db_path)
    pricing = _load_pricing(dollars)
    conn = _connect_or_none(db)
    if conn is None:
        _no_data_message()
        return
    try:
        rows = _query_rollup(conn, phase=phase, rail=rail)
        _attach_rollup_dollars(
            conn, rows, pricing, phase_filter=phase, rail_filter=rail
        )
    finally:
        conn.close()

    columns = ["phase", "rail", "model", "total_tokens", "attempts"]
    if pricing is not None:
        columns.append("dollars_estimate")
    _emit(rows, columns, as_json)


@cli.command("rework")
@click.option(
    "--threshold",
    type=int,
    default=1,
    show_default=True,
    help="Stories with attempt_number > threshold are reported.",
)
@_common
def rework_cmd(
    threshold: int,
    project_dir: str,
    db_path: str | None,
    dollars: str | None,
    as_json: bool,
) -> None:
    """Stories that required more than --threshold attempts."""

    db = _resolve_db(project_dir, db_path)
    pricing = _load_pricing(dollars)
    conn = _connect_or_none(db)
    if conn is None:
        _no_data_message()
        return
    try:
        rows = _query_rework(conn, threshold=threshold)
        _attach_per_story_dollars(conn, rows, pricing)
    finally:
        conn.close()

    columns = [
        "story_id",
        "attempts",
        "total_tokens",
        "builder_tokens",
        "reviewer_tokens",
    ]
    if pricing is not None:
        columns.append("dollars_estimate")
    _emit(rows, columns, as_json)


@cli.command("expensive")
@click.option(
    "--top",
    type=int,
    default=10,
    show_default=True,
    help="Number of stories to report.",
)
@_common
def expensive_cmd(
    top: int,
    project_dir: str,
    db_path: str | None,
    dollars: str | None,
    as_json: bool,
) -> None:
    """Top stories by total tokens, with per-role breakdown."""

    db = _resolve_db(project_dir, db_path)
    pricing = _load_pricing(dollars)
    conn = _connect_or_none(db)
    if conn is None:
        _no_data_message()
        return
    try:
        rows = _query_expensive(conn, top=top)
        _attach_per_story_dollars(conn, rows, pricing)
    finally:
        conn.close()

    if as_json:
        # In JSON mode return the structured breakdown dict instead of the
        # text-formatted ``role_breakdown`` string.
        out_rows = [
            {
                "story_id": r["story_id"],
                "role_breakdown": r["role_breakdown_dict"],
                "total_tokens": r["total_tokens"],
                **(
                    {"dollars_estimate": r["dollars_estimate"]}
                    if "dollars_estimate" in r
                    else {}
                ),
            }
            for r in rows
        ]
        click.echo(json.dumps(out_rows, default=_json_default))
        return

    columns = ["story_id", "role_breakdown", "total_tokens"]
    if pricing is not None:
        columns.append("dollars_estimate")
    _emit(rows, columns, as_json=False)


@cli.command("models")
@_common
def models_cmd(
    project_dir: str,
    db_path: str | None,
    dollars: str | None,
    as_json: bool,
) -> None:
    """Per (model, role) attempts, tokens, and PASS rate."""

    db = _resolve_db(project_dir, db_path)
    pricing = _load_pricing(dollars)
    conn = _connect_or_none(db)
    if conn is None:
        _no_data_message()
        return
    try:
        rows = _query_models(conn)
        _attach_models_dollars(conn, rows, pricing)
    finally:
        conn.close()

    columns = [
        "model",
        "agent_role",
        "attempts",
        "total_tokens",
        "pass_count",
        "fail_count",
        "pass_rate_pct",
    ]
    if pricing is not None:
        columns.append("dollars_estimate")
    _emit(rows, columns, as_json)


if __name__ == "__main__":
    cli()

---
id: INFRA-169
rail: INFRA
title: "`flex_build.py bump-context-tokens` — per-story context estimate advance"
status: complete
phase: "65"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build_bump_context_tokens.py
---

# INFRA-169 — `flex_build.py bump-context-tokens`

## Context

Part B of the Phase 65 fix (see phase-65.md root cause analysis). After every story
completes, the orchestrator has the actual `total_tokens` from the builder's `<usage>`
block (it already passes this to `record_attempt.py`). This story adds a `bump-context-tokens`
command that adds that cost to the running `context_current_tokens` in state.json.

Combined with INFRA-170 (stop erasing between stories) and BUILD-027 (call this after
each story), the accumulated total crosses the threshold after enough stories — fully
mechanically, without requiring the orchestrator to invoke `/context`.

## Acceptance criteria

1. `flex_build.py bump-context-tokens --cost 35000 --project-dir .` adds 35000
   to `state["context_current_tokens"]` and writes `context_current_tokens_recorded_at`
   (UTC ISO-8601).

2. When `context_current_tokens` is absent from state.json (or zero/invalid), the
   command treats the base as 0 and writes `cost` as the new value.

3. When `context_current_tokens` is present and valid, the command adds `cost` to
   the existing value (additive, not replace).

4. `--cost` must be > 0; the command prints an error to stderr and exits 1 if ≤ 0.

5. The command is a silent no-op (exit 0) when `.companion/state.json` is absent
   (non-pairmode project, fail-open — consistent with `set-context-tokens` behaviour).

6. `context_current_tokens_recorded_at` is updated to `datetime.now(timezone.utc)`
   on every successful write (TTL clock resets after each bump).

7. All criteria covered by `tests/pairmode/test_flex_build_bump_context_tokens.py`.

## Implementation guidance

Add a new Click command `bump-context-tokens` in `flex_build.py` immediately
after `cmd_set_context_tokens` (around line 780). The structure mirrors
`set-context-tokens`:

```python
@flex_build.command("bump-context-tokens")
@click.option("--cost", required=True, type=int, help="Token cost to add (must be > 0).")
@click.option("--project-dir", required=True, type=str)
def cmd_bump_context_tokens(cost: int, project_dir: str) -> None:
    """Add --cost to context_current_tokens in state.json (per-story accumulation)."""
    from datetime import datetime, timezone

    if cost <= 0:
        click.echo(
            f"bump-context-tokens: --cost must be > 0 (got {cost})", err=True
        )
        raise SystemExit(1)

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    state_path = project_path / ".companion" / "state.json"
    if not state_path.exists():
        return  # non-pairmode project, fail-open

    state = json.loads(state_path.read_text(encoding="utf-8"))
    existing = state.get("context_current_tokens")
    try:
        base = int(existing) if existing and int(existing) > 0 else 0
    except (TypeError, ValueError):
        base = 0

    state["context_current_tokens"] = base + cost
    state["context_current_tokens_recorded_at"] = datetime.now(timezone.utc).isoformat()
    # atomic write (same pattern as set-context-tokens)
    ...
```

Use the same atomic write pattern already used by `set-context-tokens` (NamedTemporaryFile
+ os.replace).

## Tests

File: `tests/pairmode/test_flex_build_bump_context_tokens.py`

```python
# Run via:
#   PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_bump_context_tokens.py -v
```

Test cases:
1. `test_bump_adds_to_existing` — state has `context_current_tokens: 25000`; bump `--cost 38000`; assert 63000.
2. `test_bump_from_absent` — no `context_current_tokens` key; bump `--cost 38000`; assert 38000.
3. `test_bump_from_zero` — `context_current_tokens: 0`; bump `--cost 38000`; assert 38000.
4. `test_bump_updates_recorded_at` — after bump, `context_current_tokens_recorded_at` present and parseable as UTC ISO-8601.
5. `test_bump_zero_cost_exits_1` — `--cost 0` exits 1, state unchanged.
6. `test_bump_negative_cost_exits_1` — `--cost -1` exits 1, state unchanged.
7. `test_bump_no_state_json_noop` — `.companion/state.json` absent; exits 0, no file created.
8. `test_bump_accumulated` — two consecutive bumps of 30000 each from absent → 60000.
9. `test_bump_resets_ttl` — bump updates `recorded_at` to within 5 seconds of now.

---
id: HARNESS-003
rail: HARNESS
title: Re-source `expected_step_tokens` off effort.db (CER-053 state half)
status: complete
phase: "HARNESS006-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/sync.py
  - tests/pairmode/test_expected_step_tokens_source.py
touches: []
---

## Context

The effort.db ≠ context-control comingling removal, state half (agreements `HARNESS006-main.md`
DP3; ≡ DP7 of HARNESS001-ante1; CER-053/D1). Today `expected_step_tokens` — the context-budget
**window-growth** constant — is seeded from the **effort-baseline builder median**
(`bootstrap.py:417` `_load_seed_expected_step_tokens()` → `by_role.builder.median`, fallback
`_DEFAULT_EXPECTED_STEP_TOKENS = 53000`), stamped fleet-wide (`sync.py:594`) and read at
`context_budget.py:526`. So a context-control constant is sourced from per-story **effort cost**
— the comingling — and never re-estimated per project (radar and forqsite both show exactly
53000, over-reserving ~53k and firing the gate too early). This story re-sources it off effort
entirely; the SPA display half is Phase G (OBS-003).

## Requires

- HARNESS001–005 complete (the thin-harness return-block shape is known: the harness's per-step
  growth is the dispatch return block + `<usage>`, not a builder's per-story cost).

## Ensures

- `bootstrap.py` `_load_seed_expected_step_tokens()` **no longer reads the effort baseline**
  (no `by_role.builder.median`). It seeds from a **thin-harness return-block growth** model:
  a fixed, conservative constant representing the dispatch loop's per-step context growth,
  defined next to the resolver/harness (not in the effort module).
  `_DEFAULT_EXPECTED_STEP_TOKENS`'s effort-derived `53000` is removed/replaced.
- `sync.py:594` and `context_budget.py:526` read the re-sourced value; the literal
  effort-derived `53000` default is removed from all three sites.
- **Invariant test:** `tests/pairmode/test_expected_step_tokens_source.py` asserts:
  (a) `bootstrap.py`'s seed function does not import or read `effort.db` / the effort baseline
  / `by_role` for the window-growth constant (assert on source text: `grep` the function body
  for absence of effort-module imports on that path);
  (b) `context_budget.py` does not import or read `effort.db` for any window-growth constant;
  (c) the seeded value matches the thin-harness growth constant, not the effort median.
- Existing context-budget tests still pass (the gate still functions; only the source of the
  growth constant changed).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Define the thin-harness growth constant once (e.g. alongside `next_action.py` or a small
  `context_model.py`) and import it in the three sites — single source, no comingling with
  `effort.db`.
- Keep the change behavioural-minimal: the gate's decision logic is unchanged; only
  `expected_step_tokens` provenance changes. Do not touch the SPA display (Phase G OBS-003).
- Preserve the per-project re-estimation hook noted in `CLAUDE.build.md` (effort.db median
  replaces the seed once ≥5 attempts accumulate) **only if** it does not reintroduce the
  comingling for the window-growth constant — per DP3 the window-growth constant must not be
  effort-derived. If that hook conflicts, remove it for the window-growth path and note it.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_expected_step_tokens_source.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget*.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: no effort-derived value feeds the context budget; the three sites read the
thin-harness growth constant; gate still functions; full suite green. Closes CER-053 state half.

### Out of scope

- The SPA `expected_step_tokens` display + provenance label — Phase G (OBS-003).
- The thin loop / agent retirement — HARNESS-001/002.
- The fold/version — RELEASE-007.

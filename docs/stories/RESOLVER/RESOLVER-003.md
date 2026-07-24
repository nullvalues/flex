---
id: RESOLVER-003
rail: RESOLVER
title: State machine + next-action subcommand (DP2, DP4, DP6)
status: complete
phase: "HARNESS001-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_next_action.py
touches:
---

## Context

The decision half of `next-action` and its CLI exposure (agreements
`HARNESS001-main.md` DP2 + DP4 + DP6). It maps the **9-state build-sequencing table**
(DP2) onto the action grammar (RESOLVER-001), consuming the Position read-model
(RESOLVER-002). It introduces the `flex_build.py next-action` subcommand — the
**first addition to the CLI surface** in the additive window; additions are permitted,
so the CLI-surface freeze test (RELEASE-003) stays green (it checks the live surface
is a *superset* of the 0.2.x snapshot).

The 9-state contract (durable-state condition → emitted action → decision owner),
evaluated at cycle-boundary seams only:

| # | Condition | Action |
|---|-----------|--------|
| 1 | `current-phase` exit 1 (no active phase / all complete) | `done` |
| 2 | active phase, unbuilt story, counter 0, model auto | `spawn-builder` (attempt 1) |
| 3 | as #2 but `select-builder-model` = `prompted-upgrade` | `await-user` (reason `model-upgrade`) |
| 4 | a pre-flight gate (auth/schema/stub) signals blocked | `await-user` (reason `gate-blocked:<which>`) |
| 5 | attempt-1 cycle failed (planned, counter 1, no commit) | `spawn-builder` (attempt 2, `retry-upgrade`) |
| 6 | attempt-2 cycle failed (counter 2, no commit) | `spawn-loop-breaker` |
| 7 | attempt-3 failed (counter 3, no commit), or user pause, or builder DEVELOPER-ACTION gate | `await-user` (reason `build-paused`) |
| 8 | story committed (PASS), more unbuilt stories remain | `spawn-builder` (next story, attempt 1) |
| 9 | last story of phase committed | `checkpoint` |

**The binding property (DP4):** every judgment-handoff state emits `await-user` and
stops — the resolver **never computes the decision** (model-upgrade, gate verdict,
loop-breaker acceptance, pause-on-warning are all owner = user/worker). DP6: `model`
is embedded for the auto spawn cases (`auto-baseline`/`auto-downgrade`/`retry-upgrade`);
`prompted-upgrade` ⇒ `await-user:model-upgrade` with the suggested model in `meta`.
**Advisory signals (not states):** guardrail-fired and context-budget-exceeded are
surfaced as `meta.warnings[]` on whatever action is emitted — never a blocking
`await-user`; the context-budget warning marks the seam as a safe-clear point.

## Requires

- RESOLVER-002 complete: `infer_position(project_dir)` returns the durable-state
  Position; the `flex_build.py` extractions exist.
- RESOLVER-001 complete: the action grammar (`make_action`, `validate_action`).

## Ensures

- `next_action.py` gains a pure decision function (e.g. `resolve_next_action(position)
  -> dict`) mapping a Position to exactly one action via `make_action`. Given the same
  durable state it is deterministic and its output passes `validate_action` (returns
  `[]`) for every reachable state.
- Each of the 9 DP2 rows maps to its tabled action: row 1 ⇒ `done`; rows 2/5/8 ⇒
  `spawn-builder` (with the correct attempt + auto model + reason); row 6 ⇒
  `spawn-loop-breaker`; row 9 ⇒ `checkpoint`; rows 3/4/7 ⇒ `await-user` with reason
  `model-upgrade` / `gate-blocked:<which>` / `build-paused` respectively.
- `scalar` is set per DP1: story ID for spawn actions, phase key for `checkpoint`,
  empty for `done`/`await-user`.
- `model` is non-null **only** on auto-resolved `spawn-builder`/`spawn-loop-breaker`;
  `prompted-upgrade` routes to `await-user:model-upgrade` with the suggested model in
  `meta` (DP6) and `model = None`.
- `meta` carries the attempt number, the FAIL-ladder rung, and the blocking gate where
  applicable; guardrail / context-budget advisories appear in `meta.warnings[]` and
  never change which action is emitted.
- `flex_build.py` registers a `next-action` subcommand: prints a human-readable line by
  default and the canonical JSON object with `--json` (consistent with `next_story.py
  --json` / `context-health`). It is **pure-read** — `grep` confirms the command writes
  no durable state — and it is **not** wired into the live `CLAUDE.build.md` (advisory
  only, DP7).
- The resolver emits **no** `spawn-reviewer` action (intra-cycle, orchestrator-held —
  DP3) and **no** `spec` action (deferred to HARNESS005).
- The CLI-surface freeze test still passes (a command is *added*, none removed/renamed),
  and `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Implement the state machine as a flat, readable mapping from Position fields to the
  tabled action — order the branches so the terminal/PASS/FAIL precedence matches DP2
  (e.g. all-complete → done; committed-last → checkpoint; committed-more → next story;
  gate-blocked → await-user; counter ladder → builder/loop-breaker/paused).
- Use the RESOLVER-002 model + `prompted-upgrade` marker already on the Position; do
  not call the selector again from the state machine.
- Build the action exclusively through `make_action` so `meta.schema_version` is always
  stamped and the output always validates.
- The subcommand is a thin click wrapper: `infer_position` → `resolve_next_action` →
  emit. Keep all logic in `next_action.py`; the command body is glue only.
- Do not render any verdict for gates (signal → `await-user:gate-blocked`), and do not
  compute the model-upgrade decision (route → `await-user:model-upgrade`). Both are DP4
  judgment handoffs.

## Tests

Extend `tests/pairmode/test_next_action.py` with state-machine + subcommand cases
(the exhaustive one-assertion-per-state backbone is RESOLVER-004; here cover the
machine logic and the CLI surface):

- A representative case per emitted action value (`done`, `spawn-builder`,
  `spawn-loop-breaker`, `checkpoint`, `await-user`) asserts the exact `{action, scalar,
  model, reason}` and that `validate_action` returns `[]`.
- `prompted-upgrade` ⇒ `await-user` reason `model-upgrade`, `model is None`, suggested
  model present in `meta`.
- A guardrail/context advisory appears in `meta.warnings[]` without changing the action.
- `flex_build.py next-action --json` emits a single object that round-trips and
  validates; the default invocation prints a human line.
- The CLI-surface freeze test passes with `next-action` present.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cli_surface_freeze.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- The full synthetic-state isolation fixture tree and the one-assertion-per-DP2-state
  matrix + the DP5 "no signature drift" guard (RESOLVER-004).
- Wiring `next-action` into the live `CLAUDE.build.md` loop (the flip — HARNESS006).
- Gate **verdict** extraction (HARNESS002); leaf-worker `spawn-reviewer` (HARNESS003).

---
id: INFRA-316
rail: INFRA
title: Between-story context etiquette — next-action consults context_budget_check between story iterations; pause-context handoff over threshold
status: complete
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
touches:
  - skills/pairmode/scripts/context_budget_check.py
  - skills/pairmode/scripts/context_budget.py
  - hooks/pre_tool_use.py
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_context_budget_check.py
  - docs/architecture.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - tests/pairmode/fixtures/next_action.schema.json
  - tests/pairmode/fixtures/next_action_samples.json
  - tests/pairmode/test_next_action_schema.py
  - tests/pairmode/test_checkpoint_step.py
  - tests/pairmode/test_harness003_isolation.py
  - tests/pairmode/test_harness004_isolation.py
  - tests/pairmode/test_harness005_isolation.py
  - tests/pairmode/test_needs_spec.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Repo-G item A#4 (AG-6): "between-story cadence … is where long phases actually
die." The 0.3.0 harness checks context health at *checkpoint* time and gates
via the PostToolUse JSONL hook continuously, but the resolver itself never
looks at the orchestrator's context budget when deciding to hand out the next
story — so a degrading session gets story N+1 anyway, and fresh-session
economics ("fresh sessions are cheap, degraded ones expensive") never enter
the decision. The threshold is **absolute** (120k tokens), not a percentage:
degradation tracks absolute context size.

The measuring tool exists: `context_budget_check.py` sums tokens for a phase
and compares against a threshold (`_DEFAULT_THRESHOLD = 120000`, `:26`;
`state.json`'s `context_budget_threshold` overrides, `:46-55`; exit 0 ok /
1 over, `:13-14`). This story makes `next-action` consult it at exactly one
seam — between story iterations — and emit a `pause-context` handoff action
when over, instead of the next `spawn-builder`.

**Correct signal: an over-threshold fixture resolves to `pause-context`
(await-user-class action naming the measured sum, the threshold, and the
handoff instruction) instead of `spawn-builder`. Forbidden proxy: a warning
string attached to a still-emitted `spawn-builder` — a warned dispatch is a
dispatch; Repo-G's whole point is that the *default* must flip to pausing.**

Important boundary honored from the operator's standing guidance: the
context-budget gate applies to pairmode build-loop work only — this seam is
inside the build loop (between stories), so it qualifies; nothing here gates
investigation/planning spawns.

## Requires

1. `context_budget_check.py`'s CLI contract (`:13-14` exit semantics,
   `:26` default, `:46-55` state override, `:79+` main). Its measurement
   (effort-db sum for the phase) is the *available* proxy for orchestrator
   context, not a perfect one — the standing lesson "never estimate
   orchestrator context headroom from effort.db cost totals" applies to
   *headroom claims*, not to this etiquette check; the spec and the emitted
   message must describe it honestly as a budget-etiquette trigger, not a
   context measurement.
2. The resolver's between-story seam: the decision rows that emit
   `spawn-builder` for "story committed, more stories remain"
   (`next_action.py:1056+`, Row 8 class). Only this seam changes — attempt
   retries (same story) are not "between stories" and stay unguarded (a
   mid-story pause strands a half-built story).
3. Acknowledge-or-clear semantics already exist in the hook-side gate
   (`context_budget_acknowledged_*` state keys, INFRA-193 lineage). The
   resolver check reuses the same acknowledgment keys so one operator
   acknowledgment clears both surfaces — duplicate state is a cold-eyes
   checklist item.
4. `pause-context` is a new action string in the resolver grammar
   (`_REQUIRED_KEYS` conformant, model null); consumers (CLAUDE.build.md
   loop prose) need one line telling the orchestrator what a `pause-context`
   handoff means: record state, summarize, end session, resume fresh.
5. Baseline 4116/211.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/fixtures/next_action.schema.json | SCHEMA_VERSION bump (pause-context action) requires updating the enum/const fixture | 2026-07-31T19:31:17Z |

| tests/pairmode/fixtures/next_action_samples.json | new pause-context action needs a covering sample (test_samples_cover_all_actions) | 2026-07-31T19:31:17Z |
| tests/pairmode/test_next_action_schema.py | enum-closure test hardcodes the 13-action count/set; pause-context bumps it to 14 | 2026-07-31T19:31:17Z |
| tests/pairmode/test_checkpoint_step.py | SCHEMA_VERSION bump 4->5 (pause-context) breaks this file's hardcoded ==4 assertion | 2026-07-31T19:46:59Z |
| tests/pairmode/test_harness003_isolation.py | SCHEMA_VERSION bump 4->5 (pause-context) breaks this file's hardcoded ==4 assertion | 2026-07-31T19:46:59Z |
| tests/pairmode/test_harness004_isolation.py | SCHEMA_VERSION bump 4->5 (pause-context) breaks this file's hardcoded ==4 assertion | 2026-07-31T19:46:59Z |
| tests/pairmode/test_harness005_isolation.py | SCHEMA_VERSION bump 4->5 (pause-context) breaks this file's hardcoded ==4 assertion | 2026-07-31T19:47:00Z |
| tests/pairmode/test_needs_spec.py | SCHEMA_VERSION bump 4->5 (pause-context) breaks this file's hardcoded ==4 assertion | 2026-07-31T19:47:00Z |
## Ensures

1. **Over-threshold flips the default.** Fixture with phase token sum >
   threshold and no fresh acknowledgment: next-action after a completed
   story returns `pause-context` (not `spawn-builder`), reason carrying
   `sum=… threshold=…`. Under threshold: `spawn-builder`, byte-identical to
   today.
2. **Acknowledgment clears exactly once.** With valid acknowledgment state,
   the same over-threshold fixture resolves to `spawn-builder`; the
   acknowledgment does not persist across a *new* over-threshold crossing
   (mirrors the hook gate's genuine-new-turn rule; share its predicate).
3. **Mid-story retries unaffected.** A FAIL-verdict retry on the same story
   resolves to `spawn-builder` attempt N+1 regardless of threshold.
4. **Threshold source order preserved.** `--threshold` arg >
   `state.json context_budget_threshold` > 120000 — the resolver path
   honors the same order via `context_budget_check`'s own resolution
   (invoke or import it; do not re-implement the order).
5. **Fail-open.** Missing effort DB, unreadable state, or a
   `context_budget_check` crash → `spawn-builder` with a warning in the
   action's warnings field. The etiquette check must never brick a build
   loop (matches `_check_cer_do_now`'s fail-open philosophy).
6. **Docs.** `docs/architecture.md` context-budget section gains the
   between-story seam (what it measures, what it does not claim to
   measure — Requires 1's honesty note); `CLAUDE.build.md.j2` gains the
   one-line `pause-context` handoff instruction.
7. **Suite green** without `-x`; baseline + added tests;
   `context_budget_check.py`'s existing tests unmodified.

## Instructions

1. Import/reuse `context_budget_check`'s resolution logic (Ensures 4) —
   subprocess invocation is acceptable if import tangles module paths;
   justify the choice in one line.
2. Wire the seam into the Row-8 class only; update the decision-table
   docstring in the same commit.
3. Share the acknowledgment predicate with the hook gate (Requires 3) —
   hoist if needed.
4. Fixtures: over/under/acknowledged/retry/fail-open.

**Do not:** gate non-build-loop spawns; gate attempt retries; make the
threshold a percentage; re-implement threshold resolution; emit a warned
spawn-builder as the over-threshold behaviour (forbidden proxy).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py tests/pairmode/test_context_budget_check.py -q 2>&1 | tail -10
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative checks: (a) over-threshold
fixture emits no `spawn-builder` anywhere in its output; (b) fail-open path
tested with a corrupted DB fixture; (c) one acknowledgment predicate exists,
shared with the hook gate.

## Out of scope

- Measuring true orchestrator context (transcript-side; the hook gate owns
  that surface).
- Any change to the PostToolUse/UserPromptSubmit hook gates.
- The `/context`-driven manual etiquette Repo-G practiced — the CLI check is
  the mechanized form; prose habits are not specced.

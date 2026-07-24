---
id: INFRA-256
rail: INFRA
title: Phase-scoped checkpoint cost rollup — filter effort rollup to the phase being checkpointed
status: draft
phase: "101"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build_checkpoint_report.py
  - tests/pairmode/test_resolver_state_cli.py
  - docs/architecture.md
---

## Context

`flex_build.py checkpoint-report` (INFRA-236) prints `=== checkpoint cost
rollup ===` as the last informational step of the checkpoint sequence, just
before `checkpoint-tag`. Its numbers come from `_query_effort_by_role`
(`flex_build.py:1860`), which was written for `resolver-state`'s cross-phase
`effort_by_role` payload: it selects **every** row in effort.db's `attempts`
table with `tokens_total IS NOT NULL AND tokens_total > 0`, with no phase,
story, or date predicate. Reusing it verbatim for the checkpoint report made
the report db-lifetime-scoped while its heading claims it is *the* checkpoint
rollup.

The operator's post-cp100 review caught the consequence: at cp-100 the report
read `builder: 19 attempt(s)` for a phase whose three stories each took exactly
one builder attempt. Nineteen is the lifetime builder count across every phase
recorded in `.companion/effort.db`. The number is not wrong as a lifetime
statistic; it is wrong as an answer to the question a checkpoint asks — "what
did *this phase* cost?" — and it actively misleads, because an inflated attempt
count at checkpoint time reads as evidence of a broken retry ladder.

Scoping must key off `story_id`, not `phase` or a timestamp window. The
`attempts` table has a `phase` column, but it is nullable and unreliable in
practice: cross-skill rows (seed, sidebar) leave it NULL by design
(`docs/architecture.md` § Effort tracking), and `record_attempt.py` only
auto-fills it when invoked with `--story-file`. A timestamp window would
mis-attribute any attempt run across a phase boundary or replayed later. The
phase doc's `## Stories` table is the authoritative membership list for a
phase, and `flex_build.py` already parses it via
`_parse_phase_stories_with_status` (`flex_build.py:1442`) — the same list the
checkpoint gates reason over. Deriving story IDs from that table and filtering
`attempts.story_id` against it makes the rollup exactly as correct as the phase
manifest itself.

Sibling story INFRA-257 fixes `attempt_number` recording. This story does not
depend on it: the rollup counts *rows*, which is the honest count of spawns
regardless of what `attempt_number` says on each row.

## Requires

- `.companion/effort.db` exists with the `attempts` schema documented in
  `docs/architecture.md` § Effort tracking (`story_id`, `phase`, `rail`,
  `agent_role`, `model`, `attempt_number`, `tokens_total`, `tool_uses`,
  `duration_ms`, `outcome`, `backend`, `ts`).
- `flex_build.py` retains `_parse_phase_stories_with_status`,
  `resolve_current_phase`, `_query_effort_by_role`, and `_next_phase_after`
  in their current form.
- The active phase resolved by `resolve_current_phase` has a `## Stories`
  table in the documented markdown format.

## Ensures

1. A new module-level helper in `skills/pairmode/scripts/flex_build.py` —
   `_query_effort_by_story_ids(db_path, story_ids)` — returns a rollup
   restricted to attempts whose `story_id` is in `story_ids`, preserving
   `_query_effort_by_role`'s `tokens_total IS NOT NULL AND tokens_total > 0`
   predicate and its `{role: {"count": int, "median_tokens": int | None}}`
   shape, plus a per-story breakdown keyed by `story_id`. It returns an empty
   result (not an exception) when the db is absent, unreadable, or
   `story_ids` is empty, matching `_query_effort_by_role`'s never-raise
   contract. Story IDs are bound as SQL parameters — no string interpolation
   into the query text.
2. `cmd_checkpoint_report` derives the phase's story IDs by reading the file
   returned by `resolve_current_phase` and passing its text through
   `_parse_phase_stories_with_status`, taking the story-ID element of each
   row. It does not read `attempts.phase`, and it does not use any timestamp
   or date window to scope the rollup.
3. The phase-scoped rollup heading names the phase it covers — the printed
   header line contains `checkpoint cost rollup` and the resolved phase key
   (e.g. `=== checkpoint cost rollup — phase 101 ===`) — so the printed output
   is self-describing when pasted into a checkpoint record.
4. Under the phase-scoped heading the report prints, for each `agent_role`
   present in the phase's attempts, `<role>: <n> attempt(s), median <n>
   tokens` (median omitted when `median_tokens` is `None`), followed by a
   per-story section listing each story ID from the phase's Stories table with
   its per-role attempt counts. A story in the table with zero recorded
   attempts is listed with an explicit zero/no-attempts marker rather than
   being silently omitted, so a story whose recording never fired is visible.
5. A lifetime rollup is retained, printed after the phase-scoped section under
   its own unambiguous heading containing both `lifetime` and an all-phases
   qualifier (e.g. `=== lifetime cost rollup (all phases) ===`), sourced from
   the unchanged `_query_effort_by_role`. It is cheap (one extra query over
   the same table) and preserves the historical baseline the operator had
   before this change; it must never be the first rollup printed, so the
   phase-scoped numbers are what an operator reads first.
6. Degradation is explicit, never silent: when `resolve_current_phase` returns
   `None`, or the resolved phase file has no parseable `## Stories` table, or
   the table yields zero story IDs, the report prints a line stating that
   phase scoping was unavailable and naming the reason, then prints the
   lifetime rollup alone. When scoping succeeds but the phase's stories have
   no recorded attempts, the report prints an explicit "no attempts recorded
   for phase <key>" line under the phase-scoped heading rather than falling
   back to lifetime numbers.
7. `resolver-state`'s `effort_by_role` payload remains lifetime-scoped and
   shape-compatible with its current output. **Decision and rationale,
   recorded here so a later reader does not re-litigate it:** `resolver-state`
   is a shipped read contract consumed by
   `skills/observability/api/src/readers/resolverState.ts` and rendered by the
   SPA's role-effort panel (`skills/observability/ui/src/components/ContextMetrics.tsx`),
   whose purpose is the cross-phase corpus view — per-role medians over the
   whole history are the statistic that panel exists to show, and narrowing it
   to the active phase would both break that intent and silently change a
   payload's semantics without a coordinated TS-side change, which is out of
   this story's scope. The two surfaces answer different questions; only
   `checkpoint-report` is phase-scoped. A test asserts `resolver-state`'s
   `effort_by_role` still counts attempts from stories outside the active
   phase.
8. `_query_effort_by_role` itself is unmodified in behaviour and signature —
   the new scoping lives in the new helper and in `cmd_checkpoint_report`, not
   by adding a filter parameter that changes existing callers' defaults.
9. `checkpoint-report` remains pure-read: the existing test asserting it writes
   nothing to `state.json` or `effort.db` still passes, and the command still
   never raises on an absent/empty effort.db or index.
10. `tests/pairmode/test_flex_build_checkpoint_report.py` covers, with an
    effort.db seeded with rows from **more than one phase's stories**: only
    the active phase's stories are counted in the phase-scoped section; the
    per-role counts equal the number of seeded rows for that phase's stories
    and no more; the lifetime section's counts are strictly greater and match
    `_query_effort_by_role`; a story listed in the Stories table with no
    attempts appears with a zero marker; a story ID present in effort.db but
    absent from the Stories table is excluded; no-active-phase and
    unparseable-Stories-table both produce the explicit scoping-unavailable
    line plus the lifetime rollup; empty effort.db still produces a minimal
    report with exit 0.
11. `docs/architecture.md` is updated in two places: the `flex_build.py` CLI
    surface description (the parenthesised subcommand list and its trailing
    notes, ~line 56) records that `checkpoint-report`'s rollup is scoped to
    the active phase's stories, derived from the phase doc's `## Stories`
    table, with the lifetime rollup printed separately; and the § Effort
    tracking section records the scoping rule and why `story_id` membership is
    used instead of the `attempts.phase` column (nullable for cross-skill
    rows, only auto-filled under `record_attempt.py --story-file`) or a
    timestamp window.
12. Full `tests/pairmode/` suite passes (known pre-existing
    `test_observability_ui.py::test_ui_build_emits_dist_index_html` failure
    acceptable if it reproduces on clean HEAD).

## Instructions

1. Read `skills/pairmode/scripts/flex_build.py` around `_query_effort_by_role`
   (~line 1860), `cmd_checkpoint_report` (~line 2061), and
   `_parse_phase_stories_with_status` (~line 1442) before editing.
2. Add `_query_effort_by_story_ids(db_path: Path, story_ids: list[str]) ->
   dict` next to `_query_effort_by_role`. Open the db with the same
   `sqlite3.connect` / try-finally-close / bare-`except` → `{}` pattern the
   existing helper uses — do not introduce a new db-access idiom. Build the
   `IN` clause from a generated `?` placeholder list bound to `story_ids`;
   never format story IDs into the SQL string. Select `story_id, agent_role,
   tokens_total` so both the by-role and by-story aggregations come from one
   query. Return a dict with a `by_role` mapping (same shape as
   `_query_effort_by_role`) and a `by_story` mapping.
3. In `cmd_checkpoint_report`, resolve the active phase file *before* the
   rollup (the existing `resolve_current_phase` call currently happens after
   the rollup — move it up, and reuse the same `phase_key` derivation for both
   the heading and the existing next-phase pointer rather than computing it
   twice). Read the phase file text, parse the Stories table, and collect the
   story IDs.
4. Print, in order: the phase-scoped heading and body, the lifetime heading
   and body, then the existing next-phase pointer line. Keep the existing
   `next phase:` output text and its "unknown"/"none (end of index)" branches
   unchanged so the INFRA-236 tests asserting on them keep passing.
5. Do not change `_query_effort_by_role`, `cmd_resolver_state`, or the
   `resolver-state` JSON document. Add the lifetime-scope lock-in assertion to
   `tests/pairmode/test_resolver_state_cli.py` alongside the existing
   `effort_by_role` tests.
6. The existing `_seed_effort_db` test helper takes `(agent_role,
   tokens_total)` tuples. Extend it to accept a `story_id` (and add a phase-doc
   Stories-table writer) in a way that keeps existing call sites working —
   either a defaulted parameter or a second helper. Do not rewrite the existing
   INFRA-236 test cases beyond what the signature change requires. Note that
   `_write_phase_index` currently writes phase files containing only a heading;
   phase-scoped tests need phase files that also carry a `## Stories` table.
7. Do not attempt to correct `attempt_number` values — that is INFRA-257. The
   counts this story prints are row counts, and the story text and a code
   comment should say so, so a reader does not mistake `3 attempt(s)` for
   `max(attempt_number) == 3`.
8. Ideology note (Step 4a, resolved inline): the rationale for choosing
   `story_id` membership over the `attempts.phase` column and over a timestamp
   window is written into `docs/architecture.md` per the "rationale-bearing
   decisions over bare rules" conviction — the constraint must not land as a
   bare rule a later agent routes around when it finds the `phase` column
   sitting unused.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_checkpoint_report.py \
  tests/pairmode/test_resolver_state_cli.py -q 2>&1 | tail -30
```

Then the full suite, without `-x` so the known pre-existing failure does not
mask a real one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance: both targeted files green; full suite green except the known
pre-existing `test_observability_ui.py::test_ui_build_emits_dist_index_html`
failure, which must be shown to reproduce on clean HEAD if it appears.

## Out of scope

- `attempt_number` correctness for repeated same-story spawns — INFRA-257.
- Changing `resolver-state`'s `effort_by_role` scope, or any change to the
  observability API/SPA (`resolverState.ts`, `ContextMetrics.tsx`).
- Backfilling or repairing the `attempts.phase` column on existing rows, or
  adding a schema migration.
- `pairmode_effort.py`'s read-time views and its PASS-rate report.
- Dollar-cost projection in the checkpoint report — tokens remain the unit
  (`docs/architecture.md` § Effort tracking, "tokens as the primary metric").

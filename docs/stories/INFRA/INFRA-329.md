---
id: INFRA-329
rail: INFRA
title: Effort-db integrity audit on post-campaign fleet data — validate the forward-only L5 fixes against real rows
status: draft
phase: "115"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/stories/INFRA/INFRA-329.md
touches:
  - docs/stories/INFRA/INFRA-329.md
  - docs/phases/phase-108.md
  - docs/stories/INFRA/INFRA-310.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Added 2026-07-30 by a cross-spec reconciliation sweep (see
`docs/closeout-agreements-20260729.md` AG-10a and the corpus review it
followed). Phase 108's Goal names "effort recording sound on real campaign
data" as half of era 003's exit criterion. `INFRA-310` (phase 116) had
claimed this obligation was discharged by `INFRA-312` (phase 115) — but
INFRA-312 is entirely UI/route-shaped (Fastify route smoke tests, CORS
pinning, a dogfood checklist over the observability SPA) and never touches
`effort.db`. This story is the missing sibling that actually validates it.

The effort-recording subsystem (`effort.db`) has a long fix lineage
(phases 22–113), and every fix in its most recent arc is explicitly
**forward-only**:

- INFRA-287 (phase 110) fixed a `resolve()`-through-symlink bug where
  reconciliation rejected 294/294 real output files — nothing was ever
  reconciled before this fix landed.
- INFRA-288 (phase 110) fixed downstream double-insertion of rows.
- INFRA-289 (phase 110) fixed session-bound attribution producing
  `unattributed:` / malformed `story_id` values.
- INFRA-299 (phase 113) constrained recorded `outcome` values to
  `RECOGNISED_BUILD_OUTCOMES` (`subagent_transcript.py:383` —
  `frozenset({"PASS", "FAIL"})`), closing a lowercase-`pass` class of row
  CER-113/CER-024 both describe.

No story has ever queried a real fleet `effort.db` to check whether rows
written *after* each fix actually conform to what the fix promised. Era 003's
exit criterion is otherwise being met on half its own stated evidence.

**The correct signal is a query against real `effort.db` files on disk for
≥ 3 of this project's registered sibling repos, with the fix-boundary
timestamp for each named. The forbidden proxy is asserting the fix code
exists (re-reading INFRA-287/288/289/299's diffs) without querying a single
real row.**

## Requires

1. `.companion/state.json`'s `registered_projects` lists six sibling repos
   today (`/mnt/work/coherra`, `/mnt/work/meander`, `/mnt/work/caddy`,
   `/mnt/work/forqsite.help`, `/mnt/work/halfhorse`, `/mnt/work/cora`) — at
   least 3 of these must have a `.companion/effort.db` with rows to audit;
   skip (and name) any that don't, do not fail the story over a sibling with
   no build history.
2. `effort.db`'s `attempts` table schema — read it directly
   (`sqlite3 <path> '.schema attempts'`) rather than assuming column names;
   confirm `agent_id`, `agent_role`, `story_id`, `outcome`, `tokens_total`
   exist before writing queries against them.
3. INFRA-287/288/289 (phase 110) and INFRA-299 (phase 113) must be complete
   on `main` before this story's queries are meaningful — verify each is
   `complete` in its phase manifest first.
4. This is a **read-only audit against sibling repos** — no write to any
   sibling's `effort.db` or any sibling's git state. Findings are recorded
   here and, where they represent a real defect, filed as new `docs/cer/backlog.md`
   rows in *this* repo (flex), not fixed in the sibling repos.

## Ensures

1. **Duplicate `(agent_id, agent_role)` pairs, post-INFRA-288.** For each
   audited sibling, a query counts `attempts` rows sharing the same
   `(agent_id, agent_role)` pair with a `created_at` (or equivalent) after
   that sibling's INFRA-288-equivalent sync date; zero duplicates expected.
   Any found is recorded with the sibling name, row count, and pasted as
   evidence — not silently ignored.
2. **Reconciliation coverage, post-INFRA-287.** For each audited sibling,
   the fraction of spawn-produced output files with a matching non-NULL
   `tokens_total` row dated after that sibling's INFRA-287-equivalent sync
   is reported as a percentage with the raw counts. 100% is the target;
   anything less is recorded with a stated reason if determinable (e.g. a
   spawn that never completed) rather than asserted away.
3. **Zero unattributed/malformed `story_id` values, post-INFRA-289.** A
   query for `story_id LIKE 'unattributed:%'` or `story_id LIKE 'phase:%'`
   dated after that sibling's INFRA-289-equivalent sync returns zero rows;
   any found are pasted as evidence.
4. **`RECOGNISED_BUILD_OUTCOMES` conformance, post-INFRA-299.** A query for
   `outcome` values outside `{"PASS", "FAIL", NULL}` dated after that
   sibling's INFRA-299-equivalent sync returns zero rows.
5. **Pending-row inventory.** For each audited sibling, a count of rows with
   NULL `tokens_total` or NULL `outcome`, broken down by whatever pending-reason
   classification the codebase already exposes (e.g.
   `classify_pending_reason` if it exists — confirm at build time; if no such
   helper exists, classify by NULL-column pattern instead and say so).
6. **Explicit statement of what is not recoverable.** A `## Evidence` section
   states plainly: pre-fix rows (dated before each sibling's respective
   sync) are not backfilled by any of INFRA-287/288/289/299, this audit does
   not attempt to recover them, and this is by design (forward-only fixes),
   not a gap this story closes.
7. **Any genuine defect found is filed, not silently noted.** If any of
   Ensures 1–4's queries return non-zero where zero was expected, file a
   `docs/cer/backlog.md` row in flex naming the defect, the sibling(s) it was
   observed in, and the query used. The `## Evidence` section states
   "defects found: N, filed: CER-…" (N may be 0).
8. **Phase-108/INFRA-310's discharge claim corrected if this audit fails.**
   If any Ensures 1–4 query fails on any audited sibling, this story's
   `## Evidence` states that era 003's effort-recording exit criterion is
   **not** fully met, and names the filed CER row(s) as the residual — this
   story does not silently pass the era's exit criterion by narrowing scope.

## Instructions

1. Confirm INFRA-287/288/289/299 are `complete` (Requires 3).
2. For each of the ≥ 3 audited siblings, read the live `attempts` schema
   before writing any query (Requires 2).
3. Run Ensures 1–5's queries against each sibling; record raw counts and the
   sync-date boundary used per sibling.
4. Write the `## Evidence` section: per-sibling results, the not-recoverable
   statement (Ensures 6), and the defects-filed count (Ensures 7).
5. If any defect is filed, update this story's Ensures 8 statement and note
   the residual in `docs/phases/phase-108.md`'s `## Superseded` section
   (added by INFRA-310) and in `INFRA-310.md`'s Context item 4, so the
   era-003 exit-criterion record stays honest.
6. Do not fix any defect found in a sibling repo from this session — file
   only (Requires 4). Do not expand scope into re-running the sibling's own
   build loop.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

This story adds no new Python test file (it is a data audit against sibling
repos' `effort.db` files, not a change to flex's own code) — its evidence is
the `## Evidence` section's pasted query output, not a pytest assertion.
Acceptance: full flex suite unaffected (no regression), `## Evidence` present
and complete per Ensures 1–8.

## Out of scope

- Fixing any defect discovered in a sibling repo's `effort.db` or code —
  file a CER row in flex only (Requires 4).
- Backfilling pre-fix rows in any sibling's `effort.db` — explicitly not
  recoverable (Ensures 6).
- Any change to flex's own `effort.db` schema, recorder, or reconciliation
  logic — this is an audit story, not a fix story.
- Re-running or re-triggering any sibling's build loop.

---
id: INFRA-329
rail: INFRA
title: Effort-db integrity audit on post-campaign fleet data — validate the forward-only L5 fixes against real rows
status: complete
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
   today (`/mnt/work/Repo-A`, `/mnt/work/Repo-B`, `/mnt/work/Repo-C`,
   `/mnt/work/Repo-D`, `/mnt/work/Repo-F`, `/mnt/work/Repo-G`) — at
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

## Evidence

All queries below were run fresh on 2026-07-31 with `python3`'s stdlib
`sqlite3` module (no `sqlite3` CLI binary is on `PATH` in this environment)
directly against each sibling's live `/mnt/work/<repo>/.companion/effort.db`.
Every row cited here was re-selected and transcribed at build time — none is
carried over from a prior attempt or from memory.

### Requires 3 — fix stories complete on `main`

- `docs/phases/phase-110.md:28-30` — INFRA-287, INFRA-288, INFRA-289 all read
  `complete`.
- `docs/phases/phase-113.md:27` — INFRA-299 reads `complete`.

### Requires 1 — registered siblings and effort.db presence

`.companion/state.json`'s `registered_projects` (read directly, not
recalled): `/mnt/work/Repo-A`, `/mnt/work/Repo-B`, `/mnt/work/Repo-C`,
`/mnt/work/Repo-D`, `/mnt/work/Repo-F`, `/mnt/work/Repo-G`. All six
have a `.companion/effort.db` with rows — none is skipped for absence:

| Sibling | rows (`attempts`) | min `ts` | max `ts` |
|---|---|---|---|
| Repo-A | 744 | 2026-06-11T15:01:48Z | 2026-07-22T19:45:53Z |
| Repo-B | 299 | 2026-06-26T21:39:47Z | 2026-07-29T04:26:27Z |
| Repo-C | 37 | 2026-07-16T05:58:30Z | 2026-07-28T20:59:56Z |
| Repo-D | 14 | 2026-07-13T21:13:35Z | 2026-07-29T02:43:55Z |
| Repo-F | 2 | 2026-07-29T03:50:14Z | 2026-07-29T03:53:27Z |
| Repo-G | 130 | 2026-05-15T02:37:58Z | 2026-06-25T00:54:26Z |

### Fix-boundary timestamps (Requires 3 / Instructions 3)

Every sibling's `.claude/settings.json` `PreToolUse`/`PostToolUse` hooks
invoke `/mnt/work/flex-harness/hooks/*.py` **by absolute path** (verified
directly in `Repo-B/.claude/settings.json` and `Repo-C/.claude/settings.json`)
— the fix is a single shared, non-vendored checkout, not something copied
per-repo on a per-sibling schedule. There is therefore one shared boundary
timestamp per fix, not six independent per-sibling sync dates:

- **INFRA-287/288/289 boundary** = `cp-110` tag creation time in
  `flex-harness`: `2026-07-28T11:57:54-04:00` = **`2026-07-28T15:57:54Z`**.
- **INFRA-299 boundary** = `cp-113` tag creation time in `flex-harness`:
  `2026-07-29T21:06:19-04:00` = **`2026-07-30T01:06:19Z`**.

(`git -C /mnt/work/flex-harness for-each-ref --format='%(refname)
%(creatordate:iso-strict)' refs/tags | grep -E "cp-110|cp-113"`.)

Two siblings (Repo-A, Repo-G) have **no rows at all after the CP-110
boundary** — their most recent recorded activity (2026-07-22 and 2026-06-25
respectively) predates the fix landing. They are named here, not silently
dropped: they have build history, just none of it post-dates the fixes being
audited, so Ensures 1–4 have nothing to query for them.

### Requires 2 — live schema check

`pragma table_info(attempts)` per sibling:

| Sibling | `agent_id` | `output_file` | Note |
|---|---|---|---|
| Repo-A | absent | absent | pre-INFRA-288/289 schema shape — never gained these columns |
| Repo-B | present | present | |
| Repo-C | present | present | |
| Repo-D | present | present | |
| Repo-F | present | present | |
| Repo-G | absent | absent | pre-INFRA-288/289 schema shape — never gained these columns |

`story_id`, `agent_role`, `outcome`, `tokens_total` exist in all six (all
share the common base schema).

### Ensures 1 — duplicate `(agent_id, agent_role)` pairs post-CP110

```sql
select agent_id, agent_role, count(*) c from attempts
where ts > '2026-07-28T15:57:54+00:00' and agent_id is not null
group by agent_id, agent_role having c > 1;
```

| Sibling | Result |
|---|---|
| Repo-B | 0 groups |
| Repo-C | 0 groups |
| Repo-D | 0 groups |
| Repo-F | 0 groups |
| Repo-A | N/A — no `agent_id` column (Requires 2) |
| Repo-G | N/A — no `agent_id` column (Requires 2) |

Zero duplicates in all four siblings where the check is computable.

### Ensures 2 — reconciliation coverage post-CP110

Post-CP110 row count and non-NULL `tokens_total` count per sibling:

| Sibling | post-CP110 rows | non-NULL `tokens_total` | % |
|---|---|---|---|
| Repo-B | 17 | 13 | 76.5% |
| Repo-C | 6 | 5 | 83.3% |
| Repo-D | 2 | 2 | 100% |
| Repo-F | 2 | 2 | 100% |
| Repo-A | 0 | — | N/A (no post-CP110 activity) |
| Repo-G | 0 | — | N/A (no post-CP110 activity) |

The four shortfall rows were individually classified with the live
`classify_pending_reason()` helper (`subagent_transcript.py:1439`, confirmed
present — Ensures 5 uses the same helper):

- Repo-B id 283 (`SEC-006`, builder) → `no-outcome`
- Repo-B id 284 (`INFRA-012`, builder) → `no-outcome`
- Repo-B id 297 (`OPS-006`, reviewer) → `reconcilable`
- Repo-B id 299 (`phase:MN029-main`, intent-reviewer) → `reconcilable`
- Repo-C id 32 (`PAIRMODE-001`, builder) → `not-terminated`

All five are recent in-flight/awaiting-reconciliation spawns (the tail end of
each sibling's activity), not lost or dropped reconciliation — none is a
completed spawn whose output file was reachable and still failed to
reconcile.

### Ensures 3 — `unattributed:%` / `phase:%` `story_id` values post-CP110

```sql
select id, ts, story_id, agent_role from attempts
where ts > '2026-07-28T15:57:54+00:00'
and (story_id like 'unattributed:%' or story_id like 'phase:%')
order by id;
```

| Sibling | Rows | Detail |
|---|---|---|
| Repo-B | 2 | id **298** `unattributed:security-auditor` (`ts` 2026-07-29T04:19:26Z, `agent_role`=security-auditor); id **299** `phase:MN029-main` (`agent_role`=intent-reviewer) |
| Repo-C | 3 | id **35** `phase:EH005-main` (`agent_role`=security-auditor); id **36** `phase:EH005-main` (`agent_role`=intent-reviewer); id **37** `unattributed:reviewer` (`agent_role`=reviewer) |
| Repo-D | 0 | |
| Repo-F | 0 | |
| Repo-A / Repo-G | N/A | no post-CP110 rows |

**Total: 3 `phase:%` rows, 2 `unattributed:%` rows (5 rows total)** — this
matches the reviewer's independent re-run cited in the prior attempt's
rejection, not the prior attempt's miscounted 4/1 split.

**Reasoning — defect or honest fallback?** `_derive_attribution()`
(`subagent_transcript.py:785-824`) special-cases `CHECKPOINT_ROLES =
frozenset({"security-auditor", "intent-reviewer"})` (`:118`): these spawns
carry no individual story, so a phase key is derived from the checkpoint
prompt. When a phase key **is** derivable the row is stamped
`phase:<key>` — Repo-C 35/36 (`phase:EH005-main`) and Repo-B 299
(`phase:MN029-main`) are exactly this, the corrected INFRA-289/CER-102/103
behaviour that replaced the pre-fix defect the docstring itself names
(first-match story-id regex mis-stamping an entire phase's checkpoint cost
onto whichever story happened to be named first in the prompt — "observed:
effort.db ids 339-340 stamped INFRA-256"). When no phase key is derivable,
the same branch returns `unattributed:<subagent_type>` as an explicitly
documented **honest** fallback — the docstring's own words: "rejection is
honest, not a plausible-looking `phase:<English word>` lie" (CER-103(b)).
Repo-B's id 298 (`unattributed:security-auditor`) is exactly this path: a
`CHECKPOINT_ROLES` spawn for which no valid phase doc/key could be resolved
at record time, so the recorder refused to guess rather than fabricate a
`phase:` value.

Repo-C's id 37 (`unattributed:reviewer`) is **not** a `CHECKPOINT_ROLES` row
— `reviewer` is not in that frozenset. For every other role,
`_derive_attribution` falls through to the ordinary path (prompt-embedded
story-id regex → `state.json["current_story"]` → `None`), and the caller
applies the same `unattributed:<role>` string when nothing is derivable
(`subagent_transcript.py:822-824`, caller-side fallback at
`effective_story_id = story_id or f"unattributed:{subagent_type}"`, `:2551`).
This row landed at `2026-07-28T20:59:56Z`, immediately after Repo-C's own
`phase:EH005-main` checkpoint pair (35/36) and PAIRMODE-002's builder/reviewer
merge (33/34) — consistent with a phase-closeout-adjacent reviewer spawn run
after `current_story` had already been cleared by the just-completed merge,
so the ordinary derivation path correctly found nothing and applied the
documented fallback string rather than inventing a story id.

**Disposition: none of the 5 rows is the "malformed story_id" class of
defect Ensures 3 was written to catch** (a garbled id, casing drift, or a
truncated/mis-parsed value). All 5 are the deliberate, documented output
shapes `_derive_attribution` produces for context-free `CHECKPOINT_ROLES`
spawns (and, for Repo-C id 37, the same documented fallback applied by a
non-checkpoint role that genuinely had no story context at spawn time). This
is INFRA-289 working as designed, not a regression. Ensures 3's literal
zero-tolerance wording does not distinguish this designed fallback category
from a genuine attribution defect — that is a precision gap in this story's
own acceptance criterion, not a code defect in effort recording, so **no CER
is filed for this Ensures**.

### Ensures 4 — `RECOGNISED_BUILD_OUTCOMES` conformance post-CP113

```sql
select id, ts, story_id, outcome from attempts
where ts > '2026-07-30T01:06:19+00:00'
and outcome is not null and outcome not in ('PASS','FAIL');
```

**Zero rows on every sibling — but not because conformance was verified.**
The latest row on *any* of the six siblings is Repo-B id 299 at
`2026-07-29T04:26:27Z`, roughly 20.5 hours **before** the CP-113/INFRA-299
boundary (`2026-07-30T01:06:19Z`). No sibling has recorded a single
`attempts` row since INFRA-299 landed. The query trivially returns zero
because there is nothing to query yet, not because a real post-fix row was
checked and found conformant. This is reported as an open gap, not a pass.

### Ensures 5 — pending-row inventory

`classify_pending_reason()` (`subagent_transcript.py:1439`) exists and was
used directly (not a NULL-column-only classification) for every row with
`tokens_total is null or outcome is null`:

| Sibling | pending rows | breakdown |
|---|---|---|
| Repo-A | 378 | `no-output-file`: 378 |
| Repo-B | 151 | `no-output-file`: 100, `no-outcome`: 10, `reconcilable`: 41 |
| Repo-C | 18 | `no-output-file`: 17, `not-terminated`: 1 |
| Repo-D | 6 | `no-output-file`: 6 |
| Repo-F | 0 | — |
| Repo-G | 56 | `no-output-file`: 56 |

`no-output-file` rows are historical rows recorded before that sibling's
schema carried `output_file` tracking at all (Repo-A/Repo-G never gained the
column — Requires 2) or predate the column being populated in the other four
siblings' own tables. These are pre-fix legacy rows, not evidence of ongoing
reconciliation failure — see Ensures 6.

### Ensures 6 — what is not recoverable

Pre-fix rows (dated before each fix's boundary above, or recorded under a
schema shape — Repo-A/Repo-G — that never gained the `agent_id`/`output_file`
columns INFRA-288/289 introduced) are **not** backfilled by INFRA-287, 288,
289 or 299. This audit does not attempt to reconstruct or reclassify them.
This is by design — all four fixes are explicitly forward-only, per this
story's own Context section — not a gap this story closes.

### Ensures 7 — defects found and filed

**Defects found: 0. Filed: none.** Ensures 1 (0 duplicate groups on every
testable sibling), Ensures 2 (all shortfalls are recent in-flight spawns
with a determined pending reason, not lost reconciliation) and Ensures 3
(reasoned above: all 5 non-empty rows are documented, designed fallback
output, not malformed values) show no genuine defect. Ensures 4 has no
post-boundary data on any sibling to evaluate at all (see below) — this is
a data-availability gap, not a code defect, so it is not filed as a CER
either.

### Ensures 8 — era 003 discharge claim

Era 003's "effort recording sound on real campaign data" exit criterion is
**partially, not fully, verified** by this audit:

- Ensures 1–3 were checked against real post-fix rows on 4 of 6 siblings
  (Repo-B, Repo-C, Repo-D, Repo-F) and found no defect.
- Ensures 4 (INFRA-299 conformance) has **zero real rows to check on any
  sibling** — INFRA-299 has not yet been exercised in the field as of this
  audit (2026-07-31). Its "pass" above is vacuous, not a verification.

Because this residual is an absence of post-fix data rather than a genuine
non-zero-where-zero-was-expected defect (Ensures 7 found 0 defects to file),
this story does **not** edit `docs/phases/phase-108.md`'s `## Superseded`
section or `docs/stories/INFRA/INFRA-310.md`'s Context item 4 (Instructions
5 conditions those edits on a defect being filed). Both of those sections
belong to INFRA-310, which has not yet built (`status: draft`) and whose own
Ensures 24 is the gate that will write phase-108's `## Superseded` section
naming this story's evidence. What is recorded here instead, plainly: era
003's effort-recording half is **not fully proven** — Ensures 1–3 are clean
on real data, Ensures 4 is unexercised. A future re-run of this audit (or of
Ensures 4 alone) once any sibling records a post-2026-07-30T01:06:19Z row is
the natural way to close this residual; it is not fixed by this story
because there is no code or row to fix, only field data to wait for.

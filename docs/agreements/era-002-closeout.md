# Era 002 close-out plan

**Purpose:** leave Era 002 in a clean, honest state before activating Era 003
(harness). Per the phase-continuity policy, an era cannot close with silently
abandoned `planned` stories — every planned story must be `complete` or formally
`deferred`, the CER Do Now must be clear, and findings not built now must be
captured in the backlog.

**Status:** plan (decisions open)

## What the observability surface revealed

Reviewing radar + forqsite side-by-side (`flex_eph/Screenshot … 11-50-04.png`)
surfaced real process defects, not just display issues:

- **D1 — `expected_step_tokens` is mis-sourced and uniform.** Both radar and
  forqsite show exactly **53000** from STATE.JSON despite being very different
  projects. Root cause: it is seeded from the *effort baseline builder median*
  (`bootstrap.py:417` `_load_seed_expected_step_tokens()` → `by_role.builder.median`,
  fallback `_DEFAULT_EXPECTED_STEP_TOKENS = 53000`) and stamped fleet-wide; `sync.py:594`
  / `context_budget.py:526` carry the same literal. So the *context-budget
  window-growth constant is sourced from per-story effort cost* — the exact
  effort.db ≠ context-control comingling (≡ harness DP7) — and is never
  re-estimated per project. Effect: the live budget gate over-reserves ~53k and
  fires far too early everywhere.
- **D2 — `context_current_tokens` stuck at the reset seed.** Both projects read
  25.0k (the SessionStart reset value) and are STALE (radar ~45h, forqsite ~15h).
  The live token writer isn't updating these projects. Needs root-cause (writer not
  firing? these projects simply idle since the fix?).
- **D3 — waypoint outcomes uniformly FAIL.** Every waypoint on both projects shows
  FAIL across 224 / 460 attempts — implausible. Either outcome recording
  (`record_attempt.py` → effort.db `outcome`) or the SPA render
  (`effortDb.ts` / `context.ts` waypoints) is wrong. Also corrupts the
  `pairmode_effort.py models` PASS-rate report.

## Era 002 actual state (verified against git + index)

- **Genuinely open:** **Phase 64** (Observability SPA hardening) only — 5 unbuilt
  stories (0 commits each):
  - INFRA-164 `flex_observability.py` CLI hardening
  - INFRA-165 `context_budget.py` flex_factor correctness — NaN
  - INFRA-166 Fastify API route hardening — null project_dir
  - INFRA-167 TypeScript parser robustness — phaseIndex blank
  - INFRA-168 `effortDb.ts` p90 off-by-one + in-flight promise dedupe
- **Status drift (built + committed, still marked `planned`):** INFRA-106, 107,
  108, 109, 110, 111, INFRA-148, BUILD-029. All have `feat(story-…)` commits;
  BUILD-029 has a `cp-70 … complete` checkpoint. → mark `complete`.
- **Era 002 doc rot:** Phases table is stale (61/62/66/70 shown `planned` but
  complete in index) and incomplete (missing most of 58–78); Rails table empty.
- **CER Do Now:** ~10 rows present, all appear RESOLVED/retriaged/moved — needs a
  clean read to confirm none genuinely open, and tidy (resolved items shouldn't sit
  under "Do Now").

> The status drift is a textbook case for the **HARNESS008 housekeeper**: nothing
> currently catches "built story still marked planned." Its forcing function has
> arrived.

## Decisions

### DC1 — Phase 64: build or defer?  *(central decision)*

**Recommendation: DEFER all of Phase 64 to Era 003 Phase G (observability
refactor).** Phase 64 hardens the *current* observability SPA and context-budget
code that Era 003 Phase G + the harness context-control work will rebuild/replace —
hardening soon-to-be-rebuilt code is wasted effort.

**Possible exception:** INFRA-165 (`context_budget.py` flex_factor NaN) is a
*correctness* bug in the live gate used *during* the Era-3 build (old loop, DP6).
If the NaN actually misbehaves, a standalone fix may be warranted; otherwise it
defers with the rest. **Decision:** ⬜ OPEN — proposed: defer all; confirm whether
INFRA-165 is a fix-now exception.

### DC2 — Status-drift stories → mark complete

The work exists in git. **Decision:** ⬜ OPEN — proposed: mark INFRA-106/107/108/
109/110/111, INFRA-148, BUILD-029 `complete` (verify each via git during execution).

### DC3 — Defects D1/D2/D3 → defer + capture

**Recommendation:** capture all three as backlog/CER entries tagged Era 003, do not
fix in Era 002. D1 already lives in the harness agreements (DP7) — cross-reference
it. D2/D3 fold into Phase G's mandate. **Decision:** ⬜ OPEN — proposed: capture +
defer; Phase G's scope explicitly absorbs Phase 64 + D1/D2/D3.

## Execution sequence (once decisions confirmed)

1. **Status reconciliation** — mark the 8 drift stories `complete`
   (`story_update.py --status complete`, verifying each against git).
2. **Era 002 doc reconciliation** — rebuild the Phases table to index truth (all
   58–78) and populate the Rails table.
3. **Phase 64 disposition (per DC1)** — if deferring: set Phase 64 + its 5 stories
   to `deferred`; add a `## Deferred stories` section to `phase-64.md` and the era
   doc, pointer "Resumed in Era 003 Phase G (HARNESS007-main)".
4. **Capture defects (per DC3)** — D1 (cross-ref DP7), D2, D3 as CER/backlog
   entries tagged Era 003 Phase G.
5. **CER Do Now clearance** — confirm no genuinely-open Do Now item; move resolved
   rows out of the section.
6. **Era transition** — run `era_transition.py` to close 002 and activate 003.
   Reconcile the proposed-era content (`era-proposed-harness-20260624-001.md`) into
   the created `003-harness.md`; fold Phase 64 + D1/D2/D3 into Phase G's scope.

## Notes

- Marking complete / deferring / backlog-capture are *bookkeeping*, not builds — no
  story specs required (they are close-out hygiene per the phase-continuity policy).
- The Era-3 harness phases cannot begin building until step 6 completes (002 closed,
  003 active).

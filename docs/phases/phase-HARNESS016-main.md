---
era: "003"
---

# flex-harness — Phase HARNESS016-main: Final fold — pre-fold gate, merge to main, re-sync

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Execute the unexecuted tail of docs/harness-cutover-runbook.md: reconcile main drift into
fold-prep, run the DP8 pre-fold discovery gate as a hard block, fold fold-prep into
/mnt/work/flex main with tag v0.3.0, re-sync migrated projects to the canonical checkout,
and retire the flex-harness worktree.

## Background

Surfaced 2026-07-15/16 while planning the fold: `fold-prep` had fallen behind `main`
by 31 commits since RELEASE-008's reconciliation, including three commits
(INFRA-192, INFRA-193, INFRA-199) that harden the exact context-budget `PreToolUse`
gate subsystem that blocked a recent builder spawn attempt in this worktree, and one
commit (INFRA-195) that changes `audit.py`/`sync.py` — the tooling the fold's own
re-sync stories (RELEASE-015/017) depend on. RELEASE-014 must land before those
budget-gate/sync-tooling changes can be trusted during the rest of this phase.

Separately, live discovery (`fleet_discovery.py`) shows the DP8 pre-fold gate
currently **fails**: all 9 fleet projects remain on pairmode 0.2.x, and neither
flex nor flex-harness has self-synced. HARNESS013-main's "Fleet Migration" phase
shipped the migration *tooling*, not the migrations themselves — that campaign is
separate, cross-repo, operator-driven work that must complete before RELEASE-015
can pass.

Further surfaced 2026-07-17: a cold-eyes architectural review (requested ahead of
the fold, to check that pairmode's enforcement mechanisms — context budget gate,
scope guard, cold-read guard — actually read as "hygiene and guideline, not law"
rather than either a hollow claim or an inescapable trap) found:

1. `main` has drifted a **second** time since RELEASE-014's merge — now 36
   commits ahead of `fold-prep` (verified via `git log fold-prep..main
   --oneline`), including INFRA-205/206/207 and checkpoints 91-94. This batch
   is load-bearing for the review's own findings (see RELEASE-019).
2. Two enforcement/flexibility gaps that are independent of the drift and
   still present on `main` at HEAD: `flex_factor` (the documented per-story
   context-ceiling override) never reaches `context_budget.decide()`
   (RELEASE-020); and the `CONTEXT CHECK REQUIRED` gate variant is an
   unacknowledgeable hard block whose own message promises a self-heal that
   cannot happen, with no real exit named (RELEASE-021).
3. Documentation staleness that undermines the "system of record" claim:
   README era status, `architecture.md`'s pre-flip build-loop description and
   "advisory-only until HARNESS006" annotations (HARNESS006 shipped), and the
   reviewer procedure's self-contradictory input-scope contract (RELEASE-022).

Two findings from the same review — dead-code `scope_guard`/`cold_read_guard`
dispatch (no matching `PreToolUse` matcher registered) and a stale
`bootstrap.py` matcher — turned out to already be fixed on `main`
(INFRA-205, INFRA-206) and are resolved as a byproduct of RELEASE-019, not
tracked as separate stories. A third finding (this repo's own
`.claude/settings.json` pointing at `/mnt/work/flex` instead of this
worktree, with only a bare `Task` matcher) is the expected pre-self-sync
state already covered by RELEASE-015/017's gate and re-sync work — not a new
story.

Further surfaced 2026-07-21: a fresh fleet-wide `fleet_discovery.py` run
(the 2026-07-17 snapshot in `docs/fleet-snapshot.md` had gone stale) shows
**0 of 18 bound projects pass DP8** — every project is still `binding:
version`, on pairmode 0.2.0 (aab, asp, base56, caddy, coherra, forqsite,
forqsite.help, halfhorse, lumin, meander, pokus, radar, rockue, stackabid,
ud) or 0.1.0 (anchor, cora), with Signal-1 absent. `stackabid` is newly
bound since the 07-17 snapshot. RELEASE-024 through RELEASE-040 originally
specced one migration story per bound sibling project (17 total;
`/mnt/work/flex` itself is out of scope here — its self-sync is
RELEASE-017's concern, not the fleet's). Each migration story explicitly
flags that its file writes land outside `/mnt/work/flex-harness`'s project
root and are therefore invisible to `scope_guard`'s enforcement, so these
must be executed directly, not dispatched to a scope-bound spawn-builder
subagent.

**anchor and cora excluded (decided 2026-07-21):** `anchor` is flex's frozen
predecessor — flex was hard-forked from it and it will not be developed
further, so it is not part of the managed fleet at all. Its migration story
(originally RELEASE-025) is removed outright, and RELEASE-015's DP8 gate is
updated to never scan or block on it. `cora` was the testbed where
anchor/flex build-loop principles were originally proven out and still
holds artifacts worth porting into flex — notably a lesson about not
allowing a schema-introducing story to complete without a matching UI
management story, which passes smoke tests but fails immediately in UAT
(flex's own `CLAUDE.md` "Conceptual rebuild completeness" policy already
codifies a version of this, but cora's specific case hasn't been reviewed
for gaps). cora's migration story (RELEASE-030) combines the 0.1.0 schema
gap with this extraction work, making it larger than a standard migration;
it is deferred (`status: backlog`) rather than dropped, and excluded from
RELEASE-015's pass/fail condition — see "Deferred stories" below.

## Stories

| ID | Title | Status |
|----|-------|--------|
| RELEASE-014 | Pre-fold reconciliation — merge main (31 commits, incl. INFRA-192/193/195/199) into fold-prep | complete |
| RELEASE-023 | Fix `_has_story_commit()` commit-message matching in `next_story.py` (resolver loop bug) | complete |
| RELEASE-019 | Second pre-fold reconciliation — merge main (36 commits, incl. INFRA-205/206/207) into fold-prep | complete |
| RELEASE-020 | Wire `flex_factor` into the context-budget `PreToolUse` gate | planned |
| RELEASE-021 | Fix the unacknowledgeable `CONTEXT CHECK REQUIRED` gate trap | planned |
| RELEASE-022 | Pre-fold doc sweep — era status, post-flip staleness, reviewer input-scope contradiction | planned |
| RELEASE-024 | Fleet migration — sync aab to pairmode 0.3.0 | planned |
| RELEASE-026 | Fleet migration — sync asp to pairmode 0.3.0 | planned |
| RELEASE-027 | Fleet migration — sync base56 to pairmode 0.3.0 | planned |
| RELEASE-028 | Fleet migration — sync caddy to pairmode 0.3.0 | planned |
| RELEASE-029 | Fleet migration — sync coherra to pairmode 0.3.0 | planned |
| RELEASE-030 | Fleet migration — sync cora to pairmode 0.3.0 (0.1.0 schema gap + artifact extraction) | backlog |
| RELEASE-031 | Fleet migration — sync forqsite to pairmode 0.3.0 | planned |
| RELEASE-032 | Fleet migration — sync forqsite.help to pairmode 0.3.0 | planned |
| RELEASE-033 | Fleet migration — sync halfhorse to pairmode 0.3.0 | planned |
| RELEASE-034 | Fleet migration — sync lumin to pairmode 0.3.0 | planned |
| RELEASE-035 | Fleet migration — sync meander to pairmode 0.3.0 | planned |
| RELEASE-036 | Fleet migration — sync pokus to pairmode 0.3.0 | planned |
| RELEASE-037 | Fleet migration — sync radar to pairmode 0.3.0 | planned |
| RELEASE-038 | Fleet migration — sync rockue to pairmode 0.3.0 | planned |
| RELEASE-039 | Fleet migration — sync stackabid to pairmode 0.3.0 | planned |
| RELEASE-040 | Fleet migration — sync ud to pairmode 0.3.0 | planned |
| RELEASE-015 | Pre-fold discovery gate (DP8) — fresh fleet snapshot, hard block on un-migrated projects | planned |
| RELEASE-016 | Fold merge — fold-prep → main, tag v0.3.0 | planned |
| RELEASE-017 | Post-fold re-sync of migrated projects + RELEASE-002 status reconciliation | planned |
| RELEASE-018 | Worktree and branch retirement — remove /mnt/work/flex-harness | planned |

## Deferred stories

RELEASE-030 (fleet migration — cora) was deferred on 2026-07-21. cora
combines the standard 0.1.0-schema-gap migration work with a separate need:
extracting build-loop lessons proven there (notably a rule about
schema-introducing stories requiring a matching UI management story, found
via cora's own history — passes smoke tests but fails UAT without it)
before a routine sync-all overwrites the artifacts that demonstrate it.
That extraction work isn't yet scoped, so the story is parked at
`status: backlog` rather than built now. RELEASE-015's DP8 gate excludes
`cora` from its pass/fail condition so this deferral doesn't block the fold.

Resumed as its own dedicated story once the artifact-extraction work is
scoped — no target phase assigned yet.

(`anchor`'s migration story, originally RELEASE-025, was not deferred but
removed outright: anchor is flex's frozen predecessor and not part of the
managed fleet, so there is nothing to resume.)

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | No new persistent schema objects introduced. |

---

### CP-HARNESS016-main Cold-eyes checklist

— developer fills in after phase completion —

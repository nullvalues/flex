---
id: INFRA-362
rail: INFRA
title: Dogfood narrative citation on flex's own story specs going forward
status: draft
phase: "118"
story_class: methodology
auth_gated: false
schema_introduces: false
primary_files:
  - docs/phases/phase-119.md
touches:
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The operator's original ask for this exercise: "manually dog-food / bootstrap these narratives,
building narrative dependency in as we go." Every prior story in this phase builds the *mechanism*
(propagation, spec-writer input, intent-reviewer check, brevity discipline, shadow-reviewer). This
story is the terminal, retrospective check: does the mechanism actually get used on real,
subsequent work, or does it sit unused the way `cer.py gate`/`groom` sat unused after being built
(Phase 117, CER-152)? This is deliberately the *last* story in the phase and deliberately thin — it
is a verification/closure step, not new construction.

## Requires

- Every other Phase 118 story (INFRA-351 through 361) must have landed.

## Ensures

1. At least one real story spec, written *after* this phase's mechanism landed (the first story of
   whatever phase comes next — likely Phase 119, or a subsequent story added to this phase's own
   tail if none exists yet), declares a non-empty `narrative_roles:` and was drafted by an actual
   spec-writer run (not hand-authored) citing the relevant narrative file(s), demonstrating
   INFRA-355's mechanism end to end on real (not fixture) content.
2. That same story is reviewed with intent-reviewer's narrative-alignment check
   (INFRA-356) actually running against it — either the post-build or pre-build mode, whichever the
   phase's own checkpoint sequence reaches first — and the finding (aligned or not) is recorded in
   this story's own Evidence section, read directly rather than assumed.
3. If any part of the mechanism doesn't hold up under this real use (a narrative reads awkwardly, a
   `narrative_roles:` tag was ambiguous, the brevity self-check from INFRA-357 didn't actually
   reduce a spec's size), that's recorded as a finding here — filed to the CER backlog if it's a
   fix for later, or fixed inline if small and directly caused by this phase's own work.
4. This story's own Evidence section is the closing record for the phase: what got dogfooded, what
   held up, what didn't.

## Instructions

1. This story necessarily runs at or near the very end of Phase 118's build sequence, after every
   mechanism it's checking is already live — do not attempt to build it earlier.
2. Do not manufacture a synthetic test story just to exercise the mechanism — use a real, needed
   piece of work (the next story this project actually builds) so the dogfood result reflects
   genuine use, not a staged demo.
3. Be honest in the Evidence section about anything that didn't work as designed — the entire
   point of dogfooding before "more definitively driving projects via narrative" (the operator's
   own framing) is to catch friction here, on flex itself, before it reaches downstream projects.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green. This story's real acceptance criterion is the Evidence section, not a test
assertion — a methodology story checking whether prior mechanism stories actually work in practice
is not itself a code change with its own test surface.

## Out of scope

- Fixing anything found to not work, beyond a small inline fix — a real problem found here should
  be filed as its own story/CER, not absorbed silently into what was meant to be a closing
  verification step.

## Evidence

**What was dogfooded.** A real `spec-writer` agent and a real `intent-reviewer` agent (both
genuinely dispatched, not simulated by a single worker) ran against `docs/stories/INFRA/INFRA-363.md`
(Phase 119's first story, drafted independently of this phase, concerning the spec-writer's own
procedure — it existed as real, needed work before this dogfood exercise touched it).

**Spec-writer run (Ensures 1).** The agent judged `narrative_roles: [SPEC-WRITER]` genuinely
applied (INFRA-363's subject — freezing the exemplar — is verbatim the SPEC-WRITER narrative's own
Open-gaps item 1), added the field, read `SPEC-WRITER-000-ideology.md` as its bounded sixth input,
and backfilled `stories: [INFRA-363]` into that narrative per Step 4c. This is the first story in
the repo to ever carry a non-empty `narrative_roles:`.

**Intent-reviewer run (Ensures 2).** A real narrative-alignment check ran against the resulting
diff. **Verdict: FAIL**, not ALIGNED — recorded honestly, not smoothed over. The blocking finding:
the cited narrative's `## Narrative` section states an attempt-count statistic ("largest specs run
~50% higher") that INFRA-363's own re-measurement disproves by ~5x, and INFRA-363's scope corrects
that claim only in `INFRA-357.md`, not in the narrative that also states it — leaving the
authoritative role-ideology doc citing evidence its own citing story just debunked. A secondary LOW
finding: one of INFRA-363's own Ensures items includes a judgment-call clause, a minor instance of
the same "must be mechanically verifiable" gap the narrative flags as a structural risk.

**What held up.** The core propagation/citation/backfill mechanism (INFRA-351/352/355) worked
exactly as designed — the spec-writer made a real, non-obvious judgment call correctly and the
backfill landed cleanly.

**What didn't hold up (Ensures 3).**
1. A worker resolving the hardcoded absolute path to `flex-harness`'s copy of
   `spec-writer/procedure.md` (per INFRA-304's established rationale for that path) got a stale,
   pre-INFRA-355/357 version with no narrative step at all — a release-channel staleness risk
   with real correctness consequences mid-phase, not something this story can fix. **Filed as
   CER-160.**
2. INFRA-355 shipped a self-contradiction: `story_new.py`'s comment says the spec-writer may decide
   `narrative_roles:`, but the procedure's Step 4 frontmatter-preservation rule had no carve-out for
   it, and the narrative's own `## Never` line ("edits any file except the single story file")
   didn't account for the Step 4c backfill it also documents. **Fixed inline** (small, and directly
   caused by this phase's own INFRA-355 work): `procedure.md`'s Step 4 now names the
   `narrative_roles:` exception explicitly, and `SPEC-WRITER-000-ideology.md`'s `## Always true`
   (five → six inputs) and `## Never` (backfill carve-out) lines are corrected; the two now-closed
   `## Open gaps` items (narrative input, brevity ceiling) are marked resolved with pointers to
   INFRA-355/357. Also filed the broader procedure/narrative contract gap as **CER-161** for anyone
   auditing other role narratives for the same drift shape.
3. The now-debunked attempt-count statistic and the unreachable 14-36-line exemplar baseline are
   **not** fixed here — correcting the statistic well means touching INFRA-363's own scope, a
   different (and concurrently-drafted) story's call to make, not this closing story's. **Filed as
   CER-162.**

**Honest bottom line.** The mechanism works on real content, but this run surfaced genuine friction
in exactly the way dogfooding is supposed to: a stale-tooling risk, a shipped contract
inconsistency (now fixed), and a live case of a narrative's own evidence going stale the moment the
work it inspired disproved it. Nothing here was staged — the FAIL verdict is the real, unforced
result of running the real mechanism on real work.

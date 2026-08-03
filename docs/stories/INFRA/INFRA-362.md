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

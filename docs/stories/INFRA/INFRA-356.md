---
id: INFRA-356
rail: INFRA
title: Add narrative-alignment checking to intent-reviewer (post-build and pre-build modes)
status: complete
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/intent-reviewer/procedure.md
touches:
  - docs/build-loop-cold-eyes-review-20260801.md
  - docs/cer/backlog.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-355 gives the spec-writer a bounded, deterministic way to know which narrative(s) a story
cites (`narrative_roles:` frontmatter). This story gives the intent-reviewer — the only role with
a phase-wide lens, per its own narrative (`docs/narratives/INTENT-REVIEWER/INTENT-REVIEWER-000-ideology.md`)
— the matching *check*: does the phase's actual built work honor the narratives its stories cited,
not just its own stated Ensures/Instructions. This is squarely within the intent-reviewer's
existing input contract (DP1.3 already reads `docs/ideology.md`; narrative files are the same class
of input, read-only, bounded by citation) — **this story does not extend the intent-reviewer to
watch a live build** (that would require reading "prior-attempt transcripts"/"accumulated
orchestrator state," which its contract explicitly forbids and this era deliberately decided not to
attempt — see INFRA-358/359/360 for the actual mid-build mechanism, a *separate* concurrent
shadow-reviewer role, not an extension of this one).

## Requires

- INFRA-351 through INFRA-355 must land first (narrative files must exist and be citable via
  `narrative_roles:` before this story has anything to check against).

## Ensures

1. Post-build mode: for each story in the phase whose `narrative_roles:` is non-empty, the
   intent-reviewer reads the cited narrative file(s) and compares the diff against that narrative's
   `Always true`/`Never` sections — same weight as an ideology-drift check (a violation is a
   finding, not a stylistic note), per the narrative README's own stated rule ("treat a divergence
   like this with the same weight `docs/build-loop-cold-eyes-review-20260801.md` gives a
   CRITICAL/HIGH finding").
2. Pre-build mode (INFRA-315): the same comparison runs against the *planned* Ensures/Instructions
   for each cited story, before any code exists — matching the existing pre-build pattern's "ask
   the same questions... of the plan itself."
3. A narrative-alignment finding gets its own tag in the `REVIEW-RESULT` output (distinct from an
   ideology-drift finding), so a downstream consumer (or this project's own CER backlog) can
   distinguish "narrative gap" from "ideology gap" from "design pivot" — the same three-way
   distinction Repo-A's own narrative README describes wanting (`Gap type: technical/narrative/both`)
   even though Repo-A itself never implemented it.
4. A story with empty/absent `narrative_roles:` is not checked against any narrative — no false
   positive from a story that never claimed to concern a role narrative.
5. Full `tests/pairmode/` suite green.

## Instructions

1. Read `docs/narratives/README.md`'s "Cross-cutting commitments" section — it already states the
   enforcement posture ("treat with the same weight... a CRITICAL/HIGH finding") this story is
   implementing; don't re-derive that decision from scratch.
2. Add a new step to the intent-reviewer's procedure (both the post-build "Starting an intent
   review" sequence and the "Pre-build mode" section) that collects the cited narrative(s) across
   all stories in the phase (dedup — multiple stories may cite the same role) and reads each
   exactly once.
3. Add the narrative/ideology/design-pivot three-way distinction to the `REVIEW-RESULT` findings
   shape.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green. (No dedicated `test_intent_reviewer.py` exists today — the intent-reviewer is a
procedure skill, not a CLI function, so verification here is a live dogfooded run per INFRA-362,
not a unit test; note this explicitly rather than inventing a test file that doesn't match how this
role is actually exercised elsewhere in the suite.)

## Out of scope

- Any mid-build or concurrent narrative check — that's INFRA-358/359/360's shadow-reviewer
  mechanism, a distinct role, not an extension of intent-reviewer's existing bounded-input,
  phase-level contract.

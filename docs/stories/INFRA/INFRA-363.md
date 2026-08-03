---
id: INFRA-363
rail: INFRA
title: Freeze the spec-writer's format exemplar; correct INFRA-357's attempt-count claim
status: draft
phase: "119"
story_class: methodology
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/spec-writer/procedure.md
touches:
  - docs/stories/INFRA/INFRA-357.md
  - docs/architecture.md
narrative_roles: [SPEC-WRITER]
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-357 (Phase 118, draft) already adds a brevity counter-instruction and a proportionality
self-check to the spec-writer procedure. This story is a separate, independent finding from a
second-opinion analysis (session 2026-08-03, requested outside the Devin/Windsurf review chain)
that reaches the same root cause by a different route and finds one thing INFRA-357 does not fix.

The spec-writer procedure's bounded input 4 is "one **recent** complete story as format exemplar."
Whatever brevity instruction accompanies that input, the exemplar itself keeps moving — today's
longest spec becomes tomorrow's format reference regardless of what the prose around it says.
INFRA-357's own Forbidden-proxy note makes exactly this argument about the precision instruction
("prose alone did not stop the exemplar-imitation spiral"); the same logic applies to leaving the
exemplar-selection input unfrozen, and INFRA-357 does not touch that input.

Separately, the analysis re-measured `.companion/effort.db` and could not reproduce INFRA-357's
Context claim that "builder attempt counts on the largest specs run roughly 50% higher than on the
earliest ones." Direct measurement (flex, n=90 stories, quartiles by spec line count): 1.32
attempts/story (shortest quartile) vs. 1.45 (longest quartile) — about 10%, not 50%. The actual
cost channel is duration per attempt, not attempt count: shortest-quartile specs (avg 99 lines)
took 4.0 min total build time touching 4.3 files; longest-quartile specs (avg 724 lines) took 29.5
min touching 9.9 files — 7.4x the time for 2.3x the file surface. This matters because a
remediation aimed at reducing retries would target the wrong mechanism; the cost is in reading and
reconciling one long attempt, not in re-attempting.

Independently, the project's own historical convention for a fixed reference point already
existed and was lost: an early hand-authored preamble (`docs/phases/preamble.md`-lineage doc,
predating this project's current phase-doc convention) stated "a story is right-sized when its
acceptance criterion fits in one sentence," paired with a concrete one-sentence-acceptance example
story. That rule is not currently stated anywhere in `skills/pairmode/skills/spec-writer/procedure.md`
or `docs/architecture.md` § Phase-authoring convention.

## Requires

None — independent of INFRA-357 and of the rest of Phase 118; can build before, after, or
alongside INFRA-357, in any order the operator chooses.

## Ensures

1. The spec-writer procedure's bounded input 4 no longer reads "one recent complete story as
   format exemplar." It instead points at a single frozen exemplar file checked into this
   project's own tree (e.g. `docs/stories/EXEMPLAR-000.md` or an equivalent fixed path — pick one
   location and state it explicitly in the procedure text). The frozen file does not rotate with
   "recency"; changing which story serves as the exemplar is itself a deliberate, reviewable edit
   to that one file, not an automatic consequence of what shipped most recently.
2. The frozen exemplar file's content demonstrates the one-sentence-acceptance-criterion rule
   inherited from the project's own early-preamble lineage: a bounded, real story (or a
   purpose-built exemplar modeled tightly on one) whose acceptance criterion fits in one sentence,
   with Ensures/Instructions scoped to only what a builder genuinely could not infer.
3. `docs/architecture.md` § Phase-authoring convention (or the nearest equivalent section) states
   the one-sentence-acceptance rule explicitly, so it is discoverable outside the procedure file
   too — this is the same rule INFRA-363's Context found stated once, in a legacy doc, and nowhere
   else.
4. INFRA-357's Context section (`docs/stories/INFRA/INFRA-357.md`) is corrected in place: replace
   the "~50% higher attempt counts" claim with the measured duration-per-attempt effect from this
   story's Context (7.4x time for 2.3x file-surface complexity, ~10% attempt-count difference).
   Do not delete or rewrite INFRA-357's own Ensures/Instructions — this is a factual correction to
   its Context only, and only if INFRA-357 has not yet been built when this story builds (if
   INFRA-357 has already shipped, correct its Context anyway; the historical record should be
   accurate regardless of build order).

**Forbidden proxy:** a brevity or proportionality instruction (INFRA-357's fix) without a frozen
exemplar (this story's fix) is not sufficient on its own — the exemplar-selection mechanism is a
separate failure mode from the drafting-instruction wording, and fixing only the wording leaves
the self-reinforcing exemplar-rotation spiral intact.

## Instructions

1. Read `skills/pairmode/skills/spec-writer/procedure.md` in full, including whatever INFRA-357
   has already changed in it (check its build status first), before editing — this is a second,
   independent surgical edit to the same file, not a rewrite.
2. Create the frozen exemplar file at a single, explicitly-named path. If an existing shipped
   story in this project's own history already satisfies the one-sentence-acceptance bar cleanly,
   prefer pointing at (or lightly adapting) that real story over inventing a synthetic one — a
   frozen exemplar drawn from this project's own proven work carries more authority than a
   fabricated example.
3. State plainly in the procedure text why the exemplar is frozen rather than rotating (cite this
   story's Context: a moving exemplar is self-reinforcing regardless of surrounding prose), so a
   future editor understands the constraint is deliberate before "helpfully" pointing it back at
   whatever shipped most recently.
4. Make the INFRA-357 Context correction as a small, clearly-marked edit (an appended correction
   note is acceptable, matching the pattern already used elsewhere in this project's stories for
   post-hoc corrections — e.g. INFRA-025's frontmatter-correction note — rather than silently
   rewriting the original claim out of the historical record).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green. (Procedure-doc and story-doc changes; verification is dogfooded against real
subsequent spec-writer runs, same as INFRA-357 — note this explicitly rather than inventing a unit
test that doesn't match how a procedure-skill change is actually exercised.)

## Out of scope

- Any automated enforcement mechanism (CI gate, script check) tying spec-writer output to the
  frozen exemplar's shape — same reasoning as INFRA-357's Out-of-scope: this is a procedure/
  judgment fix, and a hard mechanical gate is a follow-up finding if dogfooding shows the frozen
  exemplar alone isn't enough, not something to build speculatively here.
- Propagating the frozen-exemplar pattern to sibling repos (cora, anchor, forqsite, radar, etc.)
  that use the same pairmode methodology but are separate repos with their own tooling — each
  would need its own story in its own repo; this story is scoped to flex only.
- Restoring the one-sentence-acceptance rule's original source doc (the legacy preamble lineage)
  itself — this story only carries the rule forward into flex's current procedure/architecture
  docs, it does not audit or restore the original document.

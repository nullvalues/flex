---
id: INFRA-357
rail: INFRA
title: Reduce spec-writer over-specification: cap exemplar imitation, add brevity counter-instruction
status: draft
phase: "118"
story_class: methodology
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/spec-writer/procedure.md
touches:
  - docs/build-loop-cold-eyes-review-20260801.md
  - docs/phases/phase-118.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

An external review (Devin/Windsurf) of this project's own work through Phase 116 found: as story
specs grew in size, build-attempt counts rose, but quality did not — CERs kept accumulating.
Conclusion: over-constraining with specifications that go unchecked until the end of the build,
sometimes not until loop-breaker surfaces a hallucination. This project's own story-file history
confirms it directly: early specs (stories 0-119) averaged 14-36 lines; specs from stories 260-319
averaged 400-550+, peaking at 1317 (INFRA-310); builder attempt counts on the largest specs run
roughly 50% higher than on the earliest ones (measured via `.companion/effort.db`, session
2026-08-01).

Root cause candidate, found directly in the spec-writer's own procedure
(`skills/pairmode/skills/spec-writer/procedure.md` § Step 2/4): one of its five bounded inputs is
"one recent complete story as a format exemplar," and its drafting rule says Instructions "must be
precise enough that a fresh-context builder agent... can implement the story without ambiguity" —
with no counter-instruction anywhere toward proportion. This is a structurally self-reinforcing
spiral: today's long spec becomes tomorrow's exemplar, and nothing measures whether the added
length actually reduced ambiguity or just added restatement.

## Requires

None — independent of the other Phase 118 stories; can build any time.

## Ensures

1. The exemplar-selection rule (Step 2, item 4 of the spec-writer procedure) no longer picks
   uncritically from "one recent complete story" — it excludes exemplars whose length is a clear
   outlier relative to this project's own healthy historical range (define the range explicitly in
   the procedure text, e.g. citing the pre-inflation baseline this story's Context measured, rather
   than leaving "recent complete story" able to pick a 1000+ line outlier again).
2. The procedure's drafting rules gain an explicit brevity counter-instruction, stated with the
   same weight as the existing precision instruction — e.g. "Ensures/Instructions should be as
   short as achieves unambiguous, independently-verifiable acceptance. Trust the builder's ordinary
   engineering judgment on well-understood mechanics; spell out only what is genuinely ambiguous or
   load-bearing. Length is not evidence of rigor — a spec whose every line earns its place is."
3. A new proportionality self-check, run by the spec-writer after drafting: compare the draft's
   rough size against the story's own complexity signals (`primary_files`/`touches` count,
   `story_class`). If drastically disproportionate (define a concrete threshold — e.g. a story with
   one `primary_files` entry and `story_class: doc`/`lesson` drafted well past this project's
   measured healthy range), either revise down or add a one-line justification directly in the
   spec, mirroring the existing phase-authoring convention's own rule ("if scope isn't comparable
   to recent phases, is the reason explicit?") applied at the story level instead of the phase
   level.
4. This story's own resulting diff to the procedure file is itself proportionate — do not let a
   story about reducing spec bloat itself become a bloated spec or a bloated procedure edit.

**Forbidden proxy:** a brevity instruction that exists in prose but has no proportionality
self-check paired with it — prose alone did not stop the exemplar-imitation spiral in the first
place (the existing precision instruction is exactly this kind of unweighted prose, and it visibly
failed to self-correct over sixteen phases of the project's own history).

## Instructions

1. Read the spec-writer procedure's current Step 2/4 in full before editing — this is a surgical
   edit to existing rules, not a rewrite.
2. State the healthy historical range concretely in the procedure text (cite the actual measured
   numbers from this story's Context, or re-measure at build time if the historical distribution
   has shifted) rather than a vague "keep it short."
3. Write the proportionality self-check as an explicit, checkable step the spec-writer runs on its
   own draft — not an aspiration.
4. Cross-reference `docs/build-loop-cold-eyes-review-20260801.md` and this phase's own Goal from
   this story's Context, so a future reader of the procedure file understands *why* this rule
   exists, not just what it says.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green. (Procedure-doc-only change; verification is dogfooded against real subsequent
spec-writer runs per INFRA-362, not a unit test — note this explicitly rather than inventing a test
that doesn't match how a procedure-skill change is actually exercised.)

## Out of scope

- Any automated line-count enforcement mechanism (a hard CI gate on spec length) — this story is a
  procedure/judgment fix, not a mechanical cap; a hard cap risks the opposite failure (truncating a
  genuinely complex story's real requirements). If dogfooding (INFRA-362) shows prose alone isn't
  enough, a harder mechanism is a follow-up finding, not something to build speculatively here.

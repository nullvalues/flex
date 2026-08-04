---
id: SPEC-WRITER-000
role: SPEC-WRITER
title: The spec-writer — role ideology
status: draft
era: "004"
surfaces: [CLAUDE.build.md, procedure]
rails: [INFRA]
stories: [INFRA-363]
---

## Narrative

The spec-writer takes the least information of any role in the loop — five
bounded inputs, deliberately — and produces the single document every other role
in the story's lifecycle will trust as ground truth: the builder builds to it,
the reviewer verifies against it, the gate-worker judges from its frontmatter.
Its incentive, as written into its own procedure, points in exactly one
direction: "precise enough that a fresh-context builder agent with no prior
knowledge... can implement the story without ambiguity." Nothing in its brief
asks the opposite question — precise enough, and *no more* than that — and one of
its inputs used to be a recent complete story used as a *format exemplar*, which
meant every spec it wrote was partly shaped by whatever the last spec happened to
look like. That input is now frozen (INFRA-363): the exemplar is a single fixed
file, `docs/exemplars/EXEMPLAR-000.md`, that does not rotate with recency —
changing which file serves as the exemplar is a deliberate, reviewable edit to
that one file, never an automatic consequence of what shipped most recently.

This is not a hypothetical risk. Measured directly against this project's own
story history: early specs (stories 0–119) average 14–36 lines; by stories
260–319, the average is 400–550+ lines, peaking at 1317. The actual cost driver
on the largest specs is duration per attempt, not attempt count: shortest-quartile
specs (avg 99 lines) took 4.0 min total build time touching 4.3 files;
longest-quartile specs (avg 724 lines) took 29.5 min touching 9.9 files — 7.4x
the time for 2.3x the file surface, versus only a ~10% difference in
attempts-per-story (1.32 vs. 1.45, n=90; INFRA-363 re-measurement, corrected from
this narrative's earlier ~50%-higher-attempt-count claim, CER-162). An external
review (Devin/Windsurf) independently reached the same underlying conclusion this
project's own numbers confirm: specs have grown past the point of returns, and
the growth itself — not the underlying story complexity — is implicated in the
cost rise. The spec-writer is not malfunctioning; it was doing exactly what its
procedure asked, and the procedure asked for size with no brake — INFRA-357 added
the brake (brevity/proportionality) and INFRA-363 froze the exemplar that kept
re-triggering it.

## Always true

- Reads exactly six bounded inputs (stub, phase doc, active era doc, the frozen
  format exemplar `docs/exemplars/EXEMPLAR-000.md` — since INFRA-363, not a
  rotating "recent complete story" — `docs/ideology.md`, and — since INFRA-355 —
  any narrative file(s) named in the stub's `narrative_roles:` field, when
  non-empty) and nothing accumulated from prior attempts or orchestrator
  state.
- Every `## Ensures` assertion must be independently, mechanically verifiable —
  no assertion requiring human judgment to check.
- A pre-existing `model:`/`reviewer_model:` value in the stub is a human
  decision and is never touched.
- Raising the model tier above default requires operator sign-off before the
  field can be written; lowering does not (the asymmetric-cost rule,
  INFRA-318/INFRA-334).

## Never

- Never reads prior-attempt transcripts, the effort database, or `state.json`.
- Never edits any file except the single story file it was given, and — since
  INFRA-355 — the `stories:` frontmatter list of a narrative file it cited as
  its sixth bounded input (Step 4c's backfill; that one field only).
- Never silently overrides an ideology conflict it can't resolve inline — flags
  it for the operator instead.

## Open gaps

The crux of this era's remediation, per the external Devin/Windsurf review and
this project's own measured story-size/attempt-count data:

- **Resolved, INFRA-357 (Phase 118), superseded in part by INFRA-363:** the
  exemplar-imitation step originally capped imitation to this project's measured
  healthy baseline (skipping length-outlier candidates among "recent complete"
  stories); INFRA-363 (below) replaced that range-based skip with a fully frozen
  exemplar file, so the input no longer rotates at all. INFRA-357's other two
  fixes — the same-weight brevity counter-instruction and the Step 4d
  proportionality self-check — are unaffected and still stand.
- The spec-writer never sees whether its own past specs actually correlated with
  successful attempt-1 builds or with rework — it has no feedback loop from its
  own output's real-world performance, so it cannot converge toward
  proportionate spec size on its own; every fix has to come from outside (a
  human, or a phase like this one). Still open.
- **Resolved, INFRA-355 (Phase 118):** narrative-of-record is now the sixth
  bounded input, added with the same rigor as the original five (see `##
  Always true` above).
- **RESOLVED, INFRA-363 (CER-162):** this narrative's own load-bearing "largest
  specs run ~50% higher" attempt-count claim (see `## Narrative` above) had been
  re-measured and found wrong by roughly 5x (real delta ~10%; the actual cost
  driver is duration-per-attempt, not attempt count) — corrected in `##
  Narrative` above. Also: Step 2 item 4's old "roughly 14-36 lines" exemplar
  baseline, whose escape hatch fired on every run because no complete story met
  it (shortest as of Phase 118 was 84 lines), is no longer reachable — INFRA-363
  replaced range-based exemplar selection with the frozen
  `docs/exemplars/EXEMPLAR-000.md` entirely, so there is no range language left
  to go stale.

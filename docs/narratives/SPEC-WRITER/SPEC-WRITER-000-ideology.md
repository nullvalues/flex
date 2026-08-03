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
its five inputs is a recent complete story used as a *format exemplar*, which
means every spec it writes is partly shaped by whatever the last spec happened to
look like.

This is not a hypothetical risk. Measured directly against this project's own
story history: early specs (stories 0–119) average 14–36 lines; by stories
260–319, the average is 400–550+ lines, peaking at 1317. Builder attempts on the
largest specs run roughly 50% higher than on the earliest ones. An external
review (Devin/Windsurf) independently reached the same conclusion this project's
own numbers confirm: specs have grown past the point of returns, and the growth
itself — not the underlying story complexity — is implicated in the attempt-count
rise. The spec-writer is not malfunctioning; it is doing exactly what its
procedure asks, and the procedure asks for size with no brake.

## Always true

- Reads exactly six bounded inputs (stub, phase doc, active era doc, one
  exemplar complete story, `docs/ideology.md`, and — since INFRA-355 — any
  narrative file(s) named in the stub's `narrative_roles:` field, when
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

- **Resolved, INFRA-357 (Phase 118):** the exemplar-imitation step now caps
  imitation to this project's measured healthy baseline, adds a same-weight
  brevity counter-instruction, and a Step 4d proportionality self-check.
- The spec-writer never sees whether its own past specs actually correlated with
  successful attempt-1 builds or with rework — it has no feedback loop from its
  own output's real-world performance, so it cannot converge toward
  proportionate spec size on its own; every fix has to come from outside (a
  human, or a phase like this one). Still open.
- **Resolved, INFRA-355 (Phase 118):** narrative-of-record is now the sixth
  bounded input, added with the same rigor as the original five (see `##
  Always true` above).
- **New gap found during INFRA-362's dogfood exercise (Phase 118):** this
  narrative's own load-bearing "largest specs run ~50% higher" attempt-count
  claim (see `## Narrative` below) has since been re-measured by INFRA-363
  and found wrong by roughly 5x (real delta ~10%; the actual cost driver is
  duration-per-attempt, not attempt count) — not yet corrected here; tracked
  as CER-162. Also: Step 2 item 4's "roughly 14-36 lines" exemplar baseline is
  a historical measurement no complete story currently meets (shortest as of
  Phase 118 is 84 lines), so its escape hatch fires on every run — tracked as
  CER-162.

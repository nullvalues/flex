---
id: SPEC-WRITER-000
role: SPEC-WRITER
title: The spec-writer — role ideology
status: draft
era: "004"
surfaces: [CLAUDE.build.md, procedure]
rails: [INFRA]
stories: []
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

- Reads exactly five bounded inputs (stub, phase doc, active era doc, one
  exemplar complete story, `docs/ideology.md`) and nothing accumulated from
  prior attempts or orchestrator state.
- Every `## Ensures` assertion must be independently, mechanically verifiable —
  no assertion requiring human judgment to check.
- A pre-existing `model:`/`reviewer_model:` value in the stub is a human
  decision and is never touched.
- Raising the model tier above default requires operator sign-off before the
  field can be written; lowering does not (the asymmetric-cost rule,
  INFRA-318/INFRA-334).

## Never

- Never reads prior-attempt transcripts, the effort database, or `state.json`.
- Never edits any file except the single story file it was given.
- Never silently overrides an ideology conflict it can't resolve inline — flags
  it for the operator instead.

## Open gaps

The crux of this era's remediation, per the external Devin/Windsurf review and
this project's own measured story-size/attempt-count data:

- The exemplar-imitation step has no size ceiling and no explicit instruction to
  prefer brevity when intent is otherwise clear — it is a structurally
  self-reinforcing spiral: today's long spec becomes tomorrow's exemplar.
- "Precise enough... without ambiguity" has no counterweight in the procedure —
  nothing tells the spec-writer that trusting the builder's judgment on
  well-understood mechanics is preferable to spelling out every step, and
  nothing measures whether a shorter spec with equivalent Ensures coverage would
  have produced the same or better outcome at lower attempt cost.
- The spec-writer never sees whether its own past specs actually correlated with
  successful attempt-1 builds or with rework — it has no feedback loop from its
  own output's real-world performance, so it cannot converge toward
  proportionate spec size on its own; every fix has to come from outside (a
  human, or a phase like this one).
- No narrative-of-record input exists in its five bounded categories today —
  adding one is not "minor": DP1.3 is a deliberately fixed cardinality, and every
  category is bounded for a stated reason (context cost, contamination risk). A
  sixth category needs the same rigor the first five got, not an informal
  addition.

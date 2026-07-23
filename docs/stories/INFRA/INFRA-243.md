---
id: INFRA-243
rail: INFRA
title: Phase-authoring convention and tooling for single-purpose, bounded, reproducible phases
status: planned
phase: "98"
story_class: methodology
auth_gated: false
schema_introduces: false
primary_files:
  - docs/architecture.md
touches:
  - skills/pairmode/templates/phase.md.j2
  - skills/pairmode/skills/spec-writer/procedure.md
  - docs/phases/index.md
---

## Context

Audit item A2 confirmed no automation exists in 0.3 for creating a new phase or
seeding story rows into one: `spec-writer/procedure.md:142,203` explicitly says
"Never touch the phase doc" — it only elaborates a stub row already present in an
existing phase table. There is no resolver action, no CLI command for phase creation.
This session's phase-97/phase-98 authoring (including this very phase) was done by
hand, directly — the only path that currently exists.

Operator decision: manual phase instantiation (operator feeds the objective) is fine
and stays the intended workflow — this is not a request to rebuild 0.2's "spec next
phase" mode. What's actually missing is a **convention**: a documented, checkable
standard for what makes a phase well-formed, so manual authoring stays consistent
across operators and sessions rather than drifting. Three explicit criteria, as
stated by the operator:

1. **Single purpose.** A phase is bounded by one idea/objective — not a grab-bag of
   unrelated fixes. (This story's own sibling, phase-98, exists specifically because
   mixing this regression-remediation batch into phase-97's fold-mechanics table would
   have violated this criterion.)
2. **Bounded, comparable complexity.** Phases should be roughly similar in total
   scope/effort to each other. When a single idea is too large for one phase, the
   break points between the resulting phases should be **intentional seams** —
   natural stopping points where the software is in a coherent, buildable state — not
   arbitrary chunking by story count.
3. **Reproducible from artifacts.** A phase's committed artifacts (the phase doc, its
   stories' spec files, whatever `docs/architecture.md`/`docs/ideology.md` sections it
   references) should let another agent or a human reader — with no access to the
   conversation that produced them — understand and continue the work. This is close
   to (but not currently checked against) the project's existing "Read before any
   task" three-document cold-start claim in `CLAUDE.md`.

No existing phase-doc template or authoring guidance in this repo currently states or
checks any of these three criteria explicitly.

## Ensures

- `docs/architecture.md` gains a documented phase-authoring convention section stating
  the three criteria above, in the operator's terms, as the standard new phases are
  expected to meet — this is the primary deliverable; automation is secondary and
  bounded per Instructions below.
- `skills/pairmode/templates/phase.md.j2` (the phase-doc template used when hand- or
  spec-writer-authoring a phase) gains a short header comment or Goal-section prompt
  reminding the author to state the phase's single purpose explicitly (mirroring how
  phase-98's own Goal section does this) — a lightweight nudge, not enforcement
  machinery.
- A **phase-authoring checklist** (a short, explicit list — analogous to the existing
  CP-N Cold-eyes checklist used at phase *completion*, but applied at phase
  *authoring* time) is added to `docs/architecture.md` or a dedicated
  `docs/phase-authoring.md`, covering: does this phase state one purpose; is its scope
  comparable to recent phases (rough story count / primary_files count as a proxy, not
  a hard metric); would an agent with no conversation history, given only this phase's
  doc + its stories, be able to start building it correctly.
- This story's own phase (98) and its sibling (97) are checked against the new
  checklist retroactively as a worked example in the commit message or a short note in
  `docs/architecture.md` — proving the convention is usable, not just declared.
- No resolver/CLI automation for phase creation is added — explicitly out of scope,
  matching the operator's decision that manual instantiation is the intended workflow.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains) — this is a
  documentation-and-template story; the test run confirms no template rendering
  regression.

## Instructions

1. Draft the phase-authoring convention section for `docs/architecture.md`, in the
   operator's own three-criteria framing from Context.
2. Add the lightweight Goal-section prompt to `phase.md.j2`.
3. Write the phase-authoring checklist (distinct from and complementary to the
   existing phase-*completion* Cold-eyes checklist).
4. Walk phase-97 and phase-98 against the new checklist as a worked example; note any
   gap found (e.g., if phase-97's scope is judged too large relative to phase-98,
   that's useful signal for the convention's calibration, not necessarily something to
   fix retroactively).
5. Run `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` to confirm no
   template test regresses from the `phase.md.j2` change.

## Out of scope

- Any resolver action, CLI command, or spec-writer capability for creating a new phase
  or seeding story rows — explicitly not wanted per the operator's decision; manual
  authoring is the intended workflow, this story only makes it consistent.
- Retroactively splitting or resizing any existing phase to fit the new convention.
- Enforcing the checklist mechanically (a hook, a CI check) — this story establishes
  the convention as documented practice; mechanical enforcement is a candidate for a
  future story if drift is observed, not built preemptively here.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure (template
rendering tests confirm `phase.md.j2`'s change doesn't break existing phase-doc
generation).

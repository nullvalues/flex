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
  - skills/pairmode/templates/docs/phases/phase.md.j2
touches:
  - skills/pairmode/scripts/phase_new.py
  - skills/pairmode/skills/spec-writer/procedure.md
  - docs/phases/index.md
  - tests/pairmode/test_phase_new.py
---

## Context

**Amended after adversarial review — the original premise here was factually
wrong and is corrected below; do not build against the original Context text.**

The original audit (item A2) claimed no automation exists in 0.3 for creating a new
phase, citing `spec-writer/procedure.md:142,203`'s "Never touch the phase doc" as
evidence. That citation is accurate but the conclusion drawn from it was not:
`skills/pairmode/scripts/phase_new.py` exists, is wired to `/flex:pairmode phase-new`,
renders a phase doc from `skills/pairmode/templates/docs/phases/phase.md.j2`, and
updates `docs/phases/index.md`. Spec-writer correctly stays out of phase authoring
(it only elaborates an existing stub story) — that's a *different* tool's job, and
that tool already exists. This session's phase-97/phase-98 authoring was done by hand
directly not because no tooling exists, but because it wasn't invoked — a process
gap, not a tooling gap.

So this story is **not** "build phase-creation tooling." It's: the existing
`phase_new.py`/`phase.md.j2` pair doesn't currently prompt for or check any of the
three criteria below, so a phase authored through it (or by hand, as phase-97/98 were)
can still drift from the convention. Operator decision: manual phase instantiation
(operator feeds the objective via `phase-new`) is fine and stays the intended
workflow — this was never a request to rebuild 0.2's fuller "spec next phase" mode
(era-doc scanning, Plan-subagent drafting, confirm gates). What's actually needed is
a **convention**, made self-distributing by living inside the tool that already
renders every phase doc: a documented, checkable standard for what makes a phase
well-formed. Three explicit criteria, as stated by the operator:

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
  expected to meet.
- `skills/pairmode/templates/docs/phases/phase.md.j2` — the actual template
  `phase_new.py` renders — gains a short header comment or Goal-section prompt
  reminding the author to state the phase's single purpose explicitly (mirroring how
  phase-98's own Goal section does this), so the nudge reaches every phase authored
  through the existing tool without requiring anyone to remember to open
  `architecture.md` first.
- A **phase-authoring checklist** (a short, explicit list — analogous to the existing
  CP-N Cold-eyes checklist used at phase *completion*, but applied at phase
  *authoring* time) is added to `docs/architecture.md` or a dedicated
  `docs/phase-authoring.md`, covering: does this phase state one purpose; is its scope
  comparable to recent phases (rough story count / primary_files count as a proxy, not
  a hard metric); would an agent with no conversation history, given only this phase's
  doc + its stories, be able to start building it correctly. Consider whether
  `phase_new.py` can print this checklist to the operator at creation time (a CLI
  echo, not new gating logic) — cheap, and keeps the nudge inside the tool rather than
  purely in docs.
- This story's own phase (98) and its sibling (97) are checked against the new
  checklist retroactively as a worked example in the commit message or a short note in
  `docs/architecture.md` — proving the convention is usable, not just declared.
- No new resolver action or gating logic is added — `phase_new.py` already exists and
  already does the mechanical work (render + index update); this story only makes the
  convention visible inside it, matching the operator's decision that phase
  instantiation stays manual/operator-driven, not newly automated.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains).

## Instructions

1. Draft the phase-authoring convention section for `docs/architecture.md`, in the
   operator's own three-criteria framing from Context.
2. Add the lightweight Goal-section prompt to
   `skills/pairmode/templates/docs/phases/phase.md.j2`.
3. Write the phase-authoring checklist (distinct from and complementary to the
   existing phase-*completion* Cold-eyes checklist); decide whether `phase_new.py`
   echoes it to the operator on creation.
4. Walk phase-97 and phase-98 against the new checklist as a worked example; note any
   gap found (e.g., if phase-97's scope is judged too large relative to phase-98,
   that's useful signal for the convention's calibration, not necessarily something to
   fix retroactively).
5. Run `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q`, including
   `test_phase_new.py`, to confirm no template-rendering or CLI-output regression.

## Out of scope

- Any *new* resolver action or spec-writer capability for creating a phase —
  `phase_new.py` already exists and already does this; this story only adds the
  convention prompts to it, not new orchestration logic.
- Retroactively splitting or resizing any existing phase to fit the new convention.
- Enforcing the checklist mechanically (a hook, a CI check) — this story establishes
  the convention as documented practice plus a printed reminder; mechanical
  enforcement is a candidate for a future story if drift is observed, not built
  preemptively here.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure (template
rendering tests confirm `phase.md.j2`'s change doesn't break existing phase-doc
generation).

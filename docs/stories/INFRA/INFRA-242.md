---
id: INFRA-242
rail: INFRA
title: Redesign ideology enforcement — spec-time alignment + narrow reviewer drift check
status: planned
phase: "98"
story_class: methodology
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/spec-writer/procedure.md
  - skills/pairmode/skills/reviewer/procedure.md
touches:
  - docs/architecture.md
  - tests/pairmode/test_spec_writer.py
  - tests/pairmode/test_pairmode_sync.py
---

## Context

0.2's reviewer ran a full 3-part ideology check on every story
(`/mnt/work/flex/skills/pairmode/templates/agents/reviewer.md.j2:142-171`): conviction
consistency, constraint-rationale preservation, and fingerprint awareness, re-reading
`docs/ideology.md` from scratch each time. 0.3 dropped this entirely from the per-story
reviewer (`reviewer/procedure.md` has zero mentions of "ideology") and moved it
exclusively to the checkpoint-level `intent-reviewer` (`intent-reviewer/procedure.md:76-78,
133-154`), which runs once per phase, not once per story.

Operator decision this session, explicitly correcting an assumption in the initial
audit: **this was not intended as "move the same check to a cheaper cadence."** The
actual design intent is a division of labor across the pipeline stages:

- Ideology alignment belongs primarily at **spec-authoring time** — a spec that's
  already ideology-consistent (checked against `docs/ideology.md`'s convictions,
  constraints, and fingerprints when the spec is written or elaborated) means the
  builder inherits that alignment structurally by implementing the spec faithfully.
- The reviewer's role narrows accordingly: not a full ideology re-audit of the diff
  against `docs/ideology.md` from scratch, but a **drift check** — did the
  implementation introduce anything the spec didn't call for that also happens to
  violate ideology? This is scoped to the gap between spec and diff, not the gap
  between diff and the whole of `docs/ideology.md`.
- The checkpoint-level `intent-reviewer` remains the phase-wide backstop it already
  is — unaffected by this story.

Confirmed this session: `spec-writer/procedure.md`'s input contract (§ Input contract,
`:38-46`) does not currently read `docs/ideology.md` at all, and its checklist has no
ideology-alignment step. This is the actual gap — not that the reviewer got cheaper,
but that spec-writing was never given the check in the first place when the 0.2→0.3
redesign moved ideology enforcement out of the per-story reviewer.

## Ensures

- `spec-writer/procedure.md`'s bounded input contract gains `docs/ideology.md` as a
  fifth declared input (or is folded into an existing declared input if one already
  covers it structurally).
- The spec-writer's elaboration checklist gains an ideology-alignment step: for each
  convictions/constraints/fingerprints entry in `docs/ideology.md`, does the drafted
  spec's `## Ensures`/`## Instructions` introduce anything that contradicts it? If
  `docs/ideology.md` doesn't exist, skip with a note (mirroring 0.2's skip behavior)
  rather than failing.
- If the spec-writer finds a conflict, it either resolves it within the spec draft
  (preferred, since the spec-writer already has full context on the story intent) or
  flags it for the operator rather than silently proceeding — decide and document
  which.
- `reviewer/procedure.md` gains a narrow ideology **drift** check, distinct from 0.2's
  full re-audit: compare the diff against the story's own spec (`primary_files` +
  `## Ensures`/`## Instructions`, already read for RAIL SCOPE) and flag anything in the
  diff that (a) wasn't called for by the spec and (b) independently violates a
  convictions/constraints/fingerprints entry. A diff that exactly matches its
  spec-approved scope does not need `docs/ideology.md` re-read at all — the drift
  check only activates on out-of-spec content, keeping it cheap on the common
  in-scope-and-clean path.
- `docs/architecture.md` documents this three-stage division of labor (spec-time
  alignment, reviewer drift-only, checkpoint-level phase backstop) explicitly, so it
  doesn't read as a straight "moved to checkpoint" simplification again.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains).

## Instructions

1. Add `docs/ideology.md` to spec-writer's declared input contract and an
   ideology-alignment elaboration step, modeled on 0.2's 5a/5b/5c structure but applied
   to the spec draft rather than a diff.
2. Decide and implement the spec-writer's conflict-resolution behavior (resolve inline
   vs. flag for operator).
3. Add the narrow drift-only check to `reviewer/procedure.md`, gated on
   out-of-spec diff content as described in Ensures — not a full re-audit on every
   story.
4. Update `docs/architecture.md` with the three-stage division of labor.
5. Add/update test coverage for the spec-writer's new ideology step and the
   reviewer's drift-only gating (in-scope diff skips the ideology re-read; out-of-scope
   diff triggers it).
6. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Any change to the checkpoint-level `intent-reviewer`'s existing phase-wide ideology
  drift check — it's correct and unaffected by this story.
- Re-litigating whether `docs/ideology.md` itself needs new sections — this story only
  changes *when in the pipeline* it gets consulted, not its content.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure; new
coverage proves (a) a spec draft that would contradict `docs/ideology.md` is caught at
spec-writer time, and (b) the reviewer's drift check fires only on out-of-spec diff
content, not on every story.

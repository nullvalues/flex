---
id: INFRA-239
rail: INFRA
title: Make checkpoint-tag mark the phase complete
status: planned
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - CLAUDE.build.md
  - skills/pairmode/skills/checkpoint-docs/procedure.md
  - tests/pairmode/test_record_checkpoint_step.py
  - tests/pairmode/test_next_action.py
  - docs/architecture.md
---

## Context

0.2's `CLAUDE.build.md.j2` ran `flex_build.py mark-phase-complete` as checkpoint step
7, before tagging (`:961-967`). `cmd_mark_phase_complete` still exists in `flex_build.py`
(`:641-673`) but has zero callers anywhere in this codebase: not in `CLAUDE.build.md`
(the checkpoint section is `record-checkpoint-step` + `git tag` only, `CLAUDE.build.md:43-47`),
not in the resolver, not in any checkpoint procedure skill.

Worse, `record-checkpoint-step checkpoint-tag` *resets* `state.json["checkpoint_step"]`
to `[]` (`flex_build.py:1859-1861`, RESOLVER-017, added specifically to fix a prior
silent-skip bug). Combined with the missing `mark-phase-complete` call, the sequence
after tagging is: the same phase re-resolves as active (its index-status row is still
not `complete`) → phase-completion guards pass (nothing declares it done) →
`checkpoint_step` is empty → `checkpoint-security` gets re-emitted for a phase that was
just tagged. The resolver's `done` branch (`next_action.py:947-949`) requires all four
checkpoint steps present simultaneously, which the tag-time reset structurally
prevents from ever being true again for that phase. Every phase in this repo's
`docs/phases/index.md` currently shows `complete` only because an operator or
orchestrator manually edited the status cell outside this documented loop — exactly
the same manual pattern this session used for INFRA-234/235's own status flips.

## Ensures

- Completing the `checkpoint-tag` step (either the `record-checkpoint-step
  checkpoint-tag` CLI call itself, or an adjacent deterministic step in the same
  command) also writes `complete` to the phase's status cell in `docs/phases/index.md`
  via the existing `mark_phase_complete` helper — CLI-side, not orchestrator prose.
- A resolver sequence test: after a full simulated checkpoint (all four steps
  recorded, tag applied), `next-action` on the same project state emits the next
  phase's first action (or `done` if none remain) — never `checkpoint-security` for
  the just-tagged phase again.
- `docs/architecture.md`'s state-ownership table and checkpoint-sequence description
  (§10-area content referencing `mark_phase_complete`/`checkpoint_step`) match the
  implemented flow.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains).

## Instructions

1. Wire `mark_phase_complete` into the `record-checkpoint-step checkpoint-tag` code
   path in `flex_build.py`, so completing that step and marking the phase complete
   happen atomically in one CLI call rather than requiring the orchestrator to
   remember a second command.
2. Extend `test_record_checkpoint_step.py` to assert the phase-index write happens
   alongside the `checkpoint_step` reset.
3. Add a resolver-level regression test reproducing the exact failure mode described
   in Context (tag without phase-complete → same phase re-resolves →
   `checkpoint-security` re-emitted) and asserting it's fixed.
4. Update `docs/architecture.md`.
5. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Retroactively correcting any already-manually-marked `complete` phase rows in
  `docs/phases/index.md` — those are already correct as data, just not produced by
  this mechanism; nothing to fix there.
- INFRA-236/237/238 — adjacent state-lifecycle gaps, separate root causes.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure; new
coverage proves the tag→complete→next-phase-or-done sequence, not just the
CLI call's direct effect in isolation.

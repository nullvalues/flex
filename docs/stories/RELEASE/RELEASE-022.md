---
id: RELEASE-022
rail: RELEASE
title: Pre-fold doc sweep — era status, post-flip staleness, reviewer input-scope contradiction
status: planned
phase: "HARNESS016-main"
story_class: documentation
auth_gated: false
schema_introduces: false
touches:
  - README.md
  - docs/architecture.md
  - docs/brief.md
  - skills/pairmode/skills/reviewer/procedure.md
---

## Requires

- RELEASE-019 complete (doc sweep should read the post-reconciliation tree,
  not a stale one).
- Cold-eyes review (2026-07-17) found, still present on `main` at HEAD:
  - `README.md:16` states "Era 002 — active"; `docs/phases/index.md` is well
    into Era 003 (HARNESS006's flip is complete, later HARNESS phases are
    complete or in this same phase).
  - `docs/architecture.md` retains roughly a dozen "advisory-only until the
    flip (HARNESS006)" annotations after HARNESS006 shipped, and its
    "Pairmode build loop" section (approximately lines 167-280) still
    describes the pre-flip orchestrator's step sequence rather than the
    current thin resolver loop `CLAUDE.build.md` (28 lines, post-flip)
    actually runs.
  - `skills/pairmode/skills/reviewer/procedure.md` limits the reviewer to
    four named inputs (lines ~37-47) and forbids reading beyond them
    (line ~371), but line ~63 separately instructs "Read
    `docs/architecture.md` in full" (a fifth input) and checklist item 11
    (lines ~249-257) requires sweeping every `*.md` under `docs/` — a
    worker following the stated input contract literally cannot execute the
    checklist that immediately follows it.
- `docs/brief.md` currently states nothing explicit about which enforcement
  mechanisms are advisory (acknowledgeable, e.g. the context-budget gate)
  versus hard (e.g. protected-glob edits, the CER Do Now checkpoint gate),
  or the sanctioned override for each — the "hygiene and guideline, not law"
  framing this fold-prep review was requested to check currently exists only
  in conversation, not in the repo.

## Ensures

- `README.md`'s era status matches `docs/phases/index.md`'s actual current
  era and phase state at time of this story.
- `docs/architecture.md`'s "advisory-only until the flip" annotations are
  removed or updated to reflect that HARNESS006 shipped; the "Pairmode build
  loop" section is rewritten to describe the current thin resolver loop in
  `CLAUDE.build.md`, not the pre-flip orchestrator.
- `skills/pairmode/skills/reviewer/procedure.md`'s stated input-scope
  contract (the four-input limit and its "do not read beyond" instruction)
  is reconciled with its own architecture-read instruction and doc-sweep
  checklist item — either by widening the stated contract to include what
  the checklist actually requires, or by narrowing the checklist to match
  the stated contract. Pick whichever preserves the checklist's actual
  review coverage; do not silently drop checklist item 11's doc-sweep.
- `docs/brief.md` gains a short (2-4 sentence) explicit statement of which
  pairmode enforcement mechanisms are advisory/acknowledgeable versus hard,
  and the sanctioned override path for each advisory one (e.g.
  `flex_factor` for the context ceiling, `set-context-tokens`/`/clear` for
  the context gate). This is new content, not a rewrite of brief.md's
  existing scope — keep it to the one short addition.
- No change to `CLAUDE.build.md` itself (it is already correctly thin
  post-flip; this story fixes the *description* of it elsewhere, not the
  file).

## Instructions

1. Diff `README.md`'s era claim against `docs/phases/index.md`'s actual
   state; update `README.md` to match.
2. Grep `docs/architecture.md` for "advisory-only" and "until the flip" to
   find all stale annotations; remove or update each individually rather
   than a blanket delete, since some may still carry genuine context.
   Rewrite the pre-flip build-loop description against the current
   `CLAUDE.build.md`.
3. Read `skills/pairmode/skills/reviewer/procedure.md` in full to confirm
   the exact contradiction between the stated input-scope limit and the
   architecture-read/doc-sweep instructions, then reconcile per Ensures.
4. Add the advisory-vs-hard paragraph to `docs/brief.md`, placed where it
   reads naturally alongside existing scope/intent language — do not create
   a new top-level section for a four-sentence addition.

## Tests

`TEST RUN: documentation story — no test file expected`. Verification is
manual: re-read `README.md`, `docs/architecture.md`, `docs/brief.md`, and
`skills/pairmode/skills/reviewer/procedure.md` after the edits and confirm
no remaining reference to "Era 002 — active," no remaining "advisory-only
until the flip (HARNESS006)" annotation, and the reviewer procedure's input
contract no longer contradicts its own checklist.

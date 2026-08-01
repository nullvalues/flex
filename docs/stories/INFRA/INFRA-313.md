---
id: INFRA-313
rail: INFRA
title: CER backlog gate and groom — cer.py gate wired into checkpoint, cer.py groom, gate conditions in rows
status: complete
phase: "116"
story_class: code
auth_gated: false
schema_introduces: true
primary_files:
  - skills/pairmode/scripts/cer.py
touches:
  - skills/pairmode/scripts/next_action.py
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/templates/docs/cer/backlog.md.j2
  - tests/pairmode/test_cer.py
  - tests/pairmode/test_flex_build.py
  - docs/cer/backlog.md
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Cora item A#1 (`/mnt/work/cora/docs/agreements/flex-upstream-candidates.md`,
the doc's own priority item; AG-6): the CER quadrants only work if something
re-reads them — "Do Later is where findings go to die." Today `cer.py` is
capture-only (`append_finding`, `cer.py:223`); the only reader is
`next_action._check_cer_do_now` (`next_action.py:394`), a resolver-side soft
gate on `## Do Now`. Three behaviours land here:

1. **`cer.py gate`** — exits nonzero when `## Do Now` holds an open
   (un-RESOLVED/SUPERSEDED, non-placeholder) row; wired into the checkpoint
   sequence so a tag cannot be cut over an open Do Now finding.
2. **`cer.py groom`** — re-reads `## Do Later` / `## Do Much Later` for rows
   whose explicit `gate:` condition may have arrived, and prints them for the
   operator. **The operator decides pulls — groom never edits the backlog and
   never promotes automatically** (preserved do-not-do).
3. **`gate:` conditions in rows** — a recognized inline token in the Finding
   cell (`gate: <condition text>`), not a new table column (the 5-column
   `ID | Finding | Source | Date | Phase` shape is parsed by
   `_parse_entries_from_backlog`, `cer.py:81`, and by external greps; a sixth
   column would break both). CER-121 and CER-125 already carry the token in
   this format (filed at spec time, 2026-07-29) — they are groom's first live
   test data.

The promotion ledger half of A#1 already exists
(`docs/phases/index.md` § backlog promotions) and is **not rebuilt** (AG-6).

## Requires

1. `cer.is_placeholder_row` (`cer.py:144`) and
   `next_action._check_cer_do_now` (`next_action.py:394-437`) — the existing
   open-Do-Now predicate. `gate` must share one predicate with the resolver
   check, not fork a second copy (duplicate-state is a cold-eyes checklist
   item). Direction: hoist the scan into `cer.py` as a public function;
   `next_action` imports it (it already imports `is_placeholder_row`).
2. The checkpoint sequence: `record-checkpoint-step`
   (`flex_build.py:~2916+`, `_CHECKPOINT_STEPS_KEY` at `:2922`), terminal
   step `checkpoint-tag` (`:2990`). Identify the step list and insert the
   gate before `checkpoint-tag` completes — coordinate with INFRA-314, which
   adds the deferral gate at the same seam and builds immediately after.
3. `docs/cer/backlog.md` live shape: quadrant headings at `:11/:50/:192/:221`
   (re-locate by text), placeholder row in Do Never, disposition-token
   vocabulary (`RESOLVED|SUPERSEDED|OBSOLETE|REJECTED|AMENDED|BACKLOG-RETAIN`).
4. Baseline 4116/211.

## Ensures

1. **`cer.py gate` exists.** Exit 0 when Do Now is clean (resolved-only or
   placeholder), exit 1 listing each open row's ID and first 80 chars when
   not. **Correct signal: the exit code; forbidden proxy: a printed warning
   with exit 0.**
2. **One predicate, two consumers.** `next_action._check_cer_do_now` and
   `gate` call the same public function in `cer.py`; the resolver's
   behavioural contract (fail-open on missing/unreadable file, placeholder
   exemption) is preserved verbatim and covered by existing tests unmodified.
3. **Checkpoint wiring.** The `checkpoint-tag` step of
   `record-checkpoint-step` runs the gate and **refuses to record the step**
   (nonzero, actionable message naming the open rows) when the gate fails.
   Resolution is fix-or-retriage: the message states that an open row is
   cleared by a `RESOLVED`/`SUPERSEDED` annotation or a written re-triage to
   another quadrant — never by deletion.
4. **`cer.py groom` exists.** Scans Do Later + Do Much Later; for every open
   row prints ID, quadrant, and its `gate:` condition text (or `(no gate:)`);
   summarizes counts. Exit code 0 always (groom informs; the operator
   decides). **Correct signal: row inventory with gate conditions surfaced;
   forbidden proxy: any write to `docs/cer/backlog.md` — groom's diff must be
   empty, and a test asserts the file is byte-identical after a groom run.**
5. **`gate:` token recognized, documented, templated.** The token's grammar
   (`gate:` followed by free text until the next bold token or cell end) is
   parsed by groom, documented in `docs/architecture.md`'s CER section, and
   the backlog template (`templates/docs/cer/backlog.md.j2`) gains one
   comment line describing it. Live rows CER-121 and CER-125 are groom's
   fixtures: a test runs groom against a fixture backlog containing both
   shapes (with and without `gate:`).
6. **Cold-eyes-review hook documented.** The architecture note states the
   operating rule (from the global backlog-grooming policy): every cold-eyes
   review runs `cer.py groom` and surfaces arrived-gate rows as "ready to
   pull forward"; pulls are operator decisions recorded in the promotion
   ledger. No automation of the pull is built or implied.
7. **CER row annotated.** The A#1 filing row (see `docs/cer/backlog.md`,
   filed 2026-07-29 as part of the closeout agreements if present) or —
   if no row exists because A#1 arrived as an agreement, not a finding —
   no annotation is required; state which case applied in the evidence.
8. **Suite green.** Full run without `-x`; baseline + added tests.

## Instructions

1. Hoist the Do Now scan out of `next_action.py` into `cer.py` first
   (Requires 1); keep the resolver's tests green unmodified — they are the
   contract.
2. Add `gate` and `groom` as subcommands of the existing `cer.py` CLI entry
   (`cli`, `cer.py:360`), following its current invocation style.
3. Wire the checkpoint refusal (Ensures 3) with a test that drives
   `record-checkpoint-step checkpoint-tag` against a fixture with one open
   Do Now row and asserts refusal, then annotates the row and asserts
   success.
4. Do not add a sixth table column; do not auto-promote; do not touch the
   promotion ledger mechanism.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cer.py tests/pairmode/test_next_action.py tests/pairmode/test_flex_build.py -q 2>&1 | tail -15
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative checks: (a) groom leaves
the backlog byte-identical; (b) the gate's failure path is exercised by a
test that asserts the checkpoint step is *not* recorded; (c) exactly one
open-Do-Now predicate exists (`grep` for the scan logic appears once).

## Out of scope

- Auto-promotion or auto-editing of any backlog row (operator-only, forever).
- Rebuilding the promotion ledger (exists in `docs/phases/index.md`).
- Retroactively adding `gate:` to historical rows beyond CER-121/CER-125.
- Downstream propagation of the new checkpoint behaviour (rides the post-tag
  sync campaign, propagatable thanks to INFRA-311).

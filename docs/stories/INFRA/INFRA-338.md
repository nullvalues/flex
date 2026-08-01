---
id: INFRA-338
rail: INFRA
title: Fix cer.py backlog-append corruption: unify the row parser between reader and writer
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CRITICAL finding F7 of `docs/build-loop-cold-eyes-review-20260801.md` (opus, reproduced against a
live copy of the backlog): `cer.py`'s `append_finding` writer does a full parse → re-render →
whole-file overwrite using a naive `\|`-split regex (`_TABLE_ROW_RE`), while the reader half
(`_scan_rows_in_sections`) correctly uses `table_utils.split_table_row`. Real rows in this file
routinely contain escaped pipes (e.g. `Task\|Agent`, which appears verbatim in several already-
`**RESOLVED**` rows — CER-066 is itself the finding about naive pipe-splitting, ironically). An
append near such a row can truncate its `**RESOLVED …**` annotation at the first escaped pipe,
destroying the annotation text and flipping `find_open_do_now_rows` from `[]` to reporting those
rows as newly unresolved — which then permanently locks `record-checkpoint-step checkpoint-tag`'s
CER Do-Now gate (exit 3, refuses forever) with no way to recover the destroyed annotation text
short of `git checkout` on the file. The existing 5-line/0-entry parse-failure warning only catches
total parse failure, not partial corruption of a subset of rows.

Fix direction: make the append path's row-splitting use the same `table_utils.split_table_row`
the reader uses — one shared parser for both directions, not two independently-maintained ones.

**Folded in (era 004's own goal is zero unresolved operational findings, not "later" — same file):**

- **CER-152 (LOW):** `cer.py gate`/`cer.py groom`'s own docstrings claim they are wired into the
  checkpoint sequence ("Wired into the `checkpoint-tag` step of `record-checkpoint-step`") — the
  live gate (`flex_build._cer_do_now_gate_message`) imports the shared function directly and never
  shells out to the CLI, and `groom` (era 002's stated "run on every cold-eyes review" policy) has
  no enforcement or reminder anywhere in the loop. Either correct the docstrings to describe the
  real (direct-import) wiring, or actually wire the CLI subcommands in if a second surface is
  wanted — don't leave both existing with one silently unused.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests

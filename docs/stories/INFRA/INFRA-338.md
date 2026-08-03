---
id: INFRA-338
rail: INFRA
title: Fix cer.py backlog-append corruption: unify the row parser between reader and writer
status: complete
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/cer.py
touches:
  - tests/pairmode/test_cer.py
  - docs/cer/backlog.md
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

Verified against the working tree at spec time (2026-08-01, `main` @ `b4cec2cf`):
`skills/pairmode/scripts/cer.py:55-63` (`_TABLE_ROW_RE`) is a regex that matches a literal `|`
character positionally — it has no awareness of the `(?<!\\)` unescaped-pipe lookbehind
`table_utils._UNESCAPED_PIPE_RE` uses, so a cell containing `\|` splits the row at that character
exactly as if it were a real column boundary. `_TABLE_ROW_RE` has exactly one call site
(`cer.py:120`, inside `_parse_entries_from_backlog`), which `append_finding` calls (via
`_load_or_create_backlog`, `cer.py:474`) before every append to seed `entries` from the existing
file — so *every* `append_finding` call re-parses and re-renders the whole file through this
defective path, not just appends that happen to land near an escaped-pipe row.

## Requires

None — this story is independent of every other story in Phase 117 (see phase-117.md § Ordering:
"INFRA-338 … is independent of everything else in this phase and can build any time") and touches
no file any other Phase 117 story's Instructions name.

## Ensures

### A — the writer's read-before-append path uses the shared, escape-aware splitter

**A1.** `cer._parse_entries_from_backlog` no longer calls `_TABLE_ROW_RE.match`. It splits each
candidate table row with `table_utils.split_table_row` — the same function
`cer._scan_rows_in_sections` already uses — via
`cols = [c.strip() for c in split_table_row(stripped) if c.strip()]`, identical to the filtering
`_scan_rows_in_sections` (`cer.py:310`) already applies.

**A2.** The module-level constant `_TABLE_ROW_RE` (`cer.py:55-63`) is deleted entirely.
`grep -n _TABLE_ROW_RE skills/pairmode/scripts/cer.py tests/pairmode/*.py` returns no matches
anywhere in the repository after this story lands.

**A3.** A row is recognised as a finding row (as `_TABLE_ROW_RE`'s `(CER-\d{3})` capture group
used to gate the whole match) by testing `cols[0]` against the existing `_CER_ID_RE` constant
(`cer.py:51`, `re.compile(r"\bCER-(\d{3})\b")`) with `.fullmatch(cols[0])` rather than `.search`,
so a cell that merely *contains* a `CER-NNN` substring inside longer text is not mistaken for an
ID cell. No new regex constant is introduced — `_CER_ID_RE` is reused, matching the module's
existing single-source-of-truth-per-pattern convention (`is_placeholder_row`, `is_resolution_marked`).

**A4.** Rows with fewer than 5 non-empty cells after the split (malformed/truncated rows) are
skipped without raising — `_parse_entries_from_backlog` never raises `IndexError` on a
short row; `_load_or_create_backlog`'s existing `try/except Exception` (`cer.py:442-447`) around
the whole parse remains the outer safety net, but the per-row guard means well-formed rows
elsewhere in the same file are not lost just because one malformed row exists among them.

**A5.** Field extraction stays positional and unchanged in meaning: `cols[0]` = id, `cols[1]` =
finding, `cols[2]` = source, `cols[3]` = date, `cols[4]` = phase, `cols[5]` = resolution (present
only for 6-column Do Never rows). The existing `is_placeholder_row(cols)` defensive skip
(`cer.py:134`, "this branch cannot fire today" per its own comment) is kept as-is — its comment is
updated to state that the branch is now doubly defensive: `_CER_ID_RE.fullmatch` on the
placeholder row's first cell (`—`, `–`, or `-`) already fails before `is_placeholder_row` is ever
reached, so this remains dead-but-intentional defense-in-depth, not a behaviour change.

### B — the corruption is closed: escaped-pipe rows survive an append unmutated

**B1.** The correct signal: appending a new finding to a backlog whose existing rows contain an
escaped pipe (e.g. `Task\|Agent`) in any cell — finding, source, or a `**RESOLVED …**`
annotation — leaves every byte of every existing row's rendered output identical except for the
one new row appended at the end of its quadrant's entry list. **Forbidden proxy: `append_finding`
returning without raising, or the CLI exiting 0** — a corrupted-but-still-parseable row can do
both while silently truncating another row's annotation, which is exactly how F7 was reproduced
without producing an exception. The test must diff full row text, not just check that the call
succeeded.

**B2.** Specifically: a Do Now row containing `**RESOLVED Phase 1** — matcher fixed (Task\|Agent)`
retains that full annotation text, unedited, after `append_finding` is called for an unrelated new
finding in the same file. `find_open_do_now_rows` on the post-append content still excludes that
row (it is still resolution-marked) — this is the same signal the `checkpoint-tag` gate reads, so
the regression test asserts both the raw text and the gate-facing predicate.

### C — CER-152: the docstrings describe the real wiring, not an aspirational one

**C1.** `cer.py`'s `cmd_gate` docstring (`cer.py:704-717`) no longer states or implies that the
`gate` CLI subcommand itself is invoked by `record-checkpoint-step`'s `checkpoint-tag` step. It
states accurately that `checkpoint-tag` (`flex_build._cer_do_now_gate_message`) imports
`find_open_do_now_rows` directly and never shells out to `cer.py gate`; that `cer.py gate` is a
standalone CLI entry point sharing the same underlying scan for manual or CI use outside the
build loop; and it keeps the existing INFRA-313 cross-reference to `next_action._check_cer_do_now`
as the resolver's own consumer of the same shared function.

**C2.** `cer.py`'s `cmd_groom` docstring (`cer.py:749-763`) states accurately that `cer.py groom`
has no automated invocation, checkpoint-step wiring, or scheduled reminder anywhere in the build
loop today — running it is an operator-followed policy (the global backlog-grooming policy,
`CLAUDE.md`), not a mechanically enforced one. It does not claim or imply any CLI-to-checkpoint
wiring that does not exist.

**C3.** No new CLI-invocation call site, subprocess call, or checkpoint-sequence edit is added
anywhere in the repository as part of closing CER-152 — this story takes the "correct the
docstrings" branch of the fix direction, not the "wire the CLI in" branch. `git diff` for this
story touches no line inside `flex_build.py`'s checkpoint-sequence functions
(`_cer_do_now_gate_message`, `cmd_record_checkpoint_step`, or any `_SPAWN_ACTIONS`/dispatch table).

**C4.** The CER-152 row in `docs/cer/backlog.md` (§ Do Later, currently reading "Absorbed at spec
time by INFRA-338 (Phase 117) — folded into the cer.py append-corruption fix rather than
deferred") is annotated `**RESOLVED INFRA-338 (Phase 117)**` with a one-sentence statement of what
landed (docstrings corrected, no new wiring added). No other row in the file is edited.

### D — tests

**D1.** `tests/pairmode/test_cer.py` gains, at minimum:
- `test_parse_entries_handles_escaped_pipe_in_finding_cell` — a fixture Do Now row whose finding
  cell contains `Task\|Agent` parses via `_parse_entries_from_backlog` to exactly one entry, with
  the finding field equal to the cell's stripped text including the literal `\|` (unescaped, i.e.
  not shredded into two entries or a truncated field).
- `test_append_finding_does_not_truncate_neighboring_resolved_row_with_escaped_pipe` — seeds
  `docs/cer/backlog.md` directly (bypassing the CLI) with a Do Now row annotated
  `**RESOLVED Phase 1** — matcher fixed (Task\|Agent)`, calls `append_finding` for an unrelated
  new finding in the same quadrant, then asserts (a) the seeded row's line is byte-identical
  before and after, and (b) `find_open_do_now_rows` on the post-append content still excludes that
  row's ID — the § B1/B2 regression test, reproducing F7 and proving it fixed.
- `test_parse_entries_from_backlog_matches_scan_rows_for_escaped_pipe_fixture` — for the same
  escaped-pipe fixture text, `_parse_entries_from_backlog`'s per-row `finding`/`source`/`date`
  values match the corresponding cells `_scan_rows_in_sections` returns for the same row — a
  parity check that both readers now agree on one row's field boundaries.
- A grep-form or source-inspection assertion (e.g. reading `cer.py`'s source text in the test and
  asserting `"_TABLE_ROW_RE"` is absent) pinning § A2, so a future edit cannot silently reintroduce
  the constant.

**D2.** All existing tests in `tests/pairmode/test_cer.py` (as read at spec time, including
`test_multiple_calls_accumulate`, `test_cer_id_not_restarted_after_gap`,
`test_malformed_backlog_emits_warning`, `test_normal_backlog_no_warning`,
`test_graceful_on_unexpected_content`, and every `gate`/`groom` CLI test) remain green, unedited
in their assertions — this story changes `_parse_entries_from_backlog`'s implementation, not its
public return shape for any row already covered by an existing fixture.

**D3.** Full suite green, run **once without `-x`** so a pre-existing failure cannot mask a new
one.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.

1. **Rewrite `_parse_entries_from_backlog` (`skills/pairmode/scripts/cer.py`).** Replace the
   `_TABLE_ROW_RE.match(stripped)` branch with a `table_utils.split_table_row`-based split,
   mirroring `_scan_rows_in_sections`'s own filtering
   (`cols = [c.strip() for c in split_table_row(stripped) if c.strip()]`). Gate row recognition on
   `_CER_ID_RE.fullmatch(cols[0])` instead of the deleted regex's capture group. Guard the
   `len(cols) < 5` case per § A4. `table_utils.split_table_row` is already imported at the top of
   `cer.py` (`from table_utils import split_table_row`, `cer.py:29`) — no new import is needed.

2. **Delete `_TABLE_ROW_RE`.** Confirmed by grep at spec time that it has exactly one call site
   (inside the function you are rewriting) and no other reference in `skills/` or `tests/`
   (§ A2). Remove the constant and its docstring comment block (`cer.py:53-63`) entirely — do not
   leave it dead-but-defined.

3. **Do not touch anything else in `cer.py`'s read/write surface.** `_scan_rows_in_sections`,
   `find_open_do_now_rows`, `find_groomable_rows`, `is_placeholder_row`, `is_resolution_marked`,
   `_escape_table_cell`, `_next_cer_id`, `_render_backlog`, and `append_finding`'s own body
   (beyond the effect of the rewritten function it calls indirectly via
   `_load_or_create_backlog`) are unedited. This story's surface is exactly
   `_parse_entries_from_backlog` plus the two docstrings named in step 4.

4. **Fix the two docstrings for CER-152.** Update `cmd_gate`'s docstring per § C1 and
   `cmd_groom`'s docstring per § C2. Do not add any new CLI-invocation code path, subprocess call,
   or checkpoint-sequence edit (§ C3) — this story deliberately takes the docstring-correction
   branch of the fix direction, not the CLI-wiring branch; see § Out of scope.

5. **Annotate the CER-152 backlog row** per § C4 once steps 1-4 are built and tested green. Edit
   only that one row in `docs/cer/backlog.md` — no other row is touched, and the preamble is
   unedited.

6. **Write the tests named in § D1**, then run the full suite per § D3 and confirm § D2's existing
   tests are unaffected.

## Tests

```bash
# Focused — the parser and the append-path regression
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cer.py -q

# Full suite — once, WITHOUT -x, so a pre-existing failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:**

- The focused run is green, including every new test named in § D1.
- Every pre-existing test in `test_cer.py` (§ D2) is green, unedited.
- Full suite green against the `main` baseline plus this story's additions. No new failures. A
  `test_observability_ui` failure is worktree-only (CER-090): fix by `rsync`-ing the vendored
  payload from the main checkout, never `pnpm install`; state in the build report that it does not
  reproduce on a clean `main` checkout.

**New tests required** (names indicative, per § D1):

- `test_parse_entries_handles_escaped_pipe_in_finding_cell`
- `test_append_finding_does_not_truncate_neighboring_resolved_row_with_escaped_pipe`
- `test_parse_entries_from_backlog_matches_scan_rows_for_escaped_pipe_fixture`
- a `_TABLE_ROW_RE`-absence pin (name indicative, e.g. `test_table_row_re_constant_removed`)

## Out of scope

- **Actually wiring `cer.py gate`/`cer.py groom` as CLI subprocess calls into the checkpoint
  sequence. Rejected for this story, not deferred silently.** The fix direction offers two
  branches (correct the docstrings, or wire the CLI in); this story takes the docstring branch,
  since a second, CLI-shelling wiring surface for a check that already has a working direct-import
  consumer (`_cer_do_now_gate_message`) would itself be the "two implementation surfaces that can
  drift" shape CER-152 warns about, not a fix for it. If a future need for a genuinely separate CLI
  gate (e.g. a pre-commit hook, a CI job outside the build loop) arises, that is a new story with
  its own Ensures, not folded in here.
- **Building an automated `groom` reminder/scheduler.** CER-152 notes `groom` has no enforcement
  anywhere in the loop; this story corrects the docstring's claim about that state rather than
  building the enforcement. A scheduled or checkpoint-triggered `groom` reminder is a policy/UX
  decision for a future story, not a LOW-severity docstring-accuracy fix.
- **Editing `_scan_rows_in_sections`, `find_open_do_now_rows`, or `find_groomable_rows`.** These
  already use `table_utils.split_table_row` correctly (they are the reader half F7 contrasts
  against) and are not touched.
- **Auditing other positional-`cols`-index call sites in the repository for the same bug class.**
  INFRA-297 already completed that audit and consolidation (`docs/cer/backlog.md`'s CER-069 row,
  **RESOLVED**) for every site that existed at that time; `_parse_entries_from_backlog` was, per
  this story's own Context, an eighth site that regressed after INFRA-297 (or was never covered by
  it) and needs its own fix — that is exactly what this story is. No new sweep of other files is
  in scope here.
- **Backfilling a recovery path for annotation text already destroyed by a prior corrupted
  append.** This story prevents future corruption; it does not attempt to reconstruct any
  `**RESOLVED …**` text a past append may have already truncated in any consuming repo's backlog.
  A project that hit this before this story landed still needs `git checkout`/history inspection
  to recover, as the Context describes.

## Evidence

Covered-contracts gate (INFRA-317): `skills/pairmode/scripts/cer.py` is a `primary_files:` entry
and appears in the `covered_contracts` pair `## Pairmode build loop::skills/pairmode/scripts/cer.py`
declared in `CLAUDE.build.md`. Both the named doc section (`docs/architecture.md` § Pairmode build
loop) and the source file were read in full before editing either.

Contract lines relied on (`docs/architecture.md` § Pairmode build loop, step 10):

- "`cer.py gate --project-dir <dir>` exits 0 when Do Now is clean (resolved-only, or the scaffolded
  placeholder row) and exits 1, listing each open row's ID and first 80 characters, when it is not
  — the exit code is the signal, never a printed warning with exit 0. The `checkpoint-tag` step of
  `record-checkpoint-step` calls this same scan directly (`_cer_do_now_gate_message`) before any
  state.json read or write" — confirms the real wiring `cmd_gate`'s docstring (§ C1) now states:
  `checkpoint-tag` imports the shared scan directly and never shells out to `cer.py gate`. No
  divergence found — the doc already described the direct-import wiring accurately; this story
  brought `cer.py`'s own docstring into agreement with it.
- "A **`gate:` token** is a recognized inline marker inside a row's Finding cell … not a sixth table
  column: the 5-column `ID | Finding | Source | Date | Phase` shape (parsed by
  `cer._parse_entries_from_backlog` and by external greps) is unchanged." — confirms § A5's
  positional field contract (`cols[0]`..`cols[4]`, 6th column present only for Do Never rows) is
  preserved by the rewrite; no divergence found.
- "`cer.py groom --project-dir <dir>` … groom's exit code is always 0 — it informs, it never
  decides … Per the global backlog-grooming policy, every cold-eyes review should run `cer.py
  groom` …" — confirms `cmd_groom`'s corrected docstring (§ C2): groom has no checkpoint-step
  wiring or scheduled reminder, running it is an operator-followed policy, not a mechanically
  enforced one. No divergence found.

No divergence between the doc section and the source file was found on any of the above — this
story's docstring corrections align `cer.py`'s own text with what `docs/architecture.md` already
documented as the real behavior.

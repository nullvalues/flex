---
id: INFRA-294
rail: INFRA
title: "_check_cer_do_now: stop reading the scaffolded (none) placeholder row as an unresolved Do Now item"
status: complete
phase: "112"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - skills/pairmode/scripts/cer.py
touches:
  - tests/pairmode/test_checkpoint_routing.py
  - tests/pairmode/test_cer.py
  - docs/architecture.md
  - docs/stories/INFRA/INFRA-294.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This is Phase 112's defect 2 — the cheapest of the three campaign unblockers and
the one that fires on *every* migrated repo. Repo-C's first 0.3.0 checkpoint was
blocked by `next_action._check_cer_do_now` (`skills/pairmode/scripts/next_action.py:383`)
treating the scaffolded CER-backlog empty-state placeholder row
(`| — | *(none)* | — | — | — |`) as an unresolved Do Now item, so
`check_checkpoint_guards` returned `{"ok": False, "failed_guard": "cer-do-now"}`
and the resolver emitted `await-user:checkpoint-guard-failed:cer-do-now`
forever. The Repo-C operator worked around it by hand-deleting the row (Repo-C
commit `f234915`, filed there as CER-C004). Every repo bootstrapped from
`skills/pairmode/templates/docs/cer/backlog.md.j2` — which emits that row
whenever a quadrant is empty (`:23`, `:40`, `:57`, and the six-column Do Never
variant at `:74`) — reproduces this on its *first* checkpoint, which is exactly
the moment a freshly migrated consumer is least able to diagnose it.

The guard is the load-bearing half of the fix. A template-only change (dropping
the placeholder row) would strand every repo already scaffolded with it,
including the entire migration fleet, so the template is deliberately left
alone (see § Out of scope) and the guard is taught to tolerate the row.

The placeholder rule already exists once in the codebase: `cer.py:118-120`
(`if cer_id == "—" or finding == "*(none)*": continue`) inside
`_parse_entries_from_backlog`. Per the phase's cold-eyes correction 5, this
story must **share or mirror that rule, not author a third independent
variant** — duplicate state with independent writers is exactly what the CP-112
checklist asks about. So the rule is extracted into one public, stdlib-only
predicate in `cer.py` and both call sites consume it.

Recon already performed for the builder (do not redo it):

- `_check_cer_do_now` (`next_action.py:383-416`) walks `## Do Now`, skips the
  `---` separator and the `ID`/`Finding` header row, and returns `False` for any
  remaining `|`-row lacking `RESOLVED` or `SUPERSEDED`. It has no placeholder
  concept at all. It fails open (returns `True`) when the file is missing or
  unreadable; keep that.
- Its only caller is `check_checkpoint_guards` (`next_action.py:519`), guard 2
  of 3.
- `cer.py`'s placeholder branch is presently **unreachable**: `_TABLE_ROW_RE`
  (`cer.py:43-53`) requires the first cell to match `CER-\d{3}`, so a
  placeholder row never produces a match object and never reaches line 118.
  Extracting the predicate is therefore behaviour-preserving for `cer.py` — do
  not "fix" the regex or change parse behaviour there; this story only makes the
  rule reusable and gives it a test.
- Repo-C's real-world row had four cells (`| — | *(none)* | — | — |`) while the
  template emits five (Do Now) and six (Do Never). The predicate must be
  column-count agnostic.
- `next_action.py` imports siblings function-locally after inserting its own
  directory on `sys.path` (`:132-135`; e.g. `from flex_build import ...` at
  `:602`, `from next_story import ...` at `:700`). `cer.py` imports `click` and
  `jinja2` at module level, which is no new burden — `flex_build.py:50` already
  imports `click` and `next_action` already imports it function-locally.
- Existing guard coverage lives in `tests/pairmode/test_checkpoint_routing.py`
  (`:254` unresolved row → guard fails, `:276` all-RESOLVED → guard passes) and
  `tests/pairmode/test_harness004_isolation.py:270` (end-to-end
  `await-user:checkpoint-guard-failed:cer-do-now`). `tests/pairmode/test_next_action.py`
  has **no** `_check_cer_do_now` coverage.
- `cer.py:70` exposes `_render_backlog(cer_entries, project_name)`, which
  renders the real template — the round-trip regression test uses it rather than
  hand-writing a placeholder fixture.
- No CER backlog item is assigned to this story (Phase 112's backlog pulls route
  CER-033/CER-099 to INFRA-293 and CER-059a to INFRA-295). Repo-C's CER-C004
  lives in Repo-C's own backlog and is closed there by the operator, not here.

## Requires

- Working tree clean at HEAD on `main`; no other Phase 112 story in flight in
  the same worktree.
- `skills/pairmode/scripts/next_action.py` still defines `_check_cer_do_now` and
  `check_checkpoint_guards` with guard 2 wired at `:519`.
- `skills/pairmode/scripts/cer.py` still defines `_parse_entries_from_backlog`
  with the `cer_id == "—" or finding == "*(none)*"` skip.
- INFRA-293 and INFRA-295 are **not** prerequisites — the three Phase 112
  stories touch disjoint files and may build in any order.

## Ensures

1. `skills/pairmode/scripts/cer.py` defines a module-level public function
   `is_placeholder_row(cells)` that takes a sequence of already-stripped table
   cell strings and returns `bool`. It uses only the standard library (no
   `click`, `jinja2`, or regex state from `cer.py`'s constants), performs no
   I/O, and its docstring names the defect it prevents (scaffolded empty-state
   row read as an unresolved Do Now item) and the template rows it describes.
2. `is_placeholder_row` returns `True` for each of: `["—", "*(none)*", "—", "—", "—"]`
   (template Do Now shape), `["—", "*(none)*", "—", "—", "—", "—"]` (template
   Do Never shape), and `["—", "*(none)*", "—", "—"]` (the four-cell shape
   observed in Repo-C). It returns `False` for
   `["CER-999", "An unresolved finding", "some-source", "2026-01-01", "1"]` and
   for `[]`.
3. `cer.py`'s `_parse_entries_from_backlog` calls `is_placeholder_row` in place
   of its inline `cer_id == "—" or finding == "*(none)*"` test.
   `grep -c 'finding == "\*(none)\*"' skills/pairmode/scripts/cer.py` returns 0
   outside the body of `is_placeholder_row` — i.e. the literal comparison exists
   in exactly one function.
4. `next_action._check_cer_do_now` imports `is_placeholder_row` from `cer` and
   skips any Do Now row for which it returns `True`, before the
   `RESOLVED`/`SUPERSEDED` test is applied. `skills/pairmode/scripts/next_action.py`
   contains no independent literal `*(none)*` comparison:
   `grep -c '(none)' skills/pairmode/scripts/next_action.py` returns 0.
5. `next_action._check_cer_do_now(project_dir)` returns `True` when
   `docs/cer/backlog.md` is the output of `cer._render_backlog(cer_entries=[])`
   (the exact bytes a freshly bootstrapped project receives).
6. `next_action._check_cer_do_now` still returns `False` for a Do Now section
   containing `| CER-999 | An unresolved finding | some-source | 2026-01-01 | 1 |`,
   and still returns `True` when the file is absent, is unreadable, or contains
   only `RESOLVED`/`SUPERSEDED` rows. Existing behaviour is unchanged for every
   non-placeholder input.
7. `tests/pairmode/test_cer.py` gains unit tests for `is_placeholder_row`
   covering every case listed in Ensures 2.
8. `tests/pairmode/test_checkpoint_routing.py` gains a regression test that
   writes `cer._render_backlog(cer_entries=[])` to `<tmp>/docs/cer/backlog.md`
   and asserts `check_checkpoint_guards(tmp_path, phase_file, gate_fn=lambda: True)`
   returns `{"ok": True}`. The test fails if the placeholder skip is reverted.
9. `tests/pairmode/test_checkpoint_routing.py` gains a second regression test
   using the literal four-cell Repo-C row `| — | *(none)* | — | — |` under
   `## Do Now`, also asserting `{"ok": True}`.
10. `docs/architecture.md` line ~768's checkpoint entry (the
    "Pre-checkpoint guards (phase-completion, CER Do Now, build gate)" sentence)
    records that the CER Do Now guard skips scaffolded placeholder rows using
    the shared `cer.is_placeholder_row` predicate, in one added sentence. No
    other architecture prose changes.
11. `skills/pairmode/templates/docs/cer/backlog.md.j2` is byte-identical to
    HEAD: `git diff --stat HEAD -- skills/pairmode/templates/docs/cer/backlog.md.j2`
    is empty.
12. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` reports no
    failures other than the known pre-existing
    `test_observability_ui.py::test_ui_build_emits_dist_index_html` failure, and
    only if that failure also reproduces on clean HEAD.

## Instructions

1. **Add the shared predicate to `cer.py`.** Define it at module level, near
   `_escape_table_cell` (i.e. with the other pure helpers), as:

   ```python
   def is_placeholder_row(cells) -> bool:
   ```

   Rule: return `True` when `cells` is non-empty and either the first cell is a
   bare dash cell (`"—"`, `"–"`, or `"-"` after stripping) or any cell equals
   `"*(none)*"`. Return `False` otherwise, including for an empty sequence.
   Strip each cell defensively so callers may pass raw split output. Do not
   depend on the column count — the scaffolded row appears in four-, five-, and
   six-column shapes across sections and consumer repos.

   Write a rationale-bearing docstring (this project prefers rationale-bearing
   rules over bare ones): state that the row is the Jinja template's empty-state
   marker emitted by `docs/cer/backlog.md.j2` when a quadrant has no entries,
   that it is not a finding, and that treating it as one blocked Repo-C's first
   0.3.0 checkpoint.

2. **Rewire `cer._parse_entries_from_backlog`** to call
   `is_placeholder_row([cer_id, finding])` in place of the inline comparison at
   `cer.py:118-120`. Keep the `continue`. Change nothing else in that function —
   in particular do not touch `_TABLE_ROW_RE`. Note in a short comment that the
   branch is defensive (the regex already excludes placeholder rows by requiring
   a `CER-NNN` id), so this is a de-duplication of the rule, not a behaviour
   change.

3. **Fix the guard in `next_action._check_cer_do_now`.** Inside the function,
   add a deferred sibling import matching the module's existing idiom:

   ```python
   from cer import is_placeholder_row  # type: ignore[import]
   ```

   Place it at the top of the function body (before the file read), not at
   module scope — `next_action.py`'s header block is stdlib-only by design and
   every sibling dependency in this module is imported function-locally
   (`flex_build` at `:602`, `next_story` at `:700`).

   In the row loop, after the header-row skip and before the
   `RESOLVED`/`SUPERSEDED` test, add:

   ```python
   if is_placeholder_row(cols):
       continue
   ```

   Do **not** wrap the import in `try`/`except ImportError`. `cer.py` is a
   sibling in the same scripts directory and is always present; swallowing the
   error would silently restore the exact false positive this story removes,
   which contradicts the project's "never silently pass contradictions"
   constraint. The function's existing fail-open behaviour for a missing or
   unreadable `backlog.md` stays exactly as it is — that is a different failure
   mode (absent data, not broken code).

   Update the function docstring to state the placeholder exemption and name
   `cer.is_placeholder_row` as its source of truth.

4. **Extend the module docstring** of `next_action.py` only if you add a new
   `INFRA-294` note block consistent with the existing per-story blocks
   (`INFRA-283`, `INFRA-265`, …). One short paragraph; no `SCHEMA_VERSION` bump
   — the action grammar, Position shape, and routing are all unchanged.

5. **Tests — `tests/pairmode/test_cer.py`.** Add `is_placeholder_row` to the
   existing `from skills.pairmode.scripts.cer import (...)` block at `:10` and
   add unit tests for the five cases in Ensures 2. Follow the file's flat
   `def test_*` style; no new fixtures or classes.

6. **Tests — `tests/pairmode/test_checkpoint_routing.py`.** Add the two
   regression tests next to the existing CER guard tests (`:254`, `:276`),
   reusing that file's `_make_phase_file` helper and `gate_fn=lambda: True` so
   the live pytest subprocess never runs:

   - `test_check_guards_cer_do_now_scaffolded_placeholder_passes` — import
     `_render_backlog` from `cer` inside the test, write
     `_render_backlog(cer_entries=[])` to `<tmp>/docs/cer/backlog.md`, assert
     `{"ok": True}`. This is the load-bearing test: it binds the guard to the
     *real template output*, so a future template edit that changes the
     placeholder shape breaks here rather than in a consumer's first checkpoint.
   - `test_check_guards_cer_do_now_four_cell_placeholder_passes` — hand-write
     the Repo-C-observed `| — | *(none)* | — | — |` row under `## Do Now`, assert
     `{"ok": True}`.

   Leave `tests/pairmode/test_harness004_isolation.py:270` untouched — its
   fixture uses a real `CER-042` row and must keep failing the guard.

7. **Architecture note.** Append one sentence to the checkpoint entry in
   `docs/architecture.md` (~`:768`), immediately after the existing
   "Pre-checkpoint guards …" sentence, recording that the CER Do Now guard
   exempts scaffolded placeholder rows via `cer.is_placeholder_row` (INFRA-294)
   and why (the template emits the row for every empty quadrant, so without the
   exemption every freshly bootstrapped repo fails its first checkpoint). Do not
   rewrite the file-inventory line at `:76`.

8. **Ideology note (Step 4a, resolved inline).** The drafted instructions were
   shaped by two ideology entries. "Never silently pass contradictions" is why
   step 3 forbids a `try/except ImportError` fallback around the shared
   predicate — a swallowed import would restore the false positive silently. The
   "codify policy over implicit convention" conviction, plus the CP-112
   duplicate-state check, is why the rule is extracted into one named predicate
   with a rationale-bearing docstring rather than mirrored as a second inline
   comparison in `next_action.py`. No accepted constraint is touched: this story
   writes no state, adds no hook logic, and leaves the hook-pipe-sidebar
   boundary alone. `is_placeholder_row` is a pure function, preserving
   `next_action.py`'s pure-read invariant.

## Tests

Targeted run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_checkpoint_routing.py \
  tests/pairmode/test_cer.py \
  tests/pairmode/test_harness004_isolation.py \
  tests/pairmode/test_next_action.py -q
```

Then the full suite, without `-x` so the known pre-existing failure cannot mask
a real one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Revert-check (run manually, do not commit the revert): temporarily remove the
`if is_placeholder_row(cols): continue` line and confirm both new
`test_checkpoint_routing.py` tests fail. Restore before finishing.

**Acceptance:** the targeted run is fully green; the full run reports no
failures except `test_observability_ui.py::test_ui_build_emits_dist_index_html`
if and only if that failure also reproduces on clean HEAD.

## Out of scope

- **Editing `skills/pairmode/templates/docs/cer/backlog.md.j2`.** Removing or
  reshaping the placeholder row would fix nothing for the repos already
  scaffolded with it (the whole migration fleet), and would leave rendered
  backlogs with an empty table body. The template is the *specification* of the
  row shape this story teaches the guard to tolerate; Ensures 11 pins it
  byte-identical.
- **`cer.py`'s `_TABLE_ROW_RE` and the unreachable-branch question.** That the
  placeholder skip in `_parse_entries_from_backlog` can never fire today is
  recorded here as recon, not repaired. Any change to the row regex risks the
  CER append/ID-sequencing path and belongs in its own story.
- **The other two pre-checkpoint guards.** `_check_phase_completion` and
  `_run_build_gate_subprocess` are untouched.
- **Repo-C's CER-C004 and any consumer-repo remediation.** Repo-C's operator
  already deleted the row by hand; closing C004 in Repo-C's backlog and
  re-syncing the fleet is Phase 106 campaign work, not this story.
- **INFRA-293's grammar reconciliation and INFRA-295's snapshot targeting** —
  sibling Phase 112 stories, disjoint files.
- **Any `SCHEMA_VERSION` bump or action-grammar change.** The Position dict, the
  action vocabulary, and `resolve_next_action`'s routing table are all unchanged;
  only the truth value of guard 2 for placeholder-only backlogs differs.

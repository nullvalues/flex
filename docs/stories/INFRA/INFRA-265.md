---
id: INFRA-265
rail: INFRA
title: Thread an explicit phase key through record-checkpoint-step and checkpoint-tag (CER-077)
status: complete
phase: "104"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/next_action.py
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_record_checkpoint_step.py
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_flex_build_current_phase.py
  - tests/pairmode/test_templates.py
  - docs/stories/INFRA/INFRA-265.md
---

## Context

`record-checkpoint-step checkpoint-tag` is the single most destructive write in
the build loop: it resets `state.json["checkpoint_step"]` **and** flips a row in
`docs/phases/index.md` to `complete`. It has never been told *which* phase it is
closing. `_record_checkpoint_step` (`flex_build.py:2128`) calls
`resolve_current_phase(project_dir)` and marks whatever that returns — a
read-model whose contract is "the FIRST index row that is not inactive and whose
phase file exists". When the index holds more than one candidate row, "first"
is a heuristic, not a fact.

**CER-077's live hit:** on 2026-07-23 the `fold-prep` index carried phase-97 and
phase-98 both flagged `active`. Phase 98's `checkpoint-tag` resolved to
phase-97 — the still-in-progress fold, blocked on RELEASE-058 — and marked it
complete as a side effect of tagging 98. Caught by hand and reverted in commit
`c6c2c6a`. Nothing in the code noticed; the wrong-phase write is indistinguishable
from a correct one after the fact.

**The ambiguity is live again right now, in a second shape.** `docs/phases/index.md`
currently has phases 104, 105, 106, 107 and 108 all `planned`, each with a phase
file on disk. `resolve_current_phase` picks 104 because it is first. That happens
to be right today and would be silently wrong the moment a phase is built out of
index order, or a row is hand-edited, or 104's row is marked complete before the
tag call — three states this repo has already produced at least once each. A
five-candidate index and a function documented to pick the first one is exactly
the CER-077 condition, minus the luck.

**INFRA-260 (phase 102) already put the missing fact in the file.** Closing
CER-083, it made `_record_checkpoint_step` stamp `state.json["checkpoint_phase"]`
with the resolved phase key on **every** call, in the same atomic write as the
step append, and reset it to `""` on the terminal step. So by the time
`checkpoint-tag` runs, the three gate steps of that same checkpoint have already
recorded the phase key — recorded *while that phase was unambiguously the active
one*, before any tagging or index mutation. That stamp is a better source of
truth than a fresh re-derivation, and the fix is largely to **consume what is
already there** rather than re-derive. What INFRA-260 did not do — and explicitly
listed in its `## Out of scope` — is remove the re-derivation itself. That is
this story.

**The shape of the fix, and why it is precedence rather than a single source.**
An explicit `--phase-key` passed by the caller is the only source that carries
operator intent; the stamp is the only source recorded while the phase was
provably active; re-derivation is a guess. So: explicit key first, stamp second,
re-derivation third **and only when it is unambiguous**, and a loud non-zero
exit with no write when none of the three yields a single answer. Conflicting
sources (an explicit key that disagrees with the stamp) also error — two
disagreeing answers is strictly less trustworthy than none, and picking either
one is the CER-077 failure mode wearing a different hat.

**Why `--phase-key` is optional and not required.** `record-checkpoint-step` is
a fleet CLI: every downstream project's bootstrapped `CLAUDE.build.md` calls it
without the flag, and era 003's additive-until-flip contract (`docs/eras/003…` §
Versioning) forbids breaking those signatures. An optional flag plus a precedence
chain that errors rather than guesses gives the same guarantee — the wrong phase
can never be marked complete — without breaking a single existing call site.
flex's own loop doc and the fleet template are both updated to pass it, so the
strong path becomes the default path.

**And the read-model itself.** CER-077's second fix direction is to make
`resolve_current_phase` deterministic-or-erroring rather than silently picking.
This story does that for the case CER-077 actually observed — **more than one row
flagged `active`** — and deliberately *not* for multiple `planned` rows, because
a queue of planned future phases is the normal, correct steady state of every
index in the fleet (this one included: 105–108) and raising there would break
`next-action` on every project. Two rows claiming `active` is never correct; it
is a corrupt index, and the resolver must say so instead of choosing. The
multi-`planned` ambiguity is handled where it actually causes harm — at the
irreversible mark-complete write — by the precedence chain above, not by
crippling the read-model.

## Requires

- INFRA-260 is complete (phase 102): `_record_checkpoint_step` writes
  `state.json["checkpoint_phase"]` in the same atomic write that appends the
  step, resets it to `""` on the terminal step, and
  `next_action.infer_position` reads it to discard a checkpoint list stamped for
  a different phase.
- `skills/pairmode/scripts/flex_build.py` exposes, at the line numbers current
  at spec time: `resolve_current_phase` (559), `_parse_index_phases` (~520),
  `_mark_phase_complete_in_index` (716), `cmd_current_phase` (637),
  `cmd_next_action` (1800), `cmd_resolver_state` (~2020),
  `cmd_checkpoint_report` (2164), `_record_checkpoint_step` (2072) and
  `cmd_record_checkpoint_step` (2287).
- `skills/pairmode/scripts/next_action.py` exposes `_resolve_active_phase` (534)
  — which imports `_parse_index_phases` and `resolve_current_phase` from
  `flex_build` — and `infer_position` (600), which calls it at line 656.
- `skills/pairmode/scripts/index_integrity.py` exposes
  `is_phase_inactive(status)` returning True for `complete`/`deferred`/`backlog`
  only.
- `docs/phases/index.md` exists, with phase 103 `complete` and phases 104–108
  `planned`, each having a `docs/phases/phase-<key>.md` file. This is the live
  layout the A5 regression test reproduces.
- `docs/cer/backlog.md` contains a `CER-077` row whose `Phase` cell reads `98`.
- Phase-104 ordering: INFRA-263 also edits `flex_build.py` and is built first
  (`docs/phases/phase-104.md` § Ordering). Rebase on the current branch tip
  before starting; if a conflict appears in `flex_build.py`, it is expected and
  resolvable — the two stories touch different functions.
- Known environmental failure inside fresh story worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story.

## Ensures

**A1. The flag exists and is optional.**
`flex_build.py record-checkpoint-step --help` output contains `--phase-key`.
Invoking `record-checkpoint-step <step> --project-dir <dir>` with **no**
`--phase-key` remains a valid invocation (no click "missing option" error) — every
existing fleet call site keeps working.

**A2. An explicit key is validated before any write.** When `--phase-key K` is
given and `docs/phases/index.md` exists but contains no row whose phase ref
equals `K`, the command exits **2**, prints a stderr message containing both `K`
and the string `--phase-key`, and writes nothing: `.companion/state.json` and
`docs/phases/index.md` are byte-identical to their pre-invocation contents.

**A3. `checkpoint-tag` resolves its phase key by a fixed precedence, and never
falls through to a guess.** In `_record_checkpoint_step`, for the terminal step:

1. `--phase-key` when supplied (after A2 validation);
2. otherwise `state.json["checkpoint_phase"]` when it is a non-empty string;
3. otherwise `resolve_current_phase`, **only when the index yields exactly one
   candidate row** — a row whose status is neither inactive per
   `is_phase_inactive` nor `complete*`, and whose `phase-<key>.md` file exists;
4. otherwise: exit **2**, no write to `state.json` and none to
   `docs/phases/index.md`, with a stderr message that lists every candidate
   phase key it found and instructs the operator to re-run with `--phase-key`.

**A4. Disagreeing sources are an error, not a choice.** When `--phase-key K` is
given, `state.json["checkpoint_phase"]` is a non-empty string, and the two
differ, the command exits **2** with no write to either file, and the stderr
message names both values.

**A5. Regression test for the live multi-`planned` layout (the whole point of
this story).** A test builds a project whose `docs/phases/index.md` mirrors the
current repo — phase 103 `complete`, phases 104, 105, 106, 107, 108 all
`planned`, all five phase files present — and whose `state.json` has **no**
`checkpoint_phase` key, then asserts both halves:

- `record-checkpoint-step checkpoint-tag --project-dir <dir>` (no flag) exits
  **2**; the index is byte-identical afterwards (no row flipped to `complete`);
  `state.json` is byte-identical (the `checkpoint_step` reset did not fire);
  stderr names all five candidate keys.
- The same fixture with `--phase-key 104` exits **0**; the 104 row reads
  `complete`; rows 105–108 still read `planned`; `checkpoint_step` is `[]` and
  `checkpoint_phase` is `""`.

**A6. The INFRA-260 stamp is consumed, so the mandated loop path needs no flag at
the tag step.** A test drives the real CLI over the A5 fixture: three gate steps
recorded with `--phase-key 104`, then `checkpoint-tag` with **no** flag. Result:
exit 0, only the 104 row is `complete`, `state.json["checkpoint_step"] == []`,
`state.json["checkpoint_phase"] == ""`. No re-derivation was needed and none
occurred.

**A7. No-index behaviour is unchanged.** With no `docs/phases/index.md` at all,
`record-checkpoint-step checkpoint-tag` still exits 0 and performs the
`checkpoint_step` reset with no mark-complete — the existing
`test_record_checkpoint_step.py::test_checkpoint_tag_noop_when_no_index` and
`test_all_four_step_ids_accepted` pass unmodified.

**A8. Non-terminal steps degrade to a warning, never an error.** For a
non-terminal step with no `--phase-key` and an ambiguous index, the command exits
**0**, stamps `checkpoint_phase` as `""`, and prints a one-line stderr warning
naming the candidate keys. Rationale, which must appear as a code comment:
nothing irreversible happens on a non-terminal step, an empty stamp is the
documented INFRA-260 backward-compatible value, and the terminal step will demand
the key anyway. With `--phase-key K` supplied, a non-terminal step stamps
`checkpoint_phase == K`.

**A9. `resolve_current_phase` errors instead of picking when two rows claim
`active`.** `flex_build.py` defines a module-level
`AmbiguousActivePhaseError(RuntimeError)`. `resolve_current_phase` raises it when
**more than one** index row has a normalised status of `active` (exact match or
`active`-prefixed, e.g. `active (paused)`) **and** whose phase file exists; the
exception message names every competing phase key and cites CER-077. Exactly one
`active` row, zero `active` rows with any number of `planned` rows, and the
no-index fallback scan all behave **exactly** as they do today — verified by the
existing `test_flex_build_current_phase.py` and
`test_next_action.py::test_resolve_current_phase_consistency` passing unmodified.

**A10. Ambiguity surfaces as a loud CLI error, never a traceback.** Each of
`current-phase`, `checkpoint-report`, `next-action`, `resolver-state` and
`record-checkpoint-step` catches `AmbiguousActivePhaseError`, prints its message
to stderr, and exits **2**. For a project whose index has two `active` rows with
files, no one of those five commands emits the string
`Traceback (most recent call last)` on stdout or stderr.

**A11. The resolver applies the same rule and still writes nothing.**
`next_action._resolve_active_phase` obtains the double-`active` verdict from the
shared helper in `flex_build` (no second copy of the row walk), so
`infer_position` raises `AmbiguousActivePhaseError` rather than picking one. The
exception propagates out of `infer_position` — it is not swallowed by the
`except Exception` around the `checkpoint_step` state read (`next_action.py:842`),
whose scope stays limited to reading `state.json`. `next_action.py` performs no
writes.

**A12. Both loop docs pass the key.** `CLAUDE.build.md` § Checkpoint and
`skills/pairmode/templates/CLAUDE.build.md.j2` § Checkpoint each show
`--phase-key <phase-key>` on the gate-step `record-checkpoint-step` call *and* on
step 1 of the checkpoint-tag sequence, and state in one clause that the key is
what stops the wrong phase being marked complete (CER-077). Neither file gains or
loses a `##`-level heading (drift-report granularity — INFRA-260 B3), and
`grep -c 'flex-harness' skills/pairmode/templates/CLAUDE.build.md.j2` still prints
`0`.

**A13. Documentation records the contract.** `docs/architecture.md`:
(a) the `state.json` `checkpoint_phase` and `checkpoint_step` state-ownership
rows (lines ~1482–1483) name `--phase-key` as the primary source and state the
A3 precedence chain and the error-on-ambiguity rule; (b) the
`record-checkpoint-step` / checkpoint-tag prose near line 536 states the
precedence, the exit-2 behaviour, and that no partial write occurs; (c) the
`resolve_current_phase` contract records that >1 `active` row raises
`AmbiguousActivePhaseError` while multiple `planned` rows do not, with the
rationale from `## Context`.

**A14. CER-077 is closed in place.** The `CER-077` row in `docs/cer/backlog.md`
carries a `**Resolved by INFRA-265 (Phase 104):**` note describing both halves
(explicit `--phase-key` + stamp-consuming precedence chain that errors rather
than re-deriving; `resolve_current_phase` raising on >1 `active` row) and naming
the regression tests. Its `Phase` cell reads `104`. The row is not deleted or
moved — `docs/cer/backlog.md:6` ("Findings are not deleted — resolved findings
remain in place with a resolution note").

**A15. The suite is green.** `uv run pytest tests/pairmode/` passes, except the
known CER-090 worktree-environmental failure named in `## Requires`.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Do not create a git tag, do not push, and run no command against
`/mnt/work/flex-harness`.

1. **Add the shared candidate helper** to `flex_build.py`, next to
   `resolve_current_phase`. Define
   `AmbiguousActivePhaseError(RuntimeError)` at module level and a pure helper
   — suggested `_active_phase_candidates(project_dir) -> list[tuple[str, str]]`
   — that returns `(phase_ref, status)` for every index row that is not inactive
   (`index_integrity.is_phase_inactive`, plus the existing
   `startswith("complete")` guard) **and** whose `docs/phases/phase-<ref>.md`
   exists. One row walk, reused by everything below; do not add a second index
   parse anywhere.

2. **Make `resolve_current_phase` raise on double-`active`.** Using the helper,
   count candidates whose status is `active` or `active`-prefixed. If more than
   one, raise `AmbiguousActivePhaseError` with a message naming every competing
   key and citing CER-077. Otherwise return the first candidate's file exactly as
   today. Do **not** raise on multiple `planned` rows — 105–108 are planned right
   now and the whole fleet resolver depends on first-planned-wins staying
   deterministic. Put that reasoning in the docstring, not just the diff.

3. **Add `--phase-key` to `cmd_record_checkpoint_step`** as an optional
   `click.option` (`default=None`, `type=str`, help text naming CER-077), and
   thread it into `_record_checkpoint_step(step_id, project_dir, phase_key=None)`.
   Keep the positional `step_id` argument and `--project-dir` unchanged.

4. **Rewrite the key resolution inside `_record_checkpoint_step`.** Order the
   logic so that *every* validation and ambiguity check happens **before** the
   atomic state write and before `_mark_phase_complete_in_index` — an exit-2 path
   must leave both files byte-identical (A2/A4/A5). Concretely:

   - If `phase_key` is given and an index exists, verify a row with that ref
     exists (`_parse_index_phases`); if not → stderr + return 2 (A2).
   - Read the existing `state.json` (as today) and its `checkpoint_phase` stamp.
     If `phase_key` is given, the stamp is a non-empty string, and they differ →
     stderr naming both + return 2 (A4).
   - Resolve the effective key by the A3 precedence. Wrap the
     `resolve_current_phase` fallback in `try/except AmbiguousActivePhaseError`
     → stderr + return 2 (A10). For the fallback, use
     `_active_phase_candidates`: exactly one candidate → use it; zero candidates
     or no index → effective key `""`; more than one candidate → for the
     terminal step, stderr listing all candidate keys + `--phase-key` instruction
     + return 2 (A3.4); for a non-terminal step, warn on stderr, use `""`, and
     continue (A8).
   - Keep the idempotent early return (step already present → 0, no write) ahead
     of all of this, unchanged.
   - Terminal step: call `_mark_phase_complete_in_index(effective_key, …)` only
     when `effective_key` is non-empty, then reset `checkpoint_step` to `[]` and
     `checkpoint_phase` to `""` in the same atomic write, exactly as INFRA-260
     left it. A `False` return from `_mark_phase_complete_in_index` after A2
     validation means "already complete" and is benign — do not treat it as an
     error.

   Delete the "no phase key is threaded through the CLI args" sentence from the
   `_record_checkpoint_step` docstring (`flex_build.py:2090`); it becomes false
   with this story.

5. **Surface the exception at the CLI boundary** (A10). Add a small internal
   helper (e.g. `_resolve_current_phase_or_exit(project_path)`) that catches
   `AmbiguousActivePhaseError`, echoes the message to stderr and
   `sys.exit(2)`, and use it in `cmd_current_phase` and `cmd_checkpoint_report`.
   For `cmd_next_action` and `cmd_resolver_state`, wrap the `infer_position(…)`
   call in the same try/except. Never let the exception reach click's default
   handler — an operator staring at a traceback will not read the phase keys out
   of it.

6. **Keep the resolver consistent** (A11). In `next_action._resolve_active_phase`,
   import and call the shared `_active_phase_candidates` from `flex_build` (it
   already imports `_parse_index_phases` and `resolve_current_phase` from there)
   and apply the same >1-`active` raise. Do not duplicate the walk, do not catch
   the exception inside `next_action.py`, and do not widen the
   `except Exception` at line 842 — its job is tolerating an unreadable
   `state.json`, and swallowing an ambiguity error there would reintroduce a
   silent pick. Update the module docstring's contract notes (the block around
   lines 72–94 that already documents `checkpoint_phase`).

7. **Tests.**
   - `tests/pairmode/test_record_checkpoint_step.py` — extend the `_setup_project`
     helper (or add a sibling) that also writes an index and phase files, then
     add: A1 (`--help` contains `--phase-key`, and a no-flag invocation still
     works), A2, A4, A5 (both halves — build the index with 103 `complete` and
     104–108 `planned`, all five files present; assert byte-identity of both
     files on the exit-2 path via a pre/post `read_bytes()` comparison), A6
     (drive all four steps through `CliRunner` in sequence), A8 (non-terminal +
     ambiguous → exit 0, `checkpoint_phase == ""`, warning on stderr). A7 is
     covered by the existing tests, which must not be edited.
   - `tests/pairmode/test_flex_build_current_phase.py` — A9: two `active` rows
     with files → `resolve_current_phase` raises `AmbiguousActivePhaseError` and
     the `current-phase` CLI exits 2 with both keys on stderr and no traceback;
     one `active` row plus four `planned` rows → returns the `active` one; zero
     `active` plus five `planned` → returns the first planned (unchanged
     behaviour).
   - `tests/pairmode/test_next_action.py` — A11: a two-`active` index makes
     `infer_position` raise, and `next-action --json` exits 2 without a
     traceback. Follow the existing `TestResolveNextActionCheckpoint` pattern
     (real project dir on disk, assert through `infer_position` /
     `resolve_next_action`, not a synthetic position dict).
   - `tests/pairmode/test_templates.py` — A12: the rendered `.j2` contains
     `--phase-key` in its `## Checkpoint` section and contains no `flex-harness`.

8. **Docs** — apply A13 to `docs/architecture.md` and A14 to
   `docs/cer/backlog.md` (append the resolution note to the existing CER-077
   Finding cell; set its `Phase` cell to `104`; leave the row in place).

9. **Ideology note (Step 4a — resolved inline, no conflict).** Three points
   shaped this spec. *"Never silently pass contradictions"* is the whole story:
   two sources disagreeing about which phase is being closed is a contradiction,
   and A4/A3.4 make it exit 2 rather than resolve it by precedence — the
   constraint's rationale is that a system which misses contradictions gives
   false confidence, which is worse than no system. *"Rationale-bearing decisions
   over bare rules"* is why steps 2 and 4 require the "planned rows do not raise"
   reasoning to live in the docstring: a future agent reading only the rule would
   reasonably "tidy" it into raising on any multi-candidate index and break every
   project in the fleet. *"Sidebar owns all state writes"* is preserved by keeping
   `record-checkpoint-step` the sole writer of both `checkpoint_step` and
   `checkpoint_phase`; step 6 explicitly forbids the tempting shortcut of having
   the resolver clear or repair a stamp it observes.

## Tests

Run from the story worktree root. Targeted first:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_record_checkpoint_step.py \
  tests/pairmode/test_flex_build_current_phase.py \
  tests/pairmode/test_next_action.py \
  tests/pairmode/test_next_action_compose.py \
  tests/pairmode/test_flex_build_checkpoint_report.py \
  tests/pairmode/test_templates.py -q 2>&1 | tail -30
```

Then the full suite, **without `-x`** so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable assertions the reviewer may run directly:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  record-checkpoint-step --help | grep -c -- --phase-key      # must be >= 1
grep -c 'flex-harness' skills/pairmode/templates/CLAUDE.build.md.j2   # must print 0
grep -c -- '--phase-key' CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2
```

Acceptance:

- every new test from `## Instructions` step 7 passes, in particular the A5
  five-`planned`-row case in both its exit-2 and its `--phase-key 104` halves;
- the pre-existing `test_record_checkpoint_step.py` cases —
  `test_all_four_step_ids_accepted`, `test_checkpoint_tag_noop_when_no_index`,
  `test_checkpoint_tag_marks_active_phase_complete_in_index`,
  `test_non_terminal_steps_do_not_touch_index`,
  `test_sequential_appends_accumulate_then_reset_on_terminal_step` — pass
  **unmodified**, and so do INFRA-260's three `checkpoint_phase` stamp
  regressions in `test_next_action.py`;
- `test_next_action_compose.py`, which asserts `resolve_current_phase` is
  composed rather than reimplemented, still passes;
- the full suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if
  it appears, state that it reproduces on clean `HEAD` and is unrelated.

Documentation-only assertions (A12, A13, A14) are verified by the reviewer from
the diff.

Note for `spec-preflight`: `--phase-key`, `AmbiguousActivePhaseError` and
`_active_phase_candidates` do not exist in the codebase yet — they are created by
this story, and any preflight finding naming them is expected.

## Out of scope

- **Making `--phase-key` required.** It stays optional; every downstream
  project's bootstrapped loop calls the command without it, and era 003's
  additive-until-flip contract keeps existing CLI signatures working. The
  precedence chain, not a required flag, is what delivers the guarantee.
- **Raising on multiple `planned` rows in `resolve_current_phase`.** Argued in
  `## Context`; a queue of planned phases is the correct steady state of every
  index in the fleet. Ambiguity is caught at the irreversible write instead.
- **Auto-repairing a double-`active` index.** The commands report and stop. A
  writer that "fixes" the index would be a second writer of phase status and is
  precisely the class of silent correction that produced CER-077.
- **Adding a double-`active` invariant to `index_integrity.py` / `check-index`.**
  Worth having, cheap, and a genuinely separate surface with its own violation
  format and tests — file it rather than fold it in.
- **The `mark-phase-complete` standalone CLI.** It already takes an explicit
  `--phase` and is not affected.
- **The observability API/SPA** (`ui/`, the Fastify routes) — nothing there
  invokes `record-checkpoint-step`, and an exit-2 path from a CLI it does not
  call needs no rendering.
- **The flex-harness release channel** (INFRA-260's promotion step). Unchanged;
  this story neither promotes nor documents it further.
- **CER-071/CER-073 (INFRA-263), CER-091 (INFRA-264), CER-088/089/016
  (INFRA-266), CER-082 (INFRA-267), CER-074/076 (INFRA-268)** — sibling phase-104
  stories, each with its own file surface.
- **Any new persistent schema object.** `checkpoint_phase` remains a key in the
  existing `.companion/state.json`, not a table; `schema_introduces: false`
  stands and no management-surface row is owed.

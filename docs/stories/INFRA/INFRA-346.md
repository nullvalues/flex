---
id: INFRA-346
rail: INFRA
title: Unify the two phase-completion definitions so the resolver's own gate is at least as strict as checkpoint-tag's deferral gate
status: complete
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/era_transition.py
touches:
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_checkpoint_routing.py
  - tests/pairmode/test_flex_build_mark_phase_complete.py
  - tests/pairmode/test_record_checkpoint_step.py
  - tests/pairmode/test_era_transition.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F13 of `docs/build-loop-cold-eyes-review-20260801.md` (opus): two disagreeing
definitions of "phase complete" exist, and the checkpoint sequence's own ordering lets the weaker
one gate all the expensive work before the stronger one gets a chance to refuse. The resolver's
own phase-completion guard (`next_action._check_phase_completion`) reads only the phase doc's
Stories table, accepting `complete`/`deferred` with no requirement that a `deferred` row actually
have a `## Deferred stories` section. The `checkpoint-tag` step's deferral gate
(`flex_build._deferral_gate_message`, built by INFRA-314) reads story-file frontmatter and
requires `index_integrity.is_formally_deferred` — the stronger, correct check. But
`CLAUDE.build.md`'s mandated order calls `record-checkpoint-step checkpoint-tag` directly after
`checkpoint-report`, without re-polling `next-action` first — so a phase with a story that's
`complete`/`deferred` in the table but missing/wrong in its own frontmatter still gets all three
checkpoint workers (security/intent/docs) spawned and their results recorded before the terminal
step finally refuses. Correct outcome, but only after the expensive part already ran.

Fix direction: make `_check_phase_completion` consult the same `is_formally_deferred` predicate
`_deferral_gate_message` already uses (both should share one definition, not two), so the weaker
check can no longer diverge from the stronger one and the resolver refuses to dispatch
`checkpoint-security` in the first place when a story's own frontmatter disagrees with its
phase-table row.

**Folded in (era 004's own goal is zero unresolved operational findings, not "later" — same
checkpoint/era-completion subsystem this story is already touching):**

- **CER-154 (LOW):** era-ledger flip failures are silently swallowed — `_flip_era_ledger_row`'s
  `"not_found"` return value is computed and discarded by its caller, so `checkpoint-tag` can
  silently leave the era ledger stale while the phase-index flip succeeds; compounded by the search
  being restricted to `status: active` era docs, so re-tagging a phase from an already-closed era
  silently skips the ledger entirely. Separately, `era_transition`'s disposition gate fails open on
  any unparseable `## Phases` ledger table (no cells matching exactly `phase`/`status` → vacuous
  `[]` → the gate passes and "Era N closed" prints over live, un-dispositioned phases). Surface
  `"not_found"` as a real error/warning instead of discarding it, and make the disposition gate
  fail *closed* (refuse) rather than open on an unparseable ledger.
- **CER-155 (LOW):** `docs/phases/index.md`'s `Tag` column is never mechanically written by any
  tool — rows 8-105 carry hand-written `· cpNN` suffixes, rows 106-116 carry none despite
  `cp-106`..`cp-116` all existing. Have `checkpoint-tag`'s mark-complete step also write the `Tag`
  cell, and have it verify the tag actually exists (git-side) before declaring the step done, so a
  failed `git tag && push` after a successful mark-complete is detectable rather than silently
  idempotent-and-useless on retry.
- **CER-158 (LOW):** `record-checkpoint-step` without an explicit `--phase-key` degrades ambiguity
  (one active phase plus queued `planned` rows — the common case) to a warning and stamps the step
  under key `""`, invisible to the keyed-shape resolver read — the same gate step can re-emit
  indefinitely. Since this story is already unifying the phase-completion checks, make this case a
  hard refusal (matching the "fail closed on ambiguity" spirit of CER-154's disposition-gate fix)
  rather than a silent no-op key.

## Requires

Re-verified against the working tree at spec time (2026-08-02, `main`). A builder finding any
anchor moved should re-locate by symbol name, not line number, and note the drift in its report.

- **INFRA-339 and INFRA-340 are both merged** (`git log --oneline` shows
  `feat(story-INFRA-339): remove unreachable, session-scoping-unsafe pause-context Row-8 check` and
  `feat(story-INFRA-340): wire checkpoint-security/checkpoint-intent model selectors, remove
  dangling gate-worker meta`). Both touched `next_action.py`'s Row 8/Row 9 region per the phase
  doc's Ordering section; this story builds after both, on the landed shape, not a mid-phase
  snapshot.
- `next_action._check_phase_completion(active_phase_file)` (`:588-626`) currently takes exactly one
  parameter and reads only the phase doc's `## Stories` table via `split_table_row`; it has no
  awareness of story-file frontmatter or `index_integrity.is_formally_deferred`.
- `next_action.check_checkpoint_guards(project_dir, active_phase_file, *, gate_fn=None)`
  (`:758-817`) is the sole caller of `_check_phase_completion`, at `:789`, and already resolves a
  `project_path` at `:785` — the object this story threads through.
- `next_action.py`'s Row 9 block (`:1604-1661`) is the sole caller of `check_checkpoint_guards`,
  and already computes `_project_dir` at `:1607` from `active_phase_file.parent.parent.parent`
  before calling it at `:1609-1613`.
- `index_integrity.is_formally_deferred(status, story_id, phase_text)` (`:100-115`) is the single
  shared predicate: `status == "deferred"` AND `story_id` is named inside the phase doc's
  `## Deferred stories` section (via `_deferred_section_text`, `:82-97`).
- `flex_build._deferral_gate_message(phase_key, project_dir)` (`:3864-3924`) is the existing
  correct consumer: it `rglob`s `docs/stories/**/*.md`, filters to stories whose frontmatter
  `phase:` equals `phase_key`, and for each non-`complete` status calls `is_formally_deferred`
  against the phase doc's own text. This story's fix mirrors that scan shape inside
  `_check_phase_completion` rather than re-deriving a different one.
- `flex_build._flip_era_ledger_row(text, phase_key)` (`:1818-1881`) returns
  `("not_found", None)`-shaped tuples (`(None, "not_found")`) that its sole caller,
  `_mark_phase_complete_in_era_ledger` (`:1884-1988`), currently discards at `:1961-1966` — `matches`
  only ever collects non-`"not_found"` results, and `if not matches: return False` cannot
  distinguish "no active era docs" from "every active era doc's ledger was searched and none had
  this phase's row".
- `era_transition._phase_ledger_gate_message(era_path, era_text)` (`:108-133`) calls
  `index_integrity._parse_era_phase_table(era_text)` (`:127-196`), which returns `[]` both when no
  `## Phases` heading exists at all (legitimate — a legacy/first era with no ledger yet) and when a
  `## Phases` heading exists but no row has both a matching `phase`/`status` header pair
  (malformed table). Both currently produce `undispositioned == []` → the gate passes.
- `flex_build._mark_phase_complete_in_index(phase_key, project_dir)` (`:1731-1802`) rewrites only
  `cells[2]` (the Status cell) of the matching `docs/phases/index.md` row; `cells[3]` (Tag, when
  present) is read but never written. `flex_build._run_git(args, cwd, timeout=120)` (`:255-270`) is
  the existing shared git-subprocess helper (`subprocess.run(["git", *args], ...)`, captured,
  non-raising) this story reuses for the tag-existence check rather than inventing a second one.
- `flex_build._record_checkpoint_step` (`:3927-4254`)'s A3 phase-key resolution
  (`:4098-4128`) calls `_active_phase_candidates(project_dir)` (`:1511-1548`), which returns every
  index row that is **not** `is_phase_inactive` (i.e. includes `planned` rows, not just `active`
  ones) with an existing phase file — so in the live index today (`docs/phases/index.md`, phases
  117 `planned` and 118 `planned` both with existing files, no row currently `active`), an
  unflagged `record-checkpoint-step` call resolves 2 candidates, which is exactly the "ambiguous"
  branch at `:4114-4128` — currently a warning + `effective_key = ""` for a non-terminal step, a
  hard `return 2` only for the terminal step.
- `docs/architecture.md:1114-1126` (§ "Deferral/disposition gates at both boundaries") and
  `docs/architecture.md:2659,2661` (the `checkpoint_phase`/era-ledger state-table rows) are the
  documented-architecture passages this story's behaviour changes touch; both are amended, not
  left stale (Step 4a — "rationale-bearing decisions over bare rules": the doc must say what
  changed and why, not just leave the old prose to mislead the next reader).
- Baseline: `main`'s suite is green as of spec time. Run the full suite **once without `-x`**
  before merging (project convention) so a pre-existing failure cannot mask a new one.

## Ensures

### A — `next_action._check_phase_completion` unified with `is_formally_deferred` (F13, main fix)

**A1.** `_check_phase_completion` gains a second parameter,
`project_dir: "Path | None" = None`, defaulting to `None` so every existing call site that does not
pass it keeps today's table-only behaviour byte-identical (back-compat for isolated unit tests that
construct a bare phase file with no sibling `docs/stories/` tree).

**A2.** When `project_dir` is not `None`: before scanning the Stories table, the function derives
`phase_key` from `active_phase_file` the same way `next_action.py` already derives it elsewhere
(`Path(active_phase_file).stem`, stripped of a leading `"phase-"`), then `rglob`s
`project_dir/docs/stories/**/*.md`, reading each file's frontmatter via
`schema_validator._parse_frontmatter` (lazy import, matching this module's existing pattern at
`:579`), and builds a `{story_id: status}` map restricted to stories whose frontmatter `phase:`
equals `phase_key` — the same restriction shape `flex_build._deferral_gate_message` already applies
(Requires). This is computed once per call, not once per table row.

**A3.** For every Stories-table row whose status cell is `"deferred"` (case-insensitive, matching
existing normalisation): when `project_dir` is `None`, behaviour is unchanged (a bare `"deferred"`
cell still counts as complete-for-guard-purposes — A1's back-compat). When `project_dir` is given,
the function looks up the row's ID (`cols[0]`) in the frontmatter map from A2:

- If the ID is absent from the map (no story file's frontmatter names this phase, or the ID was
  never found under `docs/stories/`), the row **fails** the guard (`_check_phase_completion`
  returns `False`) — a table `deferred` claim that cannot be corroborated against any story's own
  frontmatter is a contradiction, not a pass (ideology § Accepted constraints, "Never silently pass
  contradictions").
- If the ID is present, `index_integrity.is_formally_deferred(frontmatter_status, story_id,
  phase_text)` is called against the same `phase_text` this function already read for the table
  scan (imported lazily: `from index_integrity import is_formally_deferred`). A `False` result
  (frontmatter status isn't `"deferred"`, or the ID is not named inside the phase doc's own
  `## Deferred stories` section) makes the row fail the guard.

The forbidden proxy this closes: a phase-table cell reading `deferred` with no corroborating
frontmatter, or with frontmatter that itself says something else (e.g. `status: draft`), no longer
silently passes `_check_phase_completion` while `_deferral_gate_message` would refuse the identical
phase at `checkpoint-tag`.

**A4.** `"complete"` rows are **not** re-verified against frontmatter by this story — only
`"deferred"` rows gain the frontmatter cross-check. (`_deferral_gate_message`'s own `"complete"`
short-circuit at `flex_build.py:3908-3909` is the existing precedent: a `complete` status is trusted
without further disposition-section lookup on either side.)

**A5.** `check_checkpoint_guards` (`next_action.py:758-817`) passes its already-resolved
`project_path` into `_check_phase_completion` at its call site (`:789`), so Row 9's checkpoint
dispatch (`next_action.py:1604-1661`) now benefits from A1-A4 with no further change to Row 9
itself — `_project_dir` is already computed there (Requires).

**A6.** A phase whose `## Stories` table has a story `deferred` in the table but whose own
frontmatter disagrees (wrong status, or missing from the `## Deferred stories` section) now stops
at `check_checkpoint_guards`'s Guard 1 (`failed_guard: "phase-incomplete"`) — `checkpoint-security`
is never dispatched for that phase. Forbidden proxy: a run that still spawns
`checkpoint-security`/`checkpoint-intent`/`checkpoint-docs` for such a phase before failing later at
`checkpoint-tag`'s exit code 4.

### B — `_mark_phase_complete_in_era_ledger` surfaces `"not_found"` (CER-154, part 1)

**B1.** `_mark_phase_complete_in_era_ledger` (`flex_build.py:1884-1988`) distinguishes, among its
currently-`active` era docs, those whose `_flip_era_ledger_row` call returned `"not_found"` from
those it collected into `matches`. When `matches` ends up empty **and** at least one active era doc
returned `"not_found"` for `phase_key` (i.e. active era docs exist but none of their `## Phases`
ledgers contain this phase's row), the function echoes one `warning:` line to stderr naming
`phase_key`, the searched era doc filenames, and CER-154, before returning `False` — the forbidden
proxy this closes is the prior behaviour, where "no active era docs at all" and "active era docs
exist but the row is nowhere in them" were indistinguishable silent `False` returns.

**B2.** The warning names, as one plausible cause, that the phase may belong to an already-closed
era doc's ledger (the second half of CER-154's finding) — but this story does **not** widen the
search to inactive era docs; see § Out of scope.

**B3.** `_mark_phase_complete_in_era_ledger`'s existing return contract is otherwise unchanged: still
returns `True` only when at least one write happened, still a silent no-op (no warning) when
`docs/eras/` is absent or no era doc is `status: active` — B1's new warning fires **only** on the
specific "active docs exist, all say not_found" case.

### C — `era_transition`'s disposition gate fails closed on an unparseable ledger (CER-154, part 2)

**C1.** `era_transition._phase_ledger_gate_message` (`era_transition.py:108-133`) gains a check: when
`index_integrity._parse_era_phase_table(era_text)` returns `[]` (no rows) **and** a `## Phases`
heading (or its qualified variant, e.g. `## Phases (...)`) is present in `era_text`, the gate
returns a refusal message distinct from the undispositioned-phase message — naming the era doc,
stating that the `## Phases` heading is present but no row could be parsed from its table, and
that the era-transition is refused rather than proceeding on an unparseable ledger (CER-154). The
heading detection is a small regex (`re.compile(r"^##\s+Phases\b", re.MULTILINE)`) added locally to
`era_transition.py`, deliberately duplicated rather than importing `flex_build._is_era_ledger_heading`
— matching the existing duplication precedent that module's own docstring records (Requires; avoids
a new `era_transition.py` → `flex_build.py` module dependency for two tokens).

**C2.** When `[]` is returned **and no** `## Phases` heading is present at all, behaviour is
**unchanged** — a legacy/first era genuinely without a ledger yet still closes without refusal. C1
must not regress this legitimate case (a test pins it, § E).

**C3.** `era_transition_cli` is unaffected beyond consuming C1's new refusal message the same way it
already consumes the undispositioned-phase one (`:214-217`) — no write happens on either refusal
path; `_close_era_frontmatter` stays unreached.

### D — `checkpoint-tag`'s mark-complete step writes and verifies the `Tag` cell (CER-155)

**D1.** `_mark_phase_complete_in_index` (`flex_build.py:1731-1802`) no longer returns `False`
unconditionally the instant a matched row's status is already `"complete"`. Instead, once the
matching row is located, it separately determines whether a **Tag-cell write** is warranted: it
runs `git tag --list f"cp-{phase_key}"` via the existing `_run_git` helper (`cwd=project_dir`) and
treats any non-zero exit, exception, or empty stdout as "tag does not (yet, verifiably) exist" —
never raising. When the tag **does** exist in git and the row's Tag cell (`cells[3]`, when present)
does not already contain the string `cp-{phase_key}`, the cell is rewritten to append
`" · cp-{phase_key}"` to its existing content (creating the cell if the row has fewer than 4
columns is **not** in scope — only existing 4+-column rows gain the suffix; see § Out of scope).

**D2.** The status-cell write (existing behaviour) and the Tag-cell write (D1, new) are independent:
a call may write status only, Tag only, both, or neither (fully idempotent, no I/O beyond the one
`git tag --list` check, when neither is needed). The function returns `True` when **either** write
happened, `False` when neither did. `cmd_mark_phase_complete` and `_record_checkpoint_step`'s
terminal branch (both already call this function) need no signature change to observe the new
behaviour.

**D3.** When the git-side tag does **not** yet exist (the ordinary, expected case at the moment
`record-checkpoint-step checkpoint-tag` runs — `CLAUDE.build.md`'s mandated order calls it
**before** `git tag` — see Requires/Context), the Tag cell is left exactly as it was before this
story (today's behaviour: the phase-doc link only, no `cp-<key>` suffix) — this story does not
claim to verify a tag that provably cannot exist yet at call time; it backfills the cell
opportunistically on any call (first or retry) where the tag already exists, and this is the
scoped, defensible reading of "verify the tag actually exists before declaring the step done"
given the ordering constraint (documented inline at the call site so a future reader does not
mistake the gap for an oversight).

**D4.** `test_title_and_tag_preserved` (`tests/pairmode/test_flex_build_mark_phase_complete.py`)
continues to pass unmodified: its fixture has no `.git` directory under `tmp_path`, so `_run_git`
fails/returns non-zero, D1 treats this as "tag not found", and the pre-existing
`"my-special-tag"` Tag cell is left untouched exactly as today.

### E — `record-checkpoint-step` hard-refuses on phase-key ambiguity, terminal or not (CER-158)

**E1.** `_record_checkpoint_step`'s A3 phase-key-resolution fallback (`flex_build.py:4098-4128`)
removes the `is_terminal` branch for the `len(candidates) > 1` case: **every** call (terminal or
non-terminal) with no explicit `--phase-key`, no usable `state.json["checkpoint_phase"]` stamp, and
2+ ambiguous candidate rows from `_active_phase_candidates` now echoes the existing
"ambiguous active phase" message to stderr (naming CER-077 and, per this story, CER-158) and
returns `2` — no `state.json` write, no `docs/phases/index.md` write, no era-ledger write. The
`len(candidates) == 0` and `len(candidates) == 1` branches are unchanged.

**E2.** The forbidden proxy this closes: `state.json["checkpoint_phase"] == ""` no longer gets
silently written for a non-terminal step call made against an ambiguous index — the step is now
either recorded under a real, explicit key, or not recorded at all (exit 2), never invisibly
stamped under the empty-string key the phase-keyed resolver read can never match.

**E3.** The precedence-chain docstring on `_record_checkpoint_step` (`:3986-4001`) is updated to
remove the now-false "for a non-terminal step it is only a warning ... and the stamp is left `""`"
sentence — the doc must describe the code that actually runs (Step 4a note, § Instructions).

### F — documentation and tests

**F1.** `docs/architecture.md`'s § "Deferral/disposition gates at both boundaries"
(`:1114-1126`) gains a sentence naming that `next_action._check_phase_completion` now also consumes
`index_integrity.is_formally_deferred` for `deferred`-status Stories-table rows (INFRA-346), so all
three points that decide "formally deferred" — the resolver's own pre-checkpoint guard, the
`checkpoint-tag` story→phase gate, and the `era_transition` phase→era gate — share the one
predicate.

**F2.** `docs/architecture.md:2659` (the `checkpoint_phase` state-table row) is amended to remove
the now-inaccurate "warns and stamps `""` on a non-terminal one" clause (E1/E3) — it now hard-refuses
regardless of step.

**F3.** `docs/architecture.md:2661` (the era-ledger state-table row) gains one clause naming that a
"not found in any active doc" outcome now prints a `warning:` line distinct from the pre-existing
multi-active-era warning (B1).

**F4.** New/updated tests exist for A (deferred-frontmatter agreement, mismatch, missing story,
`project_dir=None` back-compat), B (`not_found` warning), C (unparseable-ledger refusal, legacy
no-heading pass preserved), D (Tag-cell backfill when git tag exists, preserved when it does not),
E (hard refusal on ambiguity for both terminal and non-terminal steps) — see § Tests for exact
names and files.

**F5.** `tests/pairmode/test_checkpoint_routing.py::test_check_guards_deferred_stories_pass` — whose
current docstring reads `"'deferred' story status is treated as complete for the phase guard"` — is
renamed and its assertion inverted to match A3's corrected semantics: a bare `deferred` table status
with **no** corroborating story file now fails the guard (`{"ok": False, "failed_guard":
"phase-incomplete"}`); a sibling test is added asserting the **formally**-deferred case (a real
story file under the fixture's `docs/stories/` with matching `phase:` frontmatter, `status:
deferred`, and the phase file's own `## Deferred stories` section naming it) still passes
(`{"ok": True}`). This is a deliberate behaviour change, not a regression to paper over — it is F13
itself.

**F6.** `tests/pairmode/test_record_checkpoint_step.py::test_a8_non_terminal_ambiguous_step_warns_and_continues`
is renamed and its assertion inverted to match E1: the call now exits `2`, `state.json` is
byte-unchanged (no write), and the candidate rows are still named in stderr output. The sibling
`test_a8_non_terminal_step_with_explicit_phase_key_stamps_it` is unaffected (explicit `--phase-key`
given, never ambiguous) and needs no change.

## Instructions

You are the builder. Work only in this repository, inside your story worktree. Build in order
**A → E → B → C → D → F**, running the focused suite after each lettered group, then the full
suite without `-x` at the end. (A and E are grouped first because both are pure refusal-tightening
in code paths already covered by dense existing test suites — get the highest-risk behaviour
changes landed and green before the additive B/C/D work.)

**A — `_check_phase_completion`.** Add the `project_dir` parameter with `None` default. Derive
`phase_key` from `active_phase_file` using the exact `Path(...).stem` + `"phase-"` strip pattern
already used elsewhere in this file (Requires) — do not invent a second derivation. Build the
`{story_id: status}` frontmatter map once per call, before the Stories-table loop, using
`schema_validator._parse_frontmatter` (lazy import, matching this file's existing style). Add the
lookup + `is_formally_deferred` call only inside the `status == "deferred"` branch of the existing
loop; leave the `status not in ("complete", "deferred")` early-return and everything else in the
loop untouched. Update `check_checkpoint_guards` to pass `project_path` at its
`_check_phase_completion` call site. Run
`tests/pairmode/test_next_action.py tests/pairmode/test_checkpoint_routing.py -q` after this group;
fix `test_check_guards_deferred_stories_pass` per § Ensures F5 as part of this group, not later.

**E — `_record_checkpoint_step` ambiguity.** Collapse the `is_terminal` branch inside the
`len(candidates) > 1` arm of A3 (`:4114-4128`) to a single unconditional `click.echo(...); return 2`
— delete the `else: click.echo(f"warning: {message}", err=True); effective_key = ""` path entirely.
Update the docstring paragraph at `:3986-4001` per § Ensures E3 (remove the sentence describing the
now-deleted warn-and-continue behaviour). Fix
`test_a8_non_terminal_ambiguous_step_warns_and_continues` per § Ensures F6 as part of this group.
Run `tests/pairmode/test_record_checkpoint_step.py -q`.

**B — era-ledger `not_found` surfacing.** In `_mark_phase_complete_in_era_ledger`, track
`not_found_docs: list[Path]` alongside the existing `matches` accumulation in the loop at
`:1955-1963` — append to it when `status == "not_found"` instead of silently `continue`-ing past it.
After the loop, before `if not matches: return False`, add the B1 warning when `matches` is empty
and `not_found_docs` is non-empty. Do not change anything about the `len(active) > 1` warning
already at `:1942-1953` — B1 is a second, independent warning. Run
`tests/pairmode/test_flex_build_mark_phase_complete.py tests/pairmode/test_record_checkpoint_step.py -q`.

**C — `era_transition` disposition gate.** Add the module-level `_ERA_LEDGER_HEADING_RE` (or
equivalent name) to `era_transition.py` and the C1 check inside `_phase_ledger_gate_message`, after
the existing `undispositioned` check returns `None` implicitly falls through — i.e. C1's new check
only runs when `undispositioned` was already empty (rows parsed cleanly but nothing was
undispositioned, or rows is `[]`). Do not alter `_parse_era_phase_table` itself in
`index_integrity.py` — it has a second consumer (`index_integrity.py` check 2c, Requires) that must
keep receiving `[]` for both the legacy-no-heading and malformed-heading cases; the distinction
belongs only in `era_transition.py`'s gate. Run `tests/pairmode/test_era_transition.py -q`.

**D — Tag-cell write and git verification.** Restructure `_mark_phase_complete_in_index` so the
early-return-on-already-complete no longer short-circuits before the Tag-cell check runs — compute
both "does status need updating" and "does Tag need updating" before deciding whether to write at
all. Use the existing `_run_git` helper for `git tag --list f"cp-{phase_key}"`
(`cwd=project_dir`); treat any non-zero return code, raised exception, or empty stdout the same way
— "tag not found", never raising out of this function (matches this file's established
advisory-degradation style, e.g. `_run_build_gate_subprocess`'s non-timeout `except Exception`
branch). When rewriting a row for either reason, keep the existing line-by-line rewrite shape
(`new_lines`/`replaced` accumulation) — do not introduce a second table-rewrite code path. Run
`tests/pairmode/test_flex_build_mark_phase_complete.py tests/pairmode/test_record_checkpoint_step.py -q`.

**F — docs.** Make the three targeted `docs/architecture.md` edits (F1/F2/F3) as short, surgical
insertions into the existing prose — do not restructure the surrounding paragraphs. Each edit names
INFRA-346 so a future reader can find this story from the doc.

**Ideology-alignment note (Step 4a, resolved inline).** `docs/ideology.md` § Accepted constraints —
*"Never silently pass contradictions"* — is the direct rationale for § Ensures A3's fail-closed
default (an uncorroborated `deferred` table cell fails the guard rather than passing) and for
§ Ensures C1's fail-closed default on an unparseable ledger; both are phrased in Ensures using that
constraint's own vocabulary rather than a bare "make it stricter" instruction. § Core convictions —
*"rationale-bearing decisions over bare rules"* — is why § Ensures D3 records, in the story itself,
the reasoning for why "verify before declaring done" could not be implemented as a literal
before-exit git check (the mandated `record-checkpoint-step` → `git tag` ordering makes the tag
provably absent at the moment of the common-path call) rather than silently shipping a narrower
fix than the CER wording suggests and letting a future reader wonder why.

(`spec-preflight` note: `docs/ideology.md` is named above only as the source of the two quoted
constraints/convictions this story's fail-closed defaults implement — it is read, not edited, by
this story, so it is deliberately absent from `primary_files`/`touches`.)

## Tests

```bash
# Focused — A and E (next_action guard, checkpoint routing, record-checkpoint-step)
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_next_action.py tests/pairmode/test_checkpoint_routing.py \
  tests/pairmode/test_record_checkpoint_step.py -q

# Focused — B and D (mark-phase-complete / era ledger)
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_mark_phase_complete.py -q

# Focused — C (era-transition disposition gate)
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_era_transition.py -q

# Full suite — once, WITHOUT -x, so a pre-existing failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:**

- All three focused runs green, including every new/renamed test named below.
- Full suite green against the `main` baseline plus this story's changes. No new failures.

**New/updated tests required** (names indicative):

- `tests/pairmode/test_next_action.py`:
  - `test_check_phase_completion_formally_deferred_frontmatter_agrees_passes`
  - `test_check_phase_completion_deferred_frontmatter_status_mismatch_fails`
  - `test_check_phase_completion_deferred_not_named_in_deferred_section_fails`
  - `test_check_phase_completion_deferred_no_matching_story_file_fails_closed`
  - `test_check_phase_completion_project_dir_none_preserves_legacy_behaviour`
- `tests/pairmode/test_checkpoint_routing.py`:
  - rename `test_check_guards_deferred_stories_pass` →
    `test_check_guards_bare_deferred_status_without_frontmatter_fails` (assertion inverted, § F5)
  - `test_check_guards_formally_deferred_story_passes` (new, § F5)
- `tests/pairmode/test_record_checkpoint_step.py`:
  - rename `test_a8_non_terminal_ambiguous_step_warns_and_continues` →
    `test_a8_non_terminal_ambiguous_step_now_hard_refuses` (assertion inverted, § F6)
- `tests/pairmode/test_flex_build_mark_phase_complete.py`:
  - `test_mark_phase_complete_backfills_tag_cell_when_git_tag_exists`
  - `test_mark_phase_complete_leaves_tag_cell_when_git_tag_absent` (covers D4's byte-identical
    fixture behaviour explicitly, in addition to the pre-existing `test_title_and_tag_preserved`)
  - `test_mark_phase_complete_era_ledger_not_found_warns_on_stderr` (§ B1)
- `tests/pairmode/test_era_transition.py`:
  - `test_unparseable_phases_heading_refuses_close_no_write` (§ C1)
  - `test_no_phases_heading_at_all_still_allows_close` (§ C2, legacy-behaviour pin)

## Out of scope

- **Expanding `_mark_phase_complete_in_era_ledger`'s search to inactive/closed era docs.** CER-154's
  second half ("re-tagging from an already-closed era silently skips the ledger") is *named* in the
  new warning (§ Ensures B2) but not fixed by widening the search — flipping a status in a
  formally-closed era file is a write nobody has asked for and could itself corrupt a closed
  record; that is a larger, separate decision than "surface the failure".
- **Verifying the `cp-<phase_key>` git tag exists at the moment `record-checkpoint-step
  checkpoint-tag` returns.** Not achievable given `CLAUDE.build.md`'s mandated ordering (tag creation
  is step 2, after `record-checkpoint-step` is step 1) — see § Ensures D3's recorded rationale. This
  story backfills the Tag cell opportunistically on any call where the tag is already real; it does
  not add a second, later verification step to the checkpoint sequence.
- **Adding a Tag cell to a `docs/phases/index.md` row that currently has fewer than 4 columns.**
  `_mark_phase_complete_in_index` already tolerates 3-column rows (`len(cells) >= 3`); this story's
  D1 only ever appends to an *existing* 4th cell, never grows a 3-column row into a 4-column one.
- **Reformatting or auditing the entire `docs/phases/index.md` Tag column for historical rows
  (8-105 vs 106-116).** This story's fix is mechanical, forward-looking write behaviour, not a
  one-time backfill sweep of the historical rows named in CER-154's finding text.
- **CLAUDE.build.md's own prose describing the checkpoint-tag mandated order.** Unedited — the
  ordering itself (record-checkpoint-step before git tag) is the existing, correct contract this
  story's D-group works within, not something it changes.
- **Any of INFRA-336/337/338/341/342/343/345/347/348/349/350** — sibling Phase 117 stories; none of
  their findings are folded into this one.

## Evidence

Covered-contracts gate (INFRA-317): `primary_files:` includes `skills/pairmode/scripts/next_action.py`,
which matches the `covered_contracts` pair `## Module structure::skills/pairmode/scripts/next_action.py`
in `CLAUDE.build.md`'s Build standards line. Both the named doc section and the source file were
read in full before editing either.

- `docs/architecture.md`'s `## Module structure` entry for `next_action.py` (line 77) was read in
  full; it documents the module's evolution through HARNESS002-main..INFRA-341 (action grammar,
  DP2 machine, checkpoint sequencing, gate-verdict routing) but names no existing consumer of
  `index_integrity.is_formally_deferred` from `next_action.py` — confirming this story's A-group
  change (adding that consumption) is additive to the documented module contract, not a divergence
  from it. No code/doc mismatch found; § F1 amends this doc section accordingly (a short addition,
  not a correction).
- `next_action.py:588-626` (pre-story `_check_phase_completion`) was read in full and matched the
  Requires description exactly: one parameter, table-only scan via `split_table_row`, no frontmatter
  or `index_integrity` awareness.
- `next_action.py:758-817` (`check_checkpoint_guards`) was read in full; confirmed as the sole
  caller of `_check_phase_completion`, already resolving `project_path` before the call site this
  story threads it through.
- `next_action.py`'s Row 9 block (`:1604-1661` at spec time, unchanged region after the A-group
  edit) was read in full; confirmed as the sole caller of `check_checkpoint_guards`, already
  computing `_project_dir` before calling it — no further Row 9 change needed (A5).
- No divergence found between the doc section and the source file — the doc's module-structure
  entry describes `next_action.py`'s existing surface accurately; this story's change is a pure
  addition to both, applied consistently (code in A1-A5, doc in F1).

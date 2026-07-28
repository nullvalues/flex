---
id: INFRA-290
rail: INFRA
title: Data-flow checks in cold-eyes procedures and recording-state hygiene (dead keys, stale counters, permissions GC)
status: draft
phase: "110"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/reviewer/procedure.md
  - skills/pairmode/skills/security-auditor/procedure.md
  - skills/pairmode/templates/docs/phases/phase.md.j2
  - skills/pairmode/scripts/pairmode_migrate.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - docs/architecture.md
  - docs/pairmode/context-gate-flow.md
  - tests/pairmode/test_procedure_skills.py
  - tests/pairmode/test_templates.py
  - tests/pairmode/test_pairmode_migrate.py
  - tests/pairmode/test_flex_build_permissions_gc.py
  - docs/stories/INFRA/INFRA-290.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This is the last story of Phase 110 and the only one that is not a bug fix.
INFRA-287, INFRA-288 and INFRA-289 repair four specific breaks in the effort
recording pipeline. This story addresses the reason all four survived multiple
cold-eyes reviews, a security audit, an intent review and two checkpoints
without being caught, and then sweeps the residue the same blindness left
behind.

**The methodology gap.** Every one of CER-101..104 is the same shape: a
*producer/consumer mismatch* that no existing checklist item asks about.
The reviewer checklist (`skills/pairmode/skills/reviewer/procedure.md`,
items 1-12) checks hook performance, pipe contract, spec safety, skill
isolation, lessons integrity, test coverage, protected files, Python
standards, rail scope, build gate, documentation currency and ideology
drift. The security checklist
(`skills/pairmode/skills/security-auditor/procedure.md`, items 1-6) checks
hook performance, pipe contract, spec safety, credential exposure, path
traversal and layer violation. Neither ever asks "who reads this?" or "who
writes this?". So:

- `attempts.agent_id` is persisted by `set_spawn_ref` and read by **nothing**
  (CER-104) — written-never-read.
- The reconciliation terminator required last-entry `stop_reason == "end_turn"`,
  a value **no writer produces any more** (CER-101) — required-never-written.
- The same effort row was inserted twice because two independently-registered
  PostToolUse hooks both fire (CER-104), and the flat `current_story` key
  duplicates the keyed `current_stories` record — duplicate state.
- The reconcile-time FAIL bump was correct but structurally **unreachable**
  behind the containment break (CER-102) — a half-implementation.

Each was individually reviewable and individually passed. The check that
would have caught all four does not exist. This story adds it, in the two
cold-eyes procedure skills and in the phase-doc checkpoint checklist, as
four standing items: **written-never-read**, **required-never-written**,
**duplicate state**, **half-implementations**.

**The hygiene residue.** The same audit turned up three small, mechanical
messes that are the *output* of the missing check rather than instances of
it, and that are cheapest to clear now while the forcing function is present:

1. `context_story_tokens` — a state.json dict introduced by INFRA-180 and
   superseded by INFRA-182. No reader remains (`context_budget.decide()`
   stopped reading it; `set-context-tokens` stopped writing it — asserted by
   `tests/pairmode/test_flex_build_set_context_tokens.py:83` and
   `tests/pairmode/test_context_budget.py:1322`), but existing entries were
   left in place fleet-wide and `docs/architecture.md` still carries a live
   key entry for it. Textbook written-never-read, now dead on both sides.
2. Legacy-shape `attempt_counter.json` — `_read_attempt_counters`
   (`flex_build.py:1299-1341`) still normalises the pre-INFRA-282 flat shape
   (`{"story_id": ..., "attempt_count": ...}`) in memory, and
   `write_attempt_count` upgrades it only as a side effect of the next write.
   A project that has not built since INFRA-282 keeps the legacy file forever.
   The migration command that exists precisely to retire 0.2.x shapes,
   `pairmode_migrate.py to-030`, does not touch it.
3. Stranded permission artifacts — `merge-story-worktree` and
   `discard-story-worktree` already call `clear_permissions_artifact`
   (`flex_build.py:3496`, `:3559`, INFRA-238), so the *ongoing* leak is
   closed. What is not closed is the backlog: 118 files currently sit in
   `docs/phases/permissions/` in this repo (≈150 in meander), every one of
   them for a story that landed before INFRA-238 or was cleaned up by hand.
   They are inert but they are exactly the kind of sediment that makes a
   later reader unable to tell live state from residue.

**The consolidation direction.** `current_stories` (keyed) is the authority;
flat `current_story` is a derived mirror kept for a named set of readers
(`docs/architecture.md:1974-1987`). The audit's recommendation is to retire
the mirror from readers first, then from writers. That is a multi-story
change and is **not** built here — this story records the direction and the
current reader inventory in `docs/architecture.md` so the next person to
touch either key inherits the plan instead of re-deriving it. Recording the
intent is the whole point (`docs/ideology.md`, "Persistent intent over
implementation detail").

## Requires

- **INFRA-287, INFRA-288 and INFRA-289 are complete and merged**, and this
  story's worktree is cut from a `HEAD` that contains all three. This story
  is last in the phase because the data-flow checks it writes must be
  illustrated with the *fixed* code, not the broken code, and because
  INFRA-288's `hook_view.py` merged-hook view is the concrete example the
  duplicate-state check points at. Verify before building:
  `git log --oneline --grep 'INFRA-289'` returns a commit reachable from
  `HEAD`.
- `skills/pairmode/skills/reviewer/procedure.md` exists and contains
  `## Input contract (DP1.3 — input-bound property)` with a numbered list
  ending at item 8, a `## Review checklist` section whose last item is
  `### 12. IDEOLOGY DRIFT — narrow, spec-gated (INFRA-242)`, and a
  `## Review output format` section immediately after the checklist.
- `skills/pairmode/skills/security-auditor/procedure.md` exists and contains
  `## Security checklist` whose last item is `### 6. LAYER VIOLATION (HIGH if
  violated)`, followed by `## Audit scope (BUILD-041)`.
- `skills/pairmode/templates/docs/phases/phase.md.j2` exists and ends with
  `### CP-{{ _phase_key }} Cold-eyes checklist` followed by the single line
  `— developer fills in after phase completion —`.
- `skills/pairmode/scripts/pairmode_migrate.py` defines `cmd_to_030`
  (`@cli.command("to-030")`), `_load_state`, `_try_parse_json`, and the
  module constants `THIN_HARNESS_STEP_TOKENS` / `ERA2_STAMP`.
- `skills/pairmode/scripts/flex_build.py` defines
  `generate_permissions_artifact`, `clear_permissions_artifact`,
  `_attempt_counter_path`, `_read_attempt_counters`,
  `_ATTEMPT_COUNTER_STORIES_KEY`, `claimed_story_ids`, `_depth_guard`, and
  the `flex_build` Click group.
- `skills/pairmode/scripts/story_context.py` exports `get_current_stories`.
- `docs/architecture.md` contains a `context_story_tokens` bullet in the
  state.json key reference (≈ line 2005), a `current_story` bullet
  (≈ lines 1974-1987), a `permission files
  (docs/phases/permissions/<story_id>.json)` row in the state-ownership table
  (≈ line 1861), and the `flex_build.py` subcommand inventory line
  (≈ line 56).
- `docs/pairmode/context-gate-flow.md` contains a table row beginning
  `| \`context_story_tokens\` | dict |` (≈ line 198).
- `tests/pairmode/test_procedure_skills.py`,
  `tests/pairmode/test_templates.py` and
  `tests/pairmode/test_pairmode_migrate.py` all exist; the last contains a
  `to-030` test block with the helpers used at `:775-900`.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command.

### A — The four data-flow checks enter the reviewer procedure

**A1. A thirteenth checklist item exists.**
`skills/pairmode/skills/reviewer/procedure.md` gains
`### 13. DATA FLOW (INFRA-290)` immediately after item 12 and before the
`---` that precedes `## Review output format`. No existing item 1-12 is
renumbered, reworded, or deleted.

**A2. The item names all four checks with those exact labels.** Item 13's
body contains the four literal strings `written-never-read`,
`required-never-written`, `duplicate state` and `half-implementation`, each
introduced as its own bolded sub-check with (i) a one-sentence definition,
(ii) the concrete question the reviewer must answer, and (iii) a severity.
Severities are: written-never-read → **MEDIUM**; required-never-written →
**HIGH**; duplicate state with independent writers → **HIGH**;
half-implementation (a reachable-looking branch that no live input can
reach, or a producer with no consumer) → **HIGH**. A field that is dead
*and* documented as dead is **LOW**.

**A3. The check is diff-scoped, and says so.** Item 13 states explicitly that
it applies only to persistent state the diff **introduces or changes** — a
new or modified column, state.json key, on-disk file, hook registration or
CLI-visible field — and is **not** a whole-repository data-flow audit. A
diff that adds no persistent state passes with
`PASS — DATA FLOW (no persistent state introduced or changed)` and performs
no searching.

**A4. The check requires an explicit writer/reader trace.** For each item in
scope under A3, item 13 requires the reviewer to report one line naming the
**writer(s)** and the **reader(s)** it found, with `file:line` for each, and
to record `none` explicitly when a side has no site. The report line format
is given literally in the procedure so it is greppable, e.g.
`DATA FLOW: <identifier> — writers: <file:line,...> — readers: <file:line,...>`.

**A5. The input contract authorises the search, narrowly.** The
`## Input contract (DP1.3 — input-bound property)` numbered list gains a
**9th** entry permitting targeted repository searches (`grep`/`rg`/`Glob`)
over source files, scoped to identifiers the diff introduces or changes,
for this check only. The entry restates that the DP1.3 prohibition is
unchanged for **loop runtime state** — `state.json` contents, `effort.db`
records, prior-attempt transcripts, accumulated orchestrator state — and
that a code search is not a read of that state.

**A6. The forcing function is on the record.** Item 13 cites `CER-101` and
`CER-104` by ID and states in one sentence that all four sub-checks are
derived from real defects that passed items 1-12 unflagged. Naming the
origin is what stops a future editor from deleting the item as redundant.

### B — The same four checks enter the security-auditor procedure

**B1. A seventh security check exists.**
`skills/pairmode/skills/security-auditor/procedure.md` gains
`### 7. DATA-FLOW INTEGRITY (HIGH if violated; CRITICAL on silent data loss)`
as the last item of `## Security checklist`, immediately before
`## Audit scope (BUILD-041)`. Items 1-6 are unchanged.

**B2. It uses the same four labels.** Check 7's body contains the same four
literal strings as A2 (`written-never-read`, `required-never-written`,
`duplicate state`, `half-implementation`), so the two procedures cannot
drift into two different vocabularies.

**B3. Its scope is the phase diff, not the story diff.** Check 7 states that
it runs over the phase diff at checkpoint (the audit's declared input 1) and
that its purpose is the *cross-story* case the per-story reviewer cannot
see: a writer added in story N whose reader was supposed to arrive in story
N+2 and never did.

**B4. Severity is tied to data loss, not to style.** Check 7 states that a
mismatch which causes state to be **silently discarded, silently
duplicated, or silently never recorded** is CRITICAL (it is a data-corruption
risk under the procedure's own severity definition, `procedure.md:191`), and
that a merely-inert field is HIGH or below. It gives CER-104's double insert
as the CRITICAL exemplar and `attempts.agent_id` as the non-CRITICAL one.

**B5. The audit's input contract is extended in kind.** The
`## Input contract (DP1.3 — input-bound property)` list gains a fourth entry
mirroring A5 — targeted source searches scoped to identifiers in the phase
diff — with the same restatement that `state.json`, `effort.db` and
transcripts remain off-limits.

### C — The checks become a standing checkpoint item

**C1. The phase template's checklist is no longer a bare placeholder.**
`skills/pairmode/templates/docs/phases/phase.md.j2`'s
`### CP-{{ _phase_key }} Cold-eyes checklist` section renders four unchecked
markdown checkbox items — one per data-flow check, each with a
one-clause prompt — above the existing
`— developer fills in after phase completion —` line, which is retained.

**C2. The rendered output is stable and greppable.** Rendering the template
with any context produces a section containing the four literal strings from
A2 and exactly four lines beginning `- [ ] `. Asserted by a new test in
`tests/pairmode/test_templates.py`.

**C3. Existing template assertions still hold.**
`tests/pairmode/test_templates.py`'s existing phase-template classes
(`CP-1 Cold-eyes checklist` / `CP-2 Cold-eyes checklist` assertions at
`:1086` and `:1103`, and the `BOOTSTRAP-004` Schema-delivery ordering test at
`:2255`) pass unchanged, with no edit to their expected strings.

**C4. No existing phase doc is rewritten.** The diff contains no edit to any
file under `docs/phases/phase-*.md`. The template change applies to phases
scaffolded from this point forward; back-filling historical checklists would
falsify the record of what was actually checked at those checkpoints.

### D — `context_story_tokens` is retired

**D1. `to-030` removes the key.** `pairmode_migrate.py`'s `cmd_to_030` gains
a step that removes `context_story_tokens` from `state.json` when present,
following the same `[would]` / `[apply]` dry-run contract as the existing
`pipe_path` removal (`pairmode_migrate.py:947-960`) and writing via
`state_utils._atomic_write_json`. Dry-run prints
`[would] remove 'context_story_tokens' key from state.json` and changes
nothing; `--apply` prints `[apply] removed 'context_story_tokens' key from
state.json` and the key is absent afterwards. A state.json without the key is
a silent no-op.

**D2. The step is tested both ways.** `tests/pairmode/test_pairmode_migrate.py`
gains tests asserting: dry-run leaves the key present and prints `[would]`;
`--apply` removes it; a state.json lacking the key produces no output line
for it and exits 0.

**D3. Running the dry-run against this repo reports the key.**
`PATH=$HOME/.local/bin:$PATH uv run python
skills/pairmode/scripts/pairmode_migrate.py to-030 --project-dir .`
prints the `[would] remove 'context_story_tokens'` line, because flex's own
`.companion/state.json` still carries the key. The builder runs the
**dry-run only** and pastes the line into the build result; it does not run
`--apply` against the live repo (`.companion/` is gitignored, so an
`--apply` mutation would be an untracked, unreviewable side effect of a
story build).

**D4. The docs stop describing it as live state.**
`docs/architecture.md`'s `context_story_tokens` bullet (≈ line 2005) and
`docs/pairmode/context-gate-flow.md`'s table row (≈ line 198) each state
that the key is dead on both sides — no writer, no reader — and that
`pairmode_migrate.py to-030` removes it (INFRA-290). Neither entry is
deleted: the key still exists in un-migrated projects' state.json, so a
reader who finds one needs the entry to explain it.

### E — Stale legacy-shape `attempt_counter.json` is retired

**E1. `to-030` deletes a *stale* legacy counter file, and only a stale one.**
`cmd_to_030` gains a step that inspects
`.companion/attempt_counter.json`. It acts **only** when the file parses as
a dict, has **no** `stories` key, and has a string `story_id` key (the
pre-INFRA-282 flat shape, `flex_build.py:1335-1340`). For a keyed-shape file,
an absent file, or an unparseable file, it does nothing and prints nothing.

**E2. "Stale" is defined and enforced, not assumed.** The legacy file is
deleted only when its `story_id` is **not in flight**: no
`.pairmode-worktrees/<story_id>/` directory exists, and `state.json`'s
`current_stories` has no entry for it and its `current_story` mirror does
not name it. When the story **is** in flight, the file is instead **upgraded
in place** to the keyed shape
(`{"stories": {"<story_id>": <count>}}`) and a line saying so is printed.
Deleting a live counter would silently reset a running story's escalation
ladder to attempt 1 — the exact class of silent data loss this phase exists
to stop.

**E3. Both outcomes honour the dry-run contract.** Dry-run prints
`[would] delete stale legacy-shape attempt_counter.json (story <id>, not in
flight)` or `[would] upgrade legacy-shape attempt_counter.json to keyed shape
(story <id> in flight)` and writes nothing. `--apply` performs the action and
prints the `[apply]` form. Writes go through
`state_utils._atomic_write_json`; the delete is `Path.unlink(missing_ok=True)`
inside a `try/except OSError`.

**E4. Four cases are tested.** `tests/pairmode/test_pairmode_migrate.py`
covers: (a) legacy shape, story not in flight, `--apply` → file gone;
(b) legacy shape, story in flight via a `current_stories` entry, `--apply` →
file present and keyed-shape; (c) legacy shape, story in flight via a
`.pairmode-worktrees/<id>/` directory, `--apply` → file present and
keyed-shape; (d) keyed shape already → file byte-identical and no output line
emitted.

**E5. `_read_attempt_counters` is unchanged.** The diff contains no edit to
`_read_attempt_counters`, `write_attempt_count`, `read_attempt_count`,
`bump_attempt_count` or `clear_attempt_count`. Legacy-shape *reading* stays
supported — `to-030` is a deliberate, operator-invoked migration, not a
reason to break projects that have not run it.

### F — Stranded permission artifacts are collectable

**F1. A `permissions-gc` subcommand exists.** `flex_build.py` gains
`@flex_build.command("permissions-gc")` with `--project-dir` (default `.`)
and `--apply` (flag, default `False`). It calls `_depth_guard(project_path)`
like its siblings. (`permissions-gc` does not exist in the source tree today;
`spec-preflight` flagging it as unverifiable is expected and intentional —
this story creates it.)

**F2. Report by default, delete only with `--apply`.** Without `--apply` it
prints one `[would] delete docs/phases/permissions/<story_id>.json` line per
collectable artifact plus a `permissions-gc: N collectable, M retained` summary,
and deletes nothing. With `--apply` it deletes each collectable artifact and
prints `[apply] deleted ...` per file plus the same summary. This mirrors
`clear-stale-stories`' report-then-`--apply` shape (`flex_build.py:1506`)
rather than inventing a second convention.

**F3. Retention is conservative and reason-bearing.** An artifact
`docs/phases/permissions/<story_id>.json` is **retained** — never collected —
when any of: a `.pairmode-worktrees/<story_id>/` directory exists (the
INFRA-280 in-flight claim); `state.json`'s `current_stories` holds a
`<story_id>` key, or its `current_story` mirror names it; or the file name
does not parse as a story ID. Every retained file's reason is printed at
`--verbose`-equivalent detail in the summary block (one line per retained
file naming which rule retained it). Everything else is collectable.

**F4. It is pure and total.** `permissions-gc` never reads or writes
`effort.db`, never edits story files, never edits `state.json`, and exits `0`
on every path including a missing `docs/phases/permissions/` directory
(printing `permissions-gc: 0 collectable, 0 retained`), a missing
`.companion/state.json`, and an unreadable individual artifact (which is
retained, not deleted).

**F5. Behaviour is tested.**
`tests/pairmode/test_flex_build_permissions_gc.py` (new) asserts: dry-run
lists but does not delete; `--apply` deletes a collectable artifact; a
worktree-claimed artifact survives `--apply`; a `current_stories`-claimed
artifact survives `--apply`; a `current_story`-mirror-claimed artifact
survives `--apply`; a non-story-ID filename survives; a missing permissions
directory exits 0 with the zero summary.

**F6. This repo's own residue is reported, not swept.** The builder runs the
**dry-run only** against this repo and reports the collectable/retained
counts in the build result. It does **not** run `--apply` — deleting 118
files is an operator decision, and a story build must not carry an unrelated
mass deletion in its diff.

**F7. No existing command changes.** The diff contains no edit to
`generate_permissions_artifact`, `clear_permissions_artifact`,
`cmd_permissions_create`, `cmd_merge_story_worktree` or
`cmd_discard_story_worktree`. `tests/pairmode/test_cli_surface_freeze.py`
passes with no edit — its contract is superset-only, so an added command is
already allowed.

### G — Documentation

**G1. The data-flow check placement is documented.** `docs/architecture.md`
gains one short subsection (bolded-lead paragraph style, sited alongside the
existing ideology-enforcement placement prose at ≈ lines 1755-1780) recording
the three-layer placement of the data-flow checks: per-story reviewer
(diff-scoped, item 13), checkpoint security-auditor (phase-diff-scoped,
check 7), and the CP-NN phase-doc checklist (human, at checkpoint). It names
the four checks, cites `INFRA-290, CER-101, CER-104`, and states the forcing
function in one sentence. No new `##`-level heading is added.

**G2. The consolidation direction is recorded — and only recorded.**
`docs/architecture.md`'s `current_story` bullet (≈ lines 1974-1987) gains a
closing paragraph stating: `current_stories` is the authority and the flat
mirror is scheduled for retirement; the retirement order is **readers first,
then writers**; and the mirror's current reader inventory. The inventory must
be **derived by grep at build time**, not copied from this spec or from the
phase doc's audit dossier — list every site that reads `current_story` other
than `story_context.py`'s own mirror maintenance, with `file:line`. The
paragraph states plainly that no reader is retired by this story.

**G3. `permissions-gc` is in the inventories.** `docs/architecture.md`'s
`flex_build.py` subcommand line (≈ line 56) lists `permissions-gc`, and the
`permission files (docs/phases/permissions/<story_id>.json)` ownership-table
row (≈ line 1861) names `permissions-gc` as a second writer alongside
`permissions-create`, with its retention rule summarised in one clause.

**G4. No CER row is claimed.** The diff contains no edit to
`docs/cer/backlog.md`. This story closes no CER — CER-101/102/103/104 belong
to INFRA-287/288/289, and CER-105/106/107 were deferred at phase-scaffold
time. Adding a note here would misattribute their resolution.

### Cross-cutting

**H1. No behaviour change to the recording pipeline.** The diff contains no
edit to `subagent_transcript.py`, `effort_recorder.py`, `effort_db.py`,
`record_attempt.py`, `context_budget.py`, `scope_guard.py`, `hook_view.py`,
`next_action.py`, or any file under `hooks/`.

**H2. `schema_introduces` stays `false`.** No new table, column, or
persistent file shape is introduced. `to-030`'s two new steps and
`permissions-gc` only remove or normalise state that already exists, so no
row is owed in `docs/phases/phase-110.md` § Schema delivery.

**H3. The full test suite is green** (`tests/pairmode/`), run once **without**
`-x`.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order A/B/C (procedure + template prose and their tests) → D/E
(`to-030`) → F (`permissions-gc`) → G (docs), and run the suite after C, after
E and after F. G is prose and should be written last, against what actually
shipped.

**0. Rebase check.** Confirm INFRA-287..289 are in your `HEAD` (`## Requires`).
Read the current bodies of the two procedure skills, `cmd_to_030`, and
`flex_build.py`'s permissions helpers as they exist *now* — the line numbers
throughout this spec are anchors, not coordinates. If a sibling story changed
one of them, layer on top; never revert its work to make an assertion here
easier to satisfy.

**1. (A) Write reviewer item 13.** Add it after item 12, before the `---`
preceding `## Review output format`. Keep it tight — this item runs on every
review, so cost matters. Structure it as: a one-line scope gate (A3), then the
four bolded sub-checks (A2), then the required report line format (A4), then
the CER citation (A6). Write the scope gate **first** and make the no-op path
obvious; a reviewer that starts grepping on a docs-only diff has already made
the item too expensive to keep.

The four sub-checks, in this order:

- **written-never-read** — the diff adds or changes a field/key/column/file
  that no code path reads. Question: name the reader. MEDIUM (LOW if the diff
  itself documents it as intentionally inert).
- **required-never-written** — a read path, predicate or default depends on a
  value in a shape or with a value that no current writer produces. Question:
  name the writer, and confirm it still produces that shape *today*. HIGH.
- **duplicate state** — the same fact is now stored in two places with
  independent writers, or the same event now has two producers. Question: which
  one is authoritative, and what reconciles them when they disagree? HIGH.
- **half-implementation** — a branch that looks reachable but cannot be reached
  by any live input, or a producer whose consumer is deferred to a later story.
  Question: trace one concrete input that reaches it. HIGH.

**2. (A5) Extend the input contract.** Add entry 9 to the numbered list. Word
it so the boundary is unambiguous: source searching is permitted; reading loop
runtime state is not. This is a deliberate, minimal widening of DP1.3 — say so
in the entry, and say why (the check is unperformable otherwise), so a future
reader does not treat it as contract erosion.

**3. (B) Write security check 7.** Same four labels, phase-diff scope,
data-loss-tied severity. Do **not** copy item 13 wholesale — the audit's job is
the cross-story case (B3), and a verbatim duplicate will drift. Add the fourth
input-contract entry (B5).

**4. (C) The phase template.** Add four `- [ ] ` lines under the CP heading,
keeping the `— developer fills in after phase completion —` line beneath them.
Use plain literal text, no Jinja logic — the section must render identically
for every phase. Then extend `tests/pairmode/test_templates.py` with a class
covering C2, and confirm C3's existing assertions still pass untouched.

**5. (A/B tests).** Extend `tests/pairmode/test_procedure_skills.py` with a
class asserting the four literal labels appear in **both** procedure files, that
the reviewer file contains `### 13. DATA FLOW`, that the security file contains
`### 7. DATA-FLOW INTEGRITY`, and that both input-contract lists gained their
new entry. Follow the file's existing fixture style (it already loads procedure
text for the hardcoded-literal parametrization at `:39-48`); do not introduce a
second way of loading the same files.

**6. (D/E) `to-030`.** Add both steps inside `cmd_to_030`, after the existing
`pipe_path` block (D) and after the `effort_tracking` backfill (E), before
`_protected_path_preview`. Follow the surrounding style exactly: `[would]` /
`[apply]` prefixes, `_atomic_write_json` for writes, no exceptions escaping.

For E's in-flight test, add a small module-level helper — e.g.
`_counter_story_in_flight(project_path: Path, story_id: str) -> bool` — that
checks the worktree directory and both state.json shapes, and returns `False`
on any error rather than raising. Do not import `flex_build` or `scope_guard`
for this: `pairmode_migrate.py` runs against *other* projects' trees and must
not depend on the target project's module layout, and the check is three
`Path.exists()` / dict lookups. Note that reasoning in a comment.

**7. (F) `permissions-gc`.** Site it next to `cmd_permissions_create`. Factor
the classification into a pure helper —
`collectable_permission_artifacts(project_path) -> tuple[list[Path], list[tuple[Path, str]]]`
returning `(collectable, [(path, retain_reason), ...])` — so the tests assert on
the classification rather than on stdout parsing, and the command becomes a thin
printer over it. Reuse `story_context.get_current_stories` for the keyed read
rather than re-parsing `state.json` by hand; read the flat mirror from the same
loaded state dict. For the worktree check, reuse `flex_build`'s existing
`.pairmode-worktrees/<id>` path derivation rather than re-deriving the layout.

The retention rules are a **whitelist of reasons to keep**, not a blacklist of
reasons to delete: anything the helper cannot positively classify is retained.
A GC that deletes on uncertainty is a GC that deletes a live permission
artifact and hands the next builder a fail-closed scope guard with no
explanation.

**8. (G) The prose.** Write G1's placement paragraph, G2's consolidation
paragraph (grep the reader inventory — do not copy it), and G3's two inventory
edits. Keep G1 short; the procedure skills are the canonical source and
architecture.md's job is to say where the checks live and why, not to restate
them.

**9. Verification runs.** Execute D3's and F6's dry-runs against this repo and
paste both outputs into the build result. Neither is `--apply`.

**10. Ideology note (Step 4a — resolved inline, no conflict).** Three entries
shaped this spec. *"Never silently pass contradictions"* is the whole premise of
items A/B/C: a producer/consumer mismatch is a contradiction between two parts
of the system, and a checklist that cannot see it provides exactly the false
confidence the constraint names as worse than no system at all. *"Decision
fidelity over convenience"* is why E2 refuses the dossier's flat "delete the
legacy counter" and gates the delete on a positive not-in-flight test, and why
F3 retains on uncertainty — the convenient version of both silently discards
state, which is the failure mode this phase exists to fix. *"Persistent intent
over implementation detail"* is why G2 records the `current_story` retirement
*direction* rather than either building it now or leaving it in a phase doc
that a future reader will not open. *"Hooks are thin relays only"* does not
bind here — nothing in this story runs on a hook path — but its rationale
(never make the cheap path expensive) is why A3's scope gate and its explicit
no-op verdict are Ensures rather than suggestions.

## Tests

Run from the story worktree root. After item C, after item E, and after item F:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_procedure_skills.py \
  tests/pairmode/test_templates.py \
  tests/pairmode/test_pairmode_migrate.py \
  tests/pairmode/test_flex_build_permissions_gc.py \
  tests/pairmode/test_cli_surface_freeze.py \
  -q 2>&1 | tail -30
```

Then the adjacent surface, to catch collateral damage in the counter and
permission paths:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_attempt_counter.py \
  tests/pairmode/test_flex_build_permissions_create.py \
  tests/pairmode/test_flex_build.py \
  tests/pairmode/test_story_context.py \
  tests/pairmode/test_hooks.py \
  -q 2>&1 | tail -30
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
# A1/A2 — reviewer item 13 and its four labels
grep -c '### 13. DATA FLOW' skills/pairmode/skills/reviewer/procedure.md          # 1
for s in 'written-never-read' 'required-never-written' 'duplicate state' \
         'half-implementation'; do
  grep -c "$s" skills/pairmode/skills/reviewer/procedure.md
done                                                                              # all >= 1

# B1/B2 — security check 7 and the same four labels
grep -c '### 7. DATA-FLOW INTEGRITY' \
  skills/pairmode/skills/security-auditor/procedure.md                            # 1
for s in 'written-never-read' 'required-never-written' 'duplicate state' \
         'half-implementation'; do
  grep -c "$s" skills/pairmode/skills/security-auditor/procedure.md
done                                                                              # all >= 1

# C1 — four checkbox items in the phase template
grep -c '^- \[ \] ' skills/pairmode/templates/docs/phases/phase.md.j2             # 4

# C4 — no historical phase doc rewritten
git diff --name-only HEAD | grep -c '^docs/phases/phase-'                         # 0

# D1/E1 — the two to-030 steps exist
grep -n "context_story_tokens\|attempt_counter" \
  skills/pairmode/scripts/pairmode_migrate.py

# F1 — the subcommand exists
PATH=$HOME/.local/bin:$PATH uv run python \
  skills/pairmode/scripts/flex_build.py permissions-gc --help                     # exit 0

# G4 — no CER row claimed
git diff --name-only HEAD | grep -c '^docs/cer/backlog.md'                        # 0

# H1 — recording pipeline untouched
git diff --name-only HEAD | grep -cE '^(hooks/|skills/pairmode/scripts/(subagent_transcript|effort_recorder|effort_db|record_attempt|context_budget|scope_guard|hook_view|next_action)\.py)'   # 0
```

Verification runs (dry-run only — paste both outputs into the build result):

```bash
# D3
PATH=$HOME/.local/bin:$PATH uv run python \
  skills/pairmode/scripts/pairmode_migrate.py to-030 --project-dir . 2>&1 | \
  grep -i 'context_story_tokens\|attempt_counter'

# F6
PATH=$HOME/.local/bin:$PATH uv run python \
  skills/pairmode/scripts/flex_build.py permissions-gc --project-dir . 2>&1 | tail -5
```

Acceptance:

- every new test from A-G passes;
- `tests/pairmode/test_templates.py`'s existing phase-template assertions pass
  unedited (C3), and `tests/pairmode/test_cli_surface_freeze.py` passes unedited
  (F7);
- both verification dry-runs complete with exit 0 and their output is quoted in
  the build result;
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so explicitly in the build
  result.

## Out of scope

- **Retiring the flat `current_story` key.** G2 records the direction and the
  reader inventory; it changes no reader and no writer. Retiring the mirror
  touches `hooks/session_start.py`, `global_session_check.py`,
  `subagent_transcript.py` and the observability API's `context.ts` route — a
  cross-surface change with its own regression risk, and one that must not ride
  along inside a methodology story.
- **Back-filling the four checklist items into existing `docs/phases/phase-*.md`
  cold-eyes checklists** (C4). Those sections are the record of what was
  actually checked at each checkpoint; rewriting them would make the record lie.
- **Retroactively running the data-flow checks over the existing codebase.**
  This story installs the check; it does not perform a repository-wide audit.
  Anything such an audit would find belongs in a CER row, filed when the check
  first runs for real.
- **Deleting this repo's 118 stranded permission artifacts, or meander's ~150.**
  F6 reports; the operator decides when to run `--apply`. A story diff is the
  wrong place for a mass deletion of untracked-by-this-story files.
- **Wiring `permissions-gc` into the build loop or the checkpoint sequence.**
  It is an operator-invoked command in this story. Making it automatic is a
  behaviour change to the loop that needs its own reversibility argument — and
  `merge`/`discard` already clear artifacts inline (INFRA-238), so the automatic
  path is already covered for everything built after that story.
- **Removing legacy-shape support from `_read_attempt_counters`** (E5). The
  reader stays permissive; `to-030` is the deliberate migration. Breaking the
  reader would strand every project that has not yet run it.
- **Changing `set-context-tokens`, `context_budget.decide()`, or any other
  `context_story_tokens` code path.** They already neither write nor read it
  (INFRA-182); this story only removes the residue and corrects the docs.
- **CER-105, CER-106 and CER-107.** Filed to the backlog at phase-scaffold time
  and explicitly not in this phase (`docs/phases/phase-110.md` § Deferred to CER
  backlog), even though all three are data-flow findings of exactly the class
  this story's checks are designed to catch.
- **Adding the data-flow checks to the `intent-reviewer` or `checkpoint-docs`
  procedures.** The phase dossier names the reviewer and the security-auditor;
  the intent-reviewer's contract is plan-vs-built alignment, which is a
  different question. If checkpoint experience shows a gap there, that is a new
  finding.

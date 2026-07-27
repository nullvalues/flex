---
id: RELEASE-062
rail: RELEASE
title: Canonize the permanent release channel: retire RELEASE-061, rewrite RELEASE-060, amend runbook final-fold steps
status: draft
phase: "105"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/stories/RELEASE/RELEASE-060.md
  - docs/stories/RELEASE/RELEASE-061.md
  - docs/harness-cutover-runbook.md
  - docs/phases/phase-97.md
touches:
  - docs/stories/RELEASE/RELEASE-060.md
  - docs/stories/RELEASE/RELEASE-061.md
  - docs/harness-cutover-runbook.md
  - docs/phases/phase-97.md
  - docs/architecture.md
  - docs/stories/RELEASE/RELEASE-062.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

<!-- SPEC-WRITER NOTE (Step 5): the frontmatter arrived with no `primary_files:`
     key and `touches: []`. The spec-writer input contract forbids editing
     frontmatter, so both were preserved as-is and this story is returned
     `status: "revised"` for the operator to populate. The file set this story
     actually touches is enumerated verbatim in `## Instructions` step 0 — copy
     it into `primary_files:`/`touches:` before dispatching a builder. -->

## Context

Era 003 established `/mnt/work/flex-harness` as a **temporary** artefact. The
era doc's § Versioning & compatibility, DP1 ("Dev-line isolation"), describes it
as a `git worktree` on the `harness` branch holding breaking code *until the
flip*, with `/mnt/work/flex` staying on `main` as the fleet-facing stable
checkout. Every downstream document written during `HARNESS001-ante1` inherited
that framing, and two RELEASE stories were scaffolded in phase 97 to execute the
teardown it implied:

- `docs/stories/RELEASE/RELEASE-061.md` — *"Worktree and branch retirement —
  remove /mnt/work/flex-harness"*
- `docs/stories/RELEASE/RELEASE-060.md` — *"Post-fold re-sync of migrated
  projects + RELEASE-002 status reconciliation"*

Reality diverged. The flip landed (`HARNESS006-main`), phase 97 was **deferred**
rather than built (`docs/eras/003-flex-orchestrator-as-harness.md` § Phases,
row 97), and phase 102 — *"Effort-recording smoke test and harness
release-channel fast-forward"*, status `complete` — kept the harness checkout
alive and promoted it to the channel from which the fleet consumes flex.
`docs/architecture.md` already carries the canon as a section titled
**`### Release channel — flex-harness`** (present at spec time near line 881).
The checkout is load-bearing today: this phase's own build loop invokes pairmode
scripts out of `/mnt/work/flex-harness/skills/pairmode/scripts`.

So the repository currently asserts two contradictory futures for the same
directory. `docs/architecture.md` says it is the permanent release channel; a
planned story says it gets deleted; and `docs/harness-cutover-runbook.md`
§ Final fold sequence (line 417 at spec time) still carries fold-completion steps
written against the temporary-worktree topology. This is exactly the condition
the project's ideology names first — *"Never silently pass contradictions"* — and
it is not hypothetical harm: the next agent to run the fold sequence, or to pick
up phase 97's deferred stories, will act on whichever of the three documents it
reads first.

This story is the phase's **channel canon** work. It carries no CER; the phase's
CER load (CER-081/058/059/080/087/040/041) belongs to INFRA-269/270/271/272. It
is `story_class: doc` — no production code changes, no schema, no CLI behaviour.
Its entire deliverable is that a reader of the runbook, of `architecture.md`, and
of the phase-97 story files comes away with **one** answer about what
`/mnt/work/flex-harness` is and whether it survives. The phase's § Checkpoint
proves names that consistency directly.

**Why retire rather than delete.** `docs/cer/backlog.md:6` records the project
convention that findings are annotated in place rather than removed, and the
phase-continuity policy makes deferred work an auditable trail, not an erasure.
RELEASE-061 is therefore superseded with a recorded reason, not deleted — a
future agent that finds a reference to RELEASE-061 must be able to open the file
and learn *why* the retirement happened, per the *"rationale-bearing decisions
over bare rules"* conviction.

## Requires

- `docs/stories/RELEASE/RELEASE-060.md` exists, `status: draft`, `phase: "97"`,
  title *"Post-fold re-sync of migrated projects + RELEASE-002 status
  reconciliation"*.
- `docs/stories/RELEASE/RELEASE-061.md` exists, `status: draft`, `phase: "97"`,
  title *"Worktree and branch retirement — remove /mnt/work/flex-harness"*.
- `docs/harness-cutover-runbook.md` exists (507 lines at spec time) and contains
  a `## Final fold sequence` heading.
- `docs/architecture.md` contains a `### Release channel — flex-harness` heading.
- `docs/phases/phase-97.md` exists and is the phase doc naming RELEASE-060 and
  RELEASE-061 in its `## Stories` table; the era ledger
  (`docs/eras/003-flex-orchestrator-as-harness.md` § Phases) shows phase 97 as
  `deferred`.
- No sibling phase-105 story is a prerequisite. `docs/phases/phase-105.md`
  § Ordering states INFRA-272 and RELEASE-062 are independent; this story does
  not touch `fleet_discovery.py`, `scope_guard.py`, or any script INFRA-269/270/271
  touch, so it may build in any order relative to them.
- Known environmental failure inside fresh story worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story.

## Ensures

**E1. RELEASE-061 is retired, not deleted.**
`docs/stories/RELEASE/RELEASE-061.md` still exists. Its frontmatter `status:` is
no longer `draft`; it is a terminal non-build status drawn from the set already
used elsewhere in `docs/stories/` (`skipped` preferred; `deferred` is not
acceptable because the work is never resumed). Its `id`, `rail`, `title` and
`phase` fields are unchanged. `grep -c '^id: RELEASE-061'` on the file prints
`1`.

**E2. RELEASE-061 records why it was retired.**
The body of `docs/stories/RELEASE/RELEASE-061.md` contains a
`## Superseded` section that names `RELEASE-062` and `docs/phases/phase-105.md`,
states that `/mnt/work/flex-harness` is the permanent release channel and is
therefore never removed, and cites `docs/architecture.md`
§ *Release channel — flex-harness* plus phase 102 as the point the disposition
changed. `grep -c 'RELEASE-062' docs/stories/RELEASE/RELEASE-061.md` prints at
least `1`.

**E3. No live instruction to remove the harness checkout survives.**
Across `docs/`, every remaining occurrence of a directive to delete, remove,
retire, or tear down `/mnt/work/flex-harness` (or the `harness` branch/worktree)
sits inside a superseded/historical note that names RELEASE-062 or phase 105 in
the same section. Concretely, the reviewer runs:

```bash
grep -rn "remove /mnt/work/flex-harness\|git worktree remove\|delete the harness branch" docs/
```

and every hit is either (a) inside the `## Superseded` section of RELEASE-061,
or (b) inside a rollback-only procedure that is explicitly labelled as such.
No hit appears in `docs/harness-cutover-runbook.md` § Final fold sequence as a
step to perform.

**E4. RELEASE-060 is rewritten against the permanent-channel topology.**
`docs/stories/RELEASE/RELEASE-060.md` retains its `id`, `rail`, `phase: "97"`
and `status: draft`, and its body no longer assumes the harness checkout is
temporary or about to be removed. Its body contains a `## Context` section that
states the permanent-channel fact and links `docs/architecture.md`
§ *Release channel — flex-harness*. Any step in it that was predicated on the
teardown is either removed or restated as a re-sync performed *from* the
permanent channel.

**E5. RELEASE-060 declares its relationship to RELEASE-061.**
`docs/stories/RELEASE/RELEASE-060.md` contains a line naming `RELEASE-061` and
stating it is superseded, so a reader of 060 alone cannot conclude a teardown is
still pending.

**E6. The runbook's final-fold steps match reality.**
`docs/harness-cutover-runbook.md` § *Final fold sequence* contains a paragraph or
call-out — headed with the words `permanent release channel` — that states:
(a) `/mnt/work/flex-harness` survives the fold and is the channel the fleet
consumes flex from;
(b) `/mnt/work/flex` remains the `main` checkout;
(c) the fold does **not** end with a worktree/branch removal, and the previously
planned removal (RELEASE-061) is retired;
(d) `docs/architecture.md` § *Release channel — flex-harness* is the canonical
statement, and the runbook defers to it on any disagreement.
`grep -c 'permanent release channel' docs/harness-cutover-runbook.md` prints at
least `1`.

**E7. The runbook has no orphaned cross-reference.**
Every `RELEASE-0NN` identifier still referenced in
`docs/harness-cutover-runbook.md` resolves to a file under
`docs/stories/RELEASE/`, and any reference to `RELEASE-061` is annotated as
retired at the point of reference.

**E8. `docs/architecture.md` § Release channel is the single source and is not
duplicated.** The count of `### Release channel` headings in
`docs/architecture.md` is exactly `1`, and no `##`-level heading is added to or
removed from the file. If the section needed an amendment to cover (a)–(d) of E6,
that amendment is made in place under the existing heading; the runbook and the
story files point at it rather than restating the policy.

**E9. Phase 97's ledger stays honest.**
`docs/phases/phase-97.md`'s `## Stories` table row for RELEASE-061 reflects the
same terminal status set in E1, and the phase doc's `## Deferred stories` section
(required by the phase-continuity policy for a `deferred` phase) records that
RELEASE-061 is superseded rather than awaiting resume. RELEASE-060's row is
unchanged apart from anything required to stay consistent with E4.

**E10. Index integrity is clean.**
```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  check-index --project-dir .
```
exits `0`, with no new finding naming `RELEASE-060`, `RELEASE-061`, `RELEASE-062`
or `phase-97` relative to a run on the pre-change tree.

**E11. No code, no schema, no scripts.**
`git diff --name-only` for this story lists only paths under `docs/`. No file
under `skills/`, `tests/`, `ui/`, or `.claude-plugin/` is modified.
`schema_introduces: false` stands and no management-surface row is owed in
`docs/phases/phase-105.md` § Schema delivery.

**E12. The suite is green.**
`uv run pytest tests/pairmode/` passes, except the known CER-090 worktree
environmental failure named in `## Requires`.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
This is a documentation story: change no Python, no templates, no tests. Do not
create a git tag, do not push, and **run no command that mutates
`/mnt/work/flex-harness`** — that directory is the subject of this story, not its
worktree.

0. **Record the file set.** The files this story touches are exactly:
   - `docs/stories/RELEASE/RELEASE-060.md`
   - `docs/stories/RELEASE/RELEASE-061.md`
   - `docs/harness-cutover-runbook.md`
   - `docs/phases/phase-97.md`
   - `docs/architecture.md` (only if E8's in-place amendment is needed)
   - `docs/stories/RELEASE/RELEASE-062.md` (this file)

   If the frontmatter's `primary_files:`/`touches:` are still empty when you
   start, that is the spec-writer's flagged gap (see the note at the top of this
   file) — populate them from this list as your first edit, and say so in your
   BUILD-RESULT.

1. **Read before writing.** In order: `docs/architecture.md`
   § *Release channel — flex-harness*; `docs/harness-cutover-runbook.md`
   § *Final fold sequence* (and § *Rollback procedure*, so you can tell a
   rollback step from a fold step); `docs/stories/RELEASE/RELEASE-060.md`;
   `docs/stories/RELEASE/RELEASE-061.md`; `docs/phases/phase-97.md`. The
   spec-writer is input-bound and did **not** read these; the exact wording of
   each amendment is yours to derive from what is actually there. Where this spec
   and the files disagree on detail, the files win — report the discrepancy in
   your BUILD-RESULT rather than forcing the spec's phrasing.

2. **Retire RELEASE-061 (E1, E2).** Flip its frontmatter `status:` to `skipped`
   — the terminal status for work that will never be built — leaving every other
   frontmatter field byte-identical. Do not delete the file and do not empty its
   body. Add a `## Superseded` section at the top of the body, before any
   existing section, stating: superseded by RELEASE-062 (phase 105); the harness
   checkout is the permanent release channel per `docs/architecture.md`
   § *Release channel — flex-harness*; the disposition changed at phase 102
   (*harness release-channel fast-forward*, complete); the teardown this story
   would have performed must never be executed. Keep it to a short paragraph
   plus a bullet list — the file is a tombstone, not a new spec.

3. **Rewrite RELEASE-060 (E4, E5).** Keep `status: draft` and `phase: "97"`: this
   story is still legitimately pending under a deferred phase, and re-homing it
   into another phase is out of scope. Rewrite its body so the re-sync it
   describes is performed *from* the permanent channel. Add a `## Context`
   paragraph carrying the permanent-channel fact and the link to
   `docs/architecture.md` § *Release channel — flex-harness*, and one line naming
   RELEASE-061 as superseded. Delete or restate any step that only made sense if
   the harness checkout were about to disappear. Do not attempt to fully elaborate
   RELEASE-060 into a build-ready spec — a spec-writer pass will do that when
   phase 97 resumes; your job is to remove the false premise, not to finish the
   story.

4. **Amend the runbook (E6, E7).** In `docs/harness-cutover-runbook.md`
   § *Final fold sequence*, add a call-out headed with the exact phrase
   `permanent release channel` covering points (a)–(d) of E6, and delete or
   convert any step in that section that instructs removal of the worktree or the
   `harness` branch. Preserve `## Rollback procedure` — a rollback that removes a
   worktree is a recovery action, not a fold step; if any ambiguity remains,
   label it explicitly as rollback-only so E3's grep can distinguish it. Then
   sweep the whole file for `RELEASE-0NN` references and annotate the RELEASE-061
   ones as retired (E7). Do not restructure the runbook's heading tree.

5. **Keep the canon single (E8).** Do not copy the release-channel policy into
   the runbook or into either story file — link to
   `docs/architecture.md` § *Release channel — flex-harness* instead. Amend that
   section in place **only** if it does not already state all four of E6's
   points; if it does, leave `docs/architecture.md` untouched and drop it from
   `touches:`. Adding a second `### Release channel` heading, or a parallel
   policy paragraph in the runbook, recreates the two-sources-of-truth condition
   this story exists to remove.

6. **Reconcile phase 97 (E9).** Update the RELEASE-061 row in
   `docs/phases/phase-97.md` § Stories to the status set in step 2, and extend
   that phase doc's `## Deferred stories` section with a line stating RELEASE-061
   is superseded by RELEASE-062 and is not awaiting resume. If phase 97 has no
   `## Deferred stories` section, add one — the phase-continuity policy requires
   it for a `deferred` phase, and its absence is a finding to report in your
   BUILD-RESULT.

7. **Verify (E3, E10, E11).** Run the greps and `check-index` from `## Tests`.
   `check-index` must exit 0; capture a baseline run on the pre-change tree
   first so E10's "no new finding" comparison is real.

8. **Ideology note (Step 4a — resolved inline, no conflict).** Two convictions
   shaped this spec. *"Never silently pass contradictions"* is the story's whole
   premise, and it is why E3 is written as an exhaustive `docs/`-wide grep rather
   than "fix the runbook": leaving a single live teardown instruction anywhere in
   `docs/` reproduces the contradiction at a different address, and the
   constraint's rationale is that false confidence is worse than no record at
   all. *"Rationale-bearing decisions over bare rules"* is why step 2 forbids
   deleting RELEASE-061 and requires the `## Superseded` prose: a status flipped
   to `skipped` with no reason is a bare rule, and the first agent to encounter a
   reference to RELEASE-061 would have no way to learn that the removal was
   deliberately abandoned. No accepted constraint is touched — the three recorded
   constraints (never silently pass contradictions; hooks are thin relays;
   sidebar owns all state writes) all govern runtime behaviour, and this story
   changes no runtime code (E11).

## Tests

`story_class: doc` — no test file is expected and no test file is added. The
checks below are the acceptance surface.

Run from the story worktree root.

```bash
# E3 — no live teardown instruction anywhere in docs/
grep -rn "remove /mnt/work/flex-harness\|git worktree remove\|delete the harness branch" docs/

# E1/E2 — RELEASE-061 retired in place, with a reason
grep -n '^status:' docs/stories/RELEASE/RELEASE-061.md          # must not be 'draft'
grep -c '^## Superseded' docs/stories/RELEASE/RELEASE-061.md    # must print 1
grep -c 'RELEASE-062' docs/stories/RELEASE/RELEASE-061.md       # must be >= 1

# E5 — RELEASE-060 names the supersession
grep -c 'RELEASE-061' docs/stories/RELEASE/RELEASE-060.md       # must be >= 1

# E6 — runbook call-out present
grep -c 'permanent release channel' docs/harness-cutover-runbook.md  # must be >= 1

# E8 — canon not duplicated
grep -c '^### Release channel' docs/architecture.md             # must print 1

# E11 — docs-only diff
git diff --name-only main... | grep -v '^docs/'                 # must print nothing
```

```bash
# E10 — index integrity
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  check-index --project-dir .
```

```bash
# E12 — full suite, without -x so a known failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance:

- every grep above returns the stated result, and each E3 hit that remains is
  visibly inside RELEASE-061's `## Superseded` section or an explicitly
  rollback-only block;
- `check-index` exits 0 with no new finding versus the pre-change baseline;
- the full suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if
  it appears, state that it reproduces on clean `HEAD` and is unrelated;
- E4, E6, E7 and E9 are prose assertions verified by the reviewer from the diff.

Note for `spec-preflight`: this story names section headings
(`## Superseded`, the `permanent release channel` call-out) and a status value
that do not exist in the tree yet — they are created by this story, and any
preflight finding naming them is expected. `### Release channel — flex-harness`,
`## Final fold sequence`, `docs/phases/phase-97.md`, `RELEASE-060.md` and
`RELEASE-061.md` were all confirmed present at spec time.

## Out of scope

- **Executing any part of the fold or the fleet migration.** This story amends
  the runbook's *description* of the final fold; it runs no migration step
  against any fleet project. The migration campaign is phase 106
  (`docs/eras/003-flex-orchestrator-as-harness.md` § Phases).
- **Building or resuming phase 97.** RELEASE-060 stays `status: draft` under
  `phase: "97"` and stays deferred. Elaborating it into a build-ready spec, or
  re-homing it into phase 105, is a later spec-writer pass — this story removes a
  false premise from it and nothing more.
- **RELEASE-002 status reconciliation.** Named in RELEASE-060's title; it is
  RELEASE-060's work when phase 97 resumes, not this story's. Do not touch
  `docs/stories/RELEASE/RELEASE-002.md`.
- **Any change to `/mnt/work/flex-harness` itself.** No `git worktree` command,
  no branch operation, no file written into that checkout. The story canonizes
  the channel in documentation; it does not administer it.
- **The other phase-105 stories and their CERs.** CER-081 (INFRA-269), CER-058/059
  (INFRA-270), CER-080/087 (INFRA-271), CER-040/041 (INFRA-272) are untouched.
  Do not edit `fleet_discovery.py`, `scope_guard.py`, `context_budget.py`, or
  `docs/cer/backlog.md`.
- **Restructuring `docs/harness-cutover-runbook.md`.** Its heading tree, its
  § Strategy (Option Y), § Rolling sequence, § Per-project mechanic and
  § Pre-fold discovery gate sections are left alone. Only § Final fold sequence
  and orphaned `RELEASE-0NN` cross-references are in scope.
- **A release-channel CLI, check, or automated guard.** No script asserts the
  channel's existence, and no test is added to enforce the documentation
  consistency. If that guard is wanted, it is a CER, not this story.
- **Any new persistent schema object.** No table, no file, no new state key.

---
id: INFRA-260
rail: INFRA
title: Tag-pinned release-channel fast-forward — promote flex-harness to cp tags as a documented checkpoint step; route tagging through record-checkpoint-step (CER-083)
status: draft
phase: "102"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/next_action.py
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_templates.py
  - docs/stories/INFRA/INFRA-260.md
---

## Context

Two related defects are closed here, both rooted in the same thing: the
checkpoint's terminal step is prose, not code.

**CER-083 — the raw-git-tag gap.** `flex_build.py record-checkpoint-step` was
built (RESOLVER-012) to be the sole writer of `state.json["checkpoint_step"]`,
and RESOLVER-017 + INFRA-239 made its `checkpoint-tag` branch do two
load-bearing things atomically: reset `checkpoint_step` to `[]`, and mark the
just-tagged phase `complete` in `docs/phases/index.md`. But `CLAUDE.build.md`'s
§ Checkpoint instructs the terminal step as a raw
`git tag cp-<phase-key> && git push origin main --tags` — the CLI is never
called for `checkpoint-tag`, so neither the reset nor the index write ever
fires. Live consequence at cp99→phase-100 (2026-07-24): the leftover list held
the three gate steps and no `checkpoint-tag` entry, so phase-100's
`next-action` computed its remaining sequence as `[checkpoint-tag]` and resolved
straight to tagging — silently skipping the security audit, the intent review,
and the docs review. The gates are the phase-quality backstop; skipping them is
invisible. The fix has two halves: mandate the CLI path in the loop doc *and*
make the resolver refuse to honour a checkpoint list that belongs to a different
phase, so the same prose slip cannot silently skip gates a second time.

**The release channel.** `/mnt/work/flex`'s own `CLAUDE.build.md` sets
`pairmode_scripts_dir = /mnt/work/flex-harness/skills/pairmode/scripts` — flex's
orchestrator runs its build loop out of the sibling worktree, not out of `main`.
That worktree (branch `fold-prep`, HEAD `1263c36`) has not moved since
RELEASE-059's fold and is 57 commits behind `main`; its HEAD *is* an ancestor of
`main`, so it is a clean fast-forward away from current. Because it is stale, it
lacks INFRA-256's phase-scoped `checkpoint-report`, INFRA-257's truthful
`attempt_number`, and INFRA-258's async reconciliation — INFRA-259 had to carry
an explicit `## Requires` clause telling the operator *not* to run
`flex_build.py` from there, and the orchestrator has been quietly substituting
`skills/pairmode/scripts/…` from `main` instead. The documented path and the
practised path have diverged.

**Decision (recorded so it is not re-litigated): keep the harness worktree as
the toolchain flex executes, and promote it only at checkpoints.** The
alternative was to repoint `pairmode_scripts_dir` at `/mnt/work/flex` and delete
the indirection. Rejected: flex dogfoods its own pairmode, so pointing the live
loop at the working tree means every half-built story's CLI edits take effect on
the very loop building it — a toolchain that changes under the harness mid-phase
is exactly the class of self-reference this project has already been bitten by.
Pinning the executed toolchain to the last checkpoint tag gives flex a release
channel with the same property it gives downstream consumers: you run a version
that passed all three checkpoint gates. `main` stays the dev line; the harness
worktree is the pinned channel; promotion is a fast-forward to the cp tag, and
it becomes a documented step of the checkpoint sequence so it can never drift 57
commits again.

**Actor split (why this story is spec'd with owners).** The promotion is a write
to a *different working directory* — `/mnt/work/flex-harness` — and the cp-102
tag it pins to does not exist until after this story is built, reviewed, merged,
and the three gate workers have run. A builder subagent works inside a
disposable per-story worktree and is scoped to this repository; it can neither
see the future tag nor legitimately mutate a sibling checkout. So the builder
writes the *procedure* and the *documentation*, and the orchestrator (or
operator) *executes* the promotion at cp-102 and records the evidence, exactly
as INFRA-259 split its owner-labelled assertions. Every assertion below names
its owner and the working directory its commands run in.

**Frontmatter note.** This file's `touches:` key originally carried the
`story_new.py` stub's trailing `# If this story changes…` comment. The harness
frontmatter parser reads that comment as a scalar string value, which crashes
`create-story-worktree`; it was hit live on INFRA-259. The comment has been
replaced here by a real block list. The stub template that emits it
(`story_new.py:67`, guarded by
`test_story_new.py::test_story_frontmatter_touches_has_architecture_comment`) is
a fleet-wide latent trap, but fixing it is a different story — see
`## Out of scope`.

## Requires

- INFRA-259 is complete (this phase's first story); `docs/phases/phase-102.md`
  lists both stories and carries a `### CP-102 Cold-eyes checklist` section.
- `skills/pairmode/scripts/flex_build.py` exposes `record-checkpoint-step`
  (`cmd_record_checkpoint_step` → `_record_checkpoint_step`), whose
  `checkpoint-tag` branch resets `state.json["checkpoint_step"]` to `[]` and
  calls `_mark_phase_complete_in_index` (RESOLVER-012 / RESOLVER-017 /
  INFRA-239).
- `skills/pairmode/scripts/next_action.py` exposes `infer_position` (which reads
  `state.json["checkpoint_step"]` into `position["checkpoint_step"]`),
  `resolve_next_action`, and `_CHECKPOINT_SEQUENCE`.
- `CLAUDE.build.md` and `skills/pairmode/templates/CLAUDE.build.md.j2` both
  contain a `## Checkpoint` section whose terminal instruction is a raw
  `git tag … && git push …`.
- `docs/cer/backlog.md` contains a `CER-083` row under `## Do Much Later` whose
  `Phase` cell is `—`.
- `/mnt/work/flex-harness` exists as a `git worktree` of this repository, on
  branch `fold-prep`, with no *tracked* modifications, and its HEAD is an
  ancestor of `main`. Verified by the orchestrator, not the builder:
  `git -C /mnt/work/flex-harness status --porcelain --untracked-files=no` is
  empty, and
  `git -C /mnt/work/flex merge-base --is-ancestor "$(git -C /mnt/work/flex-harness rev-parse HEAD)" main`
  exits 0.
- Known environmental failure: `test_observability_ui.py::test_ui_build_emits_dist_index_html`
  fails inside fresh story worktrees (CER-090). It is not caused by this story.

## Ensures

Assertions **B1–B10 are builder-owned** and are verified by the reviewer from
the diff, in this repository (`/mnt/work/flex`, via the story worktree).
Assertions **O1–O4 are orchestrator-owned**, execute at cp-102 after the tag
exists, and touch `/mnt/work/flex-harness`; the builder creates them as
labelled, non-empty `RESULT: PENDING — owner: orchestrator, at cp-102`
placeholders in `## Promotion record`, each carrying the exact command to run.
The reviewer verifies those placeholders exist and are complete, and must
**not** attempt to perform O1–O4.

### Builder-owned

**B1. `CLAUDE.build.md` § Checkpoint mandates the CLI tagging path.** Within the
`## Checkpoint` section of `/mnt/work/flex/CLAUDE.build.md`, the literal string
`record-checkpoint-step checkpoint-tag` appears, and its first occurrence is at
an earlier byte offset than the first occurrence of `git tag`. The section
states in words that the CLI call happens **first** and that a raw `git tag`
alone is forbidden, and cites `CER-083`.

**B2. The same ordering holds in the shared template.**
`skills/pairmode/templates/CLAUDE.build.md.j2`'s `## Checkpoint` section
satisfies the same first-occurrence ordering as B1, expressed with the existing
`{{ pairmode_scripts_dir }}` and `{{ default_branch | default('main') }}`
placeholders. Rendering the template (as `tests/pairmode/test_templates.py`
already does) produces the same ordering in the output.

**B3. No section-level drift is introduced.** Neither `CLAUDE.build.md` nor the
`.j2` gains or loses any `##`-level heading: the added text lives inside the
existing `## Checkpoint` section. (`drift_report` compares canonical vs project
files at heading granularity; a heading present in one and not the other reports
as MISSING/EXTRA for every downstream project.)

**B4. The release-channel step is project-local, not fleet-wide.**
`/mnt/work/flex/CLAUDE.build.md` § Checkpoint contains a promotion instruction
naming `/mnt/work/flex-harness` and pointing at `docs/architecture.md` for the
full procedure. `skills/pairmode/templates/CLAUDE.build.md.j2` contains **no**
occurrence of the string `flex-harness` (`grep -c` on the template returns 0) —
downstream projects have no such worktree and must not be told to fast-forward
one.

**B5. `record-checkpoint-step` stamps the phase it recorded against.**
`_record_checkpoint_step` in `skills/pairmode/scripts/flex_build.py` writes
`state.json["checkpoint_phase"]` — the phase key resolved by the same
`resolve_current_phase` read-model already used by the `checkpoint-tag` branch,
or `""` when it cannot be resolved — in the same atomic state write that appends
the step. The terminal `checkpoint-tag` branch, which resets `checkpoint_step`
to `[]`, also resets `checkpoint_phase` to `""`. The idempotent early return
(step already present) performs no write, as today.

**B6. The resolver ignores a checkpoint list stamped for another phase.**
`infer_position` in `skills/pairmode/scripts/next_action.py` reads
`state.json["checkpoint_phase"]`. When that stamp is a non-empty string **and**
differs from the active phase's key (derived from the resolved
`active_phase_file`), `position["checkpoint_step"]` is `[]`. When the stamp is
absent, empty, or equal to the active phase key, `position["checkpoint_step"]`
is the stored list unchanged — state files predating this story must keep
resuming correctly. `next_action.py` performs no writes (it remains a pure
read-model).

**B7. Three regression tests exist and pass**, in
`tests/pairmode/test_next_action.py`:

- a test named for CER-083 that builds a real project dir whose `state.json`
  holds `checkpoint_step: ["checkpoint-security", "checkpoint-intent",
  "checkpoint-docs"]` with `checkpoint_phase` set to a **prior** phase key, an
  index whose prior phase is `complete` and whose next phase is `planned` (so
  the next phase resolves active, with no unbuilt stories), and asserts
  `resolve_next_action(infer_position(project_dir), …)` returns
  `checkpoint-security` — **not** `checkpoint-tag`;
- a test that the same list stamped with the **active** phase's own key still
  yields `checkpoint-tag` (a genuine mid-checkpoint resume is not destroyed);
- a test that an **unstamped** state file (no `checkpoint_phase` key) yields the
  stored list unchanged (backward compatibility).

**B8. Documentation records the mechanism and the procedure.**
`docs/architecture.md` contains (a) a state-ownership table row for `state.json`
`checkpoint_phase` naming `flex_build.py record-checkpoint-step` as sole writer
and the resolver as read-only, with the adjacent `checkpoint_step` row updated
to mention the stamp-mismatch rule; and (b) a subsection documenting the release
channel — what `/mnt/work/flex-harness` is, why the executed toolchain is
tag-pinned rather than pointed at `main`, the promotion commands verbatim (see
`## Instructions` step 6), the ancestry precondition, and the do-not-force
failure rule.

**B9. CER-083 is closed in place.** The `CER-083` row in `docs/cer/backlog.md`
carries a resolution note naming INFRA-260 and both halves of the fix (mandated
CLI tagging path; phase-stamped checkpoint state), and its `Phase` cell reads
`102`. The row is not deleted or moved (`Findings are not deleted — resolved
findings remain in place with a resolution note`, `docs/cer/backlog.md:6`).

**B10. The builder does not touch the sibling checkout.** `git diff --stat` for
this story's build lists only paths inside this repository, and the builder runs
no command containing `-C /mnt/work/flex-harness`, no `git tag`, and no
`git push`. Tagging and promotion are checkpoint-time orchestrator actions.

### Orchestrator-owned (recorded in `## Promotion record`, at cp-102)

**O1. Preconditions verified before promotion.** `### P1` records the output of
the tag lookup, the tracked-cleanliness check, and the ancestry check
(`## Instructions` step 6), and states the resolved cp-102 tag name. A
non-ancestor result is `RESULT: FAIL — divergence` and stops the promotion; it
is never resolved with `--force`, `reset --hard`, or a discard.

**O2. The fast-forward is performed and is a true fast-forward.** `### P2`
records the verbatim output of
`git -C /mnt/work/flex-harness merge --ff-only <cp-tag>`.

**O3. The channel is verifiably tag-pinned.** `### P3` records that
`git -C /mnt/work/flex-harness rev-parse HEAD` equals
`git -C /mnt/work/flex rev-parse "<cp-tag>^{commit}"`, and that
`git -C /mnt/work/flex-harness describe --tags --exact-match HEAD` prints the
cp-102 tag.

**O4. The promoted toolchain runs.** `### P4` records the verbatim output of
`checkpoint-report` invoked through the **promoted** path
(`/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py`) against
`--project-dir /mnt/work/flex`, showing the phase-scoped rollup heading for
phase 102 — proof that the pinned toolchain now carries INFRA-256 and is no
longer the stale lifetime-only build INFRA-259 had to route around.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Do not run any command against `/mnt/work/flex-harness`, do not create a git
tag, and do not push. Steps 1–5 and 7–8 are yours; step 6 is text you *write
down* for the orchestrator, not a step you execute.

1. **`CLAUDE.build.md` § Checkpoint.** Replace the terminal instruction
   ``checkpoint-tag: `git tag cp-<phase-key> && git push origin main --tags` ``
   with an ordered form. Keep it inside the existing `## Checkpoint` heading and
   keep it terse — this file is the thin harness loop and its size is
   load-bearing (era 003's invariant). Target shape:

   ```
   checkpoint-tag (in this order, never a raw `git tag` alone — CER-083):
     1. <scripts>/flex_build.py record-checkpoint-step checkpoint-tag --project-dir .
        (resets checkpoint_step and marks the phase complete in the index)
     2. git tag cp-<phase-key> && git push origin main --tags
     3. promote the release channel:
        git -C /mnt/work/flex-harness merge --ff-only cp-<phase-key>
        (see docs/architecture.md § Release channel — flex-harness)
   ```

   **CLI first, then the tag** — deliberate, not incidental: if step 2 fails
   after step 1, the missing tag is loud and re-runnable and
   `record-checkpoint-step` is idempotent; if the order were reversed and step 1
   were skipped, the failure is silent and skips the next phase's gates. Say so
   in one clause so a later editor does not "tidy" the order.

2. **Template `.j2` § Checkpoint.** Make the same edit with the existing
   placeholders (`{{ pairmode_scripts_dir }}`,
   `{{ default_branch | default('main') }}`). **Omit item 3 entirely** — no
   downstream project has a `/mnt/work/flex-harness`, and the template is what
   `sync-build` writes into every consumer. Add no new `##` heading to either
   file (B3).

3. **Stamp the phase in `_record_checkpoint_step`** (`flex_build.py`, the
   function reached from `cmd_record_checkpoint_step`). In the same state dict
   that gets the appended step, set `checkpoint_phase` to the key from the
   existing `resolve_current_phase` read-model (the `checkpoint-tag` branch
   already resolves it — hoist that resolution rather than adding a second,
   differently-derived source of the phase key), falling back to `""` when it
   cannot be resolved. In the `checkpoint-tag` branch, reset `checkpoint_phase`
   to `""` alongside the existing `checkpoint_step = []` reset, in the same
   atomic write. Do not add a CLI flag, and do not thread an explicit phase key
   through the command — that is CER-077's fix, deliberately not this story's
   (`## Out of scope`).

4. **Guard the read side in `infer_position`** (`next_action.py`, the block that
   currently reads `state.json["checkpoint_step"]` into the position dict). Read
   `checkpoint_phase` from the same parsed state. If it is a non-empty string
   and does not equal the active phase's key, expose `checkpoint_step` as `[]`.
   Derive the active phase key from the already-resolved active phase file the
   same way the rest of the module does (file stem with the `phase-` prefix
   stripped) — do not re-parse the index a second time. Absent/empty stamp →
   honour the stored list (B6). Keep `next_action.py` write-free: the whole
   module is a pure read-model, and the resolver must never repair state it
   observes.

5. **Tests.** Add the three cases from B7 to
   `tests/pairmode/test_next_action.py`, following the existing pattern in
   `TestResolveNextActionCheckpoint` (drive the real `record-checkpoint-step`
   CLI via `subprocess` where you need a realistically-written state file;
   assert through `infer_position` + `resolve_next_action`, not through a
   synthetic position dict, so the read-model is exercised end to end). Add one
   case to `tests/pairmode/test_templates.py` asserting the rendered `.j2`
   satisfies B2's ordering and B4's absence of `flex-harness`.

6. **Write the promotion procedure into `docs/architecture.md`** (B8b) and into
   this story's `## Promotion record` placeholders (O1–O4). These are the exact
   commands the orchestrator runs at cp-102, from `/mnt/work/flex`, after the
   three gate workers have passed and the tag has been pushed. `<cp-tag>` is
   resolved, never assumed — existing tags use the `cp101-<slug>` shape, not
   `cp-102`:

   ```bash
   # P1 — resolve the tag and verify the fast-forward is legitimate
   git -C /mnt/work/flex tag --list 'cp102*'
   git -C /mnt/work/flex-harness status --porcelain --untracked-files=no   # must be empty
   git -C /mnt/work/flex merge-base --is-ancestor \
       "$(git -C /mnt/work/flex-harness rev-parse HEAD)" <cp-tag> && echo FF-OK

   # P2 — promote
   git -C /mnt/work/flex-harness merge --ff-only <cp-tag>

   # P3 — verify the pin
   git -C /mnt/work/flex-harness rev-parse HEAD
   git -C /mnt/work/flex rev-parse "<cp-tag>^{commit}"
   git -C /mnt/work/flex-harness describe --tags --exact-match HEAD

   # P4 — smoke the promoted toolchain (read-only)
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py \
     checkpoint-report --project-dir /mnt/work/flex
   ```

   Three details must survive into the docs, each with its reason:
   `--untracked-files=no`, because the vendored `node_modules` payload shows as
   untracked noise (CER-090) and would otherwise fail a naive cleanliness check;
   `--ff-only`, because a non-fast-forward means the sibling worktree holds
   commits nobody has triaged, and the correct response is to **stop and
   investigate**, never `--force` or `reset --hard`; and promotion **after** the
   gates, because the whole point of the channel is that the executed toolchain
   is one that passed them.

7. **Close CER-083** (B9): append the resolution note to the existing row's
   Finding cell and set its `Phase` cell to `102`. Leave the row where it is.

8. **Ideology note (Step 4a — resolved inline, no conflict).** Three points
   shaped this spec. "Rationale-bearing decisions over bare rules" is why the
   channel-vs-repoint decision, the CLI-before-tag ordering, and the
   `--ff-only`/no-force rule are all written with their reasons in `## Context`
   and in `docs/architecture.md` rather than left as bare commands — CER-083
   happened precisely because a bare instruction (`git tag && git push`) carried
   no hint that something else depended on it. "Never silently pass
   contradictions" is why B6's guard exists at all: documentation alone leaves
   the failure mode silent, and that constraint's rationale is that a system
   which misses contradictions gives false confidence. And "sidebar owns all
   state writes" is respected by keeping the new `checkpoint_phase` field
   single-writer — `record-checkpoint-step` writes it, `next_action.py` only
   reads it; the tempting shortcut of having the resolver clear a stale stamp it
   notices would create a second writer and is explicitly forbidden by step 4.

## Tests

Run from the story worktree root:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py tests/pairmode/test_templates.py tests/pairmode/test_record_checkpoint_step.py tests/pairmode/test_checkpoint_step.py -q 2>&1 | tail -30
```

Then the full suite, **without `-x`** so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance:

- the three new `test_next_action.py` cases (B7) and the new
  `test_templates.py` case (B2/B4) pass;
- `test_record_checkpoint_step.py` and `test_next_action.py`'s existing
  RESOLVER-017 / INFRA-239 regressions still pass unchanged — the stamp must not
  alter the reset or the index mark-complete;
- the full suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html`, the known
  worktree-environmental failure (CER-090). If it appears, state that it
  reproduces on clean `HEAD` and is unrelated to this diff.

Documentation-only assertions (B1, B3, B4, B8, B9) are verified by the reviewer
by reading the diff; B4 is additionally machine-checked:

```bash
grep -c 'flex-harness' skills/pairmode/templates/CLAUDE.build.md.j2   # must print 0
```

## Out of scope

- **Performing the fast-forward.** No builder or reviewer action touches
  `/mnt/work/flex-harness`. O1–O4 are orchestrator-executed at cp-102; the
  cp-102 tag does not exist during this build.
- **Renaming the `fold-prep` branch** to something like `release-channel`.
  Tempting, but the branch tracks `origin/fold-prep`, so a rename needs an
  origin-side rename plus a delete, and the thing that actually pins the channel
  is the tag, not the branch name. Cosmetic gain, real remote risk — declined
  deliberately.
- **Repointing `pairmode_scripts_dir` at `/mnt/work/flex`.** Considered and
  rejected in `## Context`; reopening it needs a new story carrying that
  argument.
- **Automating or gating the promotion** — a `promote-release-channel`
  subcommand, or a checkpoint guard that refuses to tag while the channel is
  behind. This story makes the step documented and verifiable; making it
  enforced is new CLI surface with its own tests and architecture entry.
- **CER-077** (threading an explicit phase key through `record-checkpoint-step`
  instead of re-deriving it from `resolve_current_phase`). This story consumes
  the existing resolution for the stamp and inherits its ambiguity; fixing the
  ambiguity is a separate finding with a separate fix.
- **CER-090** (vendored `node_modules` not fully tracked, failing the UI build
  gate in fresh worktrees) and **CER-091** (the async effort-recording defects
  INFRA-259 found). Neither is touched here.
- **`story_new.py`'s stub `touches:` trailing comment** (`story_new.py:67`,
  asserted by `test_story_new.py::test_story_frontmatter_touches_has_architecture_comment`),
  which the frontmatter parser reads as a scalar and which crashes
  `create-story-worktree` when a stub is built unedited. Real, fleet-wide, and
  worth a finding — but it is a different file, a different test, and a
  different blast radius. Recorded here for the orchestrator to route; not fixed
  by this story.
- **Fleet rollout of the release-channel pattern** to sibling projects. Only
  flex has a second worktree executing its own loop.
- **Any new persistent schema object.** `checkpoint_phase` is a key in the
  existing `.companion/state.json`, not a table; `schema_introduces: false`
  stands and no management-surface row is owed.

## Promotion record

<!-- P1–P4 correspond to Ensures O1–O4. The builder creates all four as
     RESULT: PENDING placeholders carrying the exact commands; the orchestrator
     fills them at cp-102, after the three gate workers pass and the tag is
     pushed. No subsection may be empty. -->

### P1. Preconditions (tag resolved, tracked-clean, ancestry)

<!-- owner: orchestrator, at cp-102 — commands: Instructions step 6, block P1 -->

RESULT: PENDING — owner: orchestrator, at cp-102

### P2. Fast-forward

<!-- owner: orchestrator, at cp-102 — commands: Instructions step 6, block P2 -->

RESULT: PENDING — owner: orchestrator, at cp-102

### P3. Pin verification

<!-- owner: orchestrator, at cp-102 — commands: Instructions step 6, block P3 -->

RESULT: PENDING — owner: orchestrator, at cp-102

### P4. Promoted-toolchain smoke

<!-- owner: orchestrator, at cp-102 — commands: Instructions step 6, block P4 -->

RESULT: PENDING — owner: orchestrator, at cp-102

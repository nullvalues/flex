---
id: RELEASE-068
rail: RELEASE
title: Migrate pokus to pairmode 0.3.0 — canon files only
status: planned
phase: "106"
auth_gated: false
schema_introduces: false
story_class: docs
primary_files:
  - docs/stories/RELEASE/RELEASE-068.md
touches:
  - docs/stories/RELEASE/RELEASE-068.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

<!-- SPEC-WRITER NOTE (frontmatter): the stub arrived with `status: draft`, no
     `primary_files:` key, `touches: []` and no `story_class:`. All four were
     populated here per the RELEASE-064..067 precedent (operator-directed): the
     single in-repo write target is *this file* — the `## Evidence` section
     appended by the executor. Every other write target is outside the repo,
     under `/mnt/work/pokus`, and therefore cannot appear in `touches:` at all;
     that is the point of phase 106 § Execution model. The cross-repo write set
     is enumerated instead in `## Cross-repo scope boundaries` below.
     Both lists are written **block-style**, not flow-style: per RELEASE-066
     new-2 / CER-115, `primary_files: [a, b]` parses as a *string* in the
     frontmatter reader and crashes `create-story-worktree`'s
     `generate_permissions_artifact` with a `TypeError`. Do not "tidy" these into
     flow style.
     The title was narrowed from "Migrate pokus to pairmode 0.3.0 (coordinate
     around in-flight UAT-gated work)" per the operator directive recorded in
     § Context. -->

## Context

Phase 106 drives the remaining pairmode 0.3.0 fleet migrations centrally from
flex. RELEASE-063 was the canary (meander); RELEASE-064..067 migrated lumin,
caddy, forqsite.help and halfhorse using the six-step mechanic in
`docs/harness-cutover-runbook.md` § *Per-project mechanic*, each run carrying the
full evidence load: migration **plus** a proving story cycle inside the target
whose attempt rows proved the CER-101/103/104 recording cluster downstream.

**Target repo: `/mnt/work/pokus`.**

### OPERATOR DIRECTIVE (2026-07-29) — this story is canon-only

The original RELEASE-068 scope was "migrate pokus, coordinating around its
in-flight UAT-gated work" (pokus holds its own proposed migration phase,
`docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`, explicitly
gated on TEST-002 clearing). The operator has **eliminated that coordination
risk by narrowing the story rather than scheduling around it**:

> Canon-only migration of pokus — sync the pairmode 0.3.0 canon files into
> `/mnt/work/pokus` and nothing more, so phase 106 can close.

Consequences, stated plainly so no executor re-widens them:

- **No proving story cycle.** Mechanic step 6 (the sibling stories' E5/E6/E7) is
  **not** run here. The phase-106 § *Checkpoint proves* clause — "each migrated
  project completed one proving story cycle" — is **narrowed for pokus by this
  directive**. RELEASE-071 (campaign close) must record pokus as
  *canon-synced, proof-deferred* rather than silently counting it as proven. The
  campaign's downstream proof already exists (forqsite.help CONTENT-005 row 14,
  operator-ruled qualified pass; re-confirmed on halfhorse) — pokus is not
  load-bearing for it.
- **Nothing outside canon surfaces is touched.** Not pokus's Kotlin/Android code,
  not its `docs/`, not its stories or backlog, not TEST-002/TEST-003, not its
  proposed migration phase doc, not its UAT harness. See
  § *Cross-repo scope boundaries* for the exhaustive write list.
- **The coordination question does not arise.** Recon (below) confirms pokus has
  **no build attempt in flight**: working tree clean at `1bf8383`, no
  `current_story` in `.companion/state.json`, no story worktrees, TEST-002 and
  TEST-003 both `status: planned`. Canon sync cannot collide with an in-flight
  story because there is not one.

### Recon — pokus's actual state (captured 2026-07-29, read-only)

Recorded here so the executor can detect drift rather than rediscover the
baseline. These are **expectations, not evidence** — re-observe every one and
record what actually prints (see `## Ensures` C1).

| Fact | Observed value |
|---|---|
| `.companion/state.json` `pairmode_version` | `0.2.0` |
| `.companion/state.json` `expected_step_tokens` | `53000` — exactly the Era-2 stamp, so `to-030` will rewrite it to `5000` (CER-111) |
| `.companion/state.json` `effort_tracking` | `true` (already set — no backfill) |
| `.companion/state.json` residue keys | no `pipe_path`, no `context_story_tokens`, no `attempt_counter.json` present |
| `fleet_discovery.py` | `binding: version`, `signal1 (scripts path): absent — no-declaration`, `signal2: 0.2.0` |
| `pairmode_sync.py audit-hooks` | `no duplicate hook registrations found` |
| `.claude/agents/` | six fat 0.2-era shells (`builder`, `reviewer`, `loop-breaker`, `security-auditor`, `intent-reviewer`, `reconstruction-agent`); **`gate-worker.md` missing** |
| Stale result grammar in agent bodies | `builder.md` 1 hit, `reviewer.md` 1 hit (`BUILD-RESULT: DONE` / `REVIEW-RESULT: PASS`); other four clean |
| `sync.py --dry-run` RETIRED prunes | **46 sections, every one under `.claude/agents/*.md`, all attributed to INFRA-241** — zero prunes proposed in `CLAUDE.md` or `CLAUDE.build.md` |
| `.pairmode-overrides` | present but **comment-only — no declared entries** (so the L022 apply-path defect is inert here) |
| `.claude/settings.json` hook commands | all four point at **`/mnt/work/flex/hooks/*.py`** (the dev checkout), not the release channel — CER-127 class (1). Those files **do exist**, so pokus's sessions are not broken |
| `.claude/settings.local.json` | exists, 7 `Write(`/`Edit(` allow rules (no sediment problem — meander had 133) |
| Test surface | one pytest file, `tests/test_context_budget_check.py`; the project's real gate is `cd app && ./gradlew assembleDebug` |
| `pairmode_context.json` `test_command` | `cd app && ./gradlew assembleDebug` — this is what canon `CLAUDE.build.md`'s **Build standards** line will carry |

### What "canon files" means here, mechanically

The sync tooling's own registries define the surface — do not invent a wider or
narrower one:

- `audit.py` **`CANONICAL_FILES`** — `CLAUDE.md`, `CLAUDE.build.md`, and seven
  agent shells under `.claude/agents/` (`reconstruction-agent`, `gate-worker`,
  `builder`, `reviewer`, `loop-breaker`, `security-auditor`, `intent-reviewer`).
- `audit.py` **`SCAFFOLD_FILES`** — `docs/brief.md`, `docs/phases/index.md`,
  `docs/cer/backlog.md`. Section bodies here are **project-owned**; sync
  preserves them and **never prunes** them. This story does not "fix" scaffold
  files, and any INCONSISTENT/STALE PLACEHOLDER finding on them is recorded, not
  actioned.
- `.companion/state.json` — the `pairmode_version` stamp (written by `sync.py`'s
  state merge) and the `to-030` schema normalisation.
- No `skills/` payload is copied into a consuming repo by any sync path. pokus
  has no `skills/` directory and this story does not create one.

### Hazards this phase's own landings introduced

1. **Canon-retirement pruning is live (INFRA-311, cp-113).** `sync.py` now
   *deletes* downstream sections whose normalised key appears in
   `RETIRED_SECTIONS`. pokus is the first project this campaign syncs with that
   path active, and it has **46 matches**. Pruning is correct here — those
   sections are the pre-INFRA-241 fat agent bodies — but it is destructive and
   must be previewed.
2. **`sync-all --dry-run` cannot preview it (CER-133 item 6).**
   `pairmode_sync.py sync_all` marks the `sync.py` entry `skip_in_dry_run=True`
   and prints *"skipped: sync.py does not support --dry-run"* — a stale claim
   since INFRA-311. The wrapper's dry-run therefore shows **none** of the 46
   prunes. The preview in `## Instructions` step 3 routes around this by
   invoking `sync.py --dry-run` **directly**. Do not substitute
   `sync-all --dry-run` and call it a preview.
3. **`RETIRED_SECTIONS` keys are not file-scoped (CER-133 item 2).** A generic
   key such as `## before reviewing` or `**3. build gate**` would match a
   *legitimate project extension* of the same name in any canonical file. The
   per-section confirmation prompt on the apply path is the only guard. Recon
   found no collision in pokus (all 46 prunes land in agent files whose bodies
   are verifiably the retired canon), but the executor re-verifies rather than
   trusting that: **decline any prune whose section is not verifiably stale
   canon in a canonical file.**
4. **`.pairmode-overrides` is not honoured on the apply path (L022, cora).**
   Declaring a section there protects it at *audit* time only. pokus has no
   declared entries, so nothing is at risk — but do not add entries mid-story and
   assume they will hold.
5. **Canon replaces pokus's inline review checklist, and that is intended.**
   pokus's `CLAUDE.md` § *Review checklist* is a 0.2-era inline four-item list
   including its gradle build gate; canon replaces it with the thin pointer to
   `skills/pairmode/skills/reviewer/procedure.md`. The gradle gate is **not
   lost** — it survives as `test_command` on `CLAUDE.build.md`'s **Build
   standards** line, which the reviewer procedure skill reads (INFRA-240). C5
   verifies exactly that before the replacement is accepted as safe. Separately,
   that pointer path is repo-relative and does not resolve inside a consumer repo
   with no `skills/` payload — record it as a finding (C13), do not fix it here.
6. **CER-127 / INFRA-319.** pokus's hook commands point at `/mnt/work/flex/hooks`
   and **no sync or migrate rule rewrites hook command paths**. They will still
   point there after this story. That is CER-127 class (1) field evidence for
   INFRA-319 (phase 114) and is recorded, not surgically fixed — see C8 for the
   single narrow exception.

Two things about how this story runs are settled by phase 106 § *Execution model
(cross-repo — deviation from the standard loop)*, which you should read before
acting:

1. **No sandboxed builder subagent, no flex worktree.** The write targets live at
   `/mnt/work/pokus`, outside this repo; the worktree loop and `scope_guard.py`
   forbid writes there — correctly. Execution is **orchestrator-level with the
   operator present**.
2. **Acceptance is evidence-shaped, not diff-shaped.** The flex-side diff is one
   `## Evidence` section appended to this file.

The pairmode CLIs are invoked from the **permanent release channel**,
`/mnt/work/flex-harness` — canonized in `docs/architecture.md` § *Release channel
— flex-harness* and by RELEASE-062 (phase 105). Do not invoke them from
`/mnt/work/flex/skills/...`: the channel is what the fleet consumes, and it is
also what makes the resulting `pairmode_scripts_dir` declaration correct.

## Cross-repo scope boundaries

Phase 106 § *Execution model* permits this story to write outside
`/mnt/work/flex`. That permission is **not** open-ended. The complete write set
is enumerated here; anything not listed is read-only or forbidden, and a write
outside this list is a scope violation to be reported, not rationalized.

**Writable — inside `/mnt/work/flex`:**

- `docs/stories/RELEASE/RELEASE-068.md` — this file, `## Evidence` section only.
- Rows in `docs/phases/phase-106.md`, `docs/phases/index.md` and the era/effort
  ledgers **only** as written by the orchestrator's own recording CLIs
  (`flex_build.py` status/record subcommands). Hand-edits are not part of this
  story.

**Writable — inside `/mnt/work/pokus`, and only via the pairmode CLIs:**

- `CLAUDE.md` — canonical sections updated by `sync.py`.
- `CLAUDE.build.md` — regenerated wholesale to the 0.3.0 thin-harness template by
  `sync-build` (the final step of `sync-all`).
- `.claude/agents/builder.md`, `reviewer.md`, `loop-breaker.md`,
  `security-auditor.md`, `intent-reviewer.md`, `reconstruction-agent.md` —
  canonical sections appended, retired sections pruned, frontmatter and legacy
  headings rewritten by `sync.py` + `sync-agents`.
- `.claude/agents/gate-worker.md` — **created** (currently missing).
- `.companion/state.json` — `pairmode_version` stamp (`sync.py`) and 0.3.0 schema
  normalisation (`to-030`).
- `.companion/state.json.lock` — transient advisory-lock residue; **delete only**,
  never commit.
- `.claude/settings.local.json` — **only** if the operator explicitly approves a
  prune (7 rules; no sediment problem is expected), and only after a backup is
  written alongside it.
- Git objects/refs in pokus, via **one** migration commit (and its push).

**Read-only — never written by this story:**

- `/mnt/work/flex-harness` (the release channel) — scripts are *invoked* from it.
  `git -C /mnt/work/flex-harness status --porcelain` must print nothing at the end.
- Everything else under `/mnt/work/pokus`: `app/`, `product-spec/`, `scripts/`,
  `tests/`, `gradle*`, `docs/**` (including `docs/brief.md`,
  `docs/phases/index.md`, `docs/cer/backlog.md` — the `SCAFFOLD_FILES` trio),
  `docs/stories/**`, `docs/uat/**`, `docs/eras/**`,
  `phase-01-android-mediaprojection-magnifier.md`,
  `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`,
  `.claude/settings.json` (see C8), `.claude/settings.deny-rationale.json`,
  `.pairmode-overrides`, `.companion/effort.db`,
  `.companion/pairmode_context.json`, `.companion/modules.json`,
  `.companion/product.json`, `README.md`.
- `/mnt/work/meander`, `/mnt/work/lumin`, `/mnt/work/caddy`,
  `/mnt/work/forqsite.help`, `/mnt/work/halfhorse` — already migrated. No re-sync.

**Forbidden outright:**

- Every other project directory under `/mnt/work/` — RELEASE-069 and RELEASE-070
  own base56 and cora.
- Running any pokus story, spec-writing any pokus story, sequencing pokus's
  proposed migration phase, or editing pokus's backlog/index/era docs.
- `docs/harness-cutover-runbook.md` and `docs/cer/backlog.md` in flex — findings
  are *named* under C13, never applied here.

## Requires

- **The operator directive above is the governing scope.** If any instruction in
  the runbook, the phase doc, or a sibling story implies work beyond canon
  surfaces (most importantly mechanic step 6, the proving cycle), **this spec
  wins** and the wider step is skipped with a one-line note.
- **cp-105, cp-110, cp-111, cp-112 and cp-113 are tagged in flex and their
  content is in the release channel.** cp-113 matters specifically: it carries
  INFRA-311's retirement pruning, which this story exercises. A tag in flex is
  not evidence the channel was fast-forwarded — verify the channel directly.
- **RELEASE-063..067 are complete with their `## Evidence` sections present.**
  This story is specced against their playbook notes; it does not re-derive them.
- **RELEASE-069, RELEASE-070, RELEASE-071 are still `draft`.**
- `/mnt/work/pokus` exists as a git repository, its working tree is **clean**,
  and it has **no build attempt in flight** (no `current_story` in
  `.companion/state.json`, no `.companion/attempt_counter.json` naming a live
  story, no story worktrees). Per canary playbook note 1 a dirty tree is a
  **stop** with no runbook step covering it: the operator decides (discard,
  commit, or abort) and the decision is recorded verbatim. Do not stash around it
  unilaterally.
- **The operator is present.** The retirement-prune acceptance (C2/C3), any
  `settings.local.json` decision (C9), and any CER-127 escalation (C8) are
  operator calls. Canary note 7's auto-mode permission-classifier block on the
  first out-of-repo `--apply` is still unsettled (1-of-5) and needs the operator
  to toggle auto mode if it fires.
- Known flex-side environmental failure inside fresh worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story.

## Ensures

Each assertion is verified from recorded command output pasted into this file's
`## Evidence` section (see `## Instructions` step 10). "Recorded" means the exact
command and its exact output, not a paraphrase. An Ensure whose evidence is
missing from that section is a **fail**, regardless of whether the underlying
thing happened.

**C0. Preconditions are evidenced, not assumed.**
`## Evidence` records:
- `git -C /mnt/work/flex tag --list 'cp-105' 'cp-110' 'cp-111' 'cp-112' 'cp-113'`
  showing all five;
- a check that `/mnt/work/flex-harness` carries **cp-113** content — e.g.
  `git -C /mnt/work/flex-harness log --oneline -3` showing the phase-113
  checkpoint commits, or a `rev-parse` comparison against flex's `cp-113`. If the
  channel is behind, this is a **stop**; fast-forwarding it is not this story's
  work;
- `grep -c RETIRED_SECTIONS /mnt/work/flex-harness/skills/pairmode/scripts/sync.py`
  returning non-zero — the channel copy actually has the pruning path;
- the RELEASE-063..067 completeness check and the RELEASE-069..071 `draft` check;
- the operator directive quoted, with the one-line statement that mechanic step 6
  is deliberately not run.

**C1. A pre-sync baseline exists and pokus is unambiguously identified.**
`## Evidence` contains, captured **before any write to pokus**:
- the verbatim `fleet_discovery.py --no-snapshot` block for `/mnt/work/pokus`
  (`--no-snapshot` is **mandatory** — 4-of-5 prior runs, plus INFRA-295's
  refuse-by-default), showing `binding`, `signal1`, `signal2`, plus the run's
  `Projects with duplicate hooks:` line;
- `git -C /mnt/work/pokus log --oneline -3`, `git -C /mnt/work/pokus status --porcelain`
  (must be empty), and `git -C /mnt/work/pokus branch --show-current`;
- `readlink -f /mnt/work/pokus` confirming no symlink indirection and that no
  similarly-named sibling was scanned in its place;
- the in-flight check: `.companion/state.json` has no `current_story`, and
  `.companion/attempt_counter.json` is absent or names no live story;
- the **pre-sync values** of `pairmode_version` and `expected_step_tokens` from
  `.companion/state.json` (CER-111: reading `expected_step_tokens` only
  afterwards makes the delta unrecoverable);
- the **pre-sync** stale-grammar counts:
  `grep -rc 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS' /mnt/work/pokus/.claude/agents/*.md`;
- the four hook command strings from `.claude/settings.json`, verbatim;
- `ls /mnt/work/pokus/.claude/agents/` (recording that `gate-worker.md` is absent);
- one line naming which starting shape pokus is in (expected: **bound-0.2.x,
  no-declaration** — the ordinary branch lumin/caddy/forqsite.help/halfhorse took).

If any observed value differs from the § Recon table, say so explicitly and
re-assess before applying anything.

**C2. The destructive preview was taken with `sync.py` directly, and every
proposed prune was verified.**
`## Evidence` records the full output of

```bash
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/sync.py \
  --project-dir /mnt/work/pokus --dry-run
```

(run from `/mnt/work/flex-harness`), including:
- the complete `RETIRED (canon-removed, would prune):` list with its **count**;
- the complete `Would apply (dry-run):` list;
- the `Preserved:` list;
- an explicit statement, per CER-133 item 2, that **every** retired key in the
  list belongs to a `CANONICAL_FILES` agent shell whose body is verifiably
  pre-INFRA-241 canon — **and not** to a pokus-authored extension that merely
  shares a section name. Naming the files the prunes land in
  (expected: `.claude/agents/*.md` only, zero prunes in `CLAUDE.md` /
  `CLAUDE.build.md`) satisfies this.
- an explicit note that `sync-all --dry-run` was **not** used as the preview,
  citing CER-133 item 6 (`skip_in_dry_run=True` hides the entire sync.py step).

If the preview proposes a prune in `CLAUDE.md` or `CLAUDE.build.md`, or any prune
the executor cannot tie to retired canon, that prune is **declined** and the fact
is recorded. A declined prune is not a story failure; an unexamined prune is.

**C3. Canon is applied, and pokus reports 0.3.0.**
`## Evidence` records the `sync-all --apply` invocation and its output (all three
downstream steps: `sync (methodology files)` → `sync-agents` → `sync-build`), and
then:

```bash
grep pairmode_version /mnt/work/pokus/.companion/state.json
```

reading exactly `"pairmode_version": "0.3.0"`.

**C4. pokus binds the release channel.**
A post-sync `fleet_discovery.py --no-snapshot` run, in the **same command form as
C1** so the two are directly comparable, shows for `/mnt/work/pokus`:
- `signal2 (pairmode_version): 0.3.0`
- `signal1 (scripts path): /mnt/work/flex-harness/skills/pairmode/scripts`
- `binding: both`

All three. `binding: version` post-sync is a **fail**: the stamp landed but the
scripts declaration did not, and pokus would still consume an unknown copy.

**C5. `CLAUDE.build.md` is the thin template *and* pokus's real gate survived.**
`## Evidence` records:
- `grep -c 'flex_build.py next-action' /mnt/work/pokus/CLAUDE.build.md` — all five
  prior runs printed `2`; plus a `head -8` showing the thin dispatch preamble and
  the `pairmode_scripts_dir = /mnt/work/flex-harness/skills/pairmode/scripts`
  line;
- the rendered **Build standards** line verbatim
  (`grep -n 'Build standards' /mnt/work/pokus/CLAUDE.build.md`), showing
  ``test_command=`cd app && ./gradlew assembleDebug` ``. This is the assertion
  that pokus's gradle gate survived the `CLAUDE.md` review-checklist
  canonicalisation. If `test_command` renders as `(unset)`, that is a **stop** —
  the gate was lost and the sync must be rolled back per
  `docs/harness-cutover-runbook.md` § *Rollback procedure*;
- the fact that no 0.2-era fat loop section survived the regeneration: `sync-build`
  rewrites the file wholesale, so `grep -c '## Checkpoint sequence' ` (or any other
  pokus-era heading from the pre-sync file) returns `0`. Record one such check.

**C6. The seven canonical agent shells are current and the retired bodies are
gone.**
`## Evidence` records:
- `ls /mnt/work/pokus/.claude/agents/` showing all seven canonical files including
  the newly created `gate-worker.md`;
- for a **named sample of at least eight** pruned section headers spanning all
  five pruned agent files (e.g. `## Starting a story`, `## Implementation rules`,
  `## Review checklist`, `**3. Build gate**`, `## Your process`,
  `## Audit priorities`, `### 4. Domain isolation violation`,
  `## Design pivot detection`), a case-insensitive grep over
  `/mnt/work/pokus/.claude/agents/*.md` returning **zero** hits, plus the total
  prune count reported by the apply run compared against C2's dry-run count;
- the **post-sync** stale-grammar check —
  `grep -rn 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS' /mnt/work/pokus/.claude/agents/*.md`
  returns nothing (or only occurrences that are explicitly part of the new
  legacy-tolerance documentation), recorded as a delta against C1's pre-sync
  counts (expected: `builder.md` 1 → 0, `reviewer.md` 1 → 0). A surviving stale
  example is the caddy shape that re-blocked this campaign once; report it to the
  operator rather than proceeding;
- a spot-check that each shell now carries `## Inputs`, `## Procedure` and
  `## Return`, and that its `## Procedure` points at a
  `skills/pairmode/skills/<role>/procedure.md` path.

**C7. `to-030` ran, and its state deltas are recorded before and after.**
`## Evidence` records the `to-030 --apply` output in full, and specifically:
- `expected_step_tokens` **pre** (expected `53000`) and **post** (expected
  `5000`), and whether the rewrite was silent or accompanied by a WARN. This is
  the CER-111 comparison: 3-of-4 keep-with-WARN vs 1-of-4 silent rewrite; pokus
  carries the exact Era-2 stamp so a **rewrite** is expected — say so and add it
  to the tally;
- whether the `[agent-cleanup]` step printed *"content differs from known 0.2.x
  template … manual porting required"* (canary note 4 / RELEASE-065 new-2; fired
  on all five prior runs). Because `to-030` runs **after** the sync, the agent
  hashes cannot match the Era-2 allowlist, so this WARN is expected noise here —
  record it **paired with C6's clean grep**, which is what makes it survivable;
- that no state key outside `{pairmode_version, last_sync, lessons_applied,
  expected_step_tokens}` plus the INFRA-133 context-budget defaults changed:
  paste the full pre- and post-sync `.companion/state.json` side by side.

**C8. CER-127 hook-path state is recorded as INFRA-319 evidence, and not
surgically fixed.**
`## Evidence` records:
- the four hook command strings from `/mnt/work/pokus/.claude/settings.json`
  **after** the sync, showing they are unchanged (expected: still
  `uv run python /mnt/work/flex/hooks/<hook>.py`) — i.e. **no sync or migrate
  rule rewrites hook command paths**, which is CER-127 class (1) confirmed in the
  field;
- `ls /mnt/work/flex/hooks/` proving those paths **resolve on this machine**, so
  pokus's sessions are not broken and the stale binding is a portability/channel
  defect rather than an outage;
- `pairmode_sync.py audit-hooks --project-dir /mnt/work/pokus` (dry-run) output,
  and an explicit note that any remaining `DUPLICATE:` lines are plugin-sourced
  and non-pairmode (CER-110; `Projects with duplicate hooks: 0` is **not**
  asserted by this story). Recon saw none;
- one sentence linking the finding to **INFRA-319 (phase 114)** as its fix owner,
  and stating that this story performed **no** hook-path rewrite.

**Narrow exception — the only case where a settings rewrite is in scope.** If the
hook command paths do **not** resolve (files absent, so every pokus prompt would
hard-fail with `can't open file ...`), then and only then apply the **minimal**
rewrite: repoint the four existing pairmode hook commands at
`/mnt/work/flex-harness/hooks/<same-basename>.py`, changing nothing else in
`settings.json`, and record (a) the pre/post JSON diff, (b) the justification
(sessions would be broken outright), and (c) that this is a containment action
which does **not** discharge INFRA-319. Adding, removing or reordering hook
entries, touching non-pairmode hooks, or generalising the paths is out of scope
either way.

**C9. No non-canon file in pokus was modified.**
`## Evidence` records `git -C /mnt/work/pokus status --porcelain` (pre-commit) and
`git -C /mnt/work/pokus show --stat HEAD` (post-commit). The changed-path set must
be a **subset** of:

```
CLAUDE.md
CLAUDE.build.md
.claude/agents/builder.md
.claude/agents/reviewer.md
.claude/agents/loop-breaker.md
.claude/agents/security-auditor.md
.claude/agents/intent-reviewer.md
.claude/agents/reconstruction-agent.md
.claude/agents/gate-worker.md
.companion/state.json
```

plus `.claude/settings.json` **only** under C8's narrow exception, and
`.claude/settings.local.json` **only** with the recorded operator approval from
C10. Any other path — `app/**`, `docs/**`, `tests/**`, `product-spec/**`,
`.pairmode-overrides`, `.companion/effort.db` — appearing in that set is a
**scope violation**: stop, report it, and roll back per the runbook's
§ *Rollback procedure* rather than committing.

Additionally, per **CER-116**: the migration commit subject must **not** name a
`RELEASE-0NN` story ID — it is pokus's own history. `## Evidence` records the
subject verbatim (recommended:
`sync: migrate to pairmode 0.3.0 canon (canon files only)`).

**C10. `settings.local.json` is handled deliberately.**
`## Evidence` records whether `/mnt/work/pokus/.claude/settings.local.json`
exists, its `Write(`/`Edit(` rule count (recon: 7), and the **operator's decision
quoted** — the expected decision being **keep** (7 rules is not the meander-class
sediment problem). If pruned, record the post-prune count and the backup
location. "Not mentioned" is a fail; do not prune unilaterally.

**C11. pokus's cheap test surface is green, and its heavy gate is explicitly out
of scope.**
`## Evidence` records:
- the result of running pokus's single pytest file, from `/mnt/work/pokus`:
  `PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -q` (or `python -m pytest`
  if pokus has no uv project file — record which was used and why). Green is the
  expected result; a failure must be diagnosed as pre-existing or sync-caused,
  and a sync-caused failure is a **stop**;
- an explicit statement that `cd app && ./gradlew assembleDebug` — pokus's real
  build gate — was **not** run, because this story changes no Kotlin/Android
  source and an Android build is out of scope for a canon-only migration. Record
  it as a deliberate exclusion, not an omission.

**C12. Cleanliness — the flex-side diff is this file only, and the channel is
untouched.**

```bash
git -C /mnt/work/flex diff --name-only
git -C /mnt/work/flex-harness status --porcelain
```

The first lists exactly `docs/stories/RELEASE/RELEASE-068.md` (plus phase/index/
ledger rows if the orchestrator's recording CLIs touch them — tool-written, not
hand-written). No file under `skills/`, `tests/`, `ui/` or `.claude-plugin/` is
modified. The second prints **nothing**. `## Evidence` also states whether any
snapshot file was written and where; note that
`/mnt/work/flex-harness/docs/fleet-snapshot.md` exists as a tracked historical
artifact — its presence is not pollution, its **modification** is.

**C13. Findings are named, not fixed — and the narrowed scope is stated for
RELEASE-071.**
`## Evidence` ends with a **Findings / follow-ups** subsection that:
- states, for each of the six hazards in § Context, whether it **materialised**,
  **did not**, or **was not applicable**, with the observed evidence — in
  particular CER-133 items 2 and 6, CER-127, CER-111, canary note 4 and canary
  note 7;
- names any *new* deviation this run produced, with its intended destination
  (runbook amendment, CER, or lesson). Per the standing policy, **ask the
  operator before filing** anything to `docs/cer/backlog.md`; this story edits
  neither the backlog nor the runbook. Two follow-ups are already known and must
  appear: (i) canon `CLAUDE.md` § *Review checklist* and the agent shells' §
  *Procedure* point at repo-relative `skills/pairmode/skills/...` paths that do
  not resolve in a consumer repo carrying no payload (same portability class as
  CER-127; observed on pokus); (ii) pokus still holds
  `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`, now
  partially satisfied — reconciling or retiring it is **pokus's own** work in its
  own session, not this story's;
- states in one sentence, for RELEASE-071 to consume: *pokus is canon-synced at
  0.3.0 with no proving cycle; the phase-106 checkpoint-proves clause is narrowed
  for pokus by the 2026-07-29 operator directive, and pokus must be counted as
  proof-deferred, not proven.*

**C14. flex's own suite is unaffected.**
`uv run pytest tests/pairmode/` is run once at the end, **without `-x`** (a known
pre-existing failure otherwise masks later real ones), and is green except the
CER-090 worktree-environmental failure if it appears. This story changes no flex
code, so any *new* failure means something ran that should not have.

## Instructions

**Execution model — read before anything else.** You are executing this story **at
orchestrator level with the operator present**, not as a sandboxed builder
subagent in a flex worktree. **Do not create a story worktree. Do not dispatch a
builder subagent.** The write targets are outside this repo and `scope_guard.py`
will block a subagent from reaching them — correctly — and working around that
block is itself a violation. The only in-repo write is this file's `## Evidence`
section, appended at step 10. Read § *Cross-repo scope boundaries* before the
first write and treat it as the complete permission list.

All pairmode CLI invocations below are run **from `/mnt/work/flex-harness`** with
`PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/<script>.py`.

1. **Prove the gate state (C0).** Verify the five `cp-*` tags in flex, that the
   channel carries cp-113 content, and that the channel's `sync.py` contains
   `RETIRED_SECTIONS`. Verify RELEASE-063..067 complete and RELEASE-069..071
   `draft`. Quote the operator directive from § Context. If the channel is behind,
   **stop** and hand back to the operator.

2. **Capture the baseline (C1) before touching anything.** Run
   `fleet_discovery.py --no-snapshot` (never without `--no-snapshot`) and capture
   pokus's block; capture git log/status/branch, `readlink -f`, the in-flight
   check, both state-json values, the stale-grammar counts, the four hook command
   strings, and the agents directory listing. If the tree is dirty or a story is
   in flight, **stop** — that is an operator decision, recorded verbatim.

3. **Preview the destructive path with `sync.py` directly (C2).** Run
   `sync.py --project-dir /mnt/work/pokus --dry-run` and capture the entire
   output. Do **not** use `sync-all --dry-run` for this: CER-133 item 6 —
   `sync_all` sets `skip_in_dry_run=True` on the `sync.py` entry and prints
   *"skipped: sync.py does not support --dry-run"*, hiding every prune.
   Then, with the operator, walk the `RETIRED` list: confirm each key's file is a
   `CANONICAL_FILES` agent shell and each section body is pre-INFRA-241 canon.
   **Decline** — and record — any prune you cannot tie to retired canon, and any
   prune proposed inside `CLAUDE.md` or `CLAUDE.build.md`. Expected shape from
   recon: 46 prunes, all in `.claude/agents/*.md`, all INFRA-241.

4. **Apply canon (C3).** Run

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     skills/pairmode/scripts/pairmode_sync.py \
     sync-all --project-dir /mnt/work/pokus --apply
   ```

   Order matters and the wrapper enforces it: `sync.py` (canonical sections +
   retirement prunes + `state.json` stamp) → `sync-agents` (frontmatter and
   cp-112 legacy-heading replacement) → `sync-build` (wholesale `CLAUDE.build.md`
   regeneration, which discards the hybrid `sync.py` leaves behind). Do not run
   the three by hand in a different order, and do not stop after `sync.py`.

   **On `--yes`:** the runbook's step-3 form is `--apply --yes`, which suppresses
   the per-section confirmation that is CER-133 item 2's **only** guard. Prefer
   `--apply` without `--yes` so each prune and each section update is confirmed.
   If the environment cannot answer interactive prompts, `--yes` is permitted
   **only** because step 3 already reviewed the complete prune list with the
   operator — record that reasoning verbatim in `## Evidence`, and if any prune
   was declined at step 3, `--yes` is **forbidden**: resolve it interactively or
   stop.

   If the auto-mode permission classifier blocks the first out-of-repo write
   (canary note 7), ask the operator to toggle auto mode off so the permission
   prompt surfaces. Do not work around the block.

5. **Normalise state (C7).** Run
   `pairmode_migrate.py to-030 --project-dir /mnt/work/pokus --apply` **after**
   the sync, capturing the full output. Record the `expected_step_tokens`
   pre/post delta and the `[agent-cleanup]` WARN. Delete
   `.companion/state.json.lock` if it is left behind; never commit it.

6. **Verify the binding and the loop (C4, C5, C6).** Re-run
   `fleet_discovery.py --no-snapshot` in the same form as step 2 and require
   `binding: both`. Then run the `CLAUDE.build.md` checks — including the **Build
   standards `test_command`** check, which is the one that proves pokus's gradle
   gate survived — and the agent-shell checks (seven files present, sampled
   pruned headers absent, stale grammar clean, `## Inputs`/`## Procedure`/
   `## Return` present). If `test_command` renders `(unset)`, or a stale grammar
   example survived, **stop** and hand back to the operator; the runbook's
   § *Rollback procedure* (`git checkout HEAD -- CLAUDE.build.md
   .companion/state.json`, widened to the agent files and `CLAUDE.md`) is the
   exit path.

7. **Record CER-127 without fixing it (C8).** Re-read the four hook commands from
   pokus's `settings.json`, confirm they are unchanged and that the referenced
   files exist, run `audit-hooks` in dry-run, and write the INFRA-319 linkage
   sentence. Only if the paths do **not** resolve, apply C8's narrow minimal
   rewrite with its three recorded justifications. Do not perform any other
   hook-path work — that is INFRA-319's story.

8. **Handle `settings.local.json` (C10) and the test surface (C11).** Present the
   rule count to the operator and record the decision verbatim (expected: keep).
   Run pokus's pytest file and record the result; record the gradle exclusion
   explicitly.

9. **Commit once in pokus (C9).** Verify `git status --porcelain` against C9's
   allowlist **before** staging. Stage only allowlisted paths — prefer explicit
   `git add <path> …` over `git add -A`, so an unexpected path fails loudly
   instead of riding along — then commit with a subject that names no
   `RELEASE-0NN` ID (recommended:
   `sync: migrate to pairmode 0.3.0 canon (canon files only)`), and push. If any
   non-allowlisted path is dirty, **stop** and report it rather than committing.

10. **Write `## Evidence` in this file (C0–C14).** Append a single `## Evidence`
    section with one subsection per Ensure, in order, each holding the exact
    command and its exact output. Close with the **Findings / follow-ups**
    subsection C13 requires, including the RELEASE-071 proof-deferred sentence.
    Ask the operator before filing anything into `docs/cer/backlog.md`.

11. **Verify cleanliness and flex's suite (C12, C14).** Run the two cleanliness
    commands, then flex's suite **without `-x`**.

12. **Report.** State canon-only migration complete, `pairmode_version` 0.3.0,
    `binding: both`, no non-canon file touched, no proving cycle run (by
    directive), and list the follow-ups named.

**Ideology note.** `docs/ideology.md` was read. The narrowing this story applies
— canon surfaces only, findings named not fixed, no bespoke hook surgery — is
resolved *toward* the constraint rather than through it: where the global
"conceptual rebuild completeness" instinct would push for also fixing CER-127 and
reconciling pokus's proposed phase doc, this spec routes both to their owning
stories (INFRA-319; pokus's own session) and records the deferral explicitly
rather than silently omitting it.

**Spec-preflight note (INFRA-320 § C).** The scan reports
`scope: skills/pairmode/scripts/pairmode_sync.py is named in Ensures/Instructions
but is not in declared scope`. That is **intentional and must not be "fixed" by
widening `touches:`**: the script is *invoked read-only from the release channel*
(`/mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py`), never edited.
The same applies to `sync.py`, `pairmode_migrate.py`, `fleet_discovery.py` and
`audit.py`. This story modifies no flex source.

## Tests

There is no flex-side unit test for this story — it writes no flex code. The
"tests" are the recorded verification commands. Run them in this order and paste
each command with its output into `## Evidence`.

```bash
# C0 — preconditions: tags in flex AND cp-113 content in the channel
git -C /mnt/work/flex tag --list 'cp-105' 'cp-110' 'cp-111' 'cp-112' 'cp-113'
git -C /mnt/work/flex-harness log --oneline -3
grep -c RETIRED_SECTIONS /mnt/work/flex-harness/skills/pairmode/scripts/sync.py

# C1 — baseline. --no-snapshot is mandatory (INFRA-295 + 4-of-5 prior runs).
cd /mnt/work/flex-harness
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/fleet_discovery.py --no-snapshot
readlink -f /mnt/work/pokus
git -C /mnt/work/pokus log --oneline -3
git -C /mnt/work/pokus status --porcelain          # must be empty
git -C /mnt/work/pokus branch --show-current
cat /mnt/work/pokus/.companion/state.json
ls /mnt/work/pokus/.companion/attempt_counter.json 2>&1   # expect: No such file
grep -rc 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS' /mnt/work/pokus/.claude/agents/*.md
grep -o '"command": *"[^"]*"' /mnt/work/pokus/.claude/settings.json
ls /mnt/work/pokus/.claude/agents/
grep -c 'Write(\|Edit(' /mnt/work/pokus/.claude/settings.local.json

# C2 — the destructive preview. sync.py DIRECTLY, not via sync-all (CER-133(6)).
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/sync.py \
  --project-dir /mnt/work/pokus --dry-run

# C3 — apply canon (prefer without --yes; see Instructions step 4)
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-all --project-dir /mnt/work/pokus --apply
grep pairmode_version /mnt/work/pokus/.companion/state.json

# C7 — state normalisation, AFTER the sync
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_migrate.py \
  to-030 --project-dir /mnt/work/pokus --apply
cat /mnt/work/pokus/.companion/state.json
rm -f /mnt/work/pokus/.companion/state.json.lock

# C4 — post-sync binding, same command form as C1
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/fleet_discovery.py --no-snapshot

# C5 — thin loop AND pokus's gate surviving in Build standards
grep -c 'flex_build.py next-action' /mnt/work/pokus/CLAUDE.build.md    # expect 2
head -8 /mnt/work/pokus/CLAUDE.build.md
grep -n 'Build standards' /mnt/work/pokus/CLAUDE.build.md             # test_command must be the gradle command
grep -ci 'checkpoint sequence' /mnt/work/pokus/CLAUDE.build.md        # a pre-sync heading: expect 0

# C6 — agent shells: seven present, retired bodies gone, grammar clean
ls /mnt/work/pokus/.claude/agents/
grep -rin '## Starting a story\|## Implementation rules\|## Review checklist\|\*\*3. Build gate\*\*\|## Your process\|## Audit priorities\|### 4. Domain isolation violation\|## Design pivot detection' \
  /mnt/work/pokus/.claude/agents/*.md                                  # expect no output
grep -rn 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS' /mnt/work/pokus/.claude/agents/*.md
grep -l '## Procedure' /mnt/work/pokus/.claude/agents/*.md

# C8 — CER-127 evidence; recorded, not fixed
grep -o '"command": *"[^"]*"' /mnt/work/pokus/.claude/settings.json
ls /mnt/work/flex/hooks/
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  audit-hooks --project-dir /mnt/work/pokus

# C9 — nothing non-canon changed; then one commit, no RELEASE ID in the subject
git -C /mnt/work/pokus status --porcelain
git -C /mnt/work/pokus show --stat HEAD

# C11 — pokus's cheap test surface (gradle explicitly NOT run)
cd /mnt/work/pokus && PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -q 2>&1 | tail -20

# C12 — cleanliness
git -C /mnt/work/flex diff --name-only
git -C /mnt/work/flex-harness status --porcelain

# C14 — flex's own suite, WITHOUT -x so a known failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:** every command above appears in `## Evidence` with its real
output; C3/C4/C5/C6/C9 hold as written; C13's findings subsection is present and
includes the RELEASE-071 proof-deferred sentence; flex's suite shows no new
failure.

## Out of scope

- **The proving story cycle (mechanic step 6).** No pokus story is specced,
  built, reviewed or merged by this story; no `effort.db` assertions are made.
  The sibling stories' E5/E6/E7 have **no counterpart here** — by directive, not
  by oversight. RELEASE-071 records pokus as proof-deferred.
- **All pokus project work.** Kotlin/Android source under `app/`,
  `product-spec/`, `scripts/`, `tests/`, gradle configuration, TEST-002,
  TEST-003, the UAT harness under `docs/uat/`, and anything under
  `docs/stories/`. Untouched.
- **All pokus planning docs.** `docs/brief.md`, `docs/phases/index.md`,
  `docs/cer/backlog.md` (the `SCAFFOLD_FILES` trio — sync preserves their bodies
  and this story does not "fix" their findings), `docs/architecture.md`,
  `docs/ideology.md`, `docs/eras/**`, the root
  `phase-01-android-mediaprojection-magnifier.md`, and the proposed migration
  phase `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md` —
  which stays exactly as it is. Sequencing, reconciling or deleting it is pokus's
  own work in its own orchestrator session (named as a follow-up under C13).
- **No backlog or spec restructuring in pokus.** No CER filing, no rail
  creation, no phase renumbering, no index grooming.
- **CER-127's real fix.** No portable hook-path resolution, no migrate/sync
  rewrite rule, no audit check for machine-absolute hook paths. That is
  **INFRA-319 (phase 114)**. This story only supplies field evidence, plus C8's
  narrow containment rewrite in the single case where pokus's sessions would
  otherwise be broken outright.
- **CER-133's fixes.** The stale `sync.py has no --dry-run` claims, the
  `skip_in_dry_run` wrapper behaviour, `(file, key)` scoping for
  `RETIRED_SECTIONS`, and the `PAIRMODE.md` / `SKILL.md` non-destructive claims
  are routed around here, not repaired.
- **L021/L022 fixes.** The security-auditor procedure's unconsumed
  `domain_isolation_rule` and `sync.py`'s apply-path disregard for
  `.pairmode-overrides` are observed and cited; neither is fixed, and no
  `.pairmode-overrides` entries are authored in pokus.
- **Editing flex's runbook or CER backlog.** `docs/harness-cutover-runbook.md`
  keeps its uncorrected step-3/step-5 forms (5-of-5 recurrence now); findings are
  named under C13. Ask the operator before filing anything.
- **Re-syncing already-migrated projects.** meander, lumin, caddy,
  forqsite.help and halfhorse are read-only here. base56 and cora belong to
  RELEASE-069 and RELEASE-070.
- **Running pokus's gradle build.** `cd app && ./gradlew assembleDebug` is
  deliberately not run (C11 records the exclusion).

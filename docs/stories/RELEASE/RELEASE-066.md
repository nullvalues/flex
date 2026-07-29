---
id: RELEASE-066
rail: RELEASE
title: Migrate forqsite.help to pairmode 0.3.0
status: complete
phase: "106"
auth_gated: false
schema_introduces: false
story_class: docs
primary_files:
  - docs/stories/RELEASE/RELEASE-066.md
touches:
  - docs/stories/RELEASE/RELEASE-066.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

<!-- SPEC-WRITER NOTE (frontmatter): the stub arrived with no `primary_files:` key,
     `touches: []` and no `story_class:`. All three were populated here per the
     RELEASE-064 / RELEASE-065 precedent (operator-directed): the single in-repo
     write target is *this file* — the `## Evidence` section appended by the
     executor. Every other write target is outside the repo, under
     `/mnt/work/forqsite.help`, and therefore cannot appear in `touches:` at all;
     that is the point of phase 106 § Execution model. The cross-repo write set is
     enumerated instead in `## Cross-repo scope boundaries` below. -->

<!-- SPEC-WRITER NOTE (human-review signal, Step 5): this spec is written on the
     premise that the campaign hold RELEASE-065 placed on RELEASE-066..070 has been
     lifted by the phase-112 unblockers. `docs/phases/phase-106.md` does **not**
     record that re-block or its lifting — its last dated entry is the 2026-07-28
     "Resumed (post cp-110/cp-111)" paragraph, written before RELEASE-065 ran. The
     unblock is corroborated only by (a) RELEASE-065's own `## Evidence` gate
     statement, (b) the era-003 § Phases row `112 | Campaign unblockers: worker
     result-grammar reconciliation, CER-guard placeholder fix, snapshot write
     targeting | complete`, and (c) the campaign context supplied with this story.
     E0(c) turns that gap into an explicit, evidenced gate rather than an
     assumption; the phase doc should be amended to carry the re-block/unblock
     history, which is phase-authoring work and not this story's to do. -->

## Context

Phase 106 drives the remaining pairmode 0.3.0 fleet migrations centrally from
flex, using the six-step mechanic in `docs/harness-cutover-runbook.md`
§ *Per-project mechanic* as the unit of work. RELEASE-063 was the campaign canary
(meander), RELEASE-064 the first follow-on (lumin), RELEASE-065 the second
(caddy). **RELEASE-066 is the fourth run — and the first one after the campaign
was re-blocked and then unblocked.**

**Target repo: `/mnt/work/forqsite.help`.**

> **Path disambiguation — read this before running anything.** Two sibling
> repositories exist: `/mnt/work/forqsite` and `/mnt/work/forqsite.help`. They are
> different projects. This story targets **`/mnt/work/forqsite.help`** — the one
> named in the phase-106 Stories table — and `/mnt/work/forqsite` is
> out of scope entirely (see `## Out of scope`). Confirm the target from
> `fleet_discovery.py`'s candidate scan before the first write, and record the
> confirmation in E1. A mechanic run against the wrong sibling is a
> data-integrity event, not a typo: `sync-all --apply` rewrites `CLAUDE.build.md`
> and the agent files in whatever directory it is pointed at.

**Why this run matters more than the stamp.** RELEASE-065 produced a *split*
verdict on the load-bearing E6 check:

- **E6a (attribution, CER-103) and E6c (dedupe, CER-104) PASSED** — the campaign's
  first downstream proof that the cp-110 remediation reaches a consumer project.
- **E6b (content, CER-101) FAILED** — caddy's proving-cycle attempt rows landed
  with `outcome NULL` and stayed permanently pending. Root cause, isolated in
  RELEASE-065's Evidence: `sync-agents` merged frontmatter and appended new
  sections but **preserved stale 0.2-era body content**, so caddy's workers
  returned the plain-text grammar (`BUILD-RESULT: DONE`, `REVIEW-RESULT: PASS`)
  that `parse_worker_outcome` cannot read. Every 0.2-era fleet project was
  expected to hit this. RELEASE-065 therefore **BLOCKED RELEASE-066..070**.

Phase 112 (`cp-112`, era-003 § Phases: *"Campaign unblockers: worker
result-grammar reconciliation, CER-guard placeholder fix, snapshot write
targeting"*, status `complete`) was opened to clear exactly that block. Per the
campaign context supplied with this story, four unblockers landed and were
field-proven against caddy in a follow-up sweep:

1. **Legacy plain-text verdict grammar tolerance** — `parse_worker_outcome` now
   additionally accepts the 0.2-era plain-text verdict line, so a consumer whose
   agent bodies predate the JSON grammar no longer strands its rows pending.
2. **`sync-agents` legacy-heading replacement** — template sync now *replaces* the
   stale legacy return-format section instead of appending alongside it, so newly
   migrated projects get the JSON grammar as their only example.
3. **CER placeholder-row guard** — `_check_cer_do_now` no longer reads the
   scaffolded `(none)` placeholder row as an unresolved Do-Now item (RELEASE-065
   new-3 / caddy CER-C004), which previously blocked every migrated repo's first
   checkpoint until hand-edited.
4. **Snapshot-write targeting** — `fleet_discovery.py`'s default snapshot no
   longer writes `docs/fleet-snapshot.md` into the channel checkout it only reads
   scripts from (RELEASE-065 new-1).

**Both halves of the grammar fix are in play here at once**, and this story is the
first migration where that is true. That makes E6b the single most valuable
assertion in this spec: a passing E6b is **the campaign's first downstream proof
of the CER-101 content half**, which is the one piece of the cp-110 remediation
still unproven anywhere in the fleet. A failing E6b re-opens the cluster and
re-blocks RELEASE-067..070, exactly as RELEASE-065's failure did.

**The corrected Signal-1 command is now spec-mandated, not just a note.**
Canary playbook note 2 (the runbook's step-5 `discover` subcommand /
`--project-dir` flag form is wrong) **recurred 3-of-3** and the runbook is still
unamended. On top of that, RELEASE-065's E11 caught the *default snapshot path*
writing into `/mnt/work/flex-harness` because caddy's native session ran
`fleet_discovery.py` without `--no-snapshot`. Unblocker 4 fixes the targeting,
but this spec still requires `--no-snapshot` on every discovery invocation —
including any run inside the target project's own session — because that is the
form all three prior runs recorded and because the fix's downstream behaviour is
itself something E11 observes rather than assumes.

**Prior-run notes are inputs, not background.** Three runs of numbered playbook
notes now exist (RELEASE-063's nine, plus RELEASE-064's new-1/new-2 and
RELEASE-065's new-1/new-2/new-3). Where the runbook and this spec disagree on
*command form* or on *when the migration commit lands*, **this spec wins**: it
carries three runs' worth of corrections and phase 106 § Out of scope keeps
runbook edits out of migration stories.

Two things about how this story runs are unusual and are settled by phase 106
§ *Execution model (cross-repo — deviation from the standard loop)*, which you
should read before acting:

1. **No sandboxed builder subagent, no flex worktree.** The write targets live at
   `/mnt/work/forqsite.help`, outside this repo. The standard worktree loop and
   `scope_guard.py` forbid writes there — correctly. Execution is
   orchestrator-level with the operator present.
2. **Acceptance is evidence-shaped, not diff-shaped.** The flex-side diff is one
   `## Evidence` section appended to this file. The reviewer verifies recorded
   command output, not a code change.

The pairmode CLIs are invoked from the **permanent release channel**,
`/mnt/work/flex-harness` — canonized in `docs/architecture.md` § *Release channel
— flex-harness* and by RELEASE-062 (phase 105). Do not invoke them from
`/mnt/work/flex/skills/...`: the channel is what the fleet consumes, and
migrating a project with a different copy of the scripts than the fleet uses
would prove nothing about whether the cp-110/cp-111/cp-112 changes reach
consumers. This matters more here than in any prior run, because the thing being
proven downstream *is* a cp-112 change.

## Cross-repo scope boundaries

Phase 106 § *Execution model* permits this story to write outside `/mnt/work/flex`.
That permission is **not** open-ended. The complete write set is enumerated here;
anything not listed is read-only or forbidden, and a write outside this list is a
scope violation to be reported, not rationalized.

**Writable — inside `/mnt/work/flex`:**

- `docs/stories/RELEASE/RELEASE-066.md` — this file, `## Evidence` section only.
- Rows in `docs/phases/phase-106.md`, `docs/phases/index.md` and the era/effort
  ledgers **only** as written by the orchestrator's own recording CLIs
  (`flex_build.py` status/record subcommands). Hand-edits to those files are not
  part of this story.

**Writable — inside `/mnt/work/forqsite.help` (the target repo, and only via the
pairmode CLIs or an operator-approved edit):**

- `CLAUDE.build.md` — rewritten to the 0.3.0 thin-harness template by `sync-all`.
- `.claude/agents/*.md` — re-rendered by `sync-agents` (this is where unblocker 2
  lands).
- `.claude/settings.json` — pairmode hook blocks rewritten by `pairmode_sync.py`.
- `.claude/settings.local.json` — **only** if the operator approves the E9 prune,
  and only after a backup is written alongside it.
- `.companion/state.json` — `pairmode_version` stamp and scripts-path declaration,
  written by `pairmode_migrate.py to-030`.
- `.companion/state.json.lock` — transient advisory-lock residue; **delete only**,
  never commit.
- Any file the target project's *own* proving-story cycle writes under its own
  `CLAUDE.build.md` loop (mechanic step 6), inside the target repo, in the target
  project's own numbering. That cycle is the target project's work, governed by
  its own loop — not by this spec.
- Git objects/refs in the target repo, via the migration commit and the proving
  cycle's commits.

**Read-only — never written by this story:**

- `/mnt/work/flex-harness` (the release channel) — scripts are *invoked* from it.
  `git -C /mnt/work/flex-harness status --porcelain` must print nothing at the end
  (E11). If it does not, something wrote into the channel and that is a finding.
- `/mnt/work/meander`, `/mnt/work/lumin`, `/mnt/work/caddy` — read for the E10
  proof-debt re-check only. No sync, no re-migration.
- `/mnt/work/flex/skills/`, `tests/`, `ui/`, `.claude-plugin/` — untouched.

**Forbidden outright:**

- `/mnt/work/forqsite` — the *other* sibling repo. Not this target. Not read, not
  scanned as a candidate, not migrated.
- Every other project directory under `/mnt/work/` — RELEASE-067..070 own those.
- `docs/harness-cutover-runbook.md` and `docs/cer/backlog.md` in flex — findings
  are *named* under E13, never applied here.

## Requires

- **The campaign block from RELEASE-065 is lifted, and the lift is on the
  record.** RELEASE-065's `## Evidence` closes with *"RELEASE-066..070 are BLOCKED
  pending an operator decision"* on the E6b grammar-skew defect. Before starting,
  confirm with the operator that phase 112 discharged that block, and capture the
  confirmation for E0. `docs/phases/phase-106.md` does **not** record the
  re-block or its lifting (see the spec-writer note above), so the operator's
  confirmation plus the cp-112 evidence *is* the gate. If the operator is not
  present to confirm it, **stop** — this story is not eligible for unattended
  execution on an undocumented unblock.
- **cp-112 is tagged, phase 112 is complete, and its content is present in the
  release channel.** The four unblockers are what makes E6b winnable; migrating
  against a channel that predates them reproduces RELEASE-065's failure by
  construction. Verify the channel content directly — a tag in flex is not
  evidence the channel was fast-forwarded (phase 102 existed precisely for that
  step).
- **cp-105, cp-110 and cp-111 are tagged and their content is in the channel.**
  Phase 106 § Execution model: *"do not start this phase before cp-105."*
- **RELEASE-063, RELEASE-064 and RELEASE-065 are complete and all three
  `## Evidence` sections are present**, including their playbook-note and
  follow-up subsections. This story is specced against all three; if any is
  missing, stop — you are not running the playbook the campaign produced.
- **No sibling phase-106 story beyond RELEASE-063/064/065 has been started.**
  RELEASE-067..071 must still be `draft` when this story begins.
- `/mnt/work/flex-harness` exists and is the release channel described in
  `docs/architecture.md` § *Release channel — flex-harness*.
- **The target exists as a git repository and its working tree is clean** at the
  moment the mechanic begins. The path is *expected* to be
  `/mnt/work/forqsite.help`; confirm it from `fleet_discovery.py`'s candidate scan
  rather than assuming, and confirm it is not the sibling `/mnt/work/forqsite`.
  Per canary playbook note 1 — which **recurred 2-of-3**, and on caddy in the new
  form of a competing half-started self-migration — a dirty tree is a **stop**
  condition with no runbook step covering it: the operator decides (discard,
  commit, or abort) and the decision is recorded verbatim. Do not stash around it
  unilaterally.
- `docs/harness-cutover-runbook.md` contains a `## Per-project mechanic` section
  enumerating the six steps, and a `## Rollback procedure` section. That section,
  as corrected by this spec's `## Instructions`, is the step list; this spec states
  what must be *true afterwards*.
- The operator is present. Beyond the unblock confirmation, canary note 7's
  auto-mode permission classifier block on the first out-of-repo `sync-all
  --apply` is unsettled (1-of-3: fired on meander, not on lumin or caddy), and the
  E9 prune decision and E5 proving-story selection are operator calls.
- Known flex-side environmental failure inside fresh worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story; did not appear on RELEASE-065's run from
  the main checkout.

## Ensures

Each assertion below is verified from recorded command output pasted into this
file's `## Evidence` section (see `## Instructions` step 12). "Recorded" means the
exact command and its exact output, not a paraphrase. An Ensure whose evidence is
missing from that section is a **fail**, regardless of whether the underlying
thing happened.

**E0. The preconditions — including the lifted campaign block — are evidenced,
not assumed.**
`## Evidence` records:
- (a) `git -C /mnt/work/flex tag --list 'cp-105' 'cp-110' 'cp-111' 'cp-112'`
  showing all four tags;
- (b) a check that `/mnt/work/flex-harness` carries **cp-112** content — e.g. a
  `git rev-parse` comparison of flex's `cp-112` against the channel's `HEAD`, or
  `git -C /mnt/work/flex-harness log --oneline -5` showing the phase-112 commits.
  If the channel is behind, this is a **stop**; fast-forwarding it is not this
  story's work (see `## Out of scope`);
- (c) the operator's confirmation, quoted, that RELEASE-065's block on
  RELEASE-066..070 is discharged by phase 112, together with a one-line statement
  of what remains unproven: *the CER-101 content half has never passed downstream;
  this story's E6b is its first opportunity.*

**E1. A pre-migration baseline exists and the target is unambiguously identified.**
`## Evidence` contains the verbatim output of a `fleet_discovery.py` run captured
**before any write to the target**, using `--no-snapshot`, showing the target's
pre-migration `binding`, `signal1` (scripts path) and `signal2`
(`pairmode_version`), plus the run's `Projects with duplicate hooks:` line.
`## Evidence` also records:
- `git -C /mnt/work/forqsite.help log --oneline -5` and
  `git -C /mnt/work/forqsite.help status --porcelain`;
- an explicit line confirming the target is `/mnt/work/forqsite.help` and **not**
  `/mnt/work/forqsite`;
- one line stating which starting shape the target is in — bound-0.2.x,
  bound-other-version, declared-but-unstamped, or never-bootstrapped — and
  therefore which branch of `## Instructions` step 5 applies.

Without this, "the migration changed something" is unverifiable.

**E2. The target reports pairmode 0.3.0 and binds the release channel.**
A post-migration `fleet_discovery.py` run, recorded in `## Evidence` and using the
**same command form as E1** so the two are directly comparable, shows the target
with:
- `signal2 (pairmode_version): 0.3.0`
- `signal1 (scripts path): /mnt/work/flex-harness/skills/pairmode/scripts`
- `binding: both`

All three. `binding: version` post-migration is a fail: the stamp landed but the
channel declaration did not, and the target would still be consuming an unknown
copy of the scripts.

**E3. The target's *pairmode* hooks are a single block per event (CER-110-aware).**
This is the phase-106 § Checkpoint-proves `single-block hooks` condition, restated
to be attainable in the presence of CER-110 (fleet-wide plugin-sourced duplicate
hooks, unprunable by `audit-hooks --apply` by design). `## Evidence` records:
- (a) the target's own hook state from its `.claude/settings.json`, showing
  **exactly one pairmode hook block and one command per event** for the pairmode
  events (`PreToolUse`, `UserPromptSubmit`, `SessionStart`, `PostToolUse`), each
  pointing at `/mnt/work/flex-harness/hooks/...`;
- (b) `pairmode_sync.py audit-hooks --project-dir /mnt/work/forqsite.help`
  (dry-run), showing that any remaining `DUPLICATE:` lines are **plugin-sourced
  and non-pairmode**, and that nothing pairmode-owned is prunable;
- (c) the fleet-wide `Projects with duplicate hooks: N` line from the E2 run,
  recorded **informationally** with an explicit note that per CER-110 this number
  is not expected to be `0` and is not a migration defect.

`Projects with duplicate hooks: 0` is **not** asserted by this story. If (b) shows
a *pairmode-owned* duplicate, that is a real defect: record it under E12 and treat
it as a stop. Do not hand-edit the target's settings to make any number come out
right — the point is to prove `pairmode_sync.py` produces this state on its own.

**E4. The bootstrapped loop is the 0.3.0 thin-harness template, and the synced
agent bodies carry the *new* result grammar.**
`## Evidence` records:
- (a) the result of inspecting `/mnt/work/forqsite.help/CLAUDE.build.md` and
  confirms it is the thin dispatch-loop template, not the pre-flip 0.2.x prose
  loop. Use the same checks all three prior runs used so the four are comparable:
  `grep -c "flex_build.py next-action" <path>` (all prior runs printed `2`) plus a
  `head -5`;
- (b) **the unblocker-2 check, new in this story and load-bearing for E6b:** after
  `sync-agents` runs, the target's `.claude/agents/*.md` bodies contain **no
  surviving 0.2-era plain-text result-grammar example** — i.e. `grep -rn
  'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS'` over the target's agent files returns
  nothing, or returns only occurrences that are explicitly part of the new
  legacy-tolerance documentation. RELEASE-065 found caddy's `builder.md:106` still
  carrying the literal `BUILD-RESULT: DONE` example *alongside* the newly-merged
  JSON-schema reference, and the workers followed the old example. Record the grep
  and its output either way. A surviving stale example is a **predictor of E6b
  failure** and must be reported to the operator before the proving cycle starts,
  not discovered afterwards;
- (c) the observed state of any `SKILL.md` content `sync-all` wrote into the
  target — whether the skill `name:` values are the **bare** cp-111 names rather
  than the old namespaced ones. If `sync-all` copies no SKILL.md into this target
  (caddy had no `skills/` dir), record that fact instead.

**E5. A proving story cycle completed inside the target — or its absence is
recorded as an explicit, operator-owned deferral.**

*Preferred path (proof).* `## Evidence` names the target-side story ID built as the
proving cycle (mechanic step 6), states that it ran inside the target's **own**
`CLAUDE.build.md` loop with the target's own story numbering, states the full
cycle it traversed (spec-writer → builder → reviewer → merge), and states its
outcome. The story is a real, small, genuinely-wanted piece of the target
project's work — not a throwaway. `## Evidence` states explicitly which session
mode was used (native target session, or this flex session exercising
INFRA-289's `resolve_recording_project` attribution) and why, because the mode
changes what a pass proves. RELEASE-065 ran natively and proved the
`worktree-path` precedence branch; either mode is acceptable if declared.

*Fallback path (deferral).* If the target cannot run a proving cycle,
`## Evidence` records, in the same shape RELEASE-064 used: the operator's decision
**quoted verbatim**; the reason the project could not build; and an explicit
statement that E5/E6/E7 are **unevidenced, therefore not passed**, that this
story's migration is a stamp without a proof, and that the CER-101 content-half
proof remains outstanding across the whole campaign. A follow-up naming where the
proof will come from is filed under E13.

Silence is a fail. One of the two paths must be explicit in `## Evidence`.

**E6. The proving cycle's attempt rows landed in the target's effort.db —
correctly, including `outcome`.**
Applies when E5 took the preferred path; when E5 took the fallback, E6 is recorded
as *not run* with the consequence stated and is **not** claimed as passed. All
three parts are verified from recorded queries against the target's `effort.db`
(locate it; do not assume the path — meander's, lumin's and caddy's were
`.companion/effort.db`). Verify the live schema before querying: the `attempts`
table uses `agent_role`/`ts`, **not** `role`/`created_at` (RELEASE-064 E10;
confirmed by RELEASE-065's recorded schema
`attempts(id, story_id, phase, rail, agent_role, model, …, tokens_total, …,
outcome, notes, ts, …, agent_id, output_file)`).

- **E6a — attribution (CER-103).** At least one attempt row exists for the E5
  story ID **in the target's own db**, not flex's. `## Evidence` also records the
  complementary check that flex's `effort.db` contains **no** rows for the E5 story
  ID. PROVEN downstream on caddy; this run re-confirms it rather than establishing
  it.
- **E6b — content (CER-101). This is the assertion this story exists to settle.**
  Those rows have a **non-null, non-placeholder `outcome`** and a non-zero
  token/cost field. `outcome NULL` / `tokens_total NULL` persisting after both the
  in-session and an explicit reconciliation sweep is the exact pattern that failed
  on caddy and is a **fail** here. `## Evidence` must record: the raw row values;
  the result after an explicit sweep if the rows are pending at first read; and,
  if the rows resolve, the fact that **this is the campaign's first downstream
  proof of the CER-101 content half** — in those words. If they do not resolve,
  record the `read_completed_spawn` diagnosis (which of `outcome` / `tokens_total`
  / `model` parsed) so the failure is isolated the way RELEASE-065 isolated it,
  rather than reported as a bare NULL.
- **E6c — no duplicates (CER-104).** Each attempt appears **once**. Record a
  grouped count (e.g. `SELECT story_id, agent_role, COUNT(*) … GROUP BY …`)
  showing no perfect pairs with near-identical timestamps. PROVEN downstream on
  caddy (paired `recorded` + `recorded:deduped` log decisions); this run
  re-confirms.

Any of E6a/E6b/E6c failing is a stop condition (see `## Instructions` step 11).

**E7. The target's checkpoint/report path sees the attempts — including the
proving rows.**
Applies on the same condition as E6. `## Evidence` records the output of the
pairmode checkpoint or attempt-report CLI run against the target for the phase
containing the E5 story, showing the attempts (not "no attempts recorded").
RELEASE-065's E7 was **qualified**: the lifetime rollup saw historical rows but
the proving rows were excluded from medians because they were still pending
(E6b), and the phase-scoped half printed *"no active phase resolved"* because the
target's own checkpoint had already completed. This story upgrades the
requirement: if E6b passes, `## Evidence` must show the **E5 story's own rows**
reflected in the report output — that is the read-path proof RELEASE-065 could not
produce. If the phase-scoping artifact recurs, record it and say so explicitly
rather than accepting a lifetime-only rollup as a clean pass. Record the exact
command (RELEASE-065 used `flex_build.py checkpoint-report --project-dir <target>`;
confirm against `--help` before running).

**E8. The target's git history shows the migration as its own commit(s).**
`## Evidence` records `git -C /mnt/work/forqsite.help log --oneline` covering the
migration commit(s) and, if E5 ran, the proving-story commit(s), so a later
auditor can see exactly what the sync wrote and roll it back if needed. Per canary
playbook note 3 — **recurred 3-of-3** — the migration commit **precedes** the
proving cycle in history. Record the file/insertion/deletion counts for the
migration commit.

**E9. The target's `settings.local.json` sediment is handled deliberately.**
Per canary playbook note 9 (**recurred 2-of-3**: meander 133 rules / 91 stale;
lumin had no such file; caddy 48 stale rules pruned with a backup),
`## Evidence` records: whether `/mnt/work/forqsite.help/.claude/settings.local.json`
exists; if it does, the pre-migration count of `Write(`/`Edit(` allow rules, the
operator's decision (prune or keep), and — if pruned — the post-prune count and the
backup location. If the file does not exist or carries no such rules, record that
fact. "Not mentioned" is a fail.

**E10. The campaign's downstream-proof position is re-checked and restated.**
`## Evidence` records the current position across the fleet as of this run,
explicitly separating the three CERs:

- **CER-103 (attribution)** and **CER-104 (dedupe)** — PROVEN downstream by caddy
  story PAIRMODE-002 (RELEASE-065 E6a/E6c). Cite; do not re-derive.
- **CER-101 (content/outcome)** — record whether this run's E6b supplies the first
  downstream proof, or whether it remains outstanding. If outstanding, list the
  projects checked and carry the follow-up forward under E13 rather than letting
  it silently age out.
- **meander and lumin** — RELEASE-064 determined meander needs no re-sync to pick
  up cp-110 (the fixes live in channel scripts it invokes by path). Cp-112's
  `sync-agents` legacy-heading replacement **changes that determination**, because
  agent bodies *are* copied into consumer repos at sync time and meander's and
  lumin's bodies predate the JSON grammar. State the revised determination and its
  basis. Performing any re-sync is **not** this story's work (see
  `## Out of scope`); naming it is.

**E11. Cleanliness — the flex-side diff is this file only, and the channel is
untouched.**
```bash
git -C /mnt/work/flex diff --name-only
git -C /mnt/work/flex-harness status --porcelain
```
The first lists exactly `docs/stories/RELEASE/RELEASE-066.md` (plus the phase
doc's story row and index/ledger rows if the orchestrator's recording CLIs touch
them — those are tool-written, not hand-written). No file under `skills/`,
`tests/`, `ui/`, or `.claude-plugin/` is modified by this story. The second prints
**nothing**.

This is also the **unblocker-4 observation point**: RELEASE-065's channel check
caught `docs/fleet-snapshot.md` written into `/mnt/work/flex-harness` by a
discovery run that omitted `--no-snapshot`. Cp-112 retargeted the snapshot write.
`## Evidence` states whether the channel stayed clean and whether any snapshot
file was written, and where. A clean channel here is a downstream datapoint for
unblocker 4, so record it as such rather than as a non-event.

**E12. Playbook findings are recorded as a delta against *all three* prior runs.**
This file's `## Evidence` ends with a **Playbook notes** subsection that, for each
of RELEASE-063's nine numbered notes **and** the new findings from RELEASE-064
(new-1 → CER-110, new-2 → CER-111) and RELEASE-065 (new-1 snapshot pollution,
new-2 grammar skew, new-3 CER-guard placeholder false positive), states whether it
**recurred**, **did not recur**, or **was not applicable** on this target — and
then lists any *further* new deviation, manual intervention, or ambiguity this run
produced. A flat list that does not reference the prior notes fails this Ensure.
Four specific comparisons are required:

- **note 4 / RELEASE-065 new-2 (the reclassified WARN).** `to-030`'s agent-cleanup
  step printed *"content differs from known 0.2.x template … manual porting
  required"* on all three prior runs and was dismissed as noise twice before
  RELEASE-065 proved it was flagging the stale bodies that broke E6b. Record
  whether the WARN appears here **and** whether E4(b)'s grep found any surviving
  stale grammar. If cp-112's `sync-agents` replacement works, the WARN should
  either not fire or should no longer correspond to a real stale example — state
  which.
- **note 7** (auto-mode classifier block) — fired on meander, not on lumin, not on
  caddy (1-of-3, unsettled). State which happened here.
- **note 6 / CER-111** (`expected_step_tokens`) — meander kept its custom value
  with a WARN, caddy kept `53416` with a WARN, lumin was silently rewritten
  `53000 → 5000`. `## Evidence` must record this target's **pre-`to-030` value**,
  the **post-`to-030` value**, and whether a keep/WARN or a silent rewrite
  occurred. Reading the value only afterwards makes the delta unrecoverable.
- **RELEASE-065 new-3 / CER-guard placeholder (unblocker 3)** — caddy's first
  post-migration checkpoint was blocked by `_check_cer_do_now` reading the
  scaffolded `(none)` placeholder row as an unresolved Do-Now item. If this
  target's proving cycle reaches a checkpoint, record whether that false positive
  recurred. A clean checkpoint is the downstream proof of unblocker 3; a
  recurrence re-opens it.

If the mechanic ran exactly as written with no intervention, say exactly that.

**E13. Runbook or CER follow-ups are filed, not fixed here.**
Every defect surfaced under E12, plus the E10 proof-position follow-up and any E5
deferral follow-up, is *named* in `## Evidence` as a follow-up with its intended
destination (runbook amendment or CER). This story does **not** edit
`docs/harness-cutover-runbook.md` or `docs/cer/backlog.md` (see `## Out of scope`).
RELEASE-063 E11 already filed the runbook amendments for canary notes 1/2/3/5/9,
RELEASE-064's findings are filed as CER-110/CER-111, and RELEASE-065's three new
findings were routed into phase 112 — if any recurred, reference the existing item
rather than filing a duplicate. New findings get new follow-ups. The pending
runbook amendment RELEASE-065 named (note 4's entry changed from "noise" to
"warning is accurate; port stale bodies") should be re-stated with whatever this
run's evidence adds.

**E14. flex's own suite is unaffected.**
`uv run pytest tests/pairmode/` is run once at the end, **without `-x`**, and is
green except the known CER-090 worktree-environmental failure
(`tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`) if
it appears. RELEASE-065's run from the main checkout was fully green
(4083 passed, 211 skipped). This story changes no flex code, so any *new* failure
means something ran that should not have.

## Instructions

You are executing this story **at orchestrator level with the operator present**,
not as a sandboxed builder subagent in a flex worktree. Do not create a story
worktree. Do not attempt to have a builder subagent write to
`/mnt/work/forqsite.help` — `scope_guard.py` will block it, correctly, and working
around the block is itself a violation. Read `## Cross-repo scope boundaries`
before the first write and treat it as the complete permission list.

1. **Confirm the unblock, then prove the gate state (E0).** Ask the operator to
   confirm on the record that RELEASE-065's block on RELEASE-066..070 is
   discharged by phase 112, and quote the confirmation. Then confirm cp-105,
   cp-110, cp-111 and **cp-112** are tagged in flex **and** that
   `/mnt/work/flex-harness` carries cp-112 content. The channel is a separate
   checkout and its fast-forward is a distinct step. If the channel is behind,
   stop and hand back to the operator: migrating against a pre-112 channel
   reproduces RELEASE-065's E6b failure by construction.

2. **Confirm the remaining preconditions before touching anything.** Verify every
   bullet in `## Requires` and record the checks: RELEASE-063/064/065 complete
   with all three `## Evidence` sections and their playbook-note subsections
   present; RELEASE-067..071 still `draft`; the target located and its working
   tree clean. If any fails, stop and hand back to the operator.

3. **Read all three prior runs' notes, then the mechanic.** Read RELEASE-063's
   § *Playbook notes (E10)* / § *Follow-ups filed (E11)*, RELEASE-064's
   § *Playbook notes (E12)* / § *Follow-ups (E13)*, and RELEASE-065's
   § *Playbook notes (E12)* / § *Follow-ups (E13)* plus its § *Mechanic run* and
   § *E6* blocks — the last of these records the exact failure this story is
   trying to clear. Then read `docs/harness-cutover-runbook.md`
   § *Per-project mechanic* in full, and § *Rollback procedure* alongside it so
   you know the exit path before you start. The spec-writer is input-bound and did
   **not** read any of those files. Where the runbook and this spec disagree on
   *procedure*, apply the corrections (steps 4 and 8 below) and record the
   discrepancy under E12; where they disagree on *what must be true afterwards*,
   this spec's `## Ensures` wins.

4. **Capture the baseline and confirm you have the right repo (E1).** Run
   `fleet_discovery.py` from the release channel. Per canary playbook note 2 —
   **recurred 3-of-3** — the runbook's step-5 command form is wrong (it names a
   nonexistent `discover` subcommand and a `--project-dir` flag). The corrected
   Signal-1 form, used by all three prior runs, is:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
     --candidate-dir /mnt/work/forqsite.help --no-snapshot
   ```
   `--no-snapshot` is **mandatory on every discovery invocation in this story**,
   including any run the target's own session makes: RELEASE-065's E11 caught the
   default snapshot path writing into the channel checkout. Confirm flags against
   `--help` before running — cp-112 landed since the last run — and do not guess
   flags.

   Explicitly confirm the resolved path is `/mnt/work/forqsite.help` and not the
   sibling `/mnt/work/forqsite`, and record that confirmation. Save the full
   output; you will compare it against the post-migration run. Also capture
   `git -C /mnt/work/forqsite.help log --oneline -5` and `… status --porcelain`.

   Then **state the target's starting shape in one line** and pick the step-5
   branch.

5. **Branch on the baseline before running the mechanic.**
   - **Bound 0.2.x consumer** (`signal2: 0.2.x`, any `binding`) — the ordinary
     path; run the six-step mechanic as lumin and caddy did.
   - **Bound but version-absent, or bound to a non-0.2.x version** — the mechanic
     still applies, but `to-030`'s assumptions about a 0.2.x starting state may not
     hold. Run `--dry-run` first, show the operator, and record any step whose
     output differs from RELEASE-065's recorded shape.
   - **Never bootstrapped** (no pairmode binding at all) — the migration is a
     *bootstrap to 0.3.0*, not a 0.2→0.3 migration. `to-030` may be inapplicable.
     Stop and confirm the intended path with the operator before writing anything;
     record the decision. Do not improvise a bootstrap sequence and do not let a
     bootstrap masquerade as a migration in the evidence.

6. **Run the mechanic against the target.** Follow the runbook's six steps in
   order, invoking `pairmode_migrate.py` and `pairmode_sync.py` from
   `/mnt/work/flex-harness/skills/pairmode/scripts` — never from
   `/mnt/work/flex/skills/...`. Expect, from the prior three runs:
   - **note 7 (unsettled, 1-of-3):** the auto-mode permission classifier may block
     the first out-of-repo `sync-all --apply`. If it blocks, ask the operator to
     toggle auto mode off so the normal permission prompt surfaces; do not attempt
     to route around the classifier.
   - **note 5 (recurred 3-of-3):** `sync-all --apply` may leave
     `.companion/state.json.lock` behind (INFRA-285 advisory-lock artifact). It is
     transient — remove it and do **not** commit it.
   - **note 4 (recurred 3-of-3, reclassified):** the `to-030` agent-cleanup step
     prints "content differs from known 0.2.x template … manual porting required".
     RELEASE-065 proved this WARN was accurate, not noise. **Do not dismiss it.**
     Pair it with step 7's grep before deciding it is benign.
   - **CER-111 — mandatory pre-read:** **before** running `to-030 --apply`, read
     and record the target's current `expected_step_tokens` value from its state
     file. Then run `to-030` and record the value again. Report both to the
     operator along with whether a keep+WARN or a silent rewrite occurred.

   Show the operator the output of each step before proceeding to the next. If a
   step fails, **stop** — do not improvise a fix into the target. Report to the
   operator, and if the failure is unrecoverable, execute the runbook's rollback
   procedure and record what happened under E12.

7. **Verify the agent bodies before you spend a proving cycle on them (E4b).**
   Immediately after `sync-agents` / `sync-all` completes and **before** the
   proving cycle, grep the target's `.claude/agents/*.md` for the 0.2-era
   plain-text grammar (`BUILD-RESULT: DONE`, `REVIEW-RESULT: PASS`). Cp-112's
   `sync-agents` legacy-heading replacement is supposed to have removed exactly
   this. If a stale example survives, **stop and report to the operator before
   running the proving cycle** — RELEASE-065 spent a full native cycle discovering
   this after the fact, and repeating that would waste the story's most expensive
   step on a predictable failure. Do not hand-edit the agent files to make the
   grep clean: that would fake the very thing E6b is meant to prove. If the stale
   content survives, the correct outcome is a stop plus a follow-up against
   unblocker 2, not a repaired file.

8. **Commit the migration before the proving cycle (canary note 3, recurred
   3-of-3).** The runbook orders the commit after step 6; that is wrong for the
   0.3.0 loop, because the proving story's worktree snapshots git HEAD and would
   not see the migration. Commit the sync/migration changes into the target as
   their **own** commit first (prior runs used
   `sync: migrate to pairmode 0.3.0 thin-harness loop`), then run the proving
   cycle. Record the discrepancy under E12 as a recurrence of note 3.

9. **Handle the `settings.local.json` sediment (E9, canary note 9).** Before
   handing the target to a native session, check whether
   `/mnt/work/forqsite.help/.claude/settings.local.json` exists and count the stale
   `Write(`/`Edit(` allow rules. `sync-all` correctly does not touch that file, so
   any sediment survives migration and floods the first post-migration session with
   warnings. Present the count to the operator and let the operator decide
   prune-or-keep. If pruning: back the file up first (caddy's backup convention:
   `<file>.bak-pre-030-prune`), remove the stale `Write(path)` and per-file
   `Edit(path)` rules (obsolete under 0.3 story-scoped permissions), and record
   before/after counts and the backup path. This is an operator decision — do not
   prune unilaterally. If the file does not exist, record that.

10. **Verify the stamp before proving (E2, E3, E4).** Re-run the exact step-4
    `fleet_discovery.py --no-snapshot` command and confirm the target now reports
    `0.3.0`, `binding: both` with `signal1` pointing at the channel. Then run
    `audit-hooks --project-dir /mnt/work/forqsite.help` as a dry-run and inspect
    the target's `.claude/settings.json` for the per-event pairmode hook blocks —
    **assert single-block pairmode hooks, not `Projects with duplicate hooks: 0`**;
    per CER-110 that number will be non-zero fleet-wide on a plugin-sourced,
    non-pairmode basis, and chasing it to zero here would mean editing files
    `audit-hooks` deliberately never writes. Then inspect
    `/mnt/work/forqsite.help/CLAUDE.build.md` for the thin-harness template and
    record the cp-111 SKILL.md name state per E4(c). Do not proceed until
    E2/E3/E4 hold — a proving cycle run against a half-migrated project produces
    uninterpretable evidence.

11. **Run the proving story cycle (E5, E6, E7) — this is the most valuable output
    of this story.** This is mechanic step 6. Caddy's cycle proved CER-103 and
    CER-104 downstream but failed CER-101's content half; phase 112 was built to
    clear that failure. **A passing E6b here is the campaign's first downstream
    proof of the CER-101 content half and the field validation of unblockers 1
    and 2.** Treat it as the priority, not as a formality after the stamp.

    Default to a **native target session**, in the target's own `CLAUDE.build.md`
    loop, with the target's own story numbering; if the operator instead wants to
    exercise the INFRA-289 attribution path from this session, that is allowed
    provided `## Evidence` states which mode was used, because the mode changes
    what a pass proves. Do not create a flex story for the proving cycle. Pick a
    small, real, already-wanted piece of the target project's work — a no-op story
    defeats the purpose. Remind the target session that any `fleet_discovery.py`
    invocation it makes must pass `--no-snapshot` (step 4).

    When it completes, run all three E6 checks (attribution, content, duplicates)
    plus the E7 report-path check. **Verify the live `attempts` schema first**
    (`agent_role`/`ts`, not `role`/`created_at`). If the rows read back pending,
    run the explicit reconciliation sweep before declaring E6b failed, and if they
    are still pending, trace `pending_reconcilable` → `read_completed_spawn` the
    way RELEASE-065 did so the failure is isolated to a named field rather than
    reported as a bare NULL.

    Any of E6a/E6b/E6c failing is a stop condition: report it as such and do not
    start RELEASE-067. An E6b failure specifically means the phase-112 unblockers
    did not hold downstream — say that in those words, because it is a
    regression against a phase that was checkpointed as complete.

    If the target genuinely cannot run a cycle, take E5's fallback path — record
    the operator's decision verbatim, state that E5/E6/E7 are unevidenced and
    therefore not passed, and state that the CER-101 content-half proof is still
    outstanding across the whole campaign. Do not round a deferral up to a pass.

12. **Record the evidence (E0–E14).** Append a `## Evidence` section to *this
    file*, containing, in order: the E0 precondition and unblock proof; the E1
    baseline, target-path confirmation and starting-shape classification; a
    *Mechanic run* block including the CER-111 pre/post `expected_step_tokens`
    values and the E4(b) agent-body grep; the E2/E3 post-migration discovery and
    `audit-hooks` output; the E4 template and cp-111 SKILL.md check; the E5
    proving-story ID, session mode and outcome (or the quoted deferral); the
    E6a/E6b/E6c queries and output; the E7 report output; the E8 target git log;
    the E9 settings hygiene record; the E10 proof-position restatement; the E11
    cleanliness checks (including the unblocker-4 snapshot observation); the E14
    suite output; a **Playbook notes** subsection per E12; and a **Follow-ups**
    subsection per E13. Paste command output verbatim inside fenced blocks — do
    not summarize it into prose, because RELEASE-067..070 are specced against what
    actually happened and a summary loses exactly the detail a later failure would
    need.

13. **Gate the rest of the campaign — and say plainly what is still unproven.** If
    any of E2, E3, E5, E6 or E7 failed or was deferred, say so explicitly in your
    return and state that RELEASE-067..070 are blocked pending an operator
    decision. If E6b passed, say explicitly that the campaign's first downstream
    proof of the CER-101 content half now exists, name the project and story ID
    that supplied it, and state that RELEASE-067..070 are unblocked on that basis.
    Either way the return must contain one unambiguous sentence about the state of
    the downstream proof.

14. **Ideology note (Step 4a — resolved inline, no conflict).** Four things in
    `docs/ideology.md` shaped this spec. *"Never silently pass contradictions"*
    (override path: explicit acknowledgement plus a recorded reason, never silent
    bypass) is why E0(c) forces the lifted campaign block onto the record — the
    phase doc does not carry the re-block/unblock history, so proceeding without
    an evidenced confirmation would be exactly the silent bypass the constraint
    forbids. It is also why E6 stays split into three separately-failing parts, why
    E7 was *tightened* rather than left at RELEASE-065's qualified pass, and why
    E12 requires the CER-111 pre-value to be read *before* `to-030` runs.
    *"Rationale-bearing decisions over bare rules"* is why E3 remains restated
    around CER-110 (the rule's reason — prove the sync produces single-block
    pairmode hooks by itself — survives in a form that can still fail honestly)
    and why step 7 forbids hand-editing the agent bodies to make the grep clean:
    the rule's purpose is to detect stale grammar, and satisfying it by editing
    would destroy the signal. *"Decision fidelity over convenience"* is why the
    two-sibling path ambiguity (`forqsite` vs `forqsite.help`) is a recorded
    confirmation rather than an assumption. On accepted constraints: *"Hooks are
    thin relays only"* is adjacent, since the mechanic rewrites the target's hook
    block — the rationale is that hooks must not block or write state, so E3
    forbids hand-editing the target's settings to satisfy an assertion and step 6
    forbids routing around the permission classifier. *"Sidebar owns all state
    writes"* is why E6 is asserted against the db as written by the normal path,
    with no manual repair of rows permitted to make an assertion pass — and why
    step 11 requires the reconciliation *sweep* (the normal path) rather than a
    hand-written `outcome`. No constraint is overridden by this spec and nothing
    required a decision on the ideology itself, so this resolves inline rather
    than flagging.

## Tests

There is no flex-side test file for this story and none is added: `story_class` is
`docs` (documentation/evidence), the story changes no flex code, and its subject is
the state of another repository. The checks below are the acceptance surface. Run
them from `/mnt/work/flex`.

```bash
# E0 — preconditions: tags in flex AND cp-112 content in the channel
git -C /mnt/work/flex tag --list 'cp-105' 'cp-110' 'cp-111' 'cp-112'
git -C /mnt/work/flex rev-parse cp-112 ; git -C /mnt/work/flex-harness rev-parse HEAD
git -C /mnt/work/flex-harness log --oneline -5
```

```bash
# E1/E2/E3 — baseline and post-migration state. --no-snapshot is mandatory
# (RELEASE-065 E11); the runbook's step-5 form is wrong, 3-of-3 (note 2).
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
  --candidate-dir /mnt/work/forqsite.help --no-snapshot
```

```bash
# E3 — pairmode-scoped hook assertion (CER-110: fleet-wide count will NOT be 0)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
  audit-hooks --project-dir /mnt/work/forqsite.help
```

```bash
# E4(a) — thin-harness template
grep -c "flex_build.py next-action" /mnt/work/forqsite.help/CLAUDE.build.md
head -5 /mnt/work/forqsite.help/CLAUDE.build.md

# E4(b) — UNBLOCKER-2 CHECK: no surviving 0.2-era result grammar in agent bodies.
# Run this BEFORE the proving cycle. Empty output is the pass.
grep -rn 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS' /mnt/work/forqsite.help/.claude/agents/ \
  || echo "clean — no legacy plain-text grammar examples survived sync-agents"

# E4(c) — cp-111 bare skill names as landed in the target (may not exist)
grep -rn '^name:' /mnt/work/forqsite.help/.claude/skills/*/SKILL.md 2>/dev/null || \
  echo "no SKILL.md copied into target — record this"
```

```bash
# CER-111 — expected_step_tokens, BEFORE and AFTER to-030
grep -n 'expected_step_tokens' /mnt/work/forqsite.help/.companion/state.json
# ... run to-030 --apply ...
grep -n 'expected_step_tokens' /mnt/work/forqsite.help/.companion/state.json
```

```bash
# E6 — proving-cycle attempt rows in the target's own effort.db.
# Locate the db first; do not assume a path. Schema uses agent_role/ts.
find /mnt/work/forqsite.help -name 'effort.db' -not -path '*/node_modules/*'
sqlite3 <target-effort.db> ".schema attempts"

# E6a attribution: rows present in the target, absent in flex
sqlite3 <target-effort.db> "SELECT * FROM attempts WHERE story_id='<E5-STORY-ID>'"
sqlite3 /mnt/work/flex/.companion/effort.db \
  "SELECT * FROM attempts WHERE story_id='<E5-STORY-ID>'"   # must be empty

# E6b content — THE assertion this story exists to settle:
# outcome NOT NULL and tokens_total NOT NULL after reconciliation
sqlite3 <target-effort.db> \
  "SELECT id, story_id, agent_role, model, tokens_total, outcome, ts
     FROM attempts WHERE story_id='<E5-STORY-ID>'"

# E6c duplicates: one row per attempt, no perfect pairs
sqlite3 <target-effort.db> \
  "SELECT story_id, agent_role, COUNT(*) FROM attempts
    WHERE story_id='<E5-STORY-ID>' GROUP BY story_id, agent_role"
```

```bash
# E7 — the target's checkpoint/attempt report sees the PROVING rows
# (RELEASE-065 used this command; confirm the subcommand via --help)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py \
  checkpoint-report --project-dir /mnt/work/forqsite.help
```

```bash
# E9 — settings.local.json sediment, before and after
ls /mnt/work/forqsite.help/.claude/settings.local.json 2>/dev/null || echo "no settings.local.json"
grep -c 'Write(' /mnt/work/forqsite.help/.claude/settings.local.json
grep -c 'Edit('  /mnt/work/forqsite.help/.claude/settings.local.json
```

```bash
# E10 — proof-position re-check across the fleet
# cp-110 promotion timestamp recorded in RELEASE-064 E10: 2026-07-28T15:57:54Z
sqlite3 /mnt/work/meander/.companion/effort.db \
  "SELECT id, story_id, agent_role, tokens_total, outcome, ts
     FROM attempts WHERE ts > '2026-07-28T15:57:54Z'"
sqlite3 /mnt/work/caddy/.companion/effort.db \
  "SELECT id, story_id, agent_role, tokens_total, outcome, ts
     FROM attempts WHERE story_id='PAIRMODE-002'"   # RELEASE-065's pending rows
```

```bash
# E8 — migration visible in the target's history, migration commit before proving
git -C /mnt/work/forqsite.help log --oneline -10

# E11 — flex-side diff is this story file only; channel untouched (unblocker-4)
git -C /mnt/work/flex diff --name-only
git -C /mnt/work/flex-harness status --porcelain    # must print nothing
```

```bash
# E14 — flex's own suite, without -x so a known failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance:

- E0–E14 are verified by the reviewer **from the `## Evidence` section of this
  file**, not from a diff. An Ensure whose evidence is missing from that section is
  a fail;
- E0(c) records the operator's confirmation that RELEASE-065's block is discharged
  by phase 112, verbatim, and states what remains unproven;
- E1 records an explicit confirmation that the target is `/mnt/work/forqsite.help`
  and not `/mnt/work/forqsite`;
- the target shows `binding: both` and `0.3.0`, with single-block **pairmode**
  hooks per event; the fleet-wide `Projects with duplicate hooks: N` line is
  recorded informationally and is **not** required to be `0` (CER-110);
- E4(b)'s agent-body grep is recorded, was run **before** the proving cycle, and
  the agent files were not hand-edited to make it pass;
- the CER-111 pre-`to-030` and post-`to-030` `expected_step_tokens` values are both
  recorded, with the keep-or-rewrite behavior named;
- either (i) E5/E6/E7 pass — rows in the target's own db, **populated `outcome`
  and tokens**, one row per attempt, and E7's report reflects the proving rows —
  and `## Evidence` states in those words that this is the campaign's first
  downstream proof of the CER-101 content half; or (ii) E6b failed, in which case
  the `read_completed_spawn` diagnosis is recorded, the phase-112 unblockers are
  named as not holding downstream, and RELEASE-067..070 are declared blocked; or
  (iii) E5's fallback path is recorded with the operator's decision quoted;
- `git -C /mnt/work/flex-harness status --porcelain` prints nothing, and E11 states
  whether any snapshot file was written and where (unblocker-4 observation);
- the flex suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if it
  appears, state that it reproduces on clean `HEAD` and is unrelated;
- the return contains one unambiguous sentence on the state of the campaign's
  downstream CER-101 proof, and declares RELEASE-067..070 blocked or unblocked
  accordingly.

Note for `spec-preflight`: this spec references a `## Evidence` section and its
**Playbook notes** / **Follow-ups** subsections, which do not exist in this file yet
— they are created by this story, and any preflight finding naming them is expected.
It also references `/mnt/work/forqsite.help`, `/mnt/work/forqsite`,
`/mnt/work/caddy`, `/mnt/work/meander`,
`/mnt/work/flex-harness/skills/pairmode/scripts`, the
`cp-105`/`cp-110`/`cp-111`/`cp-112` tags, CER-101/103/104/110/111, INFRA-289, and
`docs/harness-cutover-runbook.md` § *Per-project mechanic* / § *Rollback
procedure*, none of which the input-bound spec-writer could open; they are sourced
from `docs/phases/phase-106.md` § *Execution model*, from `docs/eras/003-*.md`
§ *Phases* (the `112 … complete` row), from RELEASE-065's `## Evidence`, and from
the campaign context supplied with this story. All concrete paths inside the target
(`.companion/state.json`, `.companion/effort.db`, `.claude/settings.local.json`,
`.claude/agents/*.md`, `.claude/skills/*/SKILL.md`) are **expected** shapes taken
from meander, lumin and caddy, not verified for this target — locate each before
using it, and record what you actually find. The `--candidate-dir` /
`--no-snapshot` flags, the `audit-hooks` subcommand and `checkpoint-report` come
from the prior runs' recorded invocations; confirm via `--help`.

## Out of scope

- **Migrating any project other than `/mnt/work/forqsite.help`.** halfhorse, pokus,
  base56 and cora are RELEASE-067..070. Do not run the mechanic against a second
  project "while the environment is warm" — the campaign wants each data point
  separable, and this run is carrying a regression test for phase 112.
- **`/mnt/work/forqsite`.** The similarly-named sibling repo is not this target and
  is not in the campaign under this story. Do not scan it, sync it, or migrate it.
- **Re-syncing or re-migrating meander, lumin or caddy.** E10 requires *re-checking*
  the proof position and *naming* the revised meander/lumin re-sync determination
  under cp-112. Performing any re-sync, or re-running caddy's PAIRMODE-002
  reconciliation to see whether the grammar fix retro-resolves its pending rows, is
  separate work — mixing a remediation of an earlier project into this migration
  would make it impossible to tell which project's evidence proved what.
- **Fast-forwarding `/mnt/work/flex-harness` to cp-112.** If E0 finds the channel
  behind, **stop**. Promoting the channel is a release action (phase 102's
  precedent), not something a migration story does mid-run.
- **Fixing the phase-112 unblockers if they fail downstream.** If E4(b) finds
  surviving stale grammar or E6b fails, this story **stops and reports**. Repairing
  `sync-agents` or `parse_worker_outcome` is a new phase, specced from this story's
  evidence — not an inline fix, and not a hand-edit of the target's agent files.
- **Diagnosing or fixing CER-110 or CER-111.** Both are filed. This story is
  specced *around* CER-110 (E3's restated assertion) and *observes* CER-111 (the
  pre/post `expected_step_tokens` record). Neither is investigated or repaired here.
- **Amending the runbook.** If the mechanic is wrong, record it under E12 and name
  the follow-up under E13. RELEASE-063 E11 already filed amendments for notes
  1/2/3/5/9 and RELEASE-065 named the note-4 reclassification; this story adds to
  that queue rather than draining it.
- **Filing or draining CERs.** Do not edit `docs/cer/backlog.md`. CER filing is the
  checkpoint's job; the backlog drain is phase 107.
- **Amending `docs/phases/phase-106.md` to record the re-block/unblock history.**
  It should be amended (see the spec-writer note at the top of this file), but
  phase authoring is `phase_new.py`'s job and a separate action from executing a
  migration story.
- **Re-opening or amending RELEASE-063, RELEASE-064 or RELEASE-065.** Their
  verdicts stand as recorded, including RELEASE-065's E6b FAIL. This story's E10
  adds *new* evidence in *this* file; it does not rewrite any predecessor's
  history.
- **The full-fleet DP8 gate and the phase-97 close.** Both are RELEASE-071 (phase
  106 § Ordering, strictly last). This story asserts nothing about the 16/16 fleet
  snapshot.
- **Building the target's proving story to a flex-side spec.** The proving cycle is
  the target project's own work, in its own numbering, under its own loop. It gets
  no flex story ID and no row in `docs/phases/phase-106.md`.
- **Any change to flex's own code, tests, templates, or plugin manifest.** This
  story is evidence-producing. `schema_introduces: false` stands and no
  management-surface row is owed in `docs/phases/phase-106.md` § Schema delivery.
- **Automating the campaign.** No script is written to loop the mechanic over the
  fleet. If that is wanted, it is a new story informed by E12 — not a shortcut taken
  during the run that is supposed to evaluate the manual procedure.

## Evidence

**Executed 2026-07-28/29, orchestrator-level from the flex session (per § Instructions), operator present throughout.**

### E0 — preconditions and unblock proof

- (c) Operator confirmation, quoted verbatim from the live AskUserQuestion exchange: asked
  *"RELEASE-066 E0(c) requires a live, quoted operator confirmation that RELEASE-065's block on
  RELEASE-066..070 is discharged by phase 112 (cp-112 + F3 PASS on caddy rows 33/34). Do you
  confirm?"* — operator answered **"Confirmed — block discharged"**.
- Tags in flex: `git tag -l` → `cp-105`, `cp-110`, `cp-111`, `cp-112` all present.
- Channel content: `git -C /mnt/work/flex-harness log --oneline -1` → `90ff183d chore(phase-112): mark phase complete in index and era ledger (cp-112)` — the cp-112 commit itself; channel clean (`status --porcelain` empty).
- RELEASE-063/064/065 all `status: complete` with `## Evidence` + playbook-note subsections present; RELEASE-067..071 all `status: draft`.
- Dirty-target stop condition fired and was resolved by the operator, quoted verbatim: asked discard / commit / abort for
  `M .companion/effort.db`, `M .companion/state.json`, `?? .companion/state.json.lock` — operator answered
  **"Commit as pre-migration state (Recommended)"**. Committed in target as `cfe0f1b`; the `.lock` deleted, never committed.

### E1 — baseline, path confirmation, starting shape

Command (corrected Signal-1 form, flags confirmed against `--help` post-cp-112):

```
uv run python /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
  --candidate-dir /mnt/work/forqsite.help --no-snapshot
```

Baseline output (target block):

```
/mnt/work/forqsite.help
  binding: version
  signal1 (scripts path): absent — no-declaration
  signal2 (pairmode_version): 0.2.0
  DUPLICATE HOOKS: /mnt/work/forqsite.help — events: SessionStart, PostToolUse
```

- Path disambiguation: `readlink -f /mnt/work/forqsite.help` → `/mnt/work/forqsite.help` (no symlink games);
  the sibling `/mnt/work/forqsite` appears separately in the same scan already at `binding: both` / `0.3.0`.
  Confirmed the migration target is the `.help` docs-site repo, not the sibling source repo.
- `git log --oneline -5` at baseline: `cfe0f1b` (pre-migration snapshot, above), `669b281`, `809aca3`, `3aab61c`, `192410a`; `status --porcelain` empty after cfe0f1b.
- **Starting shape (one line): bound 0.2.x consumer (`binding: version`, signal1 absent, signal2 0.2.0) — ordinary path, same branch as lumin and caddy.**

### Mechanic run

- Dry-run (`sync-all --dry-run`): 1416 lines — 5 agent-file diffs (builder, intent-reviewer, loop-breaker, reviewer,
  security-auditor) + `CLAUDE.build.md`; project-specific `reconstruction-agent.md` untouched. The builder/reviewer diffs
  replace the stale `## Final output to orchestrator` plain-text block (`BUILD-RESULT: DONE` / `<usage>`) with the 0.3.0
  `## Return` JSON contract **in place** — the cp-112 legacy-heading alias replacement operating as designed.
  (First dry-run attempt was truncated by an orchestrator-side `| head` SIGPIPE; re-run clean. Operational note only.)
- Apply: `sync-all --apply --yes` exit 0. Auto-mode classifier did **not** block (note 7: still 1-of-4 overall).
- `state.json.lock` left behind by apply: **recurred (4-of-4)** — removed, not committed (note 5).
- **CER-111 pre/post:** `expected_step_tokens` read **before** `to-030`: `53416`; after: `53416` — **keep + WARN**
  (`[WARN] custom expected_step_tokens=53416 — value kept (not the Era 2 stamp).`), the meander/caddy behaviour, not lumin's silent rewrite.
- `to-030 --apply` exit 0; `pairmode_version` 0.2.0 → 0.3.0. Agent-cleanup WARN fired on all five synced files (note 4, 4-of-4) — paired with the E4(b) grep below rather than dismissed.

**E4(b) — the unblocker-2 check (run before the proving cycle, no hand-edits):**

```
$ grep -rn 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS' /mnt/work/forqsite.help/.claude/agents/
(no matches — exit 1)
```

**CLEAN.** Baseline had the stale grammar in `builder.md` and `reviewer.md` (grep count 1 each pre-sync). cp-112's
`sync-agents` replacement removed it; on caddy (pre-fix) the same content survived sync and killed E6b. This is the first
field observation of unblocker 2 working.

- Migration committed **before** the proving cycle (note 3, 4-of-4): target commit `c2485d6`
  `sync: migrate to pairmode 0.3.0 thin-harness loop` — **10 files changed, 246 insertions(+), 1127 deletions(-)**.

### E2/E3 — post-migration discovery and hooks

Same discovery command re-run; target block now:

```
/mnt/work/forqsite.help
  binding: both
  signal1 (scripts path): /mnt/work/flex-harness/skills/pairmode/scripts
  signal2 (pairmode_version): 0.3.0
```

`audit-hooks --project-dir /mnt/work/forqsite.help` (dry-run) reports duplicates only for **plugin-sourced,
non-pairmode** entries (`session-start.sh` ×2, `security_reminder_hook.py` ×6) — the CER-110 pattern, deliberately not
chased. Direct inspection of `.claude/settings.json`: **exactly one pairmode hook entry per event**
(PreToolUse/UserPromptSubmit/SessionStart/PostToolUse), all pointing at `/mnt/work/flex-harness/hooks/*.py`. E3 asserted
as single-block pairmode hooks, not `duplicate hooks: 0`, per spec.

### E4 — thin-harness template and SKILL.md state

- (a) `grep -c "flex_build.py next-action" CLAUDE.build.md` → **2** (matches all three prior runs); `head -5` shows the
  0.3.0 thin dispatch-loop header (`# CLAUDE.build.md — forqsite.help Build Orchestrator`, delegation to
  `/mnt/work/flex-harness/.../flex_build.py next-action`).
- (c) `sync-all` wrote **no SKILL.md** into this target (no `skills/` dir — caddy-like); recorded as such.

### E5 — proving story cycle

**Mode (operator-chosen, quoted): "Drive from this session (Recommended)"** — this flex session drove the target's own
loop, exercising INFRA-289 `resolve_recording_project` cross-project attribution (caddy already proved the native mode;
this run proves the flex-session branch). Story (operator-chosen, quoted): **"Drift re-sweep vs forqsite (Recommended)"**.

- Target-side story: **CONTENT-005** (phase 3, target's own numbering), scaffolded with the target's own tooling
  (`phase_new.py` / `story_new.py`), specced by an opus spec-writer, built (opus, operator-selected at the resolver's
  `model-upgrade` handoff), reviewed (opus, PASS, zero findings), merged via the target's own
  `create-story-worktree`/`merge-story-worktree` — the full spec-writer → builder → reviewer → merge cycle inside the
  target's `CLAUDE.build.md` loop. Real work, genuinely wanted: corrected the docs site's stale pnpm prereq (`8+` →
  pinned `9.15.9` per upstream `forqsite@b1e6ee73`) with a byte-exact bundle re-encode; regression guards confirmed
  scheduler count, GAP ledger, and ENV claims unchanged. Story commit `186a0f9` on target main.

### E6 — attempt rows in the target's effort.db

Live schema verified first: `attempts(id, story_id, phase, rail, agent_role, model, attempt_number, tokens_total, …,
outcome, notes, ts, …, agent_id, output_file)` — `agent_role`/`ts` as expected.

- **E6a — attribution: PASS (re-confirmed, new branch).** Rows in the **target's** db:

  ```
  (13, 'CONTENT-005', 'builder',  'opus', …)
  (14, 'CONTENT-005', 'reviewer', 'opus', …)
  ```

  Flex complement: `SELECT … FROM attempts WHERE story_id LIKE '%CONTENT-005%'` against `/mnt/work/flex/.companion/effort.db` → `[]`.
  This is the first proof of INFRA-289 attribution from a **flex-session** drive (caddy proved native; worktree-path precedence
  routed these rows to `/mnt/work/forqsite.help`).

- **E6b — content: SPLIT (see gate statement).** First read: both rows pending (`tokens_total NULL, outcome NULL`).
  Explicit sweep (`subagent_transcript.py reconcile --project-dir /mnt/work/forqsite.help --limit 200 --json`) →
  `{"reconciled": 1}`:

  ```
  (13, 'CONTENT-005', 'builder',  'opus', None, None)      ← still pending
  (14, 'CONTENT-005', 'reviewer', 'opus', 9187, 'PASS')    ← reconciled
  ```

  Row 14 resolving with a parsed `PASS` + non-zero tokens **is downstream proof of the CER-101 content half** on this
  target. Row 13 diagnosed per spec rather than reported as a bare NULL — isolated to a **named, non-grammar** cause:
  `is_reconcilable_spawn_output` → `not-terminated`, because (i) the builder transcript's final assistant entry carries
  `stop_reason: None` (the known ~18% no-stamp case the quiescence promotion exists for), and (ii) quiescence
  (`QUIESCENT_AGE_SECONDS=900`) never triggers **while the driving session is alive** — the harness atomically
  re-serializes the task output file during the session (observed: same path flapping 236 KB ↔ 125 B with mtime moving
  both directions), so mtime never ages 900 s. Decisive content check run directly:
  `parse_worker_outcome(<builder final text>)` → **`('PASS', None)`** — the parser reads the row's outcome; nothing about
  this is the caddy grammar failure. Expected to reconcile via any post-session sweep (well inside the 14-day
  `RECONCILE_MAX_AGE_DAYS` window); resolution to be recorded here when observed.

- **E6c — no duplicates: PASS (re-confirmed).**
  `SELECT story_id, agent_role, COUNT(*) … GROUP BY story_id, agent_role HAVING COUNT(*)>1` → `[]` (one row per spawn).

### E7 — report path

`flex_build.py checkpoint-report --project-dir /mnt/work/forqsite.help`:

```
=== checkpoint cost rollup — phase 3 ===
  reviewer: 1 attempt(s), median 9,187 tokens
  -- per-story --
  CONTENT-005: reviewer: 1 attempt(s), median 9,187 tokens
=== lifetime cost rollup (all phases) ===
  builder: 6 attempt(s), median 97,431 tokens
  reviewer: 7 attempt(s), median 45,398 tokens
```

**Upgrade over RELEASE-065 achieved:** the phase-scoped rollup resolves the E5 story's own phase and shows the E5
story's **own row** (CONTENT-005 reviewer) — the read-path proof RELEASE-065 could not produce. No "no active phase
resolved" artifact. The pending builder row is (correctly) excluded from medians until it reconciles; recorded, not
rounded up.

### E8 — target git history

```
186a0f9 feat(story-CONTENT-005): correct stale pnpm prereq claim after drift re-sweep
f431b99 spec(CONTENT-005): block-style primary_files (flow-style list parses as string in frontmatter reader)
efa66e2 spec(CONTENT-005): orchestrator fixes — primary_files frontmatter, dedupe phase-3 story row, correct baseline date
9aa6535 spec(CONTENT-005): elaborate drift re-sweep spec
118a421 spec(CONTENT-005): scaffold story stub
308c17f spec(phase-3): scaffold drift re-sweep phase with CONTENT-005 (RELEASE-066 proving cycle)
c2485d6 sync: migrate to pairmode 0.3.0 thin-harness loop     ← migration commit, 10 files, +246/−1127
cfe0f1b chore(pre-migration): snapshot companion runtime state …
```

Migration precedes the proving cycle (note 3 applied, 4-of-4).

### E9 — settings.local.json sediment

File exists. Pre-migration: **55** allow rules, of which **3** `Write(` + **26** per-file `Edit(` = 29 stale. Operator
decision, quoted: **"Prune (Recommended)"**. Backup: `/mnt/work/forqsite.help/.claude/settings.local.json.bak-pre-030-prune`.
Post-prune: **26** rules (29 removed). (Fleet tally: meander 91 pruned, lumin n/a, caddy 48, forqsite.help 29.)

### E10 — downstream-proof position restated

As of this run: **attribution (CER-103)** proven downstream twice — caddy native (worktree-path precedence) and now
forqsite.help flex-session-driven (both INFRA-289 branches). **Dedupe (CER-104)** re-confirmed (caddy, forqsite.help).
**Content (CER-101)** — the half the campaign was re-blocked on — now has its **first downstream proof**: forqsite.help
row 14 (reviewer) reconciled to a parsed `PASS` with real tokens through the cp-112 parser, and the cp-112 sync-agents
replacement demonstrably removed the stale grammar before the cycle (E4b). Builder row 13 pending on a
termination-detection artifact, not grammar (diagnosis above); its reconciliation completes the pair. Meander's
post-cp-110 E6 re-verification remains outstanding (its agent bodies were synced pre-cp-112; its next sync+cycle should
now succeed).

### E11 — cleanliness

- `git -C /mnt/work/flex-harness status --porcelain` → empty, throughout and after (scripts invoked, never written).
- Unblocker-4 snapshot observation: every discovery invocation in this story passed `--no-snapshot`; no snapshot write
  occurred anywhere. `/mnt/work/flex-harness/docs/fleet-snapshot.md` exists but is a **tracked historical artifact**
  (committed by INFRA-249 / DP8 baseline, last touched `2c2683fa`), unchanged this run — not RELEASE-065-style pollution.
- `/mnt/work/forqsite` (source repo): read-only throughout; builder verified `status --porcelain` byte-identical to its
  pre-build snapshot (its pre-existing dirty `.claude/agents/*.md` files untouched).

### E14 — flex suite

`uv run pytest tests/pairmode/ -q` (no `-x`): **4116 passed, 211 skipped, 0 failed** (152.87 s).

### Playbook notes (E12 — delta against the three prior runs)

1. Dirty tree: **recurred (3-of-4)** — new form again: live companion runtime state (`effort.db`/`state.json` mid-write
   sediment). Operator chose **commit** (first time; meander/caddy discarded) — pre-migration snapshot `cfe0f1b`.
2. Runbook step-5 command form: **recurred (4-of-4)**; corrected form used. Runbook § Per-project mechanic still says
   `discover --project-dir`; still unamended.
3. Commit-before-proving: **recurred / applied (4-of-4)**.
4. Agent-cleanup WARN: **recurred (4-of-4)** — fired on all five synced files. Post-cp-112 it is survivable noise *when
   paired with a clean E4(b) grep*; the runbook amendment should say exactly that.
5. `state.json.lock`: **recurred (4-of-4)**; removed, not committed.
6. `expected_step_tokens`: **keep+WARN (53416)** — 3-of-4 keep+WARN vs lumin's 1-of-4 silent rewrite; CER-111's
   value-dependence hypothesis further supported.
7. Auto-mode classifier block: **did not recur (1-of-4, unsettled).**
8. Recording/session-binding: INFRA-289 **both branches now proven** (see E10).
9. Sediment: **recurred (3-of-4)** — 29 rules pruned with backup.

New this run:

- **(new-1) In-session quiescence promotion is structurally unreachable for spawns of the live session.** The harness
  re-serializes task output files while the session runs, refreshing mtime; `QUIESCENT_AGE_SECONDS` therefore only ever
  promotes *other* sessions' leftovers. Combined with `stop_reason: None` finishers (~18%), a live orchestrator session
  cannot fully reconcile its own just-finished spawns — the rows resolve only from a later session. Not a grammar
  defect; filed as follow-up (below) alongside the deterministic-completion design note.
- **(new-2) Flow-style YAML lists in story frontmatter parse as strings.** `primary_files: [a, b]` crashed
  `create-story-worktree` (`TypeError` in `generate_permissions_artifact`); block-style lists work. Same parser family as
  CER-092. Also: the interrupted run left a half-created worktree requiring `discard-story-worktree` before retry.
- **(new-3) `story_new.py`/`phase_new.py` double-row hazard:** scaffolding the story row by hand in the phase doc *and*
  running `story_new.py --phase 3` produced a duplicate Stories-table row (one `planned`, one `draft`); deduped by hand.
  Worth a guard or a documented convention (let `story_new.py` own the row).
- **(new-4) Resolver `model-upgrade` handoff at attempt 1** for a `story_class: code` story on a no-test-suite static
  site; operator chose opus. Worth understanding what triggered the suggestion before RELEASE-067 hits the same pause.

### Follow-ups (E13 — filed, not fixed here)

- **CER to file (flex): deterministic spawn-completion recording.** `SubagentStop` hook event is unused by pairmode;
  `PostToolUse` fires at *launch* for async spawns, so completion is only ever observed by timer heuristics that (new-1)
  cannot fire in-session. Proposal: thin `SubagentStop` relay runs the single-row reconcile for its `agent_id`; demote
  the quiescence sweep to backstop. (Operator raised the design question directly; predates but is sharpened by new-1.)
- **CER to file (flex): frontmatter flow-style list support or explicit rejection** (new-2) — silent string parse →
  downstream `TypeError` is the worst of both.
- **Runbook amendments** (notes 2/3/5/9 already filed by RELEASE-063 E11; still unapplied after four runs — consider
  actually amending the runbook before RELEASE-067 rather than filing a fifth identical note): plus note-4 wording
  ("accurate warning; pair with the E4b grep") and a dirty-tree precondition step covering live companion-state sediment.
- **Row-13 completion record:** when a later sweep reconciles builder row 13, append the observed values here.
- **Meander E6 re-verification** (outstanding since RELEASE-063): now expected to pass post-cp-112; schedule its
  re-sync + one-story cycle.

### Campaign gate statement (Instructions step 13)

**The campaign's first downstream proof of the CER-101 content half now exists — supplied by forqsite.help, story
CONTENT-005, reviewer attempt row 14 (`outcome='PASS'`, `tokens_total=9187`), parsed by the cp-112 grammar from a
sync-agents-replaced agent body (E4b clean).** Builder row 13's outcome is proven parseable (`parse_worker_outcome` →
`('PASS', None)`) but the row itself remains pending on a termination-detection artifact (new-1), not on grammar; it
completes on any post-session sweep. By the strict letter of E6b ("NULL persisting after both sweeps is a fail"), this
is a **split verdict pending an operator ruling**: content half proven, full row-pair reconciliation one artifact short.
RELEASE-067..070 remain **held pending that operator ruling** — not silently started, not silently blocked.

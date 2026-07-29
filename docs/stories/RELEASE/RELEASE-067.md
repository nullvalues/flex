---
id: RELEASE-067
rail: RELEASE
title: Migrate halfhorse to pairmode 0.3.0
status: complete
phase: "106"
auth_gated: false
schema_introduces: false
story_class: docs
primary_files:
  - docs/stories/RELEASE/RELEASE-067.md
touches:
  - docs/stories/RELEASE/RELEASE-067.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

<!-- SPEC-WRITER NOTE (frontmatter): the stub arrived with no `primary_files:` key,
     `touches: []` and no `story_class:`. All three were populated here per the
     RELEASE-064 / RELEASE-065 / RELEASE-066 precedent (operator-directed): the
     single in-repo write target is *this file* — the `## Evidence` section
     appended by the executor. Every other write target is outside the repo, under
     `/mnt/work/halfhorse`, and therefore cannot appear in `touches:` at all; that
     is the point of phase 106 § Execution model. The cross-repo write set is
     enumerated instead in `## Cross-repo scope boundaries` below.
     Both lists are written **block-style**, not flow-style: per RELEASE-066
     new-2 / CER-115, `primary_files: [a, b]` parses as a *string* in the
     frontmatter reader and crashes `create-story-worktree`'s
     `generate_permissions_artifact` with a `TypeError`. Do not "tidy" these into
     flow style. -->

## Context

Phase 106 drives the remaining pairmode 0.3.0 fleet migrations centrally from
flex, using the six-step mechanic in `docs/harness-cutover-runbook.md`
§ *Per-project mechanic* as the unit of work. RELEASE-063 was the campaign canary
(meander), RELEASE-064 the first follow-on (lumin), RELEASE-065 the second
(caddy), RELEASE-066 the third (forqsite.help). **RELEASE-067 is the fifth run —
and the first run after the campaign's load-bearing downstream proof actually
landed.**

**Target repo: `/mnt/work/halfhorse`.**

**What changed under this story, and why it is a lighter run than RELEASE-066.**
RELEASE-066 completed 2026-07-29 with an **operator-ruled qualified pass on
E6b**. Its evidence established, for the first time anywhere in the fleet, that
the CER-101 *content* half reaches a consumer: forqsite.help story `CONTENT-005`,
reviewer attempt **row 14**, reconciled to `outcome='PASS'` with
`tokens_total=9187`, parsed by the cp-112 grammar out of a `sync-agents`-replaced
agent body (its E4(b) grep was clean, where caddy's was not). The builder row 13
stayed pending — but on a *termination-detection* artifact, not on grammar, and
its final assistant text was shown to parse (`parse_worker_outcome` →
`('PASS', None)`). The operator ruled that shape a **qualified pass** and
unblocked RELEASE-067..070 on that basis.

The consequence for this story is precise and should not be overstated in either
direction:

- **E6b here re-confirms; it does not establish.** RELEASE-066 owns the first
  downstream proof. This run's job is to show the same mechanism holds on a
  second, differently-shaped project. A failure here is still a stop — it would
  mean the cp-112 fixes are project-dependent — but a pass is a second data
  point, not a campaign milestone, and `## Evidence` must not claim otherwise.
- **E6a (attribution, CER-103) and E6c (dedupe, CER-104) are re-confirmations
  too**, and have been since RELEASE-065. Both INFRA-289 attribution branches are
  now proven (caddy native / worktree-path precedence; forqsite.help
  flex-session-driven). Cite, do not re-derive.

**The known reconciliation artifact — expect it, do not mistake it for a
regression.** RELEASE-066 new-1, now filed as **CER-114**: in-session quiescence
promotion is structurally unreachable for spawns of the *driving* session. The
harness re-serializes task output files while the session is alive, refreshing
their mtime, so `QUIESCENT_AGE_SECONDS` only ever promotes *other* sessions'
leftovers; combined with the ~18% of finishers that carry `stop_reason: None`,
a live orchestrator session cannot fully reconcile its own just-finished spawns.
E6b below therefore encodes the operator's ruling directly: a pending row whose
**final assistant text passes `parse_worker_outcome`**, paired with **at least one
fully reconciled row** on the same story, is the qualified-pass shape the operator
already accepted. That check is mandatory, not optional — a bare "still NULL" with
no parse check is a fail, because it cannot distinguish CER-114 from the caddy
grammar defect that re-blocked the campaign once already.

**The corrected Signal-1 command is spec-mandated, not a note.** Canary playbook
note 2 (the runbook's step-5 `discover` subcommand / `--project-dir` flag form is
wrong) has now **recurred 4-of-4** and the runbook is still unamended. Separately,
RELEASE-065's E11 caught the *default snapshot path* writing into
`/mnt/work/flex-harness`; cp-112's INFRA-295 made the snapshot refuse-by-default,
and RELEASE-066 observed a clean channel. `--no-snapshot` remains **mandatory on
every discovery invocation in this story**, including any run made inside the
target's own session — that is the form all four prior runs recorded, and E11
still *observes* the channel rather than assuming it.

**Prior-run notes are inputs, not background.** Four runs of numbered playbook
notes now exist (RELEASE-063's nine, RELEASE-064's new-1/new-2, RELEASE-065's
new-1/new-2/new-3, RELEASE-066's new-1..new-4). Where the runbook and this spec
disagree on *command form* or on *when the migration commit lands*, **this spec
wins**: it carries four runs' worth of corrections, and phase 106 § Out of scope
keeps runbook edits out of migration stories.

Two things about how this story runs are unusual and are settled by phase 106
§ *Execution model (cross-repo — deviation from the standard loop)*, which you
should read before acting:

1. **No sandboxed builder subagent, no flex worktree.** The write targets live at
   `/mnt/work/halfhorse`, outside this repo. The standard worktree loop and
   `scope_guard.py` forbid writes there — correctly. Execution is
   **orchestrator-level with the operator present**.
2. **Acceptance is evidence-shaped, not diff-shaped.** The flex-side diff is one
   `## Evidence` section appended to this file. The reviewer verifies recorded
   command output, not a code change.

The pairmode CLIs are invoked from the **permanent release channel**,
`/mnt/work/flex-harness` — canonized in `docs/architecture.md` § *Release channel
— flex-harness* and by RELEASE-062 (phase 105). Do not invoke them from
`/mnt/work/flex/skills/...`: the channel is what the fleet consumes, and migrating
a project with a different copy of the scripts than the fleet uses would prove
nothing about whether the cp-110/cp-111/cp-112 changes reach consumers.

## Cross-repo scope boundaries

Phase 106 § *Execution model* permits this story to write outside `/mnt/work/flex`.
That permission is **not** open-ended. The complete write set is enumerated here;
anything not listed is read-only or forbidden, and a write outside this list is a
scope violation to be reported, not rationalized.

**Writable — inside `/mnt/work/flex`:**

- `docs/stories/RELEASE/RELEASE-067.md` — this file, `## Evidence` section only.
- Rows in `docs/phases/phase-106.md`, `docs/phases/index.md` and the era/effort
  ledgers **only** as written by the orchestrator's own recording CLIs
  (`flex_build.py` status/record subcommands). Hand-edits to those files are not
  part of this story.

**Writable — inside `/mnt/work/halfhorse` (the target repo, and only via the
pairmode CLIs or an operator-approved edit):**

- `CLAUDE.build.md` — rewritten to the 0.3.0 thin-harness template by `sync-all`.
- `.claude/agents/*.md` — re-rendered by `sync-agents` (this is where cp-112's
  legacy-heading replacement lands).
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
- `/mnt/work/meander`, `/mnt/work/lumin`, `/mnt/work/caddy`,
  `/mnt/work/forqsite.help` — read for the E10 proof-debt re-check only. No sync,
  no re-migration.
- `/mnt/work/flex/skills/`, `tests/`, `ui/`, `.claude-plugin/` — untouched.

**Forbidden outright:**

- Every other project directory under `/mnt/work/` — RELEASE-068..070 own pokus,
  base56 and cora, and `/mnt/work/forqsite` (the sibling of RELEASE-066's target)
  is in no story's scope here.
- `docs/harness-cutover-runbook.md` and `docs/cer/backlog.md` in flex — findings
  are *named* under E13, never applied here.

## Requires

- **The campaign is unblocked, and the unblock is on the record.** RELEASE-066's
  `## Evidence` closes with the operator's ruling, quoted:
  **"Qualified pass — proceed (Recommended)"**, and states *"RELEASE-067..070 are
  unblocked on that basis."* Confirm that ruling is present in RELEASE-066 before
  starting and capture it for E0. Unlike RELEASE-066, this story does **not**
  require a fresh live operator confirmation of the unblock — the ruling is
  recorded — but it does require the executor to *read and quote* it rather than
  assert it from memory.
- **cp-105, cp-110, cp-111 and cp-112 are tagged in flex and their content is in
  the release channel.** Phase 106 § Execution model: *"do not start this phase
  before cp-105."* Verify the channel content directly — a tag in flex is not
  evidence the channel was fast-forwarded (phase 102 existed precisely for that
  step).
- **RELEASE-063, RELEASE-064, RELEASE-065 and RELEASE-066 are complete and all
  four `## Evidence` sections are present**, including their playbook-note and
  follow-up subsections. This story is specced against all four; if any is
  missing, stop — you are not running the playbook the campaign produced.
- **No sibling phase-106 story beyond RELEASE-063..066 has been started.**
  RELEASE-068..071 must still be `draft` when this story begins.
- `/mnt/work/flex-harness` exists and is the release channel described in
  `docs/architecture.md` § *Release channel — flex-harness*.
- **The target exists as a git repository and its working tree is clean** at the
  moment the mechanic begins. The path is *expected* to be `/mnt/work/halfhorse`;
  confirm it from `fleet_discovery.py`'s candidate scan rather than assuming. Per
  canary playbook note 1 — which **recurred 3-of-4**, most recently in the new form
  of live companion runtime sediment (`effort.db` / `state.json` mid-write) — a
  dirty tree is a **stop** condition with no runbook step covering it: the operator
  decides (discard, commit, or abort) and the decision is recorded verbatim. Do not
  stash around it unilaterally.
- `docs/harness-cutover-runbook.md` contains a `## Per-project mechanic` section
  enumerating the six steps, and a `## Rollback procedure` section. That section,
  as corrected by this spec's `## Instructions`, is the step list; this spec states
  what must be *true afterwards*.
- **The operator is present.** Canary note 7's auto-mode permission classifier
  block on the first out-of-repo `sync-all --apply` is still unsettled (1-of-4:
  fired on meander only), the E9 prune decision and the E5 proving-story selection
  are operator calls, and RELEASE-066's new-4 resolver `model-upgrade` handoff is
  expected to pause for an operator model choice.
- Known flex-side environmental failure inside fresh worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story; did not appear on RELEASE-065's or
  RELEASE-066's runs from the main checkout.

## Ensures

Each assertion below is verified from recorded command output pasted into this
file's `## Evidence` section (see `## Instructions` step 12). "Recorded" means the
exact command and its exact output, not a paraphrase. An Ensure whose evidence is
missing from that section is a **fail**, regardless of whether the underlying
thing happened.

**E0. The preconditions — including the recorded campaign unblock — are evidenced,
not assumed.**
`## Evidence` records:
- (a) `git -C /mnt/work/flex tag --list 'cp-105' 'cp-110' 'cp-111' 'cp-112'`
  showing all four tags;
- (b) a check that `/mnt/work/flex-harness` carries **cp-112** content — e.g. a
  `git rev-parse` comparison of flex's `cp-112` against the channel's `HEAD`, or
  `git -C /mnt/work/flex-harness log --oneline -5` showing the phase-112 commits.
  If the channel is behind, this is a **stop**; fast-forwarding it is not this
  story's work (see `## Out of scope`);
- (c) the operator's RELEASE-066 ruling **quoted from that file**
  (*"Qualified pass — proceed (Recommended)"*, 2026-07-29) together with a one-line
  statement of the current proof position: *the CER-101 content half is proven
  downstream (forqsite.help CONTENT-005 row 14); this story's E6b re-confirms it on
  a second project rather than establishing it.*

**E1. A pre-migration baseline exists and the target is unambiguously identified.**
`## Evidence` contains the verbatim output of a `fleet_discovery.py` run captured
**before any write to the target**, using `--no-snapshot`, showing the target's
pre-migration `binding`, `signal1` (scripts path) and `signal2`
(`pairmode_version`), plus the run's `Projects with duplicate hooks:` line.
`## Evidence` also records:
- `git -C /mnt/work/halfhorse log --oneline -5` and
  `git -C /mnt/work/halfhorse status --porcelain`;
- an explicit line confirming the resolved target path is `/mnt/work/halfhorse`
  (`readlink -f`, no symlink indirection) and that no similarly-named sibling was
  scanned in its place;
- one line stating which starting shape the target is in — bound-0.2.x,
  bound-other-version, declared-but-unstamped, or never-bootstrapped — and
  therefore which branch of `## Instructions` step 5 applies.

The **expected** baseline, from the last fleet discovery, is `binding: version`,
`signal1` **absent** (no-declaration), `signal2: 0.2.0` — i.e. a bound 0.2.x
consumer, the same ordinary branch lumin, caddy and forqsite.help took. That
expectation is **not** evidence: record what the scan actually prints, and if it
differs, say so and re-branch at step 5 rather than proceeding on the expectation.

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
- (b) `pairmode_sync.py audit-hooks --project-dir /mnt/work/halfhorse` (dry-run),
  showing that any remaining `DUPLICATE:` lines are **plugin-sourced and
  non-pairmode**, and that nothing pairmode-owned is prunable;
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
- (a) the result of inspecting `/mnt/work/halfhorse/CLAUDE.build.md` and confirms
  it is the thin dispatch-loop template, not the pre-flip 0.2.x prose loop. Use the
  same checks all four prior runs used so the five are comparable:
  `grep -c "flex_build.py next-action" <path>` (all four prior runs printed `2`)
  plus a `head -5`;
- (b) **the stale-grammar check, run *before* the proving cycle.** After
  `sync-agents` runs, the target's `.claude/agents/*.md` bodies contain **no
  surviving 0.2-era plain-text result-grammar example** — i.e.
  `grep -rn 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS'` over the target's agent
  files returns nothing, or returns only occurrences explicitly part of the new
  legacy-tolerance documentation. Record the **pre-sync** grep counts as well as
  the post-sync result, so the replacement is visible as a delta the way
  RELEASE-066 recorded it (`builder.md` and `reviewer.md` carried one each
  pre-sync; zero after). A surviving stale example is a **predictor of E6b
  failure** and must be reported to the operator **before** the proving cycle
  starts, not discovered afterwards;
- (c) the observed state of any `SKILL.md` content `sync-all` wrote into the
  target — whether the skill `name:` values are the **bare** cp-111 names rather
  than the old namespaced ones. If `sync-all` copies no SKILL.md into this target
  (caddy and forqsite.help had no `skills/` dir), record that fact instead.

**E5. A proving story cycle completed inside the target — or its absence is
recorded as an explicit, operator-owned deferral.**

*Preferred path (proof).* `## Evidence` names the target-side story ID built as the
proving cycle (mechanic step 6), states that it ran inside the target's **own**
`CLAUDE.build.md` loop with the target's own story numbering, states the full
cycle it traversed (spec-writer → builder → reviewer → merge), and states its
outcome. The story is a real, small, genuinely-wanted piece of the target
project's work — not a throwaway. `## Evidence` states explicitly which session
mode was used (native target session, or this flex session exercising INFRA-289's
`resolve_recording_project` attribution) and why. Both modes are now proven
(caddy native; forqsite.help flex-session-driven), so either is acceptable — but
the mode changes what a pass proves and must be declared.

*Fallback path (deferral).* If the target cannot run a proving cycle,
`## Evidence` records, in the same shape RELEASE-064 used: the operator's decision
**quoted verbatim**; the reason the project could not build; and an explicit
statement that E5/E6/E7 are **unevidenced, therefore not passed**, and that this
story's migration is a stamp without a proof. A follow-up naming where the proof
will come from is filed under E13.

Silence is a fail. One of the two paths must be explicit in `## Evidence`.

**E6. The proving cycle's attempt rows landed in the target's effort.db —
correctly, including `outcome`.**
Applies when E5 took the preferred path; when E5 took the fallback, E6 is recorded
as *not run* with the consequence stated and is **not** claimed as passed. All
three parts are verified from recorded queries against the target's `effort.db`
(locate it; do not assume the path — meander's, lumin's, caddy's and
forqsite.help's were `.companion/effort.db`). Verify the live schema before
querying: the `attempts` table uses `agent_role`/`ts`, **not** `role`/`created_at`
(RELEASE-064 E10; confirmed by RELEASE-065 and RELEASE-066).

- **E6a — attribution (CER-103).** At least one attempt row exists for the E5
  story ID **in the target's own db**, not flex's. `## Evidence` also records the
  complementary check that flex's `effort.db` contains **no** rows for the E5 story
  ID. PROVEN downstream on caddy (native) and forqsite.help (flex-session-driven);
  this run re-confirms rather than establishes.
- **E6b — content (CER-101). Re-confirmation, with the CER-114 shape explicitly
  admitted.** The rows have a **non-null, non-placeholder `outcome`** and a
  non-zero token/cost field. `## Evidence` must record: the raw row values; the
  result after an explicit reconciliation sweep if any row is pending at first
  read; and one of the following three verdicts, stated in these terms:
  - **Full pass** — every attempt row for the E5 story reconciled to a real
    `outcome` and non-zero `tokens_total`. Record it as a **second downstream
    confirmation** of the CER-101 content half; do **not** describe it as a first
    or as the campaign's proof — RELEASE-066 owns that.
  - **Qualified pass (the CER-114 shape the operator already ruled acceptable)** —
    at least one row for the E5 story is **fully reconciled** (real `outcome`,
    non-zero `tokens_total`), and every still-pending row has had
    `parse_worker_outcome` run directly against its **final assistant text** with
    the result recorded, showing the outcome *is* parseable. `## Evidence` must
    also record the `is_reconcilable_spawn_output` diagnosis (expected:
    `not-terminated`) so the cause is named as the CER-114 in-session quiescence
    artifact and not as grammar. Both halves — the reconciled row **and** the
    recorded parse check — are required; either alone is a fail.
  - **Fail** — a row is pending and its final text does **not** parse, or no row
    reconciled at all. This is the caddy pattern; it means the cp-112 fixes did not
    hold on this project. Record the `read_completed_spawn` diagnosis (which of
    `outcome` / `tokens_total` / `model` parsed) so the failure is isolated to a
    named field rather than reported as a bare NULL, and stop.
- **E6c — no duplicates (CER-104).** Each attempt appears **once**. Record a
  grouped count (e.g. `SELECT story_id, agent_role, COUNT(*) … GROUP BY … HAVING
  COUNT(*) > 1`) showing no perfect pairs with near-identical timestamps. PROVEN
  downstream on caddy and forqsite.help; this run re-confirms.

E6a or E6c failing, or E6b reaching the **Fail** verdict, is a stop condition (see
`## Instructions` step 11).

**E7. The target's checkpoint/report path sees the attempts — including the
proving rows.**
Applies on the same condition as E6. `## Evidence` records the output of the
pairmode checkpoint or attempt-report CLI run against the target for the phase
containing the E5 story, showing the attempts (not "no attempts recorded").
RELEASE-066 achieved the upgrade RELEASE-065 could not: its phase-scoped rollup
resolved the E5 story's phase and printed the E5 story's **own row**, with no
"no active phase resolved" artifact. That is the bar here: if E6b reaches a full
or qualified pass, `## Evidence` must show at least one of the E5 story's own
reconciled rows reflected in the report output. Pending rows are (correctly)
excluded from medians — record that, do not round it up. Record the exact command
(RELEASE-065/066 used `flex_build.py checkpoint-report --project-dir <target>`;
confirm against `--help` before running).

**E8. The target's git history shows the migration as its own commit(s).**
`## Evidence` records `git -C /mnt/work/halfhorse log --oneline` covering the
migration commit(s) and, if E5 ran, the proving-story commit(s), so a later auditor
can see exactly what the sync wrote and roll it back if needed. Per canary playbook
note 3 — **recurred 4-of-4** — the migration commit **precedes** the proving cycle
in history. Record the file/insertion/deletion counts for the migration commit.

Additionally, per **CER-116**: no commit subject written in the target repo under
this story may name a sibling `RELEASE-0NN` story ID. Only `spec(...)`-prefixed
commits in *flex* carry RELEASE IDs; the target's `sync:` migration commit and the
proving cycle's commits are the target project's own history and must read as such.
`## Evidence` records the migration commit subject verbatim so this is checkable.

**E9. The target's `settings.local.json` sediment is handled deliberately.**
Per canary playbook note 9 (**recurred 3-of-4**: meander 133 rules / 91 stale;
lumin had no such file; caddy 48 stale rules pruned; forqsite.help 29 pruned from
55), `## Evidence` records: whether
`/mnt/work/halfhorse/.claude/settings.local.json` exists; if it does, the
pre-migration count of `Write(`/`Edit(` allow rules, the **operator's decision**
(prune or keep) quoted, and — if pruned — the post-prune count and the backup
location. If the file does not exist or carries no such rules, record that fact.
"Not mentioned" is a fail. This is an operator decision; do not prune unilaterally.

**E10. The campaign's downstream-proof position is re-checked and restated.**
`## Evidence` records the current position across the fleet as of this run,
explicitly separating the three CERs:

- **CER-103 (attribution)** — PROVEN downstream twice, on both INFRA-289 branches
  (caddy PAIRMODE-002 native / worktree-path precedence; forqsite.help CONTENT-005
  flex-session-driven). Cite; do not re-derive.
- **CER-104 (dedupe)** — PROVEN downstream (caddy, forqsite.help). Cite.
- **CER-101 (content/outcome)** — PROVEN downstream by forqsite.help CONTENT-005
  row 14 (`outcome='PASS'`, `tokens_total=9187`), under an operator-ruled qualified
  pass. State whether this run adds a **second** confirmation, and on which
  verdict shape (full or CER-114-qualified).
- **Outstanding items to restate, not re-open:** RELEASE-066's row-13 completion
  record (does a later sweep reconcile it? if the executor can cheaply observe it,
  say so — but amending RELEASE-066 is out of scope, so record the observation
  *here*), and **meander's** E6 re-verification, outstanding since RELEASE-063 and
  now expected to pass post-cp-112 because agent bodies *are* copied into consumer
  repos at sync time and meander's and lumin's predate the JSON grammar.
  Performing any re-sync of meander or lumin is **not** this story's work (see
  `## Out of scope`); naming it is.

**E11. Cleanliness — the flex-side diff is this file only, and the channel is
untouched.**
```bash
git -C /mnt/work/flex diff --name-only
git -C /mnt/work/flex-harness status --porcelain
```
The first lists exactly `docs/stories/RELEASE/RELEASE-067.md` (plus the phase doc's
story row and index/ledger rows if the orchestrator's recording CLIs touch them —
those are tool-written, not hand-written). No file under `skills/`, `tests/`, `ui/`,
or `.claude-plugin/` is modified by this story. The second prints **nothing**.

`## Evidence` also states whether any snapshot file was written and where. Note
that `/mnt/work/flex-harness/docs/fleet-snapshot.md` **exists as a tracked
historical artifact** (RELEASE-066 E11 established this — committed by INFRA-249 /
the DP8 baseline); its mere presence is not pollution. What matters is that it is
**unchanged** and that `status --porcelain` is empty. This is the second
observation point for cp-112's INFRA-295 snapshot refuse-by-default.

**E12. Playbook findings are recorded as a delta against *all four* prior runs.**
This file's `## Evidence` ends with a **Playbook notes** subsection that, for each
of RELEASE-063's nine numbered notes **and** the new findings from RELEASE-064
(new-1 → CER-110, new-2 → CER-111), RELEASE-065 (new-1 snapshot pollution, new-2
grammar skew, new-3 CER-guard placeholder — all three routed into phase 112) and
RELEASE-066 (new-1 → CER-114, new-2 → CER-115, new-3 double-row hazard, new-4
resolver `model-upgrade` handoff), states whether it **recurred**, **did not
recur**, or **was not applicable** on this target — and then lists any *further*
new deviation, manual intervention, or ambiguity this run produced. A flat list
that does not reference the prior notes fails this Ensure. Six specific
comparisons are required:

- **note 4 / RELEASE-065 new-2 (the reclassified WARN).** `to-030`'s agent-cleanup
  step printed *"content differs from known 0.2.x template … manual porting
  required"* on all four prior runs. RELEASE-065 proved it was flagging the stale
  bodies that broke E6b; RELEASE-066 found it fired on all five synced files while
  E4(b) came back clean, i.e. survivable noise **when paired with a clean grep**.
  Record whether the WARN appears here **and** what E4(b) found, and state which of
  those two readings this run supports.
- **note 7** (auto-mode classifier block) — fired on meander only (1-of-4,
  unsettled). State which happened here.
- **note 6 / CER-111** (`expected_step_tokens`) — meander kept its custom value
  with a WARN, caddy kept `53416` with a WARN, forqsite.help kept `53416` with a
  WARN, lumin was silently rewritten `53000 → 5000` (3-of-4 keep vs 1-of-4
  rewrite). `## Evidence` must record this target's **pre-`to-030` value**, the
  **post-`to-030` value**, and whether a keep/WARN or a silent rewrite occurred.
  Reading the value only afterwards makes the delta unrecoverable.
- **RELEASE-065 new-3 / CER-guard placeholder (cp-112 INFRA-294)** — caddy's first
  post-migration checkpoint was blocked by `_check_cer_do_now` reading the
  scaffolded `(none)` placeholder row as an unresolved Do-Now item. If this
  target's proving cycle reaches a checkpoint, record whether that false positive
  recurred.
- **RELEASE-066 new-1 / CER-114 (in-session quiescence)** — record whether the E5
  cycle's rows reconciled fully in-session, or reproduced the pending-but-parseable
  shape. Either outcome is informative; a second occurrence strengthens CER-114's
  case for the deterministic `SubagentStop` completion record.
- **RELEASE-066 new-3 (double-row hazard) and new-4 (`model-upgrade` handoff)** —
  if the proving cycle scaffolds a phase/story in the target, record whether the
  `story_new.py` + hand-written row duplication recurred, and whether the resolver
  offered a `model-upgrade` handoff at attempt 1 and what the operator chose.

If the mechanic ran exactly as written with no intervention, say exactly that.

**E13. Runbook or CER follow-ups are filed, not fixed here.**
Every defect surfaced under E12, plus the E10 proof-position follow-ups and any E5
deferral follow-up, is *named* in `## Evidence` as a follow-up with its intended
destination (runbook amendment or CER). This story does **not** edit
`docs/harness-cutover-runbook.md` or `docs/cer/backlog.md` (see `## Out of scope`).
RELEASE-063 E11 already filed the runbook amendments for canary notes 1/2/3/5/9;
RELEASE-064's findings are CER-110/CER-111; RELEASE-065's three were routed into
phase 112; RELEASE-066's are CER-114/CER-115 plus its two unfiled notes. **If any
recurred, reference the existing item rather than filing a duplicate.** The runbook
amendments RELEASE-063 filed are now four runs unapplied — RELEASE-066 explicitly
recommended amending the runbook before this story rather than filing a fifth
identical note; if it still has not been amended, say so plainly and escalate it as
a standing follow-up rather than restating it a fifth time as if it were new.

**E14. flex's own suite is unaffected.**
`uv run pytest tests/pairmode/` is run once at the end, **without `-x`**, and is
green except the known CER-090 worktree-environmental failure
(`tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`) if
it appears. RELEASE-066's run from the main checkout was fully green (4116 passed,
211 skipped). This story changes no flex code, so any *new* failure means something
ran that should not have.

## Instructions

**Execution model — read before anything else.** You are executing this story **at
orchestrator level with the operator present**, not as a sandboxed builder subagent
in a flex worktree. **Do not create a story worktree. Do not dispatch a builder
subagent.** The write targets are outside this repo and `scope_guard.py` will block
a subagent from reaching them — correctly — and working around that block is itself
a violation. The only in-repo write is this file's `## Evidence` section, appended
by the orchestrator at step 12. Read `## Cross-repo scope boundaries` before the
first write and treat it as the complete permission list.

1. **Prove the gate state (E0).** Read RELEASE-066's `## Evidence` and quote the
   operator's ruling (*"Qualified pass — proceed (Recommended)"*, 2026-07-29) and
   its unblock statement. Then confirm cp-105, cp-110, cp-111 and cp-112 are tagged
   in flex **and** that `/mnt/work/flex-harness` carries cp-112 content. The channel
   is a separate checkout and its fast-forward is a distinct step. If the channel is
   behind, stop and hand back to the operator.

2. **Confirm the remaining preconditions before touching anything.** Verify every
   bullet in `## Requires` and record the checks: RELEASE-063/064/065/066 complete
   with all four `## Evidence` sections and their playbook-note subsections present;
   RELEASE-068..071 still `draft`; the target located and its working tree clean. If
   any fails, stop and hand back to the operator.

3. **Read all four prior runs' notes, then the mechanic.** Read the
   § *Playbook notes* / § *Follow-ups* subsections of RELEASE-063, RELEASE-064,
   RELEASE-065 and RELEASE-066, plus RELEASE-066's § *Mechanic run*, § *E6* and
   § *Campaign gate statement* blocks — those record the exact shape this run is
   expected to reproduce. Then read `docs/harness-cutover-runbook.md`
   § *Per-project mechanic* in full, and § *Rollback procedure* alongside it so you
   know the exit path before you start. The spec-writer is input-bound and did
   **not** read any of those files. Where the runbook and this spec disagree on
   *procedure*, apply the corrections (steps 4 and 8 below) and record the
   discrepancy under E12; where they disagree on *what must be true afterwards*,
   this spec's `## Ensures` wins.

4. **Capture the baseline and confirm you have the right repo (E1).** Run
   `fleet_discovery.py` from the release channel. Per canary playbook note 2 —
   **recurred 4-of-4** — the runbook's step-5 command form is wrong (it names a
   nonexistent `discover` subcommand and a `--project-dir` flag). The corrected
   Signal-1 form, used by all four prior runs, is:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
     --candidate-dir /mnt/work/halfhorse --no-snapshot
   ```
   `--no-snapshot` is **mandatory on every discovery invocation in this story**,
   including any run the target's own session makes. Confirm flags against `--help`
   before running and do not guess flags.

   Explicitly confirm the resolved path with `readlink -f /mnt/work/halfhorse` and
   record it. Save the full output; you will compare it against the post-migration
   run. Also capture `git -C /mnt/work/halfhorse log --oneline -5` and
   `… status --porcelain`.

   Then **state the target's starting shape in one line** and pick the step-5
   branch. The expected shape is bound-0.2.x (`binding: version`, signal1 absent,
   signal2 `0.2.0`); if the scan says otherwise, follow what it says.

5. **Branch on the baseline before running the mechanic.**
   - **Bound 0.2.x consumer** (`signal2: 0.2.x`, any `binding`) — the ordinary
     path, and the expected one here; run the six-step mechanic as lumin, caddy and
     forqsite.help did.
   - **Bound but version-absent, or bound to a non-0.2.x version** — the mechanic
     still applies, but `to-030`'s assumptions about a 0.2.x starting state may not
     hold. Run `--dry-run` first, show the operator, and record any step whose
     output differs from RELEASE-066's recorded shape.
   - **Never bootstrapped** (no pairmode binding at all) — the migration is a
     *bootstrap to 0.3.0*, not a 0.2→0.3 migration. `to-030` may be inapplicable.
     Stop and confirm the intended path with the operator before writing anything;
     record the decision. Do not improvise a bootstrap sequence and do not let a
     bootstrap masquerade as a migration in the evidence.

6. **Run the mechanic against the target.** Follow the runbook's six steps in
   order, invoking `pairmode_migrate.py` and `pairmode_sync.py` from
   `/mnt/work/flex-harness/skills/pairmode/scripts` — never from
   `/mnt/work/flex/skills/...`. Expect, from the prior four runs:
   - **note 7 (unsettled, 1-of-4):** the auto-mode permission classifier may block
     the first out-of-repo `sync-all --apply`. If it blocks, ask the operator to
     toggle auto mode off so the normal permission prompt surfaces; do not attempt
     to route around the classifier.
   - **note 5 (recurred 4-of-4):** `sync-all --apply` may leave
     `.companion/state.json.lock` behind (INFRA-285 advisory-lock artifact). It is
     transient — remove it and do **not** commit it.
   - **note 4 (recurred 4-of-4, reclassified):** the `to-030` agent-cleanup step
     prints "content differs from known 0.2.x template … manual porting required".
     Do not dismiss it on its own; pair it with step 7's grep before deciding it is
     benign.
   - **CER-111 — mandatory pre-read:** **before** running `to-030 --apply`, read
     and record the target's current `expected_step_tokens` value from its state
     file. Then run `to-030` and record the value again. Report both to the operator
     along with whether a keep+WARN or a silent rewrite occurred.
   - **Dry-run first, and beware truncation:** RELEASE-066's first `sync-all
     --dry-run` was truncated by an orchestrator-side `| head` SIGPIPE. Capture the
     full dry-run output before reading it.

   Show the operator the output of each step before proceeding to the next. If a
   step fails, **stop** — do not improvise a fix into the target. Report to the
   operator, and if the failure is unrecoverable, execute the runbook's rollback
   procedure and record what happened under E12.

7. **Verify the agent bodies before you spend a proving cycle on them (E4b).**
   Grep the target's `.claude/agents/*.md` for the 0.2-era plain-text grammar
   (`BUILD-RESULT: DONE`, `REVIEW-RESULT: PASS`) **both before the sync** (to
   capture the baseline counts) and **immediately after `sync-agents`/`sync-all`
   completes and before the proving cycle**. cp-112's legacy-heading replacement is
   supposed to remove exactly this, and RELEASE-066 observed it working. If a stale
   example survives, **stop and report to the operator before running the proving
   cycle** — RELEASE-065 spent a full native cycle discovering this after the fact.
   Do not hand-edit the agent files to make the grep clean: that would fake the very
   thing E6b is meant to prove. If stale content survives, the correct outcome is a
   stop plus a follow-up against cp-112's `sync-agents` replacement, not a repaired
   file.

8. **Commit the migration before the proving cycle (canary note 3, recurred
   4-of-4).** The runbook orders the commit after step 6; that is wrong for the
   0.3.0 loop, because the proving story's worktree snapshots git HEAD and would not
   see the migration. Commit the sync/migration changes into the target as their
   **own** commit first (prior runs used
   `sync: migrate to pairmode 0.3.0 thin-harness loop`), then run the proving cycle.
   Per **CER-116**, do not name RELEASE-067 or any sibling `RELEASE-0NN` ID in that
   subject or in any proving-cycle commit subject — those commits belong to the
   target's own history. Record the discrepancy under E12 as a recurrence of note 3.

9. **Handle the `settings.local.json` sediment (E9, canary note 9).** Before
   handing the target to a proving cycle, check whether
   `/mnt/work/halfhorse/.claude/settings.local.json` exists and count the stale
   `Write(`/`Edit(` allow rules. `sync-all` correctly does not touch that file, so
   any sediment survives migration and floods the first post-migration session with
   warnings. Present the count to the operator and let the operator decide
   prune-or-keep. If pruning: back the file up first (the fleet convention:
   `<file>.bak-pre-030-prune`), remove the stale `Write(path)` and per-file
   `Edit(path)` rules (obsolete under 0.3 story-scoped permissions), and record
   before/after counts, the backup path and the operator's decision verbatim.
   **This is an operator decision — do not prune unilaterally.** If the file does
   not exist, record that.

10. **Verify the stamp before proving (E2, E3, E4).** Re-run the exact step-4
    `fleet_discovery.py --no-snapshot` command and confirm the target now reports
    `0.3.0`, `binding: both` with `signal1` pointing at the channel. Then run
    `audit-hooks --project-dir /mnt/work/halfhorse` as a dry-run and inspect the
    target's `.claude/settings.json` for the per-event pairmode hook blocks —
    **assert single-block pairmode hooks, not `Projects with duplicate hooks: 0`**;
    per CER-110 that number will be non-zero fleet-wide on a plugin-sourced,
    non-pairmode basis, and chasing it to zero would mean editing files
    `audit-hooks` deliberately never writes. Then inspect
    `/mnt/work/halfhorse/CLAUDE.build.md` for the thin-harness template and record
    the cp-111 SKILL.md name state per E4(c). Do not proceed until E2/E3/E4 hold —
    a proving cycle run against a half-migrated project produces uninterpretable
    evidence.

11. **Run the proving story cycle (E5, E6, E7).** This is mechanic step 6 and the
    most expensive step in the story. Its purpose here is **re-confirmation on a
    second project**, not first proof: RELEASE-066 already supplied the campaign's
    downstream CER-101 content-half proof.

    Pick the session mode with the operator — native target session or this flex
    session exercising INFRA-289 attribution — and declare it in `## Evidence`, as
    both branches are now proven and the choice is informational. Do not create a
    flex story for the proving cycle; the target uses its own numbering, its own
    `CLAUDE.build.md` loop, and its own scaffolding tools. Pick a small, real,
    already-wanted piece of the target project's work — a no-op story defeats the
    purpose. Remind the target session that any `fleet_discovery.py` invocation it
    makes must pass `--no-snapshot` (step 4).

    Two scaffolding hazards carried from RELEASE-066: write any story frontmatter
    lists **block-style, never flow-style** (CER-115 — `primary_files: [a, b]`
    parses as a string and crashes `create-story-worktree`; recovery from an
    interrupted worktree creation is `discard-story-worktree` before retry), and let
    `story_new.py` own the phase-doc Stories row rather than hand-writing one
    alongside it (new-3 double-row hazard). Expect a possible resolver
    `model-upgrade` handoff at attempt 1 (new-4) and let the operator choose.

    When the cycle completes, run all three E6 checks plus the E7 report check.
    **Verify the live `attempts` schema first** (`agent_role`/`ts`, not
    `role`/`created_at`). If any row reads back pending, run the explicit
    reconciliation sweep; if it is still pending afterwards, you **must** run
    `parse_worker_outcome` directly against that row's final assistant text and
    record the result, plus the `is_reconcilable_spawn_output` diagnosis, before
    assigning a verdict. That is what separates the operator-accepted CER-114
    qualified-pass shape from the caddy grammar failure — and a "still NULL" report
    without the parse check cannot distinguish them and is a fail.

    E6a or E6c failing, or E6b reaching the **Fail** verdict, is a stop condition:
    report it as such and do not start RELEASE-068. An E6b Fail specifically means
    the cp-112 fixes did not hold on this project — say that in those words, because
    it would be a regression against a phase checkpointed as complete and against a
    proof that already exists.

    If the target genuinely cannot run a cycle, take E5's fallback path — record the
    operator's decision verbatim and state that E5/E6/E7 are unevidenced and
    therefore not passed. Do not round a deferral up to a pass.

12. **Record the evidence (E0–E14).** Append a `## Evidence` section to *this
    file*, containing, in order: the E0 precondition and quoted unblock ruling; the
    E1 baseline, path confirmation and starting-shape classification; a *Mechanic
    run* block including the CER-111 pre/post `expected_step_tokens` values and the
    E4(b) pre/post agent-body greps; the E2/E3 post-migration discovery and
    `audit-hooks` output; the E4 template and cp-111 SKILL.md check; the E5
    proving-story ID, session mode and outcome (or the quoted deferral); the
    E6a/E6b/E6c queries, output and verdict (with the parse check if any row is
    pending); the E7 report output; the E8 target git log and migration commit
    subject; the E9 settings hygiene record; the E10 proof-position restatement; the
    E11 cleanliness checks; the E14 suite output; a **Playbook notes** subsection per
    E12; and a **Follow-ups** subsection per E13. Paste command output verbatim
    inside fenced blocks — do not summarize it into prose, because RELEASE-068..070
    are specced against what actually happened and a summary loses exactly the detail
    a later failure would need.

13. **Gate the rest of the campaign — and say plainly what this run added.** The
    return must contain one unambiguous sentence about the downstream proof
    position. If E6b reached a full or qualified pass, say that this run supplies a
    **second** downstream confirmation of the CER-101 content half, name the project
    and story ID, and state that RELEASE-068..070 remain unblocked. If E6b failed or
    E5 was deferred, say so explicitly and state that RELEASE-068..070 are blocked
    pending an operator decision. Do not claim a first proof — RELEASE-066 owns it.

14. **Ideology note (Step 4a — resolved inline, no conflict).** Four things in
    `docs/ideology.md` shaped this spec. *"Never silently pass contradictions"*
    (override path: explicit acknowledgement plus a recorded reason, never a silent
    bypass) is why E6b enumerates three named verdicts instead of one binary — the
    operator's RELEASE-066 qualified-pass ruling is an acknowledged, recorded
    override of E6b's original strict letter, and encoding it explicitly here is the
    opposite of letting it quietly become the new default. It is also why the
    qualified-pass branch *requires* the `parse_worker_outcome` check and the
    `is_reconcilable_spawn_output` diagnosis: without them the ruling would degrade
    into "pending rows are fine," which is precisely the contradiction the caddy
    failure taught. *"Rationale-bearing decisions over bare rules"* is why E3 stays
    restated around CER-110 (the rule's reason — prove the sync produces single-block
    pairmode hooks by itself — survives in a form that can still fail honestly) and
    why step 7 forbids hand-editing agent bodies to make the grep clean: the rule's
    purpose is to detect stale grammar, and satisfying it by editing would destroy
    the signal. *"Decision fidelity over convenience"* is why E1 requires the
    baseline to be *recorded* even though it is already expected, and why E9 and E5
    require the operator's words verbatim. On accepted constraints: *"Hooks are thin
    relays only"* is adjacent, since the mechanic rewrites the target's hook block —
    the rationale is that hooks must not block or write state, so E3 forbids
    hand-editing the target's settings to satisfy an assertion and step 6 forbids
    routing around the permission classifier. *"Sidebar owns all state writes"* is
    why E6 is asserted against the db as written by the normal path, with no manual
    repair of rows permitted to make an assertion pass — and why step 11 requires the
    reconciliation *sweep* (the normal path) rather than a hand-written `outcome`.
    No constraint is overridden by this spec and nothing required a decision on the
    ideology itself, so this resolves inline rather than flagging.

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
# E1/E2/E3 — baseline and post-migration state. --no-snapshot is mandatory;
# the runbook's step-5 form is wrong, 4-of-4 (note 2).
readlink -f /mnt/work/halfhorse
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
  --candidate-dir /mnt/work/halfhorse --no-snapshot
```

```bash
# E3 — pairmode-scoped hook assertion (CER-110: fleet-wide count will NOT be 0)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
  audit-hooks --project-dir /mnt/work/halfhorse
```

```bash
# E4(a) — thin-harness template
grep -c "flex_build.py next-action" /mnt/work/halfhorse/CLAUDE.build.md
head -5 /mnt/work/halfhorse/CLAUDE.build.md

# E4(b) — stale-grammar check. Run BEFORE the sync (baseline counts) and again
# AFTER sync-agents, BEFORE the proving cycle. Empty output post-sync is the pass.
grep -rn 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS' /mnt/work/halfhorse/.claude/agents/ \
  || echo "clean — no legacy plain-text grammar examples survived sync-agents"

# E4(c) — cp-111 bare skill names as landed in the target (may not exist)
grep -rn '^name:' /mnt/work/halfhorse/.claude/skills/*/SKILL.md 2>/dev/null || \
  echo "no SKILL.md copied into target — record this"
```

```bash
# CER-111 — expected_step_tokens, BEFORE and AFTER to-030
grep -n 'expected_step_tokens' /mnt/work/halfhorse/.companion/state.json
# ... run to-030 --apply ...
grep -n 'expected_step_tokens' /mnt/work/halfhorse/.companion/state.json
```

```bash
# E6 — proving-cycle attempt rows in the target's own effort.db.
# Locate the db first; do not assume a path. Schema uses agent_role/ts.
find /mnt/work/halfhorse -name 'effort.db' -not -path '*/node_modules/*'
sqlite3 <target-effort.db> ".schema attempts"

# E6a attribution: rows present in the target, absent in flex
sqlite3 <target-effort.db> "SELECT * FROM attempts WHERE story_id='<E5-STORY-ID>'"
sqlite3 /mnt/work/flex/.companion/effort.db \
  "SELECT * FROM attempts WHERE story_id='<E5-STORY-ID>'"   # must be empty

# E6b content — outcome and tokens after reconciliation
sqlite3 <target-effort.db> \
  "SELECT id, story_id, agent_role, model, tokens_total, outcome, ts
     FROM attempts WHERE story_id='<E5-STORY-ID>'"
# If any row is still pending after the explicit reconcile sweep, the parse check
# below is MANDATORY before assigning a verdict (CER-114 qualified-pass shape):
#   parse_worker_outcome(<that row's final assistant text>)   -> must yield an outcome
#   is_reconcilable_spawn_output(<that spawn's output>)       -> expect 'not-terminated'

# E6c duplicates: one row per attempt, no perfect pairs
sqlite3 <target-effort.db> \
  "SELECT story_id, agent_role, COUNT(*) FROM attempts
    WHERE story_id='<E5-STORY-ID>' GROUP BY story_id, agent_role HAVING COUNT(*) > 1"
```

```bash
# E7 — the target's checkpoint/attempt report sees the PROVING rows
# (RELEASE-065/066 used this command; confirm the subcommand via --help)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py \
  checkpoint-report --project-dir /mnt/work/halfhorse
```

```bash
# E9 — settings.local.json sediment, before and after
ls /mnt/work/halfhorse/.claude/settings.local.json 2>/dev/null || echo "no settings.local.json"
grep -c 'Write(' /mnt/work/halfhorse/.claude/settings.local.json
grep -c 'Edit('  /mnt/work/halfhorse/.claude/settings.local.json
```

```bash
# E10 — proof-position re-check across the fleet (read-only)
# forqsite.help CONTENT-005 row 14 is the campaign's CER-101 content-half proof;
# row 13 is the CER-114 pending-but-parseable row whose later reconciliation is open.
sqlite3 /mnt/work/forqsite.help/.companion/effort.db \
  "SELECT id, story_id, agent_role, model, tokens_total, outcome, ts
     FROM attempts WHERE story_id='CONTENT-005'"
sqlite3 /mnt/work/caddy/.companion/effort.db \
  "SELECT id, story_id, agent_role, tokens_total, outcome, ts
     FROM attempts WHERE story_id='PAIRMODE-002'"
```

```bash
# E8 — migration visible in the target's history, migration commit before proving.
# Also confirms no sibling RELEASE-0NN ID appears in a target commit subject (CER-116).
git -C /mnt/work/halfhorse log --oneline -10

# E11 — flex-side diff is this story file only; channel untouched
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
- E0(c) quotes RELEASE-066's operator ruling and states the current proof position
  (content half already proven; this run re-confirms);
- E1 records the actual scan output and the `readlink -f` path confirmation, not the
  expected baseline;
- the target shows `binding: both` and `0.3.0`, with single-block **pairmode** hooks
  per event; the fleet-wide `Projects with duplicate hooks: N` line is recorded
  informationally and is **not** required to be `0` (CER-110);
- E4(b)'s agent-body grep is recorded **both pre-sync and post-sync**, the post-sync
  run happened **before** the proving cycle, and the agent files were not hand-edited
  to make it pass;
- the CER-111 pre-`to-030` and post-`to-030` `expected_step_tokens` values are both
  recorded, with the keep-or-rewrite behavior named;
- either (i) E5/E6/E7 reach a **full pass** — rows in the target's own db, populated
  `outcome` and tokens, one row per attempt, E7's report reflecting the proving rows
  — recorded as a *second* downstream confirmation; or (ii) E6b reaches the
  **qualified pass** shape — at least one fully reconciled row **plus** a recorded
  `parse_worker_outcome` result and `is_reconcilable_spawn_output` diagnosis for
  every pending row, attributed to CER-114 and not to grammar; or (iii) E6b **fails**
  with the `read_completed_spawn` diagnosis recorded and RELEASE-068..070 declared
  blocked; or (iv) E5's fallback path is recorded with the operator's decision quoted;
- the E8 migration commit subject is recorded verbatim and names no sibling
  `RELEASE-0NN` story ID (CER-116);
- `git -C /mnt/work/flex-harness status --porcelain` prints nothing, and E11 states
  whether any snapshot file was written or changed;
- the flex suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if it
  appears, state that it reproduces on clean `HEAD` and is unrelated;
- the return contains one unambiguous sentence on the downstream CER-101 proof
  position and declares RELEASE-068..070 blocked or unblocked accordingly, without
  claiming a first proof.

Note for `spec-preflight`: this spec references a `## Evidence` section and its
**Playbook notes** / **Follow-ups** subsections, which do not exist in this file yet
— they are created by this story, and any preflight finding naming them is expected.
It also references `/mnt/work/halfhorse`, `/mnt/work/forqsite.help`,
`/mnt/work/caddy`, `/mnt/work/meander`, `/mnt/work/lumin`,
`/mnt/work/flex-harness/skills/pairmode/scripts`, the
`cp-105`/`cp-110`/`cp-111`/`cp-112` tags, CER-090/101/103/104/110/111/114/115/116,
INFRA-249/285/289/294/295, and `docs/harness-cutover-runbook.md`
§ *Per-project mechanic* / § *Rollback procedure*, none of which the input-bound
spec-writer could open; they are sourced from `docs/phases/phase-106.md`
§ *Execution model* and its dated status paragraphs, from `docs/eras/003-*.md`
§ *Phases* (the `112 … complete` row), from RELEASE-066's `## Evidence`, and from
the campaign context supplied with this story. The function names
`parse_worker_outcome`, `is_reconcilable_spawn_output` and `read_completed_spawn`
come from RELEASE-065's and RELEASE-066's recorded diagnoses. All concrete paths
inside the target (`.companion/state.json`, `.companion/effort.db`,
`.claude/settings.local.json`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`)
are **expected** shapes taken from the four prior targets, not verified for this
one — locate each before using it, and record what you actually find. The
`--candidate-dir` / `--no-snapshot` flags, the `audit-hooks` subcommand and
`checkpoint-report` come from the prior runs' recorded invocations; confirm via
`--help`.

## Out of scope

- **Migrating any project other than `/mnt/work/halfhorse`.** pokus, base56 and
  cora are RELEASE-068..070. Do not run the mechanic against a second project
  "while the environment is warm" — the campaign wants each data point separable.
- **Re-syncing or re-migrating meander, lumin, caddy or forqsite.help.** E10
  requires *re-checking* the proof position and *naming* the outstanding
  meander/lumin re-sync determination under cp-112. Performing any re-sync, or
  re-running caddy's PAIRMODE-002 reconciliation to see whether the grammar fix
  retro-resolves its pending rows, is separate work — mixing a remediation of an
  earlier project into this migration would make it impossible to tell which
  project's evidence proved what.
- **Amending RELEASE-066 with its row-13 reconciliation.** If a later sweep is
  observed to have resolved forqsite.help's builder row 13, record the observation
  in *this* story's E10. RELEASE-066 is `complete` and its evidence is a historical
  record; the follow-up it filed is discharged by a new record, not by a rewrite.
- **Fixing CER-114.** The deterministic spawn-completion recording proposal
  (`SubagentStop` relay running a single-row reconcile, quiescence demoted to
  backstop) is filed. This story *observes* CER-114 and encodes its accepted shape
  into E6b; it does not implement, redesign, or work around it, and it does not
  hand-write an `outcome` to make a row look reconciled.
- **Fast-forwarding `/mnt/work/flex-harness` to cp-112.** If E0 finds the channel
  behind, **stop**. Promoting the channel is a release action (phase 102's
  precedent), not something a migration story does mid-run.
- **Fixing the phase-112 unblockers if they fail downstream.** If E4(b) finds
  surviving stale grammar or E6b fails, this story **stops and reports**. Repairing
  `sync-agents` or `parse_worker_outcome` is a new phase, specced from this story's
  evidence — not an inline fix, and not a hand-edit of the target's agent files.
- **Diagnosing or fixing CER-110, CER-111, CER-115 or CER-116.** All are filed. This
  story is specced *around* CER-110 (E3's restated assertion), *observes* CER-111
  (the pre/post `expected_step_tokens` record), and *complies with* CER-115
  (block-style frontmatter lists) and CER-116 (no sibling story IDs in target commit
  subjects). None is investigated or repaired here.
- **Amending the runbook.** If the mechanic is wrong, record it under E12 and name
  the follow-up under E13. RELEASE-063 E11 already filed amendments for notes
  1/2/3/5/9; this story adds to that queue rather than draining it — though E13
  requires escalating the fact that the queue is now five runs deep.
- **Filing or draining CERs.** Do not edit `docs/cer/backlog.md`. CER filing is the
  checkpoint's job; the backlog drain is phase 107.
- **Amending `docs/phases/phase-106.md`.** Its status paragraphs now carry the
  re-block/unblock history through cp-112; any further amendment is phase-authoring
  work (`phase_new.py`), a separate action from executing a migration story.
- **Re-opening or amending RELEASE-063, RELEASE-064 or RELEASE-065.** Their verdicts
  stand as recorded, including RELEASE-065's E6b FAIL.
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

**Executed 2026-07-29, orchestrator-level from the flex session (per § Instructions), operator present throughout.**

### E0 — preconditions

- E0(c) satisfied by RELEASE-066's recorded ruling (quoted there): **"Qualified pass — proceed (Recommended)"** — RELEASE-067..070 unblocked on that basis; no fresh confirmation demanded per this spec.
- Tags cp-105/110/111/112 present in flex; channel at `90ff183d` (cp-112 content), `status --porcelain` empty.
- Dirty-target stop condition fired: `M .companion/state.json` (live companion runtime state, same shape as forqsite.help's). Operator decision, quoted verbatim: **"Commit as pre-migration state (Recommended)"** → target commit `d6265a7`; no lock file present pre-sync.

### E1 — baseline, path, starting shape

Corrected `--no-snapshot` Signal-1 form (flags confirmed against `--help`); baseline target block:

```
/mnt/work/halfhorse
  binding: version
  signal1 (scripts path): absent — no-declaration
  signal2 (pairmode_version): 0.2.0
```

`readlink -f /mnt/work/halfhorse` → `/mnt/work/halfhorse`. **Starting shape: bound 0.2.x consumer — ordinary path (5th consecutive).**

### Mechanic run

- Dry-run: 1459 lines — 5 pairmode agent diffs + `CLAUDE.build.md`; 8 stale-grammar removal hunks visible in the diff.
- **E4(b) pre-sync grep** (per this spec's two-sided requirement): 4 hits — `builder.md:88,114` `BUILD-RESULT: DONE`, `reviewer.md:222,297` `REVIEW-RESULT: PASS`.
- Apply exit 0; classifier did not block (note 7: 1-of-5). `state.json.lock` left behind → removed, not committed (note 5: **5-of-5**).
- **CER-111 pre/post: `53000` → `5000` — SILENT REWRITE**, `[apply] rewrote expected_step_tokens: 53000 → 5000` (also `[apply] backfilled missing 'effort_tracking': true`). Lumin's behaviour reproduced exactly at the same pre-value; value-dependence confirmed (53416 → keep+WARN twice, 53000 → silent rewrite twice). Reported to operator pre-commit; decision, quoted verbatim: **"Accept 5000"**. CER-111 evidence strengthened, not fixed here.
- **E4(b) post-sync grep: CLEAN** (`grep -rn 'BUILD-RESULT: DONE\|REVIEW-RESULT: PASS' .claude/agents/` → no matches). Second consecutive field confirmation of the cp-112 sync-agents replacement. No hand edits.
- Migration committed **before** proving (note 3: 5-of-5): `bd24c1b` `sync: migrate to pairmode 0.3.0 thin-harness loop` — **11 files, +315/−1144** (subject contains no sibling story IDs, per this spec's CER-116 rule).

### E2/E3/E4 — stamps

Post-migration discovery: `binding: both`, `signal1: /mnt/work/flex-harness/skills/pairmode/scripts`, `signal2: 0.3.0`. Hooks: exactly one pairmode entry per event (PreToolUse/UserPromptSubmit/SessionStart/PostToolUse), all channel-bound; remaining duplicate-hook signal is the CER-110 plugin-sourced pattern, not chased. `grep -c "flex_build.py next-action" CLAUDE.build.md` → **2**; thin-harness header confirmed. No SKILL.md written into the target (no `skills/` dir); recorded.

### E9 — sediment

`settings.local.json` exists: 23 allow rules, **0** `Write(` and **0** per-file `Edit(` — no sediment; no prune decision needed; recorded as such (first target with a clean file: meander 91 pruned / lumin n/a / caddy 48 / forqsite.help 29 / halfhorse 0).

### E5 — proving cycle (ran twice; see E6 for why)

**Mode (operator-chosen, quoted): "Drive from this session (Recommended)"**; story choice (operator-chosen, quoted): **"Repair phase index (Recommended)"**.

- **Cycle 1 — INFRA-001** (halfhorse phase 2, new INFRA rail): repair `docs/phases/index.md`'s phantom "Phase 1 — in progress" row (a pairmode-0.2.0 template placeholder; the real Phase 1 — "Spam Filter for Inquire Service" — was complete and tagged `cp1-spam-filter-complete`, recorded in `docs/phase-prompts.md`). Full spec→build(haiku)→review(haiku, PASS)→merge cycle in halfhorse's own loop; story commit `197b496`.
- **Cycle 2 — INFRA-002**: replace `docs/checkpoints.md`'s fabricated `cp1-[phase-name]-complete` template with the real cp1–cp3 checkpoint history (tags verified via `git rev-parse` loops). Full cycle again (haiku/haiku, reviewer PASS); story commit `2719be6`.

Both stories are real, genuinely-wanted planning-doc repairs surfaced by recon, not throwaways.

### E6 — attempt rows (the reason there were two cycles)

- **Cycle 1 (INFRA-001): E6a FAILED — and the failure is the INFRA-289 design working.** Rows landed in **flex's** db (rows 462/463); halfhorse's `effort.db` did not exist. Cause: `/mnt/work/halfhorse` was **not in flex's `registered_projects` allowlist**, so `resolve_recording_project` rejected the worktree-path candidate and fell back to the session project, logging the designed alarm — verbatim from `.companion/effort_recording.log`:

  ```
  {"ts": "2026-07-29T03:37:47…", "subagent_type": "builder",  "decision": "skip:target-unregistered", "target_project": "/mnt/work/flex", "target_source": "rejected-unregistered"}
  {"ts": "2026-07-29T03:40:08…", "subagent_type": "reviewer", "decision": "skip:target-unregistered", "target_project": "/mnt/work/flex", "target_source": "rejected-unregistered"}
  ```

  forqsite.help succeeded in RELEASE-066 only because it was already registered (canary-era). **Campaign-mechanic gap: "register the target before driving its proving cycle from a flex session" is a missing runbook/spec step** — filed under E13. Operator decision, quoted verbatim: **"Register + rerun proving cycle (Recommended)"**. Registered via `pairmode_register.py register --project-dir /mnt/work/halfhorse` (provenance sidecar recorded; allowlist now 5 entries). Rows 462/463 remain flex-attributed (historical, per INFRA-289 precedent: no backfill).

- **Cycle 2 (INFRA-002), post-registration — E6 FULL PASS, all three parts:**
  - **E6a (re-confirmed):** rows in halfhorse's own db; flex complement for INFRA-002 → `[]`.
  - **E6b (re-confirmed, full — no qualified branch needed):** first read: builder already `(haiku, 12434, 'PASS')` (its transcript ended with a proper `end_turn`; CER-114's in-session artifact did not bite this time), reviewer pending; explicit sweep → `{"reconciled": 1}`; final:

    ```
    (1, 'INFRA-002', 'builder',  'haiku', 12434, 'PASS')
    (2, 'INFRA-002', 'reviewer', 'haiku',  9846, 'PASS')
    ```

  - **E6c (re-confirmed):** grouped duplicate count → `[]`.

### E7 — report path

`flex_build.py checkpoint-report --project-dir /mnt/work/halfhorse`:

```
=== checkpoint cost rollup — phase 2 ===
  builder: 1 attempt(s), median 12,434 tokens
  reviewer: 1 attempt(s), median 9,846 tokens
  -- per-story --
  INFRA-001: no attempts recorded
  INFRA-002: builder: 1 attempt(s), median 12,434 tokens; reviewer: 1 attempt(s), median 9,846 tokens
```

The E5 story's own rows appear in the phase-scoped rollup, **both roles fully reconciled** — a stronger read-path proof than RELEASE-066's (which had one pending row). `INFRA-001: no attempts recorded` is the honest trace of the cycle-1 misattribution, not a defect in the report path.

### E8 — target git history

```
2719be6 feat(story-INFRA-002): replace checkpoints.md template with real legacy checkpoint history
9aaefee spec(INFRA-002): elaborate checkpoints.md repair; record real cp1-cp3 tags, drop template placeholder
5be7bf8 spec(INFRA-002): scaffold checkpoints-doc repair stub
197b496 feat(story-INFRA-001): repair phantom in-progress phase-1 row and broken link
1996114 spec(INFRA-001): elaborate phase-index repair; phase 1 identified as spam-filter phase
1b4caf9 spec(INFRA-001): scaffold story stub on new INFRA rail
5d5673d spec(INFRA-001-scaffold): scaffold phase 2 planning-doc repair with story stub
bd24c1b sync: migrate to pairmode 0.3.0 thin-harness loop     ← migration, 11 files, +315/−1144
d6265a7 chore(pre-migration): snapshot companion runtime state …
```

Migration precedes both proving cycles; no sibling `RELEASE-0NN` IDs in any target commit subject.

### E10 — downstream-proof position restated

Attribution (CER-103): proven native (caddy) + flex-session (forqsite.help, halfhorse cycle 2); the rejection branch (`skip:target-unregistered` → session fallback with alarm) now also field-observed (halfhorse cycle 1). Dedupe (CER-104): re-confirmed on every target since. Content (CER-101): **halfhorse is the first target with a full (unqualified) E6b pass** — both rows reconciled with parsed outcomes through the cp-112 grammar; forqsite.help row 13 remains pending on the CER-114 artifact (unchanged, awaiting a post-session sweep); meander E6 re-verification still outstanding.

### E11 — cleanliness

`git -C /mnt/work/flex-harness status --porcelain` → empty throughout. Every discovery invocation carried `--no-snapshot`; no snapshot write anywhere. `/mnt/work/flex-harness/docs/fleet-snapshot.md` unchanged (tracked INFRA-249 artifact). No other fleet repo touched.

### E14 — flex suite

`uv run pytest tests/pairmode/ -q` (no `-x`): **4116 passed, 211 skipped, 0 failed** (153.78 s).

### Playbook notes (E12 — delta against four prior runs)

1. Dirty tree: **recurred (4-of-5)** — live companion-state sediment again; operator chose **commit** (2nd time).
2. Runbook step-5 form: **recurred (5-of-5)**; corrected form used.
3. Commit-before-proving: **applied (5-of-5)**.
4. Agent-cleanup WARN: recurred; paired with clean post-sync E4(b) grep — survivable noise pattern holds.
5. `state.json.lock`: **recurred (5-of-5)**.
6. `expected_step_tokens`: **silent rewrite at 53000 (2-of-5 silent, 2-of-5 keep+WARN at 53416, 1 n/a)** — CER-111's value-dependence confirmed with a clean A/B; operator accepted the stamp.
7. Auto-mode classifier block: did not recur (1-of-5).
8. Recording: INFRA-289 all three branches now field-observed (target-registered native, target-registered flex-session, **unregistered rejection with alarm**).
9. Sediment: **first clean target** (0 stale rules).

New this run:

- **(new-1) Missing mechanic step: target registration.** Driving a proving cycle from a flex session requires the target in flex's `registered_projects` *before* the spawns run; nothing in the runbook or the RELEASE-066/067 spec lineage said so. Cost here: one wasted-attribution cycle (INFRA-001 rows 462/463 in flex's db) and a rerun. Fix: add "register the target (`pairmode_register.py register --project-dir <target>`) at mechanic step 0 when driving from flex" to the runbook amendment set; RELEASE-068..070 specs must carry it.
- **(new-2) `story_new.py` prompts interactively for a new rail** (`Rail INFRA does not exist. Create it? [Y/n]`) — aborts under a non-interactive orchestrator unless piped `yes`; worth a `--create-rail` flag.
- **(new-3) `phase_new.py`+hand-rowed story caused no duplicate this time** (row added only by `story_new.py`) — RELEASE-066 new-3 discipline held.

### Follow-ups (E13 — filed, not fixed here)

- **Runbook amendment set now includes registration (new-1)** — the RELEASE-063-era amendments are five runs unapplied; strongly recommend an actual runbook-edit story before RELEASE-068 rather than a sixth identical note.
- **CER to file: `story_new.py` non-interactive rail creation** (new-2).
- **CER-111**: A/B evidence recorded here (53000 silent × 2, 53416 keep+WARN × 2); the existing backlog row should absorb this data when next groomed.
- forqsite.help row 13 post-session reconciliation: still open (RELEASE-066 E13 item, unchanged).
- meander E6 re-verification: still open.

### Campaign gate statement (Instructions step 13)

**E6b re-confirmed — fully, with no qualified branch: halfhorse story INFRA-002's builder and reviewer rows both reconciled to parsed `PASS` outcomes with real token counts through the cp-112 grammar (the first unqualified E6b pass of the campaign), and the E4(b) post-sync grep was clean before the cycle ran.** E6a's cycle-1 failure was the INFRA-289 rejection branch operating as designed against an unregistered target, resolved by operator-approved registration and a rerun; it is a mechanic gap, not a recording defect. **RELEASE-068..070 are unblocked**, with the explicit carry-forward that their specs must include target registration as a precondition step.

---
id: RELEASE-065
rail: RELEASE
title: Migrate caddy to pairmode 0.3.0 (seed never delivered)
status: complete
phase: "106"
auth_gated: false
schema_introduces: false
story_class: docs
primary_files:
  - docs/stories/RELEASE/RELEASE-065.md
touches:
  - docs/stories/RELEASE/RELEASE-065.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

<!-- SPEC-WRITER NOTE (frontmatter): the stub arrived with no `primary_files:` key,
     `touches: []` and no `story_class:`. All three were populated here per the
     RELEASE-064 precedent (operator-directed): the single in-repo write target is
     *this file* — the `## Evidence` section appended by the executor. Every other
     write target is outside the repo, under `/mnt/work/caddy`, and therefore cannot
     appear in `touches:` at all; that is the point of phase 106 § Execution model. -->

## Context

Phase 106 drives the remaining pairmode 0.3.0 fleet migrations centrally from
flex, using the six-step mechanic in `docs/harness-cutover-runbook.md`
§ *Per-project mechanic* as the unit of work. RELEASE-063 was the campaign canary
(meander), RELEASE-064 was the first follow-on (lumin), and **RELEASE-065 is the
second follow-on — the first run against a playbook that has been exercised
twice**, with two rounds of findings in hand.

**Target repo: `/mnt/work/caddy`.**

**What "(seed never delivered)" in the title means, and why it changes step 4.**
Phase 106 § *Parent phase* records that Phase 97's RELEASE-043..057 fleet-migration
stubs were "deferred to per-project sessions that produced zero migrations."
For caddy specifically, that per-project seed prompt was never delivered at all —
so caddy has had *no* prior migration work of any kind, not even a partial or
abandoned attempt. The practical consequence is that **caddy's pre-state is not
known to this spec and must not be assumed.** Unlike lumin — whose
`binding: version / signal1 absent / signal2 0.2.0` baseline was already recorded
verbatim in RELEASE-063's E1 — caddy's binding, declared scripts path, recorded
`pairmode_version`, and even whether it was ever bootstrapped at all are open
questions that E1 answers empirically. `## Instructions` step 4 therefore branches
on what E1 finds rather than presuming a 0.2.x-consumer starting point, and E1's
recorded baseline is a **hard gate** on proceeding: no write to `/mnt/work/caddy`
happens before that output exists in `## Evidence`.

**The campaign gate is overridden, and this story carries the debt.**
RELEASE-064 completed the migration *mechanic* on lumin (E0–E4, E8–E14 pass) but
its proving cycle was **deferred by explicit operator decision** — recorded
verbatim in RELEASE-064 `## Evidence` § *E5 / E6 / E7*: *"Lumin isn't in a spot to
build, we'll just have to mark it complete and continue on. I'll have to prove it
out later."* RELEASE-064's E10 additionally established that meander has had **no
post-cp-110 build activity**, so there are no fresh canary rows either. The
combined position at the moment this story is specced is therefore:

> **No downstream proof exists — from any project — that the cp-110
> effort-recording remediation (CER-101/103/104) actually works in a consumer
> project.** The fix shipped and the channel carries it; nothing has yet observed
> it working outside flex.

RELEASE-064's own acceptance declared RELEASE-065..070 gated on exactly that
proof. **The operator has explicitly overridden that gate to proceed with this
story.** This spec does not re-litigate the override; it makes the debt visible
and assigns it a destination. Concretely:

- If caddy **can** run a proving cycle, then this story's E5/E6/E7 become the
  campaign's **first downstream proof** of the cp-110 remediation. That is the
  most valuable thing this story can produce — more valuable than the stamp — and
  `## Instructions` step 9 is written accordingly.
- If caddy **cannot** (no buildable work, operator unavailable for a native
  session, project not in a state to build), the deferral is recorded in the same
  shape RELEASE-064 used, the proof remains **outstanding**, and the story says so
  in its return. A second silent deferral that reads as a pass is the failure mode
  this paragraph exists to prevent.

**Two campaign findings from RELEASE-064 change what you assert here.** Both were
filed as CERs and both are *inputs*, not background:

- **CER-110 — fleet-wide plugin-sourced duplicate-hook signal.** Since cp-110's
  merged hook view (INFRA-288 `hook_view.py`), `fleet_discovery.py` reports
  `Projects with duplicate hooks: 16` — all 16 fleet projects, on a
  plugin-sourced, non-pairmode basis (`session-start.sh` ×2,
  `security_reminder_hook.py` ×6 on lumin), unprunable by `audit-hooks --apply`
  which by design never writes plugin files. **A `Projects with duplicate hooks: 0`
  assertion is unattainable until CER-110 is diagnosed.** E3 below is therefore
  specced as a *pairmode-scoped* single-block assertion plus an informational
  record of the fleet-wide number — not as the canary's `0` assertion.
- **CER-111 — `to-030` silently rewrites custom `expected_step_tokens`.** On the
  canary a custom value was kept with a WARN; on lumin `to-030` silently rewrote
  `53000 → 5000` with no keep/WARN path and no operator prompt. The mechanic here
  must therefore **read and record the pre-state value before running `to-030`**
  and record any rewrite, so the delta is observable rather than inferred.

**One packaging change since RELEASE-064.** Phase 111 (cp-111) de-namespaced the
four `skills/*/SKILL.md` names to bare names and changed `marketplace.json` to a
local-relative `source`. `sync-all` propagates SKILL.md content to the target, so
this migration is the first to carry that content downstream. E4 records the
observed post-sync state of those names in caddy rather than assuming it.

**The playbook notes are inputs, not background reading.** RELEASE-063 recorded
nine numbered notes; RELEASE-064's `## Evidence` § *Playbook notes (E12)* records
the delta against them plus two new findings. Of particular operational relevance:
notes 2 (wrong runbook command form), 3 (commit-before-proving reorder) and 5
(`state.json.lock` residue) **recurred on lumin** and their corrected forms are in
RELEASE-064's Evidence; note 7 (auto-mode classifier block) **did not recur**; and
note 9 (`settings.local.json` sediment) was **not applicable** to lumin, which has
no such file. Caddy may differ on all of these — "did not recur once" is not
"resolved." Where the runbook and this spec disagree on *command form* or on *when
the migration commit lands*, **this spec wins**: it carries two runs' worth of
corrections and the runbook has still not been amended (RELEASE-063 E11 filed the
amendments; phase 106 § Out of scope keeps runbook edits out of migration stories).

Two things about how this story runs are unusual and are settled by phase 106
§ *Execution model (cross-repo — deviation from the standard loop)*, which you
should read before acting:

1. **No sandboxed builder subagent, no flex worktree.** The write targets live at
   `/mnt/work/caddy`, outside this repo. The standard worktree loop and
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
would prove nothing about whether the cp-110/cp-111 changes reach consumers.

## Requires

- **The campaign-gate override is on the record.** RELEASE-064's acceptance
  gated RELEASE-065..070 on a completed downstream proving cycle; that gate has
  been explicitly overridden by the operator to run this story. Before starting,
  confirm the override with the operator and capture the confirmation for E0. If
  the operator is not present to confirm it, **stop** — this story is not
  eligible for unattended execution on an overridden gate.
- **cp-110 is tagged, phase 110 is complete, and its content is present in the
  release channel.** RELEASE-064 E0 evidenced
  `/mnt/work/flex-harness` HEAD == `cp-110` exactly. Re-verify rather than citing
  it: the channel has since taken cp-111.
- **cp-111 is tagged and its content is present in the channel.** Phase 111
  (plugin packaging repair: bare skill names, local-relative marketplace source)
  is complete and, per era 003 § Phases, sits after 110. `sync-all` propagates
  that content into caddy, so the channel state at migration time is part of what
  this migration delivers.
- **cp-105 is tagged and phase 105 is complete.** Phase 106 § Execution model:
  *"do not start this phase before cp-105."*
- **RELEASE-063 and RELEASE-064 are complete and both `## Evidence` sections are
  present**, including RELEASE-063 § *Playbook notes (E10)* / § *Follow-ups filed
  (E11)* and RELEASE-064 § *Playbook notes (E12)* / § *Follow-ups (E13)*. This
  story is specced against both; if either is missing, stop — you are not running
  the playbook the campaign produced.
- **No sibling phase-106 story beyond RELEASE-063/064 has been started.**
  RELEASE-066..071 must still be `draft` when this story begins.
- `/mnt/work/flex-harness` exists and is the release channel described in
  `docs/architecture.md` § *Release channel — flex-harness*.
- **caddy exists as a git repository and its working tree is clean** at the moment
  the mechanic begins. The path is *expected* to be `/mnt/work/caddy`; confirm it
  from `fleet_discovery.py`'s candidate scan rather than assuming, and if caddy is
  not found at that path, stop and get the path from the operator. Per canary
  playbook note 1, a dirty tree is a **stop** condition with no runbook step
  covering it: the operator decides (discard, commit, or abort) and the decision is
  recorded. Do not stash around it unilaterally.
- `docs/harness-cutover-runbook.md` contains a `## Per-project mechanic` section
  enumerating the six steps, and a `## Rollback procedure` section. That section,
  as corrected by this spec's `## Instructions`, is the step list; this spec states
  what must be *true afterwards*.
- The operator is present. Beyond the override confirmation, canary note 7's
  auto-mode permission classifier block on the first out-of-repo `sync-all
  --apply` may or may not recur (it did on meander, it did not on lumin), and the
  E9 prune decision and E5 proving-story selection are operator calls.
- Known flex-side environmental failure inside fresh worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story; does not appear when the suite is run from
  the main checkout.

## Ensures

Each assertion below is verified from recorded command output pasted into this
file's `## Evidence` section (see `## Instructions` step 11). "Recorded" means the
exact command and its exact output, not a paraphrase. An Ensure whose evidence is
missing from that section is a **fail**, regardless of whether the underlying
thing happened.

**E0. The preconditions — including the overridden gate — are evidenced, not
assumed.**
`## Evidence` records:
- (a) `git -C /mnt/work/flex tag --list 'cp-105*' 'cp-110*' 'cp-111*'` showing all
  three tags;
- (b) a check that `/mnt/work/flex-harness` carries cp-111 content — e.g.
  `git -C /mnt/work/flex-harness log --oneline -5` showing the phase-111 commits,
  or a `git rev-parse` comparison against flex's `cp-111` tag. A tag in flex is
  not evidence the channel was fast-forwarded (that is a distinct step — phase 102
  existed precisely for it). If the channel is behind, this is a **stop**;
  fast-forwarding it is not this story's work (see `## Out of scope`);
- (c) the operator's confirmation, quoted, that the RELEASE-064 campaign gate is
  overridden for this story, together with a one-line statement of the standing
  debt: *no downstream proof of the cp-110 recording remediation exists yet.*

**E1. A pre-migration baseline exists, and caddy's unknown pre-state is
characterized.**
`## Evidence` contains the verbatim output of a `fleet_discovery.py` run captured
**before any write to caddy**, showing caddy's pre-migration `binding`, `signal1`
(scripts path) and `signal2` (`pairmode_version`), plus the run's
`Projects with duplicate hooks:` line. `## Evidence` also records
`git -C <caddy> log --oneline -5` and `git -C <caddy> status --porcelain`, and
states in one line which starting shape caddy is in — bound-0.2.x, bound-other-
version, declared-but-unstamped, or never-bootstrapped — and therefore which
branch of `## Instructions` step 5 applies. Without this, "the migration changed
something" is unverifiable, and for caddy specifically there is no prior recorded
baseline anywhere in the campaign to fall back on.

**E2. caddy reports pairmode 0.3.0 and binds the release channel.**
A post-migration `fleet_discovery.py` run, recorded in `## Evidence` and using the
**same command form as E1** so the two are directly comparable, shows caddy with:
- `signal2 (pairmode_version): 0.3.0`
- `signal1 (scripts path): /mnt/work/flex-harness/skills/pairmode/scripts`
- `binding: both`

All three. `binding: version` post-migration is a fail: the stamp landed but the
channel declaration did not, and caddy would still be consuming an unknown copy of
the scripts.

**E3. caddy's *pairmode* hooks are a single block per event (CER-110-aware).**
This is the phase-106 § Checkpoint-proves `single-block hooks` condition, restated
to be attainable in the presence of CER-110. `## Evidence` records:
- (a) caddy's own hook state from its `.claude/settings.json`, showing **exactly
  one pairmode hook block and one command per event** for the pairmode events
  (`PreToolUse`, `UserPromptSubmit`, `SessionStart`, `PostToolUse`), each pointing
  at `/mnt/work/flex-harness/hooks/...`;
- (b) `pairmode_sync.py audit-hooks --project-dir <caddy>` (dry-run), showing that
  any remaining `DUPLICATE:` lines are **plugin-sourced and non-pairmode**, and
  that nothing pairmode-owned is prunable;
- (c) the fleet-wide `Projects with duplicate hooks: N` line from the E2 run,
  recorded **informationally** with an explicit note that per CER-110 this number
  is not expected to be `0` and is not a caddy migration defect.

`Projects with duplicate hooks: 0` is **not** asserted by this story. If (b)
shows a *pairmode-owned* duplicate, that is a real defect: record it under E12 and
treat it as a stop. Do not hand-edit caddy's settings to make any number come out
right — the point is to prove `pairmode_sync.py` produces this state on its own.

**E4. caddy's bootstrapped loop is the 0.3.0 thin-harness template, and the
cp-111 packaging content is recorded.**
`## Evidence` records:
- (a) the result of inspecting `<caddy>/CLAUDE.build.md` and confirms it is the
  thin dispatch-loop template, not the pre-flip 0.2.x prose loop. Use the same
  checks the previous two runs used so the three are comparable:
  `grep -c "flex_build.py next-action" <path>` (both prior runs printed `2`) plus a
  `head -5`;
- (b) the observed state of any `SKILL.md` content `sync-all` wrote into caddy —
  specifically whether the skill `name:` values are the **bare** cp-111 names
  rather than the old namespaced ones. If `sync-all` copies no SKILL.md into this
  target, record that fact instead. This is the first migration to carry cp-111
  content downstream; recording what actually landed is the assertion, and a
  surprise here is a finding for E12, not a reason to hand-edit caddy.

**E5. A proving story cycle completed inside caddy — or its absence is recorded
as an explicit, operator-owned deferral.**

*Preferred path (proof).* `## Evidence` names the caddy-side story ID built as the
proving cycle (mechanic step 6), states that it ran inside caddy's **own**
`CLAUDE.build.md` loop with caddy's own story numbering, states the full cycle it
traversed (spec-writer → builder → reviewer → merge), and states its outcome. The
story is a real, small, genuinely-wanted piece of caddy work — not a throwaway.
Per canary playbook note 8, the cycle runs in a **native caddy session** unless
cp-110/INFRA-289's target-project attribution (`resolve_recording_project`) is
being deliberately exercised from this session; `## Evidence` states explicitly
which session mode was used and why.

*Fallback path (deferral).* If caddy cannot run a proving cycle, `## Evidence`
records, in the same shape RELEASE-064 used: the operator's decision **quoted
verbatim**; the reason caddy could not build; and an explicit statement that
E5/E6/E7 are **unevidenced, therefore not passed**, that this story's migration is
a stamp without a proof, and that the cp-110 downstream proof remains outstanding
across the whole campaign (meander, lumin and caddy). A follow-up naming where the
proof will come from is filed under E13.

Silence is a fail. One of the two paths must be explicit in `## Evidence`.

**E6. The proving cycle's attempt rows landed in caddy's effort.db — correctly.**
Applies when E5 took the preferred path; when E5 took the fallback, E6 is recorded
as *not run* with the consequence stated (see E5 fallback) and is **not** claimed
as passed. This is the load-bearing check and it has three parts, all verified
from recorded queries against caddy's `effort.db` (locate it; do not assume the
path — meander's and lumin's were `.companion/effort.db`). Verify the live schema
before querying: RELEASE-064 E10 found the `attempts` table uses `agent_role`/`ts`,
**not** the `role`/`created_at` names RELEASE-063 recorded.

- **E6a — attribution (CER-103).** At least one attempt row exists for the E5
  story ID **in caddy's own db**, not flex's. `## Evidence` also records the
  complementary check that flex's `effort.db` contains **no** rows for the E5 story
  ID; the canary failed precisely by having the rows in the wrong database while
  every other signal looked healthy.
- **E6b — content (CER-101).** Those rows have a non-null, non-placeholder
  `outcome` and a non-zero token/cost field. NULL `tokens_total`/`outcome` is the
  pending-reconciliation pattern the canary hit and is a **fail**.
- **E6c — no duplicates (CER-104).** Each attempt appears **once**. Record a
  grouped count (e.g. `SELECT story_id, agent_role, COUNT(*) ... GROUP BY ...`)
  showing no perfect pairs with near-identical timestamps. RELEASE-064 E10
  incidentally confirmed the historical failure shape on meander (rows 281/282:
  same story, same role, 10 ms apart, pre-cp-110); a passing count here is the
  downstream proof CER-104 is closed.

If E5 took the preferred path, **all three passing is the campaign's first
downstream proof of the cp-110 remediation** — say so in `## Evidence` in those
words, because RELEASE-066..070 are specced against whether that proof exists.
Any of E6a/E6b/E6c failing is a stop condition (see `## Instructions` step 10).

**E7. caddy's checkpoint/report path sees the attempts.**
Applies on the same condition as E6. `## Evidence` records the output of the
pairmode checkpoint or attempt-report CLI run against caddy for the phase
containing the E5 story, showing the attempts (not "no attempts recorded"). The
canary's native re-test found rows present in the db yet the report printing *"no
attempts recorded"* — a raw-row query alone does not prove the read path works.
Record the exact command (discover it from `flex_build.py --help` / the checkpoint
sequence; do not guess a subcommand name) and its output.

**E8. caddy's git history shows the migration as its own commit(s).**
`## Evidence` records `git -C <caddy> log --oneline` covering the migration
commit(s) and, if E5 ran, the proving-story commit(s), so a later auditor can see
exactly what the sync wrote into caddy and roll it back if needed. Per canary
playbook note 3 — which recurred on lumin — the migration commit **precedes** the
proving cycle in history. Record the file/insertion/deletion counts for the
migration commit.

**E9. caddy's `settings.local.json` sediment is handled deliberately.**
Per canary playbook note 9 (meander carried 133 accumulated allow rules, 91 of them
stale `Write(path)`/per-file `Edit(path)` entries that flood the first
post-migration session with warnings; lumin had no such file at all), `## Evidence`
records: whether `<caddy>/.claude/settings.local.json` exists; if it does, the
pre-migration count of `Write(`/`Edit(` allow rules, the operator's decision (prune
or keep), and — if pruned — the post-prune count and the backup location. If the
file does not exist or carries no such rules, record that fact. "Not mentioned" is
a fail.

**E10. The campaign's outstanding downstream-proof debt is re-checked and
restated.**
RELEASE-064 E10 established that meander had no post-cp-110 rows and that lumin's
proving cycle was deferred, leaving zero downstream evidence. `## Evidence`
re-checks that position as of this run and records **one** of:

- **(a)** fresh post-cp-110 attempt rows now exist somewhere in the fleet
  (meander's next cycle, lumin's deferred cycle, or caddy's own E6) — record the
  query, its output, and which project supplied the proof; **or**
- **(b)** no fresh rows exist anywhere and the proof debt is **unchanged** — state
  that explicitly, list the projects checked, and carry the follow-up forward
  under E13 rather than letting it silently age out.

RELEASE-064 already determined that **meander does not need a re-sync** to pick up
cp-110 (the fixes live in channel scripts meander invokes by path). Do not re-derive
that; cite it. If cp-111's packaging change alters that determination — because
SKILL.md content *is* copied into consumer repos at sync time — state the revised
determination and its basis. Performing any re-sync is **not** this story's work
(see `## Out of scope`); naming it is.

**E11. Cleanliness — flex-side diff is this file only, and the channel is
untouched.**
```bash
git -C /mnt/work/flex diff --name-only
git -C /mnt/work/flex-harness status --porcelain
```
The first lists exactly `docs/stories/RELEASE/RELEASE-065.md` (plus the phase
doc's story row and index/ledger rows if the orchestrator's recording CLIs touch
them — those are tool-written, not hand-written). No file under `skills/`,
`tests/`, `ui/`, or `.claude-plugin/` is modified by this story. The second prints
**nothing**: the channel is read from, never written by a migration story.

**E12. Playbook findings are recorded as a delta against *both* prior runs.**
This file's `## Evidence` ends with a **Playbook notes** subsection that, for each
of RELEASE-063's nine numbered notes **and** RELEASE-064's two new findings
(new-1 → CER-110, new-2 → CER-111), states whether it **recurred**, **did not
recur**, or **was not applicable** on caddy — and then lists any *further* new
deviation, manual intervention, or ambiguity this run produced. A flat list that
does not reference the prior notes fails this Ensure. Two specific comparisons are
required because the two prior runs disagreed:

- **note 7** (auto-mode classifier block) — recurred on meander, did not recur on
  lumin. State which happened here; two runs disagreeing means one data point does
  not settle it.
- **note 6 / CER-111** (`expected_step_tokens`) — meander kept its custom value
  with a WARN; lumin's was silently rewritten `53000 → 5000`. `## Evidence` must
  record caddy's **pre-`to-030` value**, the **post-`to-030` value**, and whether a
  keep/WARN or a silent rewrite occurred. Reading the value only afterwards makes
  the delta unrecoverable, which is exactly the gap CER-111 was filed for.

If the mechanic ran exactly as written with no intervention, say exactly that.

**E13. Runbook or CER follow-ups are filed, not fixed here.**
Every defect surfaced under E12, plus the E10 proof-debt follow-up and any E5
deferral follow-up, is *named* in `## Evidence` as a follow-up with its intended
destination (runbook amendment or CER). This story does **not** edit
`docs/harness-cutover-runbook.md` or `docs/cer/backlog.md` (see `## Out of scope`).
RELEASE-063 E11 already filed the runbook amendments for canary notes 1/2/3/5/9,
and RELEASE-064's new findings are already filed as **CER-110** and **CER-111** —
if any of those recurred, reference the existing item rather than filing a
duplicate. New findings get new follow-ups.

**E14. flex's own suite is unaffected.**
`uv run pytest tests/pairmode/` is run once at the end, **without `-x`**, and is
green except the known CER-090 worktree-environmental failure
(`tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`) if
it appears. RELEASE-064's run from the main checkout was fully green
(4079 passed, 211 skipped). This story changes no flex code, so any *new* failure
means something ran that should not have.

## Instructions

You are executing this story **at orchestrator level with the operator present**,
not as a sandboxed builder subagent in a flex worktree. Do not create a story
worktree. Do not attempt to have a builder subagent write to `/mnt/work/caddy` —
`scope_guard.py` will block it, correctly, and working around the block is itself a
violation.

1. **Confirm the override, then prove the gate state (E0).** Ask the operator to
   confirm on the record that RELEASE-064's campaign gate is overridden for this
   story, and quote the confirmation. Then confirm cp-105, cp-110 and cp-111 are
   tagged in flex **and** that `/mnt/work/flex-harness` carries cp-111 content.
   The channel is a separate checkout and its fast-forward is a distinct step. If
   the channel is behind, stop and hand back to the operator: migrating against a
   stale channel proves nothing about what the fleet consumes.

2. **Confirm the remaining preconditions before touching anything.** Verify every
   bullet in `## Requires` and record the checks: RELEASE-063 and RELEASE-064
   complete with both `## Evidence` sections and their playbook-note subsections
   present; RELEASE-066..071 still `draft`; caddy located and its working tree
   clean. If any fails, stop and hand back to the operator.

3. **Read both prior runs' notes, then the mechanic.** Read RELEASE-063's
   `## Evidence` § *Playbook notes (E10)* / § *Follow-ups filed (E11)* and
   RELEASE-064's § *Playbook notes (E12)* / § *Follow-ups (E13)* first — they are
   the corrections, and RELEASE-064's § *Mechanic run* block records the exact
   `to-030` output shape to expect. Then read
   `docs/harness-cutover-runbook.md` § *Per-project mechanic* in full, and
   § *Rollback procedure* alongside it so you know the exit path before you start.
   The spec-writer is input-bound and did **not** read any of those files. Where
   the runbook and this spec disagree on *procedure*, apply the corrections (steps
   4 and 7 below) and record the discrepancy under E12; where they disagree on
   *what must be true afterwards*, this spec's `## Ensures` wins.

4. **Capture the baseline and classify caddy's starting shape (E1).** Run
   `fleet_discovery.py` from the release channel. Per canary playbook note 2 —
   which recurred on lumin — the runbook's step-5 command form is **wrong** (it
   names a nonexistent `discover` subcommand and a `--project-dir` flag). The form
   both prior runs actually used is:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
     --candidate-dir /mnt/work/caddy --no-snapshot
   ```
   Confirm against `--help` before running — cp-110 and cp-111 both landed since
   the canary — and do not guess flags. Save the full output; you will compare it
   against the post-migration run. Also capture `git -C <caddy> log --oneline -5`
   and `git -C <caddy> status --porcelain`.

   Then **state caddy's starting shape in one line** and pick the step-5 branch.
   Because caddy's seed was never delivered, do not assume lumin's shape.

5. **Branch on the baseline before running the mechanic.**
   - **Bound 0.2.x consumer** (`signal2: 0.2.x`, any `binding`) — the ordinary
     path; run the six-step mechanic as in RELEASE-064.
   - **Bound but version-absent, or bound to a non-0.2.x version** — the mechanic
     still applies, but the `to-030` step's assumptions about a 0.2.x starting
     state may not hold. Run `--dry-run` first, show the operator, and record any
     step whose output differs from RELEASE-064's recorded shape.
   - **Never bootstrapped** (no pairmode binding at all) — the migration is a
     *bootstrap to 0.3.0*, not a 0.2→0.3 migration. `to-030` may be inapplicable.
     Stop and confirm the intended path with the operator before writing anything;
     record the decision. Do not improvise a bootstrap sequence and do not let a
     bootstrap masquerade as a migration in the evidence.

6. **Run the mechanic against caddy.** Follow the runbook's six steps in order,
   invoking `pairmode_migrate.py` and `pairmode_sync.py` from
   `/mnt/work/flex-harness/skills/pairmode/scripts` — never from
   `/mnt/work/flex/skills/...`. Expect, from the prior two runs:
   - **note 7 (unsettled):** the auto-mode permission classifier blocked the first
     out-of-repo `sync-all --apply` on meander but not on lumin. If it blocks, ask
     the operator to toggle auto mode off so the normal permission prompt surfaces;
     do not attempt to route around the classifier.
   - **note 5 (recurred twice):** `sync-all --apply` may leave
     `.companion/state.json.lock` behind (INFRA-285 advisory-lock artifact). It is
     transient — remove it and do **not** commit it.
   - **note 4 (recurred twice):** the `to-030` agent-cleanup step prints "content
     differs from known 0.2.x template … manual porting required" for
     freshly-synced 0.3.0 agent files while admitting the 0.2.x template is "(not
     available)". On both prior runs this was noise requiring no action; confirm
     the same holds here before dismissing it.
   - **CER-111 — mandatory pre-read:** **before** running `to-030 --apply`, read
     and record caddy's current `expected_step_tokens` value from its state file.
     Then run `to-030` and record the value again. Report both to the operator
     along with whether a keep+WARN or a silent rewrite occurred. Do not let
     `to-030` change that value unobserved.

   Show the operator the output of each step before proceeding to the next. If a
   step fails, **stop** — do not improvise a fix into caddy. Report to the
   operator, and if the failure is unrecoverable, execute the runbook's rollback
   procedure and record what happened under E12.

7. **Commit the migration before the proving cycle (canary note 3, recurred on
   lumin).** The runbook orders the commit after step 6; that is wrong for the
   0.3.0 loop, because the proving story's worktree snapshots git HEAD and would
   not see the migration. Commit the sync/migration changes into caddy as their
   **own** commit first (both prior runs used
   `sync: migrate to pairmode 0.3.0 thin-harness loop`), then run the proving
   cycle. Record the discrepancy under E12 as a recurrence of note 3.

8. **Handle the `settings.local.json` sediment (E9, canary note 9).** Before
   handing caddy to a native session, check whether
   `<caddy>/.claude/settings.local.json` exists and count the stale
   `Write(`/`Edit(` allow rules. `sync-all` correctly does not touch that file, so
   any sediment survives migration and floods the first post-migration session with
   warnings. Present the count to the operator and let the operator decide
   prune-or-keep. If pruning: back the file up first, remove the stale
   `Write(path)` and per-file `Edit(path)` rules (obsolete under 0.3 story-scoped
   permissions), and record before/after counts and the backup path. This is an
   operator decision — do not prune unilaterally. If the file does not exist, record
   that (as lumin's did not).

9. **Verify the stamp before proving (E2, E3, E4).** Re-run the exact step-4
   `fleet_discovery.py` command and confirm caddy now reports `0.3.0`,
   `binding: both` with `signal1` pointing at the channel. Then run
   `audit-hooks --project-dir <caddy>` as a dry-run and inspect caddy's
   `.claude/settings.json` for the per-event pairmode hook blocks — **assert
   single-block pairmode hooks, not `Projects with duplicate hooks: 0`**; per
   CER-110 that number will be non-zero fleet-wide on a plugin-sourced,
   non-pairmode basis, and chasing it to zero here would mean editing files
   `audit-hooks` deliberately never writes. Then inspect
   `<caddy>/CLAUDE.build.md` for the thin-harness template and record the cp-111
   SKILL.md name state per E4(b). Do not proceed until E2/E3/E4 hold — a proving
   cycle run against a half-migrated project produces uninterpretable evidence.

10. **Run the proving story cycle (E5, E6, E7) — this is the most valuable output
    of this story.** This is mechanic step 6, and because RELEASE-064's cycle was
    deferred and meander has produced no post-cp-110 rows, **a passing E6 here is
    the campaign's first downstream proof that the cp-110 recording remediation
    works in a consumer project.** Treat it as the priority, not as a formality
    after the stamp.

    Per canary playbook note 8, attempt recording has been session-bound: a cycle
    driven from *this* flex session may attribute rows to flex's `effort.db`
    regardless of how correct everything else is. cp-110/INFRA-289 added
    target-project attribution (`resolve_recording_project`, allowlisted against
    registered projects) which *may* make flex-driven cycles attribute correctly —
    but that is unproven downstream, which is precisely what this story can settle.
    Default to a **native caddy session**, in caddy's own `CLAUDE.build.md` loop,
    with caddy's own story numbering; if the operator instead wants to exercise the
    INFRA-289 attribution path from this session, that is allowed provided
    `## Evidence` states which mode was used, because the mode changes what a pass
    proves. Do not create a flex story for the proving cycle. Pick a small, real,
    already-wanted piece of caddy work — a no-op story defeats the purpose.

    When it completes, run all three E6 checks (attribution, content, duplicates)
    plus the E7 report-path check. **Verify the live `attempts` schema first** —
    RELEASE-064 found `agent_role`/`ts` rather than `role`/`created_at`. Any of
    them failing is the CER-101/103/104 cluster reappearing after its own
    remediation: treat it as a stop condition, report it as such, and do not start
    RELEASE-066.

    If caddy genuinely cannot run a cycle, take E5's fallback path — record the
    operator's decision verbatim, state that E5/E6/E7 are unevidenced and therefore
    not passed, and state that the campaign's downstream proof is now outstanding
    across three consecutive projects. Do not round a second deferral up to a pass.

11. **Record the evidence (E0–E14).** Append a `## Evidence` section to *this
    file*, containing, in order: the E0 precondition and override proof; the E1
    baseline and starting-shape classification; a *Mechanic run* block including
    the CER-111 pre/post `expected_step_tokens` values; the E2/E3 post-migration
    discovery and `audit-hooks` output; the E4 template and cp-111 SKILL.md check;
    the E5 proving-story ID, session mode and outcome (or the quoted deferral); the
    E6a/E6b/E6c queries and output; the E7 report output; the E8 caddy git log; the
    E9 settings hygiene record; the E10 proof-debt re-check; the E11 cleanliness
    checks; the E14 suite output; a **Playbook notes** subsection per E12; and a
    **Follow-ups** subsection per E13. Paste command output verbatim inside fenced
    blocks — do not summarize it into prose, because RELEASE-066..070 are specced
    against what actually happened and a summary loses exactly the detail a later
    failure would need.

12. **Gate the rest of the campaign — and say plainly what is still unproven.** If
    any of E2, E3, E5, E6 or E7 failed or was deferred, say so explicitly in your
    return and state that RELEASE-066..070 are blocked pending an operator
    decision. If E6 passed, say explicitly that the campaign's first downstream
    proof of cp-110 now exists, name the project and story ID that supplied it, and
    state that RELEASE-066..070 are unblocked on that basis. Either way the return
    must contain one unambiguous sentence about the state of the downstream proof;
    the worst available outcome here is a third migration that reads as a success
    while the thing the campaign is trying to verify remains untested.

13. **Ideology note (Step 4a — resolved inline, no conflict).** Four things in
    `docs/ideology.md` shaped this spec. *"Never silently pass contradictions"* is
    the reason E0(c) forces the overridden campaign gate onto the record rather
    than letting the story proceed as if the gate had been satisfied — the
    constraint's override path is explicit acknowledgement plus a recorded reason,
    never silent bypass, and that is exactly the shape E0(c) and E5's fallback
    demand. It is also why E6 stays split into three separately-failing parts and
    why E12 requires the CER-111 pre-value to be read *before* `to-030` runs: a
    coarse after-the-fact check would have silently passed on lumin's rewrite.
    *"Rationale-bearing decisions over bare rules"* is why E3 was **restated**
    rather than dropped when CER-110 made the canary's `duplicate hooks: 0` rule
    unattainable — the rule's reason (prove the sync produces single-block pairmode
    hooks by itself) survives in a form that can still fail honestly, instead of an
    assertion that would have to be waived every run. *"Decision fidelity over
    convenience"* is why E1 makes caddy's unknown pre-state a hard gate with a
    branch instead of presuming lumin's shape. On accepted constraints: *"Hooks are
    thin relays only"* is adjacent, since the mechanic rewrites caddy's hook block
    — the rationale is that hooks must not block or write state, so E3 forbids
    hand-editing caddy's settings to satisfy an assertion and step 6 forbids routing
    around the permission classifier. *"Sidebar owns all state writes"* is why E6 is
    asserted against the db as written by the normal path, with no manual repair of
    rows permitted to make an assertion pass. No constraint is overridden by this
    spec and nothing required a decision on the ideology itself, so this resolves
    inline rather than flagging.

## Tests

There is no flex-side test file for this story and none is added: `story_class` is
`docs` (documentation/evidence), the story changes no flex code, and its subject is
the state of another repository. The checks below are the acceptance surface. Run
them from `/mnt/work/flex`.

```bash
# E0 — preconditions: tags in flex AND content in the channel
git -C /mnt/work/flex tag --list 'cp-105*' 'cp-110*' 'cp-111*'
git -C /mnt/work/flex-harness log --oneline -5
git -C /mnt/work/flex rev-parse cp-111 ; git -C /mnt/work/flex-harness rev-parse HEAD
```

```bash
# E1/E2/E3 — caddy baseline and post-migration state (confirm flags via --help first;
# the runbook's step-5 form is wrong per RELEASE-063 note 2, recurred on lumin)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
  --candidate-dir /mnt/work/caddy --no-snapshot
```

```bash
# E3 — pairmode-scoped hook assertion (CER-110: fleet-wide count will NOT be 0)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
  audit-hooks --project-dir /mnt/work/caddy
```

```bash
# E4 — thin-harness template, and cp-111 bare skill names as landed in the target
grep -c "flex_build.py next-action" /mnt/work/caddy/CLAUDE.build.md
head -5 /mnt/work/caddy/CLAUDE.build.md
grep -rn '^name:' /mnt/work/caddy/.claude/skills/*/SKILL.md 2>/dev/null || \
  echo "no SKILL.md copied into target — record this"
```

```bash
# CER-111 — expected_step_tokens, BEFORE and AFTER to-030
grep -n 'expected_step_tokens' /mnt/work/caddy/.companion/state.json
# ... run to-030 --apply ...
grep -n 'expected_step_tokens' /mnt/work/caddy/.companion/state.json
```

```bash
# E6 — proving-cycle attempt rows in caddy's own effort.db.
# Locate the db first; do not assume a path. Verify the schema before querying —
# RELEASE-064 found agent_role/ts, not role/created_at.
find /mnt/work/caddy -name 'effort.db' -not -path '*/node_modules/*'
sqlite3 <caddy-effort.db> ".schema attempts"

# E6a attribution: rows present in caddy, absent in flex
sqlite3 <caddy-effort.db> "SELECT * FROM attempts WHERE story_id='<E5-STORY-ID>'"
sqlite3 <flex-effort.db>  "SELECT * FROM attempts WHERE story_id='<E5-STORY-ID>'"  # must be empty

# E6b content: outcome and tokens populated (adjust column names to the live schema)
sqlite3 <caddy-effort.db> \
  "SELECT id, story_id, agent_role, model, tokens_total, outcome, ts
     FROM attempts WHERE story_id='<E5-STORY-ID>'"

# E6c duplicates: one row per attempt, no perfect pairs
sqlite3 <caddy-effort.db> \
  "SELECT story_id, agent_role, COUNT(*) FROM attempts
    WHERE story_id='<E5-STORY-ID>' GROUP BY story_id, agent_role"
```

```bash
# E7 — caddy's checkpoint/attempt report sees the rows (discover the exact
# subcommand from --help; it must not print "no attempts recorded")
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py --help
```

```bash
# E9 — settings.local.json sediment, before and after
ls /mnt/work/caddy/.claude/settings.local.json 2>/dev/null || echo "no settings.local.json"
grep -c 'Write(' /mnt/work/caddy/.claude/settings.local.json
grep -c 'Edit('  /mnt/work/caddy/.claude/settings.local.json
```

```bash
# E10 — proof-debt re-check: any post-cp-110 rows anywhere in the fleet?
# cp-110 promotion timestamp recorded in RELEASE-064 E10: 2026-07-28T15:57:54Z
sqlite3 /mnt/work/meander/.companion/effort.db \
  "SELECT id, story_id, agent_role, tokens_total, outcome, ts
     FROM attempts WHERE ts > '2026-07-28T15:57:54Z'"
```

```bash
# E8 — migration visible in caddy's history, migration commit before proving commit
git -C /mnt/work/caddy log --oneline -10

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
- E0(c) records the operator's campaign-gate override verbatim and states the
  standing downstream-proof debt;
- caddy shows `binding: both` and `0.3.0`, with single-block **pairmode** hooks per
  event; the fleet-wide `Projects with duplicate hooks: N` line is recorded
  informationally and is **not** required to be `0` (CER-110);
- the CER-111 pre-`to-030` and post-`to-030` `expected_step_tokens` values are both
  recorded, with the keep-or-rewrite behavior named;
- either (i) E5/E6/E7 pass — rows in caddy's own db, populated `outcome`/tokens,
  one row per attempt, and E7's report does not print "no attempts recorded" — and
  `## Evidence` states in those words that this is the campaign's first downstream
  proof of the cp-110 remediation; or (ii) E5's fallback path is recorded with the
  operator's decision quoted and an explicit statement that the proof remains
  outstanding;
- `git -C /mnt/work/flex-harness status --porcelain` prints nothing;
- the flex suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if it
  appears, state that it reproduces on clean `HEAD` and is unrelated;
- the return contains one unambiguous sentence on the state of the campaign's
  downstream proof, and declares RELEASE-066..070 blocked or unblocked accordingly.

Note for `spec-preflight`: this spec references a `## Evidence` section and its
**Playbook notes** / **Follow-ups** subsections, which do not exist in this file yet
— they are created by this story, and any preflight finding naming them is expected.
It also references `/mnt/work/caddy`, `/mnt/work/meander`,
`/mnt/work/flex-harness/skills/pairmode/scripts`, the `cp-105`/`cp-110`/`cp-111`
tags, CER-110/CER-111, and `docs/harness-cutover-runbook.md` § *Per-project
mechanic* / § *Rollback procedure*, none of which the input-bound spec-writer could
open; they are sourced from `docs/phases/phase-106.md` § *Execution model* /
§ *Paused (2026-07-28)*, from RELEASE-064's `## Evidence`, and from the campaign
context supplied with this story. All concrete paths inside caddy
(`.companion/state.json`, `.claude/settings.local.json`, `.claude/skills/*/SKILL.md`,
the `effort.db` location) are **expected** shapes taken from meander and lumin, not
verified for caddy — locate each before using it, and record what you actually find.
The `--candidate-dir` / `--no-snapshot` flags and the `audit-hooks` subcommand come
from the prior runs' recorded invocations; confirm via `--help`.

## Out of scope

- **Migrating any project other than caddy.** forqsite.help, halfhorse, pokus,
  base56 and cora are RELEASE-066..070. Do not run the mechanic against a second
  project "while the environment is warm" — the campaign is running on an
  overridden gate and wants each data point separable.
- **Re-syncing or re-migrating meander or lumin.** E10 requires *re-checking* the
  proof debt and recording the position. Performing a re-sync, or running lumin's
  deferred proving cycle, is separate work: mixing a remediation of an earlier
  project into this migration would make it impossible to tell which project's
  evidence proved what.
- **Fast-forwarding `/mnt/work/flex-harness` to cp-110/cp-111.** If E0 finds the
  channel behind, **stop**. Promoting the channel is a release action (phase 102's
  precedent), not something a migration story does mid-run.
- **Diagnosing or fixing CER-110 or CER-111.** Both are filed. This story is
  specced *around* CER-110 (E3's restated assertion) and *observes* CER-111 (the
  pre/post `expected_step_tokens` record). Neither is investigated or repaired here.
- **Amending the runbook.** If the mechanic is wrong, record it under E12 and name
  the follow-up under E13. RELEASE-063 E11 already filed amendments for the canary's
  notes 1/2/3/5/9; this story adds to that queue rather than draining it.
- **Filing or draining CERs.** Do not edit `docs/cer/backlog.md`. CER filing is the
  checkpoint's job; the backlog drain is phase 107.
- **Re-opening or amending RELEASE-063 or RELEASE-064.** Their verdicts stand as
  recorded, including RELEASE-064's deferred E5/E6/E7. This story's E10 adds *new*
  evidence in *this* file; it does not rewrite either predecessor's history.
- **The full-fleet DP8 gate and the phase-97 close.** Both are RELEASE-071 (phase
  106 § Ordering, strictly last). This story asserts nothing about the 16/16 fleet
  snapshot.
- **Building caddy's proving story to a flex-side spec.** The proving cycle is
  caddy's own work, in caddy's numbering, under caddy's loop. It gets no flex story
  ID and no row in `docs/phases/phase-106.md`.
- **Any change to flex's own code, tests, templates, or plugin manifest.** This
  story is evidence-producing. `schema_introduces: false` stands and no
  management-surface row is owed in `docs/phases/phase-106.md` § Schema delivery.
- **Automating the campaign.** No script is written to loop the mechanic over the
  fleet. If that is wanted, it is a new story informed by E12 — not a shortcut taken
  during the run that is supposed to evaluate the manual procedure.

## Evidence

Executed 2026-07-28 at orchestrator level with the operator present. Target:
`/mnt/work/caddy`. **Mixed result:** migration mechanic and stamp complete
(E1–E4, E8, E9); proving cycle ran natively (E5); **E6 split verdict — E6a and
E6c PASS (first downstream proof of the CER-103 attribution and CER-104 dedupe
fixes), E6b FAIL** (outcome unparseable → rows permanently pending) with the
root cause isolated to stale 0.2-era result-grammar examples in synced consumer
agent files. Campaign gate engaged per Instructions step 12.

### E0 — override + gate proof

Operator override, quoted from the recorded decision this session: asked
*"Proceed with the campaign now, or hold until a proving cycle lands?"* the
operator selected **"Override hold → RELEASE-065"** (after previously setting
the hold on closing RELEASE-064). At execution start no downstream proof of the
cp-110 remediation existed from any project.

```
$ git -C /mnt/work/flex tag --list 'cp-105' 'cp-110' 'cp-111'
cp-105
cp-110
cp-111
$ git -C /mnt/work/flex rev-parse cp-111 ; git -C /mnt/work/flex-harness rev-parse HEAD
0bab2ee3803cb00432660a917c5611699ef1ca7e
0bab2ee3803cb00432660a917c5611699ef1ca7e   ← channel HEAD == cp-111 exactly
```

RELEASE-063/064 Evidence + playbook-note subsections present; RELEASE-066..071
all `draft` at start.

### E1 — baseline, starting-shape classification, dirty-tree stop

**Dirty-tree stop condition (canary note 1) fired.** Caddy's tree carried a
half-started SELF-migration: committed `spec(phase-EH005-main)` scaffold plus
uncommitted edits to `docs/stories/PAIRMODE/PAIRMODE-001.md`, its permissions
file, `.companion/attempt_counter.json` (attempt 1), and state.json drift.
Operator decision, quoted: **"Discard residue, central migration"** — the three
modified files were checked out, the counter deleted; the committed EH005-main
scaffold left in history (later resolved by caddy's own session as
"PAIRMODE-001 complete — migration applied externally").

```
$ fleet_discovery.py --candidate-dir /mnt/work/caddy --no-snapshot   [channel scripts]
  /mnt/work/caddy
    binding: version
    signal1 (scripts path): absent — no-declaration
    signal2 (pairmode_version): 0.2.0
    DUPLICATE HOOKS: /mnt/work/caddy — events: SessionStart, PostToolUse
Projects with duplicate hooks: 16
```

**Starting shape: bound 0.2.x consumer** (branch 1 of Instructions step 5 — the
ordinary path; same shape as lumin). Pre-state git:

```
$ git -C /mnt/work/caddy log --oneline -3
c92c869 chore(era-001): record EH005-main in era phases table; sync context state
3cdeccf spec(phase-EH005-main): scaffold phase and story specs for pairmode 0.3.0 migration [spec-mode]
3f4f1cf chore(orchestrator): commit checkpoint tail-end bookkeeping (context state, attempt counter, CORRAL-002 status)
$ git -C /mnt/work/caddy status --porcelain   (after operator-approved discard)
(no output — clean)
```

### Mechanic run

- Dry-run reviewed by operator (1387 lines; 5 agent re-renders +
  `CLAUDE.build.md` thin-harness rewrite — lumin's shape exactly); approved.
- `sync-all --apply --yes`: exit 0. **Note 7 did not recur** (no classifier
  block; unsettled 1-of-3 across the campaign).
- **CER-111 watch:** `expected_step_tokens` pre-read **53416**; post-to-030
  **53416** — `[WARN] custom expected_step_tokens=53416 — value kept (not the
  Era 2 stamp).` **Kept with WARN**, matching meander; isolates lumin's silent
  `53000 → 5000` rewrite as value-dependent (53000 presumably matches a
  known-default heuristic). Three-way comparison recorded per E12.
- `to-030 --apply`: agent-cleanup flagged all five agent files "content differs
  from known 0.2.x template … manual porting required" — **note 4 recurred, and
  this run PROVES IT IS NOT NOISE** (see E6b root cause below).
- `state.json.lock` residue — note 5 recurred third-for-third; removed, not
  committed.
- Migration committed **before** the proving cycle (note 3 applied):
  caddy `909ef3b` — `sync: migrate to pairmode 0.3.0 thin-harness loop` —
  10 files, +246/−1077; pushed.

### E2 / E3 — post-migration discovery + hooks

```
  /mnt/work/caddy
    binding: both
    signal1 (scripts path): /mnt/work/flex-harness/skills/pairmode/scripts
    signal2 (pairmode_version): 0.3.0
    DUPLICATE HOOKS: /mnt/work/caddy — events: SessionStart, PostToolUse
Projects with duplicate hooks: 16
```

E3 (pairmode-scoped per CER-110): single pairmode block per event in
`.claude/settings.json` (PreToolUse / UserPromptSubmit / SessionStart /
PostToolUse, each 1 block → channel hooks). `audit-hooks` dry-run: remaining
duplicates are plugin-sourced, non-pairmode (`session-start.sh` ×2,
`security_reminder_hook.py` ×6 — identical to lumin/fleet, CER-110). Fleet-wide
count recorded informationally: 16.

### E4 — thin-harness template + cp-111 state

```
$ grep -c "flex_build.py next-action" /mnt/work/caddy/CLAUDE.build.md
2
# CLAUDE.build.md — caddy Build Orchestrator
```

E4(b): caddy's agent frontmatter names are bare (`builder`, `reviewer`, …);
caddy has no `skills/` dir, so cp-111's SKILL.md renames have no downstream
copy here — RELEASE-064's "meander needs no re-sync" determination unchanged
under cp-111.

### E5 — proving cycle (native)

Session mode: **native caddy session** (operator-run, caddy's own
`CLAUDE.build.md` loop and story numbering). Story: **PAIRMODE-002** — "prove
migrated 0.3.0 loop and confirm Signal-1" — real, wanted work (it also resolved
the interrupted self-migration story PAIRMODE-001 as applied-externally).
Full cycle traversed: next-action → create-story-worktree → builder → reviewer
(PASS) → merge (`d6c4d1b`) → three checkpoint gates → `cp-EH005-main` tagged
and pushed. Caddy-side friction the operator's session logged (their CER-C001..
C004): CER-guard false positive on the scaffolded Do-Now placeholder row,
state.json merge contention with live hooks, and manual status-flip
bookkeeping.

### E6 — the load-bearing check: split verdict

Live schema verified first: `attempts(id, story_id, phase, rail, agent_role,
model, …, tokens_total, …, outcome, notes, ts, …, agent_id, output_file)`.

**E6a — attribution (CER-103): PASS.**

```
caddy .companion/effort.db:
(33, 'PAIRMODE-002', 'builder',  'sonnet', None, None, '2026-07-28T20:47:04...', 'aa417ea6691144d57')
(34, 'PAIRMODE-002', 'reviewer', 'sonnet', None, None, '2026-07-28T20:49:31...', 'a93395ecf5cd63a09')
flex .companion/effort.db:
SELECT ... WHERE story_id='PAIRMODE-002'  → EMPTY (no rows — correct)
```

`effort_recording.log` shows `target_project: /mnt/work/caddy` on every row —
row 34 via `target_source: worktree-path` (the INFRA-289 precedence chain,
exercised and correct).

**E6c — no duplicates (CER-104): PASS.**

```
SELECT story_id, agent_role, COUNT(*) ... GROUP BY → ('PAIRMODE-002','builder',1), ('PAIRMODE-002','reviewer',1)
```

Log shows paired `recorded` + `recorded:deduped` decisions per spawn — the
double-fire arrived and was collapsed by the agent_id idempotency key.

**E6b — content (CER-101): FAIL.** Both rows hold `tokens_total NULL, outcome
NULL` and stay pending through both the in-session and explicit sweeps.
Diagnosis (traced through `pending_reconcilable` → `read_completed_spawn`):

```
read_completed_spawn(row 33) → {outcome: None, tokens_total: 7457, model: claude-sonnet-5}
read_completed_spawn(row 34) → {outcome: None, tokens_total: 9145, model: claude-sonnet-5}
```

Tokens and model parse; **outcome does not** — the sweep correctly refuses to
commit a partial row (CER-091 defect-2 branch). Root cause: caddy's workers
returned the **0.2-era plain-text grammar** (`BUILD-RESULT: DONE`,
`REVIEW-RESULT: PASS`) instead of the WORKER-004 JSON grammar
`parse_worker_outcome` reads. `sync-agents` merges frontmatter and appends new
sections but **preserves stale body content**: caddy's `builder.md:106` still
carries the literal `BUILD-RESULT: DONE` example alongside the newly-merged
JSON-schema reference, and the workers followed the old example. This is what
agent-cleanup's "manual porting required" WARN (canary note 4) has been
pointing at across all three runs while being adjudicated as noise.

Containment/terminator themselves are healthy: both output files are
symlinked, contained, `end_turn`-terminated — `is_reconcilable_spawn_output`
returns `terminated` (the INFRA-287 predicate working). The failure is
exclusively the outcome-grammar skew.

**Also verified during diagnosis:** the CER-097 ownership filter correctly
refused external reconciliation while the caddy session was live (its
`context_sessions` entry owned the spawn-output prefix) — a positive datapoint,
not a defect.

### E7 — report path

```
$ flex_build.py checkpoint-report --project-dir /mnt/work/caddy
=== checkpoint cost rollup — phase scoping unavailable ===
  reason: no active phase resolved
=== lifetime cost rollup (all phases) ===
  builder: 18 attempt(s), median 33,280 tokens
  reviewer: 13 attempt(s), median 35,931 tokens ...
```

The lifetime rollup sees caddy's attempts (no "no attempts recorded"); the
phase-scoped half cannot resolve because caddy's phase (EH005-main) was already
checkpointed complete before the check ran — a sequencing artifact of the
native cycle having finished its own checkpoint, recorded as-is. PAIRMODE-002's
rows are excluded from medians while pending (E6b), so E7 is **qualified**: read
path proven on historical rows, not on the proving rows.

### E8 — caddy git history

```
19debf1 chore(era-001): checkpoint EH005-main — mark phase complete in index and era ledger
32135f5 chore(orchestrator): backlog EH005-main checkpoint findings; record why PAIRMODE-001 pivoted external
f234915 chore(orchestrator): remove Do Now placeholder row — next_action CER guard reads '(none)' placeholder as an unresolved item
da3f95b chore(orchestrator): PAIRMODE-002 status update — story commit d6c4d1b merged
d6c4d1b story-PAIRMODE-002: prove migrated 0.3.0 loop and confirm Signal-1
649a8b3 chore(orchestrator): mark PAIRMODE-001 complete — 0.3.0 migration applied externally (commit 909ef3b)
909ef3b sync: migrate to pairmode 0.3.0 thin-harness loop
```

Migration commit precedes the proving commits (note 3 upheld).

### E9 — settings.local.json sediment

Pre-migration: **23 `Write(` + 25 `Edit(` = 48 stale rules** (61 allow rules
total). Operator decision, quoted: **"Prune (Recommended)"**. Backed up to
`/mnt/work/caddy/.claude/settings.local.json.bak-pre-030-prune`, 48 rules
removed, 13 retained; post-prune `Write(`/`Edit(` counts both 0.

### E10 — proof-debt re-check

Meander: still no post-cp-110 rows at execution time. **This story's E6a/E6c
are the campaign's first downstream proof** of the CER-103 attribution and
CER-104 dedupe fixes. CER-101's content half remains **unproven downstream** —
blocked by the E6b grammar skew, which prevents outcome reconciliation in any
consumer repo whose agent bodies predate the JSON grammar.

### E11 — cleanliness

flex diff before this Evidence append: empty. Channel check **caught a
violation**: `docs/fleet-snapshot.md` modified in `/mnt/work/flex-harness` —
caddy's native proving session ran `fleet_discovery.py` without
`--no-snapshot`, and the default snapshot path writes into the channel
checkout. Generated file reverted (`git checkout -- docs/fleet-snapshot.md`);
channel clean. Recorded as a new finding (E12 new-1).

### E14 — flex suite

```
4083 passed, 211 skipped, 14 warnings in 178.58s
```

Green, no failures (CER-090 did not appear; run from the main checkout).

### Playbook notes (E12 — delta against both prior runs)

1. Dirty tree: **recurred** (2-of-3), in a new form — a competing half-started
   self-migration, not session residue. Operator discarded; recorded above.
2. Runbook step-5 command form: **recurred** (3-of-3; runbook still unamended).
3. Commit-before-proving: **recurred / applied** (3-of-3) — `909ef3b` first.
4. Agent-cleanup WARN: **recurred (3-of-3) — RECLASSIFIED: not noise.** The
   warn flags stale 0.2-era body content in synced agent files; on caddy that
   stale content included the old result grammar that broke E6b. The campaign
   has been dismissing its own early warning twice.
5. `state.json.lock`: **recurred** (3-of-3); removed, not committed.
6. `expected_step_tokens`: caddy **kept 53416 with WARN** (meander-like);
   three-way comparison shows lumin's silent rewrite is value-dependent
   (CER-111 refined, not closed).
7. Auto-mode classifier block: **did not recur** (1-of-3 overall; unsettled).
8. Session-binding of recording: **superseded by INFRA-289 — proven.**
   Native-session run attributed correctly, including one row via
   `worktree-path` precedence; and the flex-side complement is empty.
9. Sediment: **recurred** (2-of-3; lumin n/a) — 48 rules pruned with backup.

New findings this run:

- **(new-1) Default snapshot write pollutes the channel checkout.**
  `fleet_discovery.py` run without `--no-snapshot` (by caddy's native session)
  wrote `docs/fleet-snapshot.md` into `/mnt/work/flex-harness`. Reverted.
  Needs a CER: snapshot default should target the *project*, or refuse to write
  into a checkout it only reads scripts from.
- **(new-2, root cause of E6b) `sync-agents` preserves stale 0.2-era agent-body
  content, including the plain-text result grammar.** Consumer workers then
  return `BUILD-RESULT: DONE` / `REVIEW-RESULT: PASS` (plain text), which
  `parse_worker_outcome` cannot read → rows permanently pending
  (`outcome NULL`) → CER-101's fix unprovable downstream. Every 0.2-era fleet
  project will hit this. Needs a CER + likely a Do-Now-grade fix before
  RELEASE-066: either template-sync replaces the return-format section, or the
  parser additionally accepts the legacy plain-text verdict line (with
  `DONE` mapped or rejected explicitly).
- **(new-3) caddy's own session filed CER-C001..C004 in caddy's backlog**
  (CER-guard placeholder false positive — upstream `_check_cer_do_now` bug
  every migrated repo will hit; state.json merge contention; manual
  status-flip bookkeeping; settings.json deny-list change left uncommitted for
  operator review). The `_check_cer_do_now` placeholder-row false positive is
  flex-upstream and needs a flex CER.

### Follow-ups (E13 — filed, not fixed here)

- **CER to file (Do Now candidate): E6b outcome-grammar skew** (new-2) — blocks
  the campaign's remaining E6 proof; decide fix side (template sync vs parser
  tolerance) before RELEASE-066.
- **CER to file: `_check_cer_do_now` reads the scaffolded `(none)` placeholder
  row as an unresolved Do-Now item** (new-3; caddy CER-C004) — blocks every
  migrated repo's first checkpoint until hand-edited.
- **CER to file: fleet_discovery default snapshot writes into the channel**
  (new-1).
- **CER-111 update**: three-way `expected_step_tokens` data recorded here;
  lumin's rewrite is value-dependent.
- **Meander post-cp-110 E6 re-verification**: still outstanding (now with the
  caveat that meander's agent bodies predate the JSON grammar too — its next
  cycle will likely reproduce E6b until new-2 is fixed).
- Runbook amendments for notes 2/3/5: already filed by RELEASE-063 E11;
  note 4's entry should be **amended** from "noise" to "warning is accurate;
  port stale bodies" when the runbook is next edited.

**Campaign gate statement (Instructions step 12):** The campaign's first
downstream proof of cp-110 now exists **for attribution (CER-103) and dedupe
(CER-104)** — supplied by caddy story PAIRMODE-002. **CER-101's content half
FAILED downstream (E6b)** due to the sync-agents grammar-skew defect (new-2).
**RELEASE-066..070 are BLOCKED pending an operator decision** on fixing new-2
(and ideally new-3's checkpoint-guard false positive) first.

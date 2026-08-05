---
id: RELEASE-064
rail: RELEASE
title: Migrate Repo-J to pairmode 0.3.0
status: complete
phase: "106"
auth_gated: false
schema_introduces: false
story_class: docs
primary_files:
  - docs/stories/RELEASE/RELEASE-064.md
touches:
  - docs/stories/RELEASE/RELEASE-064.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

<!-- SPEC-WRITER NOTE (Step 5): the frontmatter arrived with no `primary_files:`
     key and `touches: []`. The spec-writer input contract forbids editing
     frontmatter, so both were preserved as-is and this story is returned
     `status: "revised"` for the operator to populate. The only file inside this
     repository that this story writes is *this file* (the `## Evidence` section
     added by the executor). Every other write target is outside the repo, under
     `/mnt/work/Repo-J`, and therefore cannot appear in `touches:` at all — which
     is the point of the phase's § Execution model deviation. Suggested value for
     both keys:
       - docs/stories/RELEASE/RELEASE-064.md
     Populate them before dispatching, and see `## Instructions` step 0. -->

## Context

Phase 106 drives the remaining pairmode 0.3.0 fleet migrations centrally from
flex, using the six-step mechanic in `docs/harness-cutover-runbook.md`
§ *Per-project mechanic* as the unit of work. RELEASE-063 was the campaign
canary (Repo-B) and RELEASE-064 is the **first follow-on** — the first migration
run against a playbook that has already been exercised once, with the canary's
findings in hand.

**Target repo: `/mnt/work/Repo-J`.** Its pre-canary state, recorded verbatim in
RELEASE-063's `## Evidence` § E1 baseline, is:

```
  /mnt/work/Repo-J
    binding: version
    signal1 (scripts path): absent — no-declaration
    signal2 (pairmode_version): 0.2.0
```

So Repo-J is a plain 0.2.x consumer with no release-channel declaration: the
migration must both stamp `0.3.0` **and** bind signal1 to
`/mnt/work/flex-harness/skills/pairmode/scripts`. `binding: both` is the
post-condition, not `binding: version`.

**Why this story was blocked, and why it is unblocked now.** RELEASE-063 passed
E1–E5 and E7–E12 but **failed E6**: the proving cycle's attempt rows did not land
in Repo-B's `effort.db` with usable content. The canary's Instructions step 8
made that a campaign gate, and phase 106 § *Paused (2026-07-28)* records
RELEASE-064..071 as blocked pending the effort-recording cluster
CER-101/102/103/104. Those were root-caused and remediated in Phase 110
(*effort-recording data-flow remediation*), checkpointed as `cp-110` and promoted
to the `/mnt/work/flex-harness` release channel. The gate is cleared — but "the
fix shipped" and "the fix works downstream" are different claims, and this story
is where the second one gets tested. That is why the E-check sequence below adds
two checks the canary did not have: a **duplicate-row** assertion (E6c, CER-104)
and a **canary re-verification** (E10, Repo-B's E6 re-run against the
post-cp-110 channel). A migration that stamps 0.3.0 while recording is still
broken is a *failed* migration even though `pairmode_status.py` would report
success — the same trap the canary fell into.

**The canary's playbook notes are inputs to this story, not background reading.**
RELEASE-063 § *Playbook notes (E10)* records nine findings; six of them change
what you do here rather than merely what you expect. They are folded into
`## Requires` and `## Instructions` below, and the runbook amendments they imply
have **not** been made yet (RELEASE-063 E11 filed them as follow-ups and phase
106 § Out of scope keeps runbook edits out of migration stories). So where the
runbook and this spec disagree on the *command form* for `fleet_discovery.py`, or
on *when* the migration commit lands relative to the proving cycle, **this spec
wins** — it carries the canary's corrections and the runbook does not yet.

Two things about how this story runs are unusual and are settled by phase 106
§ *Execution model (cross-repo — deviation from the standard loop)*, which you
should read before acting:

1. **No sandboxed builder subagent, no flex worktree.** The write targets live at
   `/mnt/work/Repo-J`, outside this repo. The standard worktree loop and
   `scope_guard.py` forbid writes there — correctly. Execution is
   orchestrator-level with the operator present.
2. **Acceptance is evidence-shaped, not diff-shaped.** The flex-side diff is one
   `## Evidence` section appended to this file. The reviewer verifies recorded
   command output, not a code change.

The pairmode CLIs are invoked from the **permanent release channel**,
`/mnt/work/flex-harness/skills/pairmode/scripts` — canonized in
`docs/architecture.md` § *Release channel — flex-harness* and by RELEASE-062
(phase 105). Do not invoke them from `/mnt/work/flex/skills/...`: the channel is
what the fleet consumes, and — after cp-110 in particular — migrating a project
with a different copy of the scripts than the fleet uses would prove nothing
about whether the recording fix reaches consumers.

## Requires

- **cp-110 is tagged, phase 110 is complete, and its output is present in the
  release channel.** This is the specific precondition that distinguishes this
  story from its blocked predecessor. Phase 106 § *Paused (2026-07-28)* states
  RELEASE-064..071 resume "after cp-110". Verify the tag exists **and** that
  `/mnt/work/flex-harness` actually contains the remediated scripts (the channel
  is a separate checkout; a tag in flex is not evidence the channel was
  fast-forwarded — see phase 102, which existed precisely because that
  fast-forward is a distinct step).
- **cp-105 is tagged and phase 105 is complete.** Phase 106 § Execution model:
  *"do not start this phase before cp-105."* Phase 105 delivered the CER-080/087
  scope-guard and CER-040/041 hook fixes that remove the known false-blocks.
- **RELEASE-063 is complete and its `## Evidence` section is present**, including
  its *Playbook notes (E10)* subsection. This story is specced against those
  notes; if the section is missing, stop — you are not running the playbook the
  canary produced.
- **No sibling phase-106 story beyond RELEASE-063 has been started.** Phase 106
  § Ordering places RELEASE-064..067 in any order *after the canary passes*;
  RELEASE-065..071 must still be `draft` when this story begins.
- `/mnt/work/flex-harness` exists and is the release channel described in
  `docs/architecture.md` § *Release channel — flex-harness*.
- `/mnt/work/Repo-J` exists, is a git repository, and its working tree is **clean**
  at the moment the mechanic begins. Per canary playbook note 1, a dirty tree is a
  **stop** condition with no runbook step covering it: the operator decides
  (discard, commit, or abort) and the decision is recorded. Do not stash around it
  unilaterally.
- `docs/harness-cutover-runbook.md` contains a `## Per-project mechanic` section
  enumerating the six steps, and a `## Rollback procedure` section. That section,
  as corrected by this spec's `## Instructions`, is the step list; this spec
  states what must be *true afterwards*.
- The operator is present. This story is not eligible for unattended execution —
  canary playbook note 7 (auto-mode permission classifier blocks the first
  out-of-repo `sync-all --apply`) guarantees at least one interactive decision.
- Known flex-side environmental failure inside fresh worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story.

## Ensures

Each assertion below is verified from recorded command output pasted into this
file's `## Evidence` section (see `## Instructions` step 8). "Recorded" means the
exact command and its exact output, not a paraphrase. An Ensure whose evidence is
missing from that section is a **fail**, regardless of whether the underlying
thing happened.

**E0. The cp-110 precondition is evidenced, not assumed.**
`## Evidence` records (a) `git -C /mnt/work/flex tag --list 'cp-110*'` showing the
tag, and (b) a check that `/mnt/work/flex-harness` carries the cp-110 content —
e.g. `git -C /mnt/work/flex-harness log --oneline -5` showing the phase-110
commits, or a diff/`git rev-parse` comparison against flex's cp-110 tag. If the
channel has not been fast-forwarded, this is a **stop**: fast-forwarding the
channel is not this story's work (see `## Out of scope`).

**E1. A pre-migration baseline exists.**
`## Evidence` contains the verbatim output of a `fleet_discovery.py` run captured
**before** any write to `/mnt/work/Repo-J`, showing Repo-J's pre-migration
`binding`, `signal1` (scripts path) and `signal2` (`pairmode_version`), plus the
run's `Projects with duplicate hooks:` line. Without this, "the migration changed
something" is unverifiable. `## Evidence` also records
`git -C /mnt/work/Repo-J log --oneline -5` and
`git -C /mnt/work/Repo-J status --porcelain` for the pre-state.

**E2. Repo-J reports pairmode 0.3.0 and binds the release channel.**
A post-migration `fleet_discovery.py` run, recorded in `## Evidence` and using the
**same command form as E1** so the two are directly comparable, shows Repo-J with:
- `signal2 (pairmode_version): 0.3.0`
- `signal1 (scripts path): /mnt/work/flex-harness/skills/pairmode/scripts`
- `binding: both`

All three. `binding: version` post-migration is a fail: it means the stamp landed
but the channel declaration did not, and Repo-J would still be consuming an
unknown copy of the scripts.

**E3. Repo-J's hooks are a single block.**
The same post-migration discovery output reports Repo-J with a single pairmode
hook block — the `single-block hooks` condition named in phase 106 § Checkpoint
proves — and `Projects with duplicate hooks: 0`. Do not hand-edit Repo-J's
settings to make the number come out right: the point is to prove
`pairmode_sync.py` produces this state on its own. If it does not, that is a real
defect and it gets recorded under E12.

**E4. Repo-J's bootstrapped loop is the 0.3.0 thin-harness template.**
`## Evidence` records the result of inspecting `/mnt/work/Repo-J/CLAUDE.build.md`
and confirms it is the thin dispatch-loop template, not the pre-flip 0.2.x prose
loop. Record the command and its output; the canary used
`grep -c "flex_build.py next-action" <path>` (printed `2`) plus a `head -5`, and
using the same checks makes the two runs comparable.

**E5. A proving story cycle completed inside Repo-J.**
`## Evidence` names the Repo-J-side story ID that was built as the proving cycle
(mechanic step 6), states that it ran inside Repo-J's **own** `CLAUDE.build.md`
loop with Repo-J's own story numbering, states the full cycle it traversed
(spec-writer → builder → reviewer → merge), and states its outcome. The story is
a real, small, genuinely-wanted piece of Repo-J work — not a throwaway. Per canary
playbook note 8, the cycle runs in a **native Repo-J session**, not driven from
this flex session; `## Evidence` states explicitly which session mode was used.

**E6. The proving cycle's attempt rows landed in Repo-J's effort.db — correctly.**
This is the load-bearing check and it has three parts, all verified from a
recorded query against `/mnt/work/Repo-J`'s `effort.db` (locate it; do not assume
the path — the canary's was `.companion/effort.db`):

- **E6a — attribution (CER-103).** At least one attempt row exists for the E5
  story ID **in Repo-J's own db**, not flex's. `## Evidence` also records the
  complementary check that flex's `effort.db` contains **no** rows for the E5
  story ID; the canary failed precisely by having the rows in the wrong database
  while every other signal looked healthy.
- **E6b — content (CER-101).** Those rows have a non-null, non-placeholder
  `outcome` and a non-zero token/cost field. NULL `tokens_total`/`outcome` is the
  pending-reconciliation pattern the canary hit and is a **fail**.
- **E6c — no duplicates (CER-104).** Each attempt appears **once**. Record a
  grouped count (e.g. `SELECT story_id, role, COUNT(*) ... GROUP BY ...`) showing
  no perfect pairs with near-identical timestamps. The canary's native re-test
  found every attempt double-inserted; a passing count here is the downstream
  proof CER-104 is closed.

Record the exact queries and their exact output. Any of E6a/E6b/E6c failing is a
stop condition (see `## Instructions` step 9).

**E7. Repo-J's checkpoint/report path sees the attempts.**
`## Evidence` records the output of the pairmode checkpoint or attempt-report CLI
run against `/mnt/work/Repo-J` for the phase containing the E5 story, showing the
attempts (not "no attempts recorded"). The canary's native re-test found rows
present in the db yet the report printing *"no attempts recorded"* — so a raw-row
query alone does not prove the read path works. Record the exact command
(discover it from `flex_build.py --help` / the checkpoint sequence; do not guess
a subcommand name) and its output.

**E8. Repo-J's git history shows the migration as its own commit(s).**
`## Evidence` records `git -C /mnt/work/Repo-J log --oneline` covering the
migration commit(s) and the proving-story commit(s), so a later auditor can see
exactly what the sync wrote into Repo-J and roll it back if needed. Per canary
playbook note 3, the migration commit precedes the proving cycle in history.

**E9. Repo-J's `settings.local.json` sediment is handled deliberately.**
Per canary playbook note 9 (Repo-B carried 133 accumulated allow rules, 91 of
them stale `Write(path)`/per-file `Edit(path)` entries that flood the first
post-migration session with warnings), `## Evidence` records: the pre-migration
count of `Write(`/`Edit(` allow rules in `/mnt/work/Repo-J`'s
`.claude/settings.local.json`; the operator's decision (prune or keep); and, if
pruned, the post-prune count and the backup location. If Repo-J has no such file
or no such rules, record that fact. "Not mentioned" is a fail — this is the
findings-become-procedure step and skipping it silently is what the canary's
notes exist to prevent.

**E10. The canary's E6 is re-verified against the post-cp-110 channel.**
RELEASE-063's E6 verdict stands as FAIL on pre-cp-110 evidence; cp-110 does not
retroactively repair Repo-B's historical NULL/duplicate rows, so re-reading the
old rows proves nothing. `## Evidence` therefore records **one** of:

- **(a) preferred —** a query against `/mnt/work/Repo-B`'s `effort.db` filtered
  to attempt rows created **after** the cp-110 channel promotion, showing correct
  attribution, populated `outcome`/tokens, and no duplicate pairs — i.e. the
  E6a/E6b/E6c checks re-run on fresh Repo-B rows; **or**
- **(b) fallback —** an explicit statement that Repo-B has had no post-cp-110
  build activity, that no fresh rows exist to query, and that Repo-J's own E6 is
  therefore the sole downstream evidence for the CER-101/103/104 fixes — together
  with a named follow-up under E13 to re-verify Repo-B on its next cycle.

`## Evidence` also records the determination of **whether Repo-B needs a re-sync**
to pick up cp-110 (i.e. whether the fix lives in channel scripts Repo-B already
invokes by path, or in hook/template content that was copied into Repo-B at
migration time and is now stale). State the determination and the basis for it.
Performing that re-sync is **not** this story's work (see `## Out of scope`);
naming it is.

**E11. Cleanliness — flex-side diff is this file only, and the channel is
untouched.**
```bash
git -C /mnt/work/flex diff --name-only
git -C /mnt/work/flex-harness status --porcelain
```
The first lists exactly `docs/stories/RELEASE/RELEASE-064.md` (plus the phase
doc's story row and index/ledger rows if the orchestrator's recording CLIs touch
them — those are tool-written, not hand-written). No file under `skills/`,
`tests/`, `ui/`, or `.claude-plugin/` is modified by this story. The second prints
**nothing**: the channel is read from, never written by a migration story.

**E12. Playbook findings are recorded as a delta against the canary's.**
This file's `## Evidence` section ends with a **Playbook notes** subsection that,
for each of RELEASE-063's nine numbered notes, states whether it **recurred**,
**did not recur**, or **was not applicable** on Repo-J — and then lists any *new*
deviation, manual intervention, or ambiguity this run produced. A flat list that
does not reference the canary's notes fails this Ensure: the campaign's value is
in learning whether the canary's findings generalize, and RELEASE-065..070 are
specced against that answer. If the mechanic ran exactly as written with no
intervention, say exactly that.

**E13. Runbook or CER follow-ups are filed, not fixed here.**
Every defect surfaced under E12, plus any E10(b) Repo-B re-verification
follow-up, is *named* in `## Evidence` as a follow-up with its intended
destination (runbook amendment or CER). This story does **not** edit
`docs/harness-cutover-runbook.md` or `docs/cer/backlog.md` (see `## Out of
scope`). Note that RELEASE-063 E11 already filed the runbook amendments for
canary notes 1/2/3/5/9 — if those recurred, reference the existing follow-up
rather than filing a duplicate.

**E14. flex's own suite is unaffected.**
`uv run pytest tests/pairmode/` is run once at the end, **without `-x`**, and is
green except the known CER-090 worktree-environmental failure
(`tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`)
if it appears. This story changes no flex code, so any *new* failure means
something ran that should not have.

## Instructions

You are executing this story **at orchestrator level with the operator present**,
not as a sandboxed builder subagent in a flex worktree. Do not create a story
worktree. Do not attempt to have a builder subagent write to `/mnt/work/Repo-J` —
`scope_guard.py` will block it, correctly, and working around the block is itself
a violation.

0. **Populate the frontmatter gap.** `primary_files:` is absent and `touches:` is
   `[]` (see the spec-writer note at the top of this file). Set both to
   `docs/stories/RELEASE/RELEASE-064.md` — the single in-repo write target. The
   out-of-repo targets under `/mnt/work/Repo-J` are deliberately *not* listed;
   `touches:` is a within-repo declaration and listing external paths there would
   misrepresent the diff surface to every gate that reads it.

1. **Prove the gate is actually clear (E0).** Before anything else, confirm cp-110
   is tagged in flex **and** that its content is present in
   `/mnt/work/flex-harness`. The channel is a separate checkout and its
   fast-forward is a distinct step (that is what phase 102 was). If the channel is
   behind, stop and hand back to the operator — running this migration against a
   pre-cp-110 channel would reproduce the canary's failure and waste the second
   data point.

2. **Confirm the remaining preconditions before touching anything.** Verify every
   bullet in `## Requires` and record the checks: cp-105 tagged; RELEASE-063
   complete with its `## Evidence` and *Playbook notes* present; no sibling
   phase-106 story beyond the canary started; Repo-J's working tree clean. If any
   fails, stop and hand back to the operator.

3. **Read the canary's notes, then the mechanic.** Read RELEASE-063's
   `## Evidence` § *Playbook notes (E10)* and § *Follow-ups filed (E11)* first —
   they are the corrections. Then read `docs/harness-cutover-runbook.md`
   § *Per-project mechanic* in full, and § *Rollback procedure* alongside it so
   you know the exit path before you start. The spec-writer is input-bound and did
   **not** read either file. Where the runbook and this spec disagree on
   *procedure*, apply the canary's correction (steps 4 and 6 below) and record the
   discrepancy under E12; where they disagree on *what must be true afterwards*,
   this spec's `## Ensures` wins.

4. **Capture the baseline (E1).** Run `fleet_discovery.py` from the release
   channel. Per canary playbook note 2 the runbook's step-5 command form is
   **wrong** (it names a nonexistent `discover` subcommand and a `--project-dir`
   flag); the form the canary actually used is:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
     --candidate-dir /mnt/work/Repo-J --no-snapshot
   ```
   Confirm against `--help` before running — cp-110 or phase 105 may have changed
   the surface — and do not guess flags. Save the full output; you will compare it
   against the post-migration run. Also capture
   `git -C /mnt/work/Repo-J log --oneline -5` and
   `git -C /mnt/work/Repo-J status --porcelain`.

5. **Run the mechanic against Repo-J.** Follow the runbook's six steps in order,
   invoking `pairmode_migrate.py` and `pairmode_sync.py` from
   `/mnt/work/flex-harness/skills/pairmode/scripts` — never from
   `/mnt/work/flex/skills/...`. Expect, from the canary:
   - **note 7:** the auto-mode permission classifier will likely block the first
     out-of-repo `sync-all --apply`. Ask the operator to toggle auto mode off so
     the normal permission prompt surfaces; do not attempt to route around the
     classifier.
   - **note 5:** `sync-all --apply` may leave `.companion/state.json.lock` behind
     (INFRA-285 advisory-lock artifact). It is transient — remove it and do **not**
     commit it.
   - **note 4:** the `to-030` agent-cleanup step may print "content differs from
     known 0.2.x template … manual porting required" for freshly-synced 0.3.0
     agent files while admitting the 0.2.x template is "(not available)". On the
     canary this was noise requiring no action; confirm the same holds here before
     dismissing it.
   - **note 6:** a custom `expected_step_tokens` may be kept with a WARN. Record
     the value and leave it unless the operator says otherwise.

   Show the operator the output of each step before proceeding to the next. If a
   step fails, **stop** — do not improvise a fix into Repo-J. Report to the
   operator, and if the failure is unrecoverable, execute the runbook's rollback
   procedure and record what happened under E12.

6. **Commit the migration before the proving cycle (canary note 3).** The runbook
   orders the commit after step 6; that is wrong for the 0.3.0 loop, because the
   proving story's worktree snapshots git HEAD and would not see the migration.
   Commit the sync/migration changes into Repo-J as their **own** commit first
   (the canary used `sync: migrate to pairmode 0.3.0 thin-harness loop`), then run
   the proving cycle. Record the discrepancy under E12 as a recurrence of note 3.

7. **Handle the `settings.local.json` sediment (E9, canary note 9).** Before
   handing Repo-J to a native session, count the stale `Write(`/`Edit(` allow rules
   in `/mnt/work/Repo-J/.claude/settings.local.json`. `sync-all` correctly does not
   touch that file, so the sediment survives migration and floods the first
   post-migration session with warnings. Present the count to the operator and let
   the operator decide prune-or-keep. If pruning: back the file up first, remove
   the stale `Write(path)` and per-file `Edit(path)` rules (obsolete under 0.3
   story-scoped permissions), and record before/after counts and the backup path.
   This is an operator decision — do not prune unilaterally.

8. **Verify the stamp before proving (E2, E3, E4).** Re-run the exact step-4
   `fleet_discovery.py` command and confirm Repo-J now reports `0.3.0`, `binding:
   both` with `signal1` pointing at the channel, and single-block hooks. Then
   inspect `/mnt/work/Repo-J/CLAUDE.build.md` and confirm the thin-harness
   template. Do not proceed until all of E2/E3/E4 hold — a proving cycle run
   against a half-migrated project produces uninterpretable evidence.

9. **Run the proving story cycle in a native Repo-J session (E5, E6, E7).** This is
   mechanic step 6. Per canary playbook note 8, attempt recording is
   session-bound: a cycle driven from *this* flex session may attribute rows to
   flex's `effort.db` regardless of how correct everything else is. Unless cp-110
   demonstrably changed that (E0's inspection will tell you), the operator runs
   the proving cycle **natively in Repo-J**, in Repo-J's own `CLAUDE.build.md` loop,
   with Repo-J's own story numbering. Do not create a flex story for it. Pick a
   small, real, already-wanted piece of Repo-J work — the point is to exercise the
   full loop (gate → spec → builder → reviewer → record → merge) on genuine work,
   so a no-op story defeats it.

   When it completes, run all three E6 checks (attribution, content, duplicates)
   plus the E7 report-path check. **Any of them failing is the CER-101/103/104
   cluster reappearing after its own remediation** — treat it as a stop condition,
   report it as such, and do not start RELEASE-065.

10. **Record the evidence (E0–E13).** Append a `## Evidence` section to *this
    file*, containing, in order: the E0 gate proof; the E1 baseline; the E2/E3
    post-migration discovery output; the E4 template check; the E5 proving-story
    ID, session mode and outcome; the E6a/E6b/E6c queries and their output; the E7
    report output; the E8 Repo-J git log; the E9 settings hygiene record; the E10
    canary re-verification; the E11 cleanliness checks; a **Playbook notes**
    subsection per E12; and a **Follow-ups** subsection per E13. Paste command
    output verbatim inside fenced blocks — do not summarize it into prose, because
    RELEASE-065..070 are specced against what actually happened, and a summary
    loses exactly the detail a later failure would need.

11. **Gate the rest of the campaign.** If any of E2, E3, E5, E6 or E7 failed, say
    so explicitly in your return and state that RELEASE-065..070 are blocked
    pending an operator decision. The canary established that a partial pass is
    treated as a gate, not a speed bump; silently proceeding to the next project
    after a partial run is the single worst outcome available here.

12. **Ideology note (Step 4a — resolved inline, no conflict).** Three things in
    `docs/ideology.md` shaped this spec. *"Never silently pass contradictions"* is
    why E0 demands proof that the channel — not just flex — carries cp-110, and
    why E6 is split into three separately-failing parts: the canary's failure mode
    was a migration that reported success while its recording was broken, which is
    exactly the false confidence the constraint exists to prevent, and a single
    coarse "rows exist?" check would have passed on the canary's own double-inserted
    NULL-outcome rows. *"Rationale-bearing decisions over bare rules"* is why E12
    requires a **delta** against the canary's nine notes rather than a fresh list:
    a second migration that records only "it worked" leaves RELEASE-065..070 with a
    bare rule and no way to tell which canary findings were Repo-B-specific. On
    accepted constraints: *"Hooks are thin relays only"* is adjacent, since the
    mechanic rewrites Repo-J's hook block and cp-110 touched the recording path —
    the constraint's rationale is that hooks must not block or write state, so E3
    forbids hand-editing Repo-J's settings to satisfy the single-block assertion,
    and step 5 forbids routing around the permission classifier. *"Sidebar owns all
    state writes"* is why E6 is asserted against the db as written by the normal
    path, with no manual repair of rows permitted to make an assertion pass. No
    constraint is overridden and nothing required an operator decision on the
    ideology itself, so this returns via inline resolution rather than a flag.

## Tests

There is no flex-side test file for this story and none is added: `story_class` is
effectively documentation/evidence, the story changes no flex code, and its
subject is the state of another repository. The checks below are the acceptance
surface. Run them from `/mnt/work/flex`.

```bash
# E0 — the gate is actually clear (flex tag AND channel content)
git -C /mnt/work/flex tag --list 'cp-110*'
git -C /mnt/work/flex-harness log --oneline -5
```

```bash
# E1/E2/E3 — Repo-J baseline and post-migration state (confirm flags via --help first;
# the runbook's step-5 form is wrong per RELEASE-063 playbook note 2)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
  --candidate-dir /mnt/work/Repo-J --no-snapshot
```

```bash
# E4 — thin-harness template
grep -c "flex_build.py next-action" /mnt/work/Repo-J/CLAUDE.build.md
head -5 /mnt/work/Repo-J/CLAUDE.build.md
```

```bash
# E6 — proving-cycle attempt rows in Repo-J's own effort.db.
# Locate the db first; do not assume a path.
find /mnt/work/Repo-J -name 'effort.db' -not -path '*/node_modules/*'

# E6a attribution: rows present in Repo-J, absent in flex
sqlite3 <Repo-J-effort.db> "SELECT * FROM attempts WHERE story_id='<E5-STORY-ID>'"
sqlite3 <flex-effort.db>  "SELECT * FROM attempts WHERE story_id='<E5-STORY-ID>'"  # must be empty

# E6b content: outcome and tokens populated (adjust column names to the schema)
sqlite3 <Repo-J-effort.db> \
  "SELECT id, story_id, role, model, tokens_total, outcome, created_at
     FROM attempts WHERE story_id='<E5-STORY-ID>'"

# E6c duplicates: one row per attempt, no perfect pairs
sqlite3 <Repo-J-effort.db> \
  "SELECT story_id, role, COUNT(*) FROM attempts
    WHERE story_id='<E5-STORY-ID>' GROUP BY story_id, role"
```

```bash
# E7 — Repo-J's checkpoint/attempt report sees the rows (discover the exact
# subcommand from --help; it must not print "no attempts recorded")
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py --help
```

```bash
# E9 — settings.local.json sediment, before and after
grep -c 'Write(' /mnt/work/Repo-J/.claude/settings.local.json
grep -c 'Edit('  /mnt/work/Repo-J/.claude/settings.local.json
```

```bash
# E10 — canary re-verification: fresh (post-cp-110) Repo-B rows only
sqlite3 /mnt/work/Repo-B/.companion/effort.db \
  "SELECT id, story_id, role, tokens_total, outcome, created_at
     FROM attempts WHERE created_at > '<CP-110-PROMOTION-TIMESTAMP>'"
```

```bash
# E8 — migration visible in Repo-J's history, migration commit before proving commit
git -C /mnt/work/Repo-J log --oneline -10

# E11 — flex-side diff is this story file only; channel untouched
git -C /mnt/work/flex diff --name-only
git -C /mnt/work/flex-harness status --porcelain    # must print nothing
```

```bash
# E14 — flex's own suite, without -x so a known failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance:

- E0–E13 are verified by the reviewer **from the `## Evidence` section of this
  file**, not from a diff. An Ensure whose evidence is missing from that section
  is a fail;
- Repo-J shows `binding: both`, `0.3.0`, and `Projects with duplicate hooks: 0`;
- E6a, E6b and E6c all pass — rows in Repo-J's db, populated `outcome`/tokens, one
  row per attempt — and E7's report does not print "no attempts recorded";
- `git -C /mnt/work/flex-harness status --porcelain` prints nothing;
- the flex suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if it
  appears, state that it reproduces on clean `HEAD` and is unrelated;
- if E2, E3, E5, E6 or E7 failed, the return explicitly declares RELEASE-065..070
  blocked.

Note for `spec-preflight`: this spec references a `## Evidence` section and its
**Playbook notes** / **Follow-ups** subsections, which do not exist in this file
yet — they are created by this story, and any preflight finding naming them is
expected. It also references `/mnt/work/Repo-J`, `/mnt/work/Repo-B`,
`/mnt/work/flex-harness/skills/pairmode/scripts`, the `cp-110` tag and
`docs/harness-cutover-runbook.md` § *Per-project mechanic* / § *Rollback
procedure*, none of which the input-bound spec-writer could open; they are sourced
from `docs/phases/phase-106.md` § *Execution model* / § *Paused (2026-07-28)* and
from RELEASE-063's `## Evidence`. The `sqlite3` column names above
(`tokens_total`, `outcome`, `created_at`, table `attempts`) are taken from
RELEASE-063's recorded E6 output and may have changed under cp-110 — verify
against the live schema at step 9 rather than trusting this note. The
`--candidate-dir` / `--no-snapshot` flags likewise come from the canary's recorded
invocation; confirm via `--help`.

## Out of scope

- **Migrating any project other than Repo-J.** Repo-C, Repo-D, Repo-F,
  Repo-K, base56 and Repo-G are RELEASE-065..070. Do not run the mechanic against a
  second project "while the environment is warm" — this is the first run after a
  failed canary, and the campaign wants a second clean data point before it
  batches.
- **Re-syncing or re-migrating Repo-B.** E10 requires *determining* whether
  Repo-B needs a re-sync to pick up cp-110, and *recording* the determination.
  Performing it is a separate story: mixing a remediation of the canary into the
  first follow-on migration would make it impossible to tell which project's
  evidence proved what.
- **Fast-forwarding `/mnt/work/flex-harness` to cp-110.** If E0 finds the channel
  behind, **stop**. Promoting the channel is a release action (phase 102's
  precedent), not something a migration story does mid-run.
- **Amending the runbook.** If the mechanic is wrong, record it under E12 and name
  the follow-up under E13. RELEASE-063 E11 already filed amendments for the
  canary's notes 1/2/3/5/9; this story adds to that queue rather than draining it.
- **Filing or draining CERs.** Do not edit `docs/cer/backlog.md`. CER filing is
  the checkpoint's job; the backlog drain is phase 107.
- **Re-opening or amending RELEASE-063.** The canary's E6 verdict stands as
  recorded on pre-cp-110 evidence. This story's E10 adds *new* evidence in *this*
  file; it does not rewrite the canary's history.
- **The full-fleet DP8 gate and the phase-97 close.** Both are RELEASE-071
  (phase 106 § Ordering, strictly last). This story asserts nothing about the
  16/16 fleet snapshot.
- **Building Repo-J's proving story to a flex-side spec.** The proving cycle is
  Repo-J's own work, in Repo-J's numbering, under Repo-J's loop. It gets no flex
  story ID and no row in `docs/phases/phase-106.md`.
- **Any change to flex's own code, tests, templates, or plugin manifest.** This
  story is evidence-producing. `schema_introduces: false` stands and no
  management-surface row is owed in `docs/phases/phase-106.md` § Schema delivery.
- **Automating the campaign.** No script is written to loop the mechanic over the
  fleet. If that is wanted, it is a new story informed by E12 — not a shortcut
  taken during the run that is supposed to evaluate the manual procedure.

## Evidence

Executed 2026-07-28 at orchestrator level with the operator present, per this
story's § Execution model. **Partial run:** E0–E4 and E8–E14 are evidenced below;
**E5/E6/E7 (proving cycle) were NOT run** — operator decision, recorded verbatim
under § E5–E7 below. This section does not claim them as passed.

### E0 — gate proof

```
$ git -C /mnt/work/flex tag --list 'cp-110*'
cp-110

$ git -C /mnt/work/flex-harness log --oneline -5
5113c862 chore(phase-110): mark phase complete in index and era ledger (cp-110)
c060db1e docs(phase-110): fill CP-110 cold-eyes checklist at checkpoint
6cf90db2 docs(phase-110): name phase 110 in architecture.md; add CHANGELOG entry (checkpoint-docs findings)
a04e3d24 chore(phase-110): sync story statuses to complete after merges
601351a6 feat(story-INFRA-290): add data-flow checks to cold-eyes procedures and clear recording-state residue

$ git -C /mnt/work/flex rev-parse cp-110 ; git -C /mnt/work/flex-harness rev-parse HEAD
5113c8622c27a503018a6a648c274a14b5069ca3
5113c8622c27a503018a6a648c274a14b5069ca3   ← channel HEAD == cp-110 exactly
```

Preconditions: cp-105 tagged; RELEASE-063 `## Evidence` + *Playbook notes (E10)* +
*Follow-ups filed (E11)* present (lines 364/638/677); RELEASE-065..071 all `draft`;
Repo-J tree clean.

### E1 — pre-migration baseline

```
$ PATH=$HOME/.local/bin:$PATH uv run python \
    /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
    --candidate-dir /mnt/work/Repo-J --no-snapshot
Flex checkout: /mnt/work/flex-harness
Candidates scanned: 16
Bound projects found: 16
[14 sibling project blocks elided — Repo-J block verbatim:]
  /mnt/work/Repo-J
    binding: version
    signal1 (scripts path): absent — no-declaration
    signal2 (pairmode_version): 0.2.0
    DUPLICATE HOOKS: /mnt/work/Repo-J — events: SessionStart, PostToolUse
Projects with duplicate hooks: 16
```

Matches RELEASE-063's recorded E1 baseline for Repo-J exactly. NOTE: the
duplicate-hooks line is 16/16 fleet-wide — the canary run printed 0 from the
settings-only view; cp-110's merged view (INFRA-288 `hook_view.py`) now sees
plugin-sourced entries. See Playbook notes (new-1).

```
$ git -C /mnt/work/Repo-J log --oneline -5
e4cb3b0 fix(phase-proposed): correct pairmode tooling path to flex-harness, not flex
9766197 docs(phase-proposed): propose pairmode 0.3.0 migration
7fcfa5e chore(orchestrator): pairmode fleet rollout — wire context-budget-gate hooks (INFRA-209)
5ab420a chore(pairmode): commit bootstrap scaffold, with corrected PreToolUse matcher
bad490f Phase 1 MVP scaffold: FCA RSS → Claude analyst → markdown digest

$ git -C /mnt/work/Repo-J status --porcelain
(no output — clean)
```

### Mechanic run (steps 2–4 of the runbook, as corrected by this spec)

- `sync-all --dry-run`: methodology skip + 5 agent-file re-renders +
  `CLAUDE.build.md` 0.2.x prose loop (1088 lines) → 0.3.0 thin-harness template.
  Reviewed by operator; approved.
- `sync-all --project-dir /mnt/work/Repo-J --apply --yes`: exit 0. **Canary note 7
  did NOT recur** — no permission-classifier block; no auto-mode toggle needed.
- `.companion/state.json.lock` (0 bytes) left behind — **note 5 recurred**;
  removed, not committed.
- `to-030 --apply` output (key lines):

```
[apply] rewrote expected_step_tokens: 53000 → 5000
[apply] backfilled missing 'effort_tracking': true in state.json
[agent-cleanup] builder.md: content differs from known 0.2.x template (or allowlist not populated). Manual porting required.
  ... (same for reviewer.md, loop-breaker.md, security-auditor.md, intent-reviewer.md;
       each diff shows "0.2.x template ... (not available)")
to-030 complete.
```

**Note 4 recurred identically** (agent-cleanup noise; no action). **Note 6
DEVIATED:** the canary's custom `expected_step_tokens` was kept with a WARN;
here to-030 silently REWROTE 53000 → 5000. See Playbook notes (6) and Follow-ups.

### E2 / E3 — post-migration discovery (same command form as E1)

```
$ PATH=$HOME/.local/bin:$PATH uv run python \
    /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
    --candidate-dir /mnt/work/Repo-J --no-snapshot
[header + 14 sibling blocks elided — Repo-J block verbatim:]
  /mnt/work/Repo-J
    binding: both
    signal1 (scripts path): /mnt/work/flex-harness/skills/pairmode/scripts
    signal2 (pairmode_version): 0.3.0
    DUPLICATE HOOKS: /mnt/work/Repo-J — events: SessionStart, PostToolUse
Projects with duplicate hooks: 16
```

E2: all three conditions hold (`0.3.0`, signal1 → channel, `binding: both`).

E3: Repo-J's own settings hook state, from `.claude/settings.json`:

```
PreToolUse: 1 block(s), 1 command(s)     uv run python /mnt/work/flex-harness/hooks/pre_tool_use.py
UserPromptSubmit: 1 block(s), 1 command(s)  uv run python /mnt/work/flex-harness/hooks/user_prompt_submit.py
SessionStart: 1 block(s), 1 command(s)   uv run python /mnt/work/flex-harness/hooks/session_start.py
PostToolUse: 1 block(s), 1 command(s)    uv run python /mnt/work/flex-harness/hooks/post_tool_use.py
```

Single pairmode hook block per event — the sync produced this state on its own;
nothing was hand-edited. The persisting DUPLICATE flag is **plugin-side and
non-pairmode**, per `audit-hooks` (dry-run; nothing prunable in settings):

```
$ pairmode_sync.py audit-hooks --project-dir /mnt/work/Repo-J
DUPLICATE: event=SessionStart basename=session-start.sh" sources=['plugin', 'plugin'] ...
DUPLICATE: event=PostToolUse basename=security_reminder_hook.py" sources=['plugin', 'plugin', 'plugin', 'plugin', 'plugin', 'plugin'] ...
```

`Projects with duplicate hooks: 0` is **unattainable this run**: the merged view
flags all 16 fleet projects on the same plugin-sourced basis. Adjudication: E3's
substance (sync produces single-block pairmode hooks) holds; the fleet-wide
plugin-duplicate signal is a new cp-110-era finding, not a Repo-J migration
defect. See Playbook notes (new-1) and Follow-ups.

### E4 — thin-harness template

```
$ grep -c "flex_build.py next-action" /mnt/work/Repo-J/CLAUDE.build.md
2
$ head -5 /mnt/work/Repo-J/CLAUDE.build.md
# CLAUDE.build.md — Repo-J Build Orchestrator

You are the build orchestrator for the Repo-J project. Drive the build loop by
delegating to `/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action` and the appropriate leaf worker. Do not write code,
review code, or commit directly — those are leaf-worker responsibilities.
```

### E5 / E6 / E7 — proving cycle: **NOT RUN (operator deferral)**

Operator statement, recorded at the decision point: *"Repo-J isn't in a spot to
build, we'll just have to mark it complete and continue on. I'll have to prove
it out later. Understood and acknowledged that we're not really doing proper
checkout on Repo-J."*

Consequences, stated per Instructions step 11:

- No Repo-J proving story was built; no session mode to record (E5 unevidenced).
- E6a/E6b/E6c were not queried — there are no proving-cycle rows to query. The
  downstream proof that the CER-101/103/104 remediation works in a consumer
  project **does not exist yet**, from Repo-J or (per E10 below) from Repo-B.
- E7's report-path check was likewise not run.
- **Campaign gate: E5/E6/E7 unevidenced = not passed.** Per this spec's own
  acceptance, RELEASE-065..070 remain gated pending a completed proving cycle on
  Repo-J (deferred follow-up below) or equivalent downstream E6 evidence.
  The operator has acknowledged this deferral explicitly.

### E8 — Repo-J git history

```
$ git -C /mnt/work/Repo-J log --oneline -3
433593d sync: migrate to pairmode 0.3.0 thin-harness loop
e4cb3b0 fix(phase-proposed): correct pairmode tooling path to flex-harness, not flex
9766197 docs(phase-proposed): propose pairmode 0.3.0 migration
```

Migration is its own commit (`433593d`), landed **before** any proving cycle
(note 3 correction applied). 10 files changed, 252 insertions, 1098 deletions.
No proving-story commit exists (see E5–E7).

### E9 — settings.local.json sediment

```
$ ls /mnt/work/Repo-J/.claude/settings.local.json
(does not exist)
```

Repo-J carries no `settings.local.json` and therefore no Write()/Edit() sediment.
Canary note 9 not applicable; no prune decision required.

### E10 — canary (Repo-B) E6 re-verification

Fallback **(b)** applies. cp-110 promotion: 2026-07-28T11:57:54-04:00 (=15:57:54Z).

```
$ python3 sqlite query — /mnt/work/Repo-B/.companion/effort.db
post-cp-110 rows (ts > 2026-07-28T15:57:54Z): 0
latest 3 rows overall:
   (282, 'SEC-006', 'builder', '2026-07-28T14:09:53.396917+00:00')
   (281, 'SEC-006', 'builder', '2026-07-28T14:09:53.386698+00:00')
   (280, 'TEST-005', 'reviewer', '2026-07-28T13:12:12.820181+00:00')
```

Repo-B has had **no post-cp-110 build activity**; no fresh rows exist to re-run
E6a/b/c against. (Rows 281/282 are incidentally a pre-cp-110 CER-104 duplicate
pair — same story, same role, 10 ms apart — confirming the historical failure
shape.) With Repo-J's proving cycle also deferred, **no downstream E6 evidence
exists at all yet**; follow-up filed below. Schema note: the live `attempts`
schema uses `agent_role`/`ts`, not the spec's `role`/`created_at` (taken from
RELEASE-063's output) — queries adjusted accordingly.

**Re-sync determination: Repo-B does NOT need a re-sync.** Basis: the
CER-101/103/104 fixes live in channel scripts (`effort_db.py`,
`subagent_transcript.py`, `hook_view.py`, `flex_build.py`) which Repo-B invokes
by path via its channel-bound hooks (`/mnt/work/flex-harness/hooks/*`); cp-110
changed no hook or agent template content of the kind copied into consumer repos
at migration time (phase-110's `phase.md.j2` change affects newly scaffolded
phase docs only, rendered from the channel template at scaffold time).

### E11 — cleanliness

```
$ git -C /mnt/work/flex diff --name-only        # before this Evidence append
(no output)
$ git -C /mnt/work/flex-harness status --porcelain
(no output — channel read from, never written)
```

Flex-side diff for this story is this file (plus tool-written status/ledger rows).

### E14 — flex suite

```
$ uv run pytest tests/pairmode/ -q     # run once, without -x
4079 passed, 211 skipped, 14 warnings in 181.72s (0:03:01)
```

Green with zero failures; the CER-090 environmental failure did not appear (run
from the main checkout, not a worktree).

### Playbook notes (E12 — delta against RELEASE-063's nine)

1. Dirty-tree stop: **did not recur** — Repo-J's tree was clean at start.
2. Runbook step-5 command form wrong: **recurred** (runbook still unamended);
   used the canary's corrected `--candidate-dir` form, confirmed via `--help`.
3. Commit-before-proving reorder: **recurred / applied** — migration committed
   as its own commit `433593d` ahead of any proving work.
4. `to-030` agent-cleanup noise: **recurred identically** — all five
   freshly-synced agent files flagged against a "(not available)" 0.2.x
   template; no action needed.
5. `state.json.lock` residue: **recurred** — removed by hand, not committed.
6. Custom `expected_step_tokens`: **DEVIATED** — canary kept its custom value
   with a WARN; on Repo-J `to-030` silently **rewrote 53000 → 5000** with no
   keep/WARN path. Behavior change vs. the canary run (possibly from the
   phase-110 `pairmode_migrate.py` changes); operator not prompted. Follow-up
   filed.
7. Auto-mode classifier block on first out-of-repo `--apply`: **did not recur**
   — `sync-all --apply` ran without any permission block from this flex session.
8. E6 execution-mode ambiguity: **still open but changed** — cp-110/INFRA-289
   added target-project attribution (`resolve_recording_project`,
   registered_projects-allowlisted), which may make flex-driven cycles attribute
   correctly; unproven downstream because the proving cycle was deferred.
9. `settings.local.json` sediment: **not applicable** — Repo-J has no such file.

New findings this run:

- **(new-1) Fleet-wide plugin-sourced duplicate-hook signal.** The cp-110 merged
  hook view reports `Projects with duplicate hooks: 16` (was 0 pre-cp-110 from
  settings-only blindness). For Repo-J the duplicates are exclusively
  plugin-sourced (`session-start.sh` ×2, `security_reminder_hook.py` ×6),
  non-pairmode, and unprunable by `audit-hooks --apply` (which by design never
  writes plugin files). Either genuine multi-plugin duplication or a
  `hook_view.py` discovery double-count; needs a CER either way. E3's
  "duplicate hooks: 0" assertion is unattainable fleet-wide until resolved.
- **(new-2) `to-030` silent `expected_step_tokens` rewrite** (see note 6 delta).

### Follow-ups (E13 — filed, not fixed here)

- **Repo-J proving cycle (E5/E6/E7) deferred by operator** — must run natively in
  Repo-J (or via the INFRA-289 attribution path) before Repo-J's migration can be
  called proven; until then the CER-101/103/104 downstream proof is outstanding
  and RELEASE-065..070 remain gated per Instructions step 11.
- **Repo-B post-cp-110 E6 re-verification** (E10(b)) — re-run E6a/b/c on
  Repo-B's next build cycle; no re-sync needed (determination above).
- **CER to file: fleet-wide plugin-sourced duplicate-hook signal** (new-1) —
  diagnose hook_view plugin discovery (genuine duplication vs. double-count);
  decide the E3 assertion's future form.
- **CER or runbook note to file: `to-030` rewrites custom `expected_step_tokens`
  without prompt/WARN** (new-2) — canary-run behavior (keep + WARN) was the
  documented expectation.
- Runbook amendments for notes 2/3/5 recurrences: already filed by RELEASE-063
  E11 — referenced, not duplicated.

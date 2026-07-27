---
id: RELEASE-063
rail: RELEASE
title: Migrate meander to pairmode 0.3.0 (campaign canary)
status: draft
phase: "106"
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

<!-- SPEC-WRITER NOTE (Step 5): the frontmatter arrived with no `primary_files:`
     key and `touches: []`. The spec-writer input contract forbids editing
     frontmatter, so both were preserved as-is and this story is returned
     `status: "revised"` for the operator to populate. The only file inside this
     repository that this story writes is *this file* (the `## Evidence` section
     added by the executor). Every other write target is outside the repo, under
     `/mnt/work/meander`, and therefore cannot appear in `touches:` at all —
     which is the point of the phase's § Execution model deviation. Suggested
     value for both keys:
       - docs/stories/RELEASE/RELEASE-063.md
     Populate them before dispatching, and see `## Instructions` step 0. -->

## Context

Phase 97 scaffolded fifteen fleet-migration stubs (RELEASE-043..057) and then
deferred them to "per-project sessions." Those sessions produced zero migrations
— the fleet is still split across pairmode methodology versions while
`main` sits at 0.3.0. Phase 106 reverses that resolution and drives the
remaining migrations centrally from flex, using the per-project mechanic already
written down in `docs/harness-cutover-runbook.md` § *Per-project mechanic*
(six steps) as the unit of work.

This story is the **canary**. Phase 106 § Ordering makes it strictly first:
RELEASE-064..070 do not start until meander has gone through the full mechanic
and come out the other side with a proving story cycle whose attempt rows landed
correctly in its `effort.db`. The purpose is not only to migrate meander — it is
to prove the campaign playbook end to end on one project while the operator is
watching, so that the seven follow-on stories can run with less scrutiny. If the
mechanic is wrong, it is wrong here, once, on the smallest blast radius, rather
than eight times.

The proving cycle also does live downstream validation of the CER-091 fix
(INFRA-264, phase 104): attempt recording landing correctly in a *migrated
consumer's* `effort.db` — not flex's own — is the only evidence that the fix
holds across the sync boundary. Phase 106 § Checkpoint proves names this
explicitly. A migration that stamps 0.3.0 but produces no attempt rows is a
**failed** canary even though `pairmode_status.py` would report success.

Two things about how this story runs are unusual and are settled by the phase
doc's § *Execution model (cross-repo — deviation from the standard loop)*, which
you should read before acting:

1. **No sandboxed builder subagent, no flex worktree.** The write targets live
   at `/mnt/work/meander`, outside this repo. The standard worktree loop and
   `scope_guard.py` forbid writes there — correctly. Execution is
   orchestrator-level with the operator present.
2. **Acceptance is evidence-shaped, not diff-shaped.** The flex-side diff for
   this story is one `## Evidence` section appended to this file. The reviewer
   verifies recorded command output, not a code change.

The pairmode CLIs are invoked from the **permanent release channel**,
`/mnt/work/flex-harness/skills/pairmode/scripts` — canonized in
`docs/architecture.md` § *Release channel — flex-harness* and by RELEASE-062
(phase 105). Do not invoke them from `/mnt/work/flex/skills/...`: the channel is
what the fleet consumes, and migrating a project with a different copy of the
scripts than the fleet uses would prove nothing.

## Requires

- **cp-105 is tagged and phase 105 is complete.** Phase 106 § Execution model
  states plainly: *"do not start this phase before cp-105."* Phase 105 delivered
  the CER-080/087 scope-guard fixes and the CER-040/041 hook fixes that remove
  the known false-blocks this story would otherwise hit. The era ledger
  (`docs/eras/003-flex-orchestrator-as-harness.md` § Phases) shows phase 105
  `complete`.
- **No sibling phase-106 story has been started.** This is the canary;
  RELEASE-064..071 must all still be `draft` when this story begins.
- `/mnt/work/flex-harness` exists and is the release channel described in
  `docs/architecture.md` § *Release channel — flex-harness*.
- `/mnt/work/meander` exists, is a git repository, and its working tree is clean
  at the moment the mechanic begins. A dirty tree is a **stop** condition, not
  something to stash around — the operator resolves it first.
- `docs/harness-cutover-runbook.md` contains a `## Per-project mechanic` section
  enumerating the six steps. That section, not this spec, is the authoritative
  step list; this spec states what must be *true afterwards*.
- The operator is present. This story is not eligible for unattended execution.

## Ensures

Each assertion below is verified from recorded command output pasted into this
file's `## Evidence` section (see `## Instructions` step 7). "Recorded" means the
exact command and its exact output, not a paraphrase.

**E1. A pre-migration baseline exists.**
`## Evidence` contains the verbatim output of a `fleet_discovery.py` run captured
**before** any write to `/mnt/work/meander`, showing meander's pre-migration
`pairmode_version` and its pre-migration hook-block state. Without this, "the
migration changed something" is unverifiable.

**E2. meander reports pairmode 0.3.0.**
A post-migration `fleet_discovery.py` run recorded in `## Evidence` shows
meander at pairmode version `0.3.0`. The recorded output is from the same
command form as E1 so the two are directly comparable.

**E3. meander's hooks are a single block.**
The same post-migration discovery output shows meander with a single pairmode
hook block — the `single-block hooks` condition named in phase 106 § Checkpoint
proves. If discovery reports duplicate or split blocks, this Ensure fails; do
not hand-edit meander's settings to make the number come out right, because the
canary's job is to prove `pairmode_sync.py` produces this state on its own.

**E4. meander's bootstrapped loop is the 0.3.0 thin-harness template.**
`## Evidence` records the result of inspecting `/mnt/work/meander`'s bootstrapped
`CLAUDE.build.md` and confirms it is the thin dispatch-loop template, not the
pre-flip 0.2.x prose loop. Record the command used (e.g. a `grep -c` for a
string that exists only in the 0.3.0 template) and its output.

**E5. A proving story cycle completed inside meander.**
`## Evidence` names the meander-side story ID that was built as the proving cycle
(mechanic step 6), states that it ran inside meander's **own**
`CLAUDE.build.md` loop with meander's own story numbering, and states its
outcome. The story is a real, small, genuinely-wanted piece of meander work — not
a throwaway.

**E6. The proving cycle's attempt rows landed in meander's effort.db.**
`## Evidence` records a query against `/mnt/work/meander`'s `effort.db` showing
at least one attempt row for the E5 story ID, with a non-null, non-placeholder
`outcome` and a non-zero token/cost field. This is the CER-091/INFRA-264
downstream validation. Record the exact query and its exact output. Zero rows is
a **fail**, and a fail here blocks RELEASE-064..070 (see `## Instructions`
step 8).

**E7. meander's git history shows the migration as its own commit(s).**
`## Evidence` records `git -C /mnt/work/meander log --oneline` for the migration
commits, so a later auditor can see exactly what the sync wrote into meander and
roll it back if needed.

**E8. The flex-side diff is this file only.**
```bash
git -C /mnt/work/flex diff --name-only
```
lists exactly `docs/stories/RELEASE/RELEASE-063.md` (plus the phase doc's story
row and index/ledger rows if the orchestrator's recording CLIs touch them — those
are tool-written, not hand-written). No file under `skills/`, `tests/`, `ui/`, or
`.claude-plugin/` is modified by this story.

**E9. Nothing was written into `/mnt/work/flex-harness`.**
`git -C /mnt/work/flex-harness status --porcelain` prints nothing. The channel is
read from, never written by a migration story.

**E10. Playbook findings are recorded, not just experienced.**
This file's `## Evidence` section ends with a short **Playbook notes** subsection
listing every deviation from `docs/harness-cutover-runbook.md`
§ *Per-project mechanic* that was necessary, every manual intervention required,
and every step that was ambiguous. If the mechanic ran exactly as written with no
intervention, say exactly that. This subsection is the canary's real deliverable —
RELEASE-064..070 are specced against it. An empty or omitted Playbook notes
subsection fails this Ensure.

**E11. Runbook or CER follow-ups are filed, not fixed here.**
If E10 surfaced a defect in the mechanic, the corresponding runbook amendment or
CER entry is *named* in `## Evidence` as a follow-up. This story does **not** edit
`docs/harness-cutover-runbook.md` or `docs/cer/backlog.md` (see `## Out of scope`).

**E12. flex's own suite is unaffected.**
`uv run pytest tests/pairmode/` is run once at the end and is green except the
known CER-090 worktree-environmental failure
(`tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`),
if it appears. This story changes no flex code, so any *new* failure means
something ran that should not have.

## Instructions

You are executing this story **at orchestrator level with the operator present**,
not as a sandboxed builder subagent in a flex worktree. Do not create a story
worktree. Do not attempt to have a builder subagent write to `/mnt/work/meander`
— `scope_guard.py` will block it, correctly, and working around the block is
itself a violation.

0. **Populate the frontmatter gap.** `primary_files:` is absent and `touches:` is
   `[]` (see the spec-writer note at the top of this file). Set both to
   `docs/stories/RELEASE/RELEASE-063.md` — the single in-repo write target. The
   out-of-repo targets under `/mnt/work/meander` are deliberately *not* listed;
   `touches:` is a within-repo declaration and listing external paths there would
   misrepresent the diff surface to every gate that reads it.

1. **Confirm the preconditions before touching anything.** Verify every bullet in
   `## Requires` and record the checks. In particular: cp-105 tagged; meander's
   working tree clean; no sibling phase-106 story already started. If any fails,
   stop and hand back to the operator — a canary run on an unprepared fleet
   proves nothing.

2. **Read the mechanic.** Read `docs/harness-cutover-runbook.md`
   § *Per-project mechanic* in full, and § *Rollback procedure* alongside it so
   you know the exit path before you start. The spec-writer is input-bound and
   did **not** read the runbook; the six steps are defined there, and where this
   spec and the runbook disagree on *procedure*, the runbook wins — record the
   discrepancy under E10 rather than forcing this spec's phrasing. Where they
   disagree on *what must be true afterwards*, this spec's `## Ensures` wins.

3. **Capture the baseline (E1).** Run `fleet_discovery.py` from the release
   channel:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py
   ```
   Consult the script's `--help` for the exact flag set — do not guess flags.
   Save the full output; you will diff it against the post-migration run. Also
   capture `git -C /mnt/work/meander log --oneline -5` and
   `git -C /mnt/work/meander status --porcelain` so the pre-state is on record.

4. **Run the mechanic against meander.** Follow the runbook's six steps in order,
   invoking `pairmode_migrate.py` and `pairmode_sync.py` from
   `/mnt/work/flex-harness/skills/pairmode/scripts` — never from
   `/mnt/work/flex/skills/...`. Run one step at a time and show the operator the
   output of each before proceeding to the next; this is a canary, and the value
   is in catching a wrong step at step 2 rather than at step 6. If a step fails,
   **stop** — do not improvise a fix into meander. Report to the operator, and if
   the failure is unrecoverable, execute the runbook's rollback procedure and
   record what happened under E10.

5. **Verify the stamp before proving (E2, E3, E4).** Re-run the same
   `fleet_discovery.py` command from step 3 and confirm meander now reports
   `0.3.0` with single-block hooks. Then inspect meander's bootstrapped
   `CLAUDE.build.md` and confirm it is the thin-harness template. Do not proceed
   to step 6 until all three hold — a proving cycle run against a half-migrated
   project produces uninterpretable evidence.

6. **Run the proving story cycle (E5, E6).** This is mechanic step 6 and it runs
   **inside meander**, in meander's own `CLAUDE.build.md` loop, with meander's own
   story numbering. Do not create a flex story for it and do not run it from this
   session's loop. Pick a small, real, already-wanted piece of meander work — the
   point is to exercise the full build loop (gate → builder → reviewer → record)
   on genuine work, so a no-op story defeats it. When it completes, query
   meander's `effort.db` for that story's attempt rows and confirm the `outcome`
   and token/cost fields are populated. **Zero rows, or rows with a placeholder
   outcome, is the CER-091 regression reappearing downstream** — treat it as a
   stop condition and report it as such.

7. **Record the evidence (E1–E9, E10, E11).** Append a `## Evidence` section to
   *this file*, containing, in order: the E1 baseline output; the E2/E3
   post-migration discovery output; the E4 template check; the E5 proving-story
   ID and outcome; the E6 effort.db query and its output; the E7 meander git log;
   the E8/E9 cleanliness checks; and a final **Playbook notes** subsection per
   E10. Paste command output verbatim inside fenced blocks — do not summarize it
   into prose, because RELEASE-064..070 are specced against what actually
   happened, and a summary loses exactly the detail a later failure would need.

8. **Gate the rest of the campaign.** If any of E2, E3, E5 or E6 failed, say so
   explicitly in your return and state that RELEASE-064..070 are blocked pending
   an operator decision. Phase 106 § Ordering makes the canary a gate, not merely
   a first item; silently proceeding to the next project after a partial canary
   is the single worst outcome available here.

9. **Ideology note (Step 4a — resolved inline, no conflict).** Two things in
   `docs/ideology.md` shaped this spec. *"Never silently pass contradictions"* is
   why E1 demands a pre-migration baseline and why E6 treats a 0.3.0 stamp with
   no attempt rows as a failure rather than a success: a migration that reports
   done while its downstream recording is broken is precisely the false
   confidence the constraint exists to prevent. *"Rationale-bearing decisions over
   bare rules"* is why E10's Playbook notes subsection is a hard Ensure rather
   than a nicety — a canary that migrates a project but records no reasoning
   leaves the seven follow-on stories with a bare rule ("run the six steps") and
   none of the why. On accepted constraints: *"Hooks are thin relays only"* is
   adjacent here, since the mechanic rewrites meander's hook block. The
   constraint's rationale is that hooks must not block or write state, so the
   instruction above (E3) forbids hand-editing meander's settings to satisfy the
   single-block assertion — the sync tool must produce a compliant thin-relay
   block on its own, or the defect is real and gets recorded under E10. No
   constraint is overridden and nothing required an operator decision, so this
   returns via inline resolution rather than a flag.

## Tests

There is no flex-side test file for this story and none is added: the story
changes no flex code, and its subject is the state of another repository. The
checks below are the acceptance surface. Run them from `/mnt/work/flex`.

```bash
# E2/E3 — meander at 0.3.0 with single-block hooks (see --help for exact flags)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py
```

```bash
# E6 — proving-cycle attempt rows landed in meander's effort.db.
# Locate the db first; do not assume a path.
find /mnt/work/meander -name 'effort.db' -not -path '*/node_modules/*'
# then query the attempt rows for the proving story ID recorded under E5
```

```bash
# E7 — migration visible in meander's history
git -C /mnt/work/meander log --oneline -10

# E8 — flex-side diff is this story file only
git -C /mnt/work/flex diff --name-only

# E9 — release channel untouched
git -C /mnt/work/flex-harness status --porcelain    # must print nothing
```

```bash
# E12 — flex's own suite, without -x so a known failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance:

- E1–E11 are verified by the reviewer **from the `## Evidence` section of this
  file**, not from a diff. An Ensure whose evidence is missing from that section
  is a fail, regardless of whether the underlying thing happened;
- `git -C /mnt/work/flex-harness status --porcelain` prints nothing;
- the flex suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if
  it appears, state that it reproduces on clean `HEAD` and is unrelated;
- if E2, E3, E5 or E6 failed, the return explicitly declares RELEASE-064..070
  blocked.

Note for `spec-preflight`: this spec references `## Evidence` and its
**Playbook notes** subsection, which do not exist in the tree yet — they are
created by this story, and any preflight finding naming them is expected. It also
references `/mnt/work/meander`, `/mnt/work/flex-harness/skills/pairmode/scripts`
and `docs/harness-cutover-runbook.md` § *Per-project mechanic*, none of which the
input-bound spec-writer could open; they are sourced from
`docs/phases/phase-106.md` § Execution model and from RELEASE-062. Verify them at
step 1 rather than trusting this note.

## Out of scope

- **Migrating any project other than meander.** lumin, caddy, forqsite.help,
  halfhorse, pokus, base56 and cora are RELEASE-064..070. Do not run the mechanic
  against a second project "while the environment is warm" — the canary's whole
  value is that exactly one project moves before the playbook is reviewed.
- **Amending the runbook.** If the mechanic is wrong, record it under E10 and name
  the follow-up under E11. Editing `docs/harness-cutover-runbook.md` inside this
  story would mean the canary and the fix land in one undifferentiated change,
  and the next reader could not tell which steps were actually executed.
- **Filing or draining CERs.** Do not edit `docs/cer/backlog.md`. CER filing is
  the checkpoint's job; the backlog drain is phase 107.
- **The full-fleet DP8 gate and the phase-97 close.** Both are RELEASE-071
  (phase 106 § Ordering, strictly last). This story asserts nothing about the
  16/16 fleet snapshot.
- **Superseding RELEASE-043..057.** Also RELEASE-071. Leave the phase-97 stubs
  exactly as they are.
- **Building meander's proving story to a flex-side spec.** The proving cycle is
  meander's own work, in meander's numbering, under meander's loop. It gets no
  flex story ID and no row in `docs/phases/phase-106.md`.
- **Any change to flex's own code, tests, templates, or plugin manifest.** This
  story is evidence-producing. `schema_introduces: false` stands and no
  management-surface row is owed in `docs/phases/phase-106.md` § Schema delivery.
- **Automating the campaign.** No script is written to loop the mechanic over the
  fleet. If that is wanted after the canary, it is a new story informed by E10 —
  not a shortcut taken during the run that was supposed to evaluate the manual
  procedure.

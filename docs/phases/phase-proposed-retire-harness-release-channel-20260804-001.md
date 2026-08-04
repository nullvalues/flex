---
era: "005"
phase_class: production
---

# project — Phase proposed-retire-harness-release-channel-20260804-001: Retire the flex-harness release-channel worktree in favor of the marketplace-cache install

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Now that Phase 120 (CER-159) proved a marketplace-installed plugin copy gives flex's own build loop the same self-reference decoupling the flex-harness sibling worktree exists to provide -- a pinned, checkpoint-gated execution copy independent of the live working tree -- evaluate retiring the release-channel worktree entirely: fold its still-relevant properties (pinned-to-last-checkpoint toolchain, INFRA-332's agent-shell backfill) into the marketplace-install workflow, update CLAUDE.build.md/architecture.md's Release channel section and the harness-cutover-runbook to match, and formally reverse the 'permanent, no fold removes it' decision those docs currently state -- or conclude the two mechanisms serve different enough purposes that both should stand, and document why.

## Background

Raised by the operator during Phase 120's checkpoint-tag promotion (2026-08-04), when
`git -C /mnt/work/flex-harness merge --ff-only cp-120` failed on the same recurring
divergence it always has (`INFRA-332`'s permanent harness-only agent-shell backfill commit).
Operator's framing at the time: *"we're going to permanently merge down to main; with the
local marketplace cache, there's no reason to run a release branch that's confusing at
best."* Deferred out of Phase 120's own scope (a sweeping architectural reversal doesn't
belong inside a checkpoint-promotion step) and captured here instead.

**The tension to resolve.** `docs/architecture.md` § *Release channel — flex-harness*
currently states the channel is *"permanent — no fold or teardown removes it"* and that the
worktree/branch-removal steps `docs/harness-cutover-runbook.md` once planned (and
`docs/stories/RELEASE/RELEASE-061.md`, `status: skipped`) *"are retired and must never be
run."* That was written when the release channel was the only mechanism giving flex's own
build loop a pinned-to-last-checkpoint toolchain, independent of the live working tree it
builds (the RESOLVER-012..017 self-reference incidents the doc cites as the reason it
exists). Phase 120 built a second mechanism with the same property, for a different reason
(CER-159's hook-firing fix): a marketplace-installed plugin copy, version-keyed, decoupled
from the live tree, requiring an explicit version bump to pick up new code. Two independent
pinned-copy mechanisms now coexist. This phase's job is to decide whether that's real
redundancy worth collapsing, or whether they're solving different problems closely enough
in shape to look redundant but not actually be (see Open questions below) — and either way,
to make the decision explicit and update the docs that currently assert permanence.

**What would need to change if retiring.** At minimum: `CLAUDE.build.md`'s
`pairmode_scripts_dir` (currently hardcoded to `/mnt/work/flex-harness/skills/pairmode/scripts`)
would need to point at the marketplace-cache install path instead;
`docs/architecture.md` § Release channel would need a full rewrite, not just an
amendment, since its "permanent" framing and promotion mechanics (P1-P4, the
`--ff-only`-only rule) would no longer apply; `docs/harness-cutover-runbook.md`'s status
as a historical document (already superseded once, per its own file) versus something
needing a final update; and the `flex-harness` git remote/worktree/branch itself — whether
it's deleted, archived, or left inert.

## Open questions (not yet resolved — this phase's design work, not this doc's)

- **Do the two mechanisms actually solve the same problem?** The release channel's stated
  reason (RESOLVER-012..017) is preventing a build loop from executing toolchain code that
  changes under it mid-phase. The marketplace-cache mechanism's reason (CER-159) is fixing
  broken hook registration. Both happen to produce "a pinned copy independent of the live
  tree" as a side effect, but confirm they're actually interchangeable for the self-reference
  concern before assuming one can replace the other — e.g. does the marketplace cache
  update at exactly checkpoint-tag time (like the harness does today), or only whenever
  someone remembers to bump the version and reinstall? INFRA-384 documented the version-bump
  requirement as a manual discipline, not an automated one — that gap matters here.
- **What does "no fold removes it" protect against, specifically?** Re-read the
  RESOLVER-012..017 incident history before concluding the channel is now redundant — those
  were real incidents, not hypothetical.
- **Migration mechanics for the deprecated worktree/branch.** `flex-harness` (branch
  `fold-prep`) is a real git remote with real history — decide archive vs. delete vs. leave
  inert, and who/what still references it (`docs/harness-cutover-runbook.md`,
  `RELEASE-062`, any fleet-wide tooling that assumes its existence).
- **Does the marketplace-cache mechanism need hardening first?** Right now it depends on a
  manually-run install sequence and a manually-remembered version bump (INFRA-383/384). If
  this phase makes it flex's *only* self-reference-decoupling mechanism, "manual and easy to
  forget" may not be good enough to inherit that responsibility alone.

## Stories

| ID | Title | Status |
|----|-------|--------|

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-proposed-retire-harness-release-channel-20260804-001 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

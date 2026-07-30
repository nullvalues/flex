---
id: RELEASE-070
rail: RELEASE
title: Migrate cora from 0.1.0 to 0.3.0 (unpark RELEASE-030 lesson-extraction carve-out)
status: complete
phase: "106"
auth_gated: false
schema_introduces: false
touches:
  - docs/stories/RELEASE/RELEASE-070.md
  - docs/phases/phase-106.md
---

## Context

**Operator report (2026-07-29):** cora was already migrated to pairmode
0.3.0 by hand, outside the campaign's driven mechanic, prior to this story
being picked up. This story is recorded as complete on that basis rather
than built — no orchestrator-level migration was performed here, matching
this phase's pattern of recording each project's actual disposition rather
than silently dropping stories that turn out not to need the standard
mechanic (see RELEASE-068's canon-only narrowing and RELEASE-069's
decommission-instead-of-migrate precedent).

The original scope ("unpark RELEASE-030 lesson-extraction carve-out") was
never separately verified as part of this closeout — recorded as an open
question in Evidence below, not silently dropped.

## Requires

N/A — no build performed; this story records an already-completed hand
migration.

## Ensures

- `pairmode_version` in cora's `.companion/state.json` reads `0.3.0`.
- Evidence section records the verification commands and their real output.

## Instructions

N/A — no orchestrator-level execution for this story. Verification only:
read `.companion/state.json` and run `fleet_discovery.py --no-snapshot`
against `/mnt/work/cora`, record the results.

## Tests

N/A — no code change in either repo.

## Evidence

**Verification only, no migration performed by this story.**

```
cat /mnt/work/cora/.companion/state.json | grep pairmode_version
-> "pairmode_version": "0.3.0"

git -C /mnt/work/cora log -3 --oneline
-> ec09fe1 chore(era-002): cold-eyes review, apps-as-code respec, flex 0.3.0 migration
   79606e6 fix(hooks): widen PreToolUse matcher to Task|Agent|Edit|Write|Read
   703f080 fix(permissions): convert Write(path) rules to Edit(path)
```
cora's own commit history confirms an explicit "flex 0.3.0 migration" commit — the hand-migration claim is corroborated, not just asserted.

`fleet_discovery.py --no-snapshot` for `/mnt/work/cora`:
```
signal1: false (absent_reason: "foreign-checkout", detail: "/mnt/work/flex/skills/pairmode/scripts")
signal2: true (value: "0.3.0")
binding: "version"
```

**Finding (not fixed here):** cora's hooks resolve to the `/mnt/work/flex` dev checkout rather than the `/mnt/work/flex-harness` release channel — a "foreign-checkout" variant of the same hook-path portability class as CER-127/INFRA-319 (routed to phase 114). `binding: version` only, not `both`. This does not block marking the story complete (the operator's hand migration is confirmed real and cora is functionally on 0.3.0), but it means cora is not yet a clean INFRA-319 example either — recorded here as field evidence, not remediated by this story.

**Open item, not resolved by this story:** the original scope line ("unpark RELEASE-030 lesson-extraction carve-out") was not separately verified as part of the hand migration — whether that specific carve-out was addressed is unconfirmed. Flagged for RELEASE-071 (campaign close) to either verify or explicitly note as still open.

**Disposition for RELEASE-071:** cora should be recorded as **hand-migrated (0.3.0, confirmed via commit history and state.json), foreign-checkout hook binding (INFRA-319 candidate), lesson-extraction carve-out unverified** — distinct from pokus's proof-deferred and base56's decommissioned dispositions.

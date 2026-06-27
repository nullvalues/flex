---
id: RELEASE-006
rail: RELEASE
title: "Cutover & migration runbook (DP5, DP6)"
status: complete
phase: "HARNESS001-ante1"
story_class: doc
primary_files:
  - docs/harness-cutover-runbook.md
touches:
---

# RELEASE-006 — Cutover & migration runbook (DP5, DP6)

## Context

This story LANDS ON `main` (which stays 0.2.x). It AUTHORS a self-contained
runbook; it does NOT execute any migration. The runbook is **executed at/after
HARNESS006** (the flip), not during ante1.

Per **DP5** (✅ AGREED — Option Y: opt-in, do-nothing-stays-stable, rolling,
sync-driven) and **DP6** (✅ AGREED — flex dogfoods its own refactor and flips
its own loop last). The binding mechanic is verified: a consumer's loop binds to
flex by the absolute `pairmode_scripts_dir` baked into its `CLAUDE.build.md` at
sync time (`Path(__file__).parent` of the syncing checkout), not by `FLEX_DIR`
(which only drives the version-nag hook). `main` stays the stable 0.2.x line for
the whole migration window; `harness` (in `/mnt/work/flex-harness`) is the
0.3.0 line. "Do nothing = stay on 0.2.x" is structural.

The new runbook file is `docs/harness-cutover-runbook.md`.

## Acceptance criteria

The runbook is self-contained and contains, as clearly-labelled sections:

1. **Strategy (Option Y).** States: opt-in, do-nothing-stays-stable, rolling,
   sync-driven; `main` stays 0.2.x through the migration window; no `stable/0.2`
   branch; the flip-`main`-immediately alternative is rejected because it breaks
   any project that does nothing.

2. **Rolling sequence (DP5 + DP6).** flex itself FIRST (finalize
   `0.3.0-dev → 0.3.0`, verify a full build round — the DP6 dogfood; flex is
   developer *and* canary) → ONE canary fleet project → the rest, one at a time.
   Operator-initiated per project; nothing forced.

3. **Per-project mechanic (DP5).** For each project P, run
   `sync-all --project-dir P` **from the harness worktree's scripts**
   (`/mnt/work/flex-harness/skills/pairmode/scripts`), which bakes the worktree
   `pairmode_scripts_dir`, the thin-harness `CLAUDE.build.md` template, and
   `pairmode_version 0.3.0`. Sequence: `--dry-run` (preview the rewrite) →
   `--apply` → verify a build round → confirm `pairmode_version` advanced to
   `0.3.0`. (FLEX_DIR repoint is optional, nag-only.)

4. **DP6 dogfood detail.** States that flex builds HARNESS001–005 with its
   existing 0.2.x loop and flips its own loop last at HARNESS006; the
   resolver/leaf workers are exercised only by their own tests until the flip;
   progressively wiring the resolver into the live loop during 001–005 is
   explicitly forbidden (voids the additive guarantee).

5. **Pre-fold discovery gate (DP8).** States that the authoritative read-only
   fleet-discovery run (RELEASE-005's tool) executes immediately BEFORE the fold
   and is a hard gate: any un-migrated bound project must be migrated (or
   consciously accepted) before the fold proceeds, because the fold makes
   `/mnt/work/flex` = 0.3.0 and would break un-migrated bound projects.

6. **Final fold sequence.** After all opted-in projects are migrated and the
   discovery gate passes:
   - fold `harness → main` (main becomes 0.3.0, unified);
   - tag `v0.3.0`;
   - re-sync each migrated project so `pairmode_scripts_dir` points back at the
     canonical `/mnt/work/flex` (no longer the transient worktree);
   - remove the transient `/mnt/work/flex-harness` worktree.

7. **Execution timing note.** The runbook states explicitly: authored in
   HARNESS001-ante1 (this story), executed at/after HARNESS006 — it is a plan,
   not an action taken now.

8. The runbook cross-references the settled agreements
   (`docs/agreements/HARNESS001-ante1.md`, DP5 + DP6 + DP8) as the authority.

## Implementation guidance

- Create `docs/harness-cutover-runbook.md` only. Transcribe the sequence and
  mechanics from DP5/DP6 (and the DP8 gate) — faithful transcription, not new
  design.
- Use concrete commands where DP5 specifies them, e.g.:
  ```bash
  # Per project P, run FROM the harness worktree's scripts:
  PATH=$HOME/.local/bin:$PATH uv run python \
    /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
    sync-all --project-dir P --dry-run
  #   then --apply, verify a build round, confirm pairmode_version == 0.3.0
  ```
- Make the section order match the execution order: strategy → flex-first
  dogfood → canary → rest → discovery gate → fold/tag/repoint/worktree-removal.
- Do NOT run any of these commands; this is an authored doc.

## Tests

Doc story — no test file expected. Verification by grep for the required
sections:

```bash
# File exists with the required section anchors
grep -nE "Option Y|opt-in|do-nothing" docs/harness-cutover-runbook.md
grep -nE "flex (itself )?first|canary|rolling" docs/harness-cutover-runbook.md
grep -nE "sync-all --project-dir|dry-run|--apply|0\.3\.0" docs/harness-cutover-runbook.md
grep -nE "discovery|pre-fold|hard gate" docs/harness-cutover-runbook.md
grep -nE "fold|v0\.3\.0|re-sync|remove the (transient )?worktree" docs/harness-cutover-runbook.md
grep -nE "executed at/after HARNESS006|authored" docs/harness-cutover-runbook.md

# Test suite passes unchanged
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Executing any part of the migration (runs at/after HARNESS006).
- The version finalization edit `0.3.0-dev → 0.3.0` itself (a runbook step
  describes it; the actual edit happens at the flip, on the harness line).
- The fleet-discovery TOOL (built in RELEASE-005); this runbook only invokes it
  as the pre-fold gate.

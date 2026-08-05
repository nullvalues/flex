---
id: INFRA-387
rail: INFRA
title: Apply to-030 stale-hook repair across remaining fleet repos
status: deferred
phase: "121"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
primary_files:
  - docs/fleet-hook-repair-20260804.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The 2026-08-04 `fleet_discovery.py` scan found 13 fleet repos still on pairmode
0.3.0 whose `.claude/settings.json` hardcodes `uv run python
/mnt/work/flex-harness/hooks/*.py` for PreToolUse/PostToolUse/UserPromptSubmit/
SessionStart — four duplicate hook groups per repo, each duplicating the correct
`${CLAUDE_PLUGIN_ROOT}/hooks/*.py` entry the marketplace-installed plugin already
provides. The operator has already repaired two repos by hand (`/mnt/work/Repo-E`,
`/mnt/work/Repo-O`) with a `to-030` + `audit-hooks` sequence; both now report 0.3.1 with
zero duplicate/machine-absolute groups. This story formalises that manual precedent
at fleet scale using the mechanism INFRA-386 folds into `sync-all`. It writes no
flex source code: its whole output is 13 other repos' repaired `settings.json` plus
a per-repo log of what happened.

## Requires

- **INFRA-386 complete (same phase).** Its fold-in is the mechanism this story runs.
  Before starting, read `docs/stories/INFRA/INFRA-386.md` and the landed
  `pairmode_sync.py` to get the exact subcommand and flags it settled on — this
  story deliberately does not hardcode them (INFRA-386 may land the repair as a
  fifth `sync-all` step, or as a separate `to-030 --hooks-only` mode).
- The flex checkout at `/mnt/work/flex` is on `main` with INFRA-386 merged; all
  commands below are invoked **from `/mnt/work/flex`** with `--project-dir <repo>`.
- The fleet target version is read at build time from
  `skills/pairmode/scripts/_version.py`'s `PAIRMODE_VERSION` (0.3.1 as of writing).
  Use that value, not a literal, when judging a repo repaired.

## Ensures

- Each of the 13 target repos below, re-scanned by `uv run python
  skills/pairmode/scripts/fleet_discovery.py --json --no-snapshot`, reports zero
  `actionable` entries in `duplicate_hooks`, an empty `machine_absolute_hooks`
  list, and `signal2_value` equal to `PAIRMODE_VERSION` — **or** appears in the log
  as an explicitly-reasoned `SKIPPED`/`FAILED` row.
- `docs/fleet-hook-repair-20260804.md` exists and contains one row per target repo
  with its outcome (`REPAIRED` / `SKIPPED` / `FAILED`), the reason for any
  non-`REPAIRED` row, and the repo's pre-mutation `git status --porcelain`
  cleanliness. Forbidden proxy: a summary that reports only the aggregate count of
  repaired repos, with per-repo outcomes unrecoverable.
- No target repo with a dirty working tree at the moment of inspection had its
  `settings.json` rewritten: it is logged `SKIPPED` with the dirty paths named.
  Forbidden proxy: a printed warning about the dirty tree followed by the write.
- A repo that errors mid-run leaves the remaining repos processed: the run's own
  exit is not gated on all 13 succeeding, and the log distinguishes the failure
  from the successes. Forbidden proxy: an abort on first failure that leaves later
  repos unvisited and unlogged.
- The final whole-fleet re-scan output, quoted in the log, shows no repo outside the
  two documented exclusions carrying `actionable` duplicate or machine-absolute
  hook findings.

### Target repos (13)

`/mnt/work/` + each of: `Repo-A`, `Repo-B`, `Repo-C`, `Repo-D`, `Repo-F`,
`Repo-G`, `Repo-H`, `Repo-I`, `Repo-J`, `Repo-K`, `Repo-L`, `Repo-M`, `Repo-N`.

## Instructions

1. Read `docs/stories/INFRA/INFRA-386.md` and the landed `pairmode_sync.py` to fix
   the exact repair invocation. Primary mechanism: `uv run python
   skills/pairmode/scripts/pairmode_sync.py sync-all --project-dir <repo> --apply
   --yes` (the fifth step INFRA-386 adds). If INFRA-386 landed a different shape,
   use what it landed and say so in the log header. The standalone fallback — only
   if INFRA-386's fold-in is unusable for a given repo — is the operator's precedent
   pair: `pairmode_migrate.py to-030 --project-dir <repo> --apply` then
   `pairmode_sync.py audit-hooks --project-dir <repo> --apply --yes`.
2. For each target repo, in order:
   a. If the path does not exist, log `SKIPPED (absent)` and continue.
   b. Run `git -C <repo> status --porcelain`. If non-empty, log `SKIPPED (dirty)`
      with the paths and continue — do not stash, do not overwrite. These are other
      operators' working trees.
   c. Run the mechanism in dry-run (omit `--apply`) and record the planned actions.
   d. Run it with `--apply --yes`.
   e. Re-run `fleet_discovery.py --json --no-snapshot`, read this repo's entry, and
      log `REPAIRED` only if it satisfies the per-repo assertion in `## Ensures`;
      otherwise log `FAILED` with the residual findings.
   f. Wrap the per-repo body so a non-zero exit or exception is caught, logged
      `FAILED`, and the loop continues to the next repo.
3. After all 13, run the whole-fleet scan once more and record it in the log.
   `fleet_discovery.py`'s candidate list is `registered_projects` plus documented
   directory names under `/mnt/work/`, so it includes entries that are not
   pairmode-bound targets (absent directories, non-flex repos). Judge "clean" only
   over repos that report a `pairmode_version` signal; list any other entry with
   findings in the log with a one-line note on why it is out of scope.
4. Write `docs/fleet-hook-repair-20260804.md` with: the mechanism actually used, the
   per-repo outcome table, and the final scan excerpt. This file is the story's
   deliverable — a transcript is not a substitute.
5. Do not modify any file inside a target repo other than what the pairmode commands
   themselves write, and do not commit in any target repo. Repaired repos are left
   with the change in their working tree for their own operator to commit
   (consistent with 2b: their trees are theirs).

## Tests

No new flex code is introduced, so no new test file is expected — this story is
operational/fleet-maintenance work whose verification is the scan in `## Ensures`,
not a unit test. Two gates instead:

```bash
# 1. Regression: the flex suite is unchanged by this story.
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q

# 2. Acceptance: whole-fleet re-scan after all 13 repos are processed.
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/fleet_discovery.py \
  --json --no-snapshot
```

Acceptance: suite green (unchanged from pre-story baseline), and gate 2's output
satisfies the final `## Ensures` assertion, quoted in
`docs/fleet-hook-repair-20260804.md`. Reviewers: the "no test file" case here is the
explicitly-justified operational exception in `CLAUDE.md`'s review checklist, not an
omission.

## Out of scope

- **`/mnt/work/Repo-E` and `/mnt/work/Repo-O`** — already repaired manually by the
  operator and confirmed clean. Do not re-touch them; they appear in the final scan
  only as evidence, never as targets.
- The `sync-all` fold-in itself — INFRA-386 owns that change. This story only runs
  what INFRA-386 ships and must not edit `pairmode_sync.py` or
  `pairmode_migrate.py`. If the fold-in proves wrong for a repo, file the finding;
  do not fix it here.
- Upgrading target repos beyond the hook repair (agent resync, narrative backfill,
  CLAUDE.build.md rewrites) beyond whatever the INFRA-386 mechanism already performs
  as part of its normal run.
- Committing or pushing in any target repo.

## Spec notes

- `primary_files:` is empty and left empty: this story writes no file inside the
  flex checkout except its own deliverable log, and `touches:` gains no test path
  because none exists for it. Flagged to the operator via `SPEC-RESULT: revised` —
  if the log path `docs/fleet-hook-repair-20260804.md` should be declared scope,
  the operator should add it before dispatch.
- spec-preflight reports four findings, all intentional: `scope:` on
  `fleet_discovery.py`, `pairmode_sync.py`, and `docs/stories/INFRA/INFRA-386.md`
  — all three are read/invoke-only references that this story is explicitly
  forbidden to edit (see `## Out of scope`), so they are correctly absent from
  declared scope; and constant warnings on `REPAIRED`/`FAILED`, which are log row
  labels this story creates, not source constants.
- Ideology check (Step 4a): no conflict. The story is read-then-write-then-verify
  with a per-repo audit record, which serves "never silently pass contradictions"
  (a dirty target tree is surfaced and skipped, never overwritten) and touches no
  hook/sidebar layering constraint — it removes hook registrations, it does not add
  logic to hooks.

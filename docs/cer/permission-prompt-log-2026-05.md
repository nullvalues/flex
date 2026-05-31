# Permission-prompt fire log — CER-029 Part 1 triage

*Opened: 2026-05-29. Closes when N≥10 fires recorded or when bucket
distribution is conclusive (whichever comes first).*

Purpose: capture every permission-prompt fire during builder turns to
classify against the four CER-029 buckets and decide whether CER-029 is
real signal or legacy denylist cruft.

## Bucket reference (from CER-029)

- **(a) Legacy cruft.** Target file IS in active story's `primary_files`
  +`touches`, but a static rule in `.claude/settings.json` or
  `settings.local.json` still gates it. Fix: expunge the static rule.
- **(b) Spec quality.** Target file is NOT in declared scope but is
  legitimately needed for the story. Fix: story scoping is wrong;
  primary_files/touches needs to grow before build.
- **(c) Layer-2 CLAUDE.md "Protected files" rule.** Target is in the
  hand-maintained protected list (`sidebar.py`, `plugin.json`, `hooks/`,
  `skills/seed/scripts/`, etc.). Same LLM-attention failure mode as
  CER-027 — mechanical-enforcement template applies.
- **(d) Breakout containment.** Target is genuinely sensitive
  (`.git/`, `.claude/settings.json` itself, plugin manifests). Fire is
  correct; rule stays as static deny.

## How to log a fire

When auto mode drops out for a permission prompt during a builder turn,
append one row below. Fast capture; classify in the moment if obvious,
or leave bucket as `?` and triage in batch later. Cheap data — don't
over-think; one row per fire even if multiple files in the same prompt.

## Log

| Date | Phase/Story | File asked for | Rule that fired (file:line if known) | Bucket | Notes |
|------|-------------|----------------|--------------------------------------|--------|-------|
| _ex_ | _phase-47 / INFRA-127_ | _example: `skills/pairmode/scripts/context_budget.py`_ | _example: `.claude/settings.json` deny `skills/**`_ | _a_ | _example: file is in INFRA-127 primary_files; deny rule predates rail-aware scoping_ |
|      |             |                |                                      |        |       |
|      |             |                |                                      |        |       |
|      |             |                |                                      |        |       |

## Tally (update as rows accumulate)

| Bucket | Count | Running interpretation |
|--------|-------|------------------------|
| (a) Legacy cruft         | 0 | — |
| (b) Spec quality         | 0 | — |
| (c) Layer-2 Protected    | 0 | — |
| (d) Breakout containment | 0 | — |

## Closing this log

When closing: write a one-paragraph summary at the bottom naming which
bucket dominated, whether CER-029 should be promoted to "Do Now,"
demoted to "Do Never," or rescoped (e.g. if bucket (a) dominates,
CER-029 becomes a one-line `.claude/settings.json` cleanup story, not a
new mechanism). Update CER-029's status column with the link to this
closed log.

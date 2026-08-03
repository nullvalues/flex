---
id: INFRA-371
rail: INFRA
title: Close four residual doc/scoping seams left by INFRA-311 canon-retirement (CER-133)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-133 (MEDIUM): six residual seams left by INFRA-311's canon-retirement landing (attempt-3
review, non-blocking observations): (1) `pairmode_sync.py:1015,1074` still asserts `sync.py` has
no `--dry-run`, which is now false; (2) `RETIRED_SECTIONS` keys are not file-scoped, so a generic
section key could false-positive-match a genuine same-named extension in a different canonical
file — needs `(file, key)` scoping before a fleet-wide sync-all campaign; (3)
`docs/pairmode/PAIRMODE.md:45,165` still describes sync as non-destructive (the README/architecture
claims were fixed in-story, but this doc was outside that story's `touches:`); (4) audit's
RECOMMENDATION output and SKILL.md's "Already up to date" short-circuit never mention retirement
prunes, so an operator can be told up-to-date while registry-matched stale canon sits downstream;
(5) `skills/pairmode/SKILL.md:258` still claims sync "Never overwrites project-specific content
(EXTRA items)" — stale, since canon-retirement pruning does overwrite/remove registry-matched
retired sections; (6) `skills/pairmode/SKILL.md:844` still asserts sync-all's dry-run gap is
because `sync.py` has no `--dry-run` flag (same stale claim as item 1), and additionally
`pairmode_sync.py`'s `sync_all` (~1073-1076) hard-skips invoking `sync.py` at all outside `--apply`
mode (`skip_in_dry_run=True`), making `sync.py`'s real `--dry-run` flag unreachable from the
sync-all wrapper even though it exists and works when invoked directly. Files:
`skills/pairmode/scripts/pairmode_sync.py`, `docs/pairmode/PAIRMODE.md`,
`skills/pairmode/SKILL.md`. Gate was "before the post-0.3.1 fleet sync campaign" — item 2
especially matters at fleet scale.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests

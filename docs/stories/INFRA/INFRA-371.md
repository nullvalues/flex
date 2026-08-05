---
id: INFRA-371
rail: INFRA
title: Close four residual doc/scoping seams left by INFRA-311 canon-retirement (CER-133)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
  - skills/pairmode/SKILL.md
  - docs/pairmode/PAIRMODE.md
touches:
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/scripts/sync.py
  - tests/pairmode/test_pairmode_sync.py
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_sync.py
  - docs/architecture.md
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

Note on the count: the frontmatter title says "four" seams (the CER's original framing); the
CER was later extended to six (items 5 and 6 above). All six are in scope for this story. The
title is left unedited so the ID/title pair stays stable against the phase manifest.

## Requires

- INFRA-311 (canon retirement) landed — `RETIRED_SECTIONS` and the retirement-prune path exist in
  `skills/pairmode/scripts/pairmode_sync.py`, and `sync.py` already has a working `--dry-run` flag.
- No dependency on any other Phase 119 story. INFRA-364 also edits `skills/pairmode/SKILL.md`, but
  at disjoint locations (~lines 373-377 and ~622-648, the `review`/`cer` duplicate block) — this
  story edits ~lines 258 and 844. Confirmed non-overlapping; either order is safe.

## Ensures

1. **Stale `--dry-run` claims are gone.** No comment, docstring, or message string in
   `skills/pairmode/scripts/pairmode_sync.py` (items 1: ~lines 1015, 1074) or in
   `skills/pairmode/SKILL.md` (item 6: ~line 844) still asserts that `sync.py` has no `--dry-run`
   flag. Verifiable by grep: no surviving occurrence of that claim in either file.
2. **`sync_all`'s dry-run mode actually reaches `sync.py`.** The `skip_in_dry_run=True` hard-skip
   that prevents `sync_all` from invoking `sync.py` outside `--apply` is removed, and a dry-run
   `sync_all` run invokes `sync.py` with `--dry-run` rather than skipping it. *Forbidden proxy:*
   correcting only the SKILL.md/comment wording about the gap while `sync.py` remains unreachable
   from the wrapper in dry-run mode. `docs/architecture.md`'s own description of `sync_all`'s
   dry-run behavior (it currently states sync.py is skipped in dry-run because it has no
   `--dry-run` flag) is updated to match this new behavior — a standing surface, so no
   frontmatter declaration is needed to touch it, but it must not be left contradicting this
   same Ensures item.
3. **`RETIRED_SECTIONS` is file-scoped.** Retirement entries are keyed by `(canonical file,
   section key)`, not by section key alone, and the prune path only fires for the canonical file a
   retirement was recorded against. A test asserts that a section whose key matches a retirement
   entry but which lives in a *different* canonical file is left intact. *Forbidden proxy:*
   keeping a flat key-only registry and relying on section names happening to be unique today.
4. **`docs/pairmode/PAIRMODE.md` no longer describes sync as non-destructive** at the two cited
   spots (~lines 45, 165); the corrected text states that registry-matched retired sections are
   pruned. No other claim in that file changes.
5. **`skills/pairmode/SKILL.md` ~line 258 no longer claims sync "Never overwrites project-specific
   content (EXTRA items)" unqualified** — the corrected text names the registry-matched
   canon-retirement prune as the exception.
6. **Up-to-date reporting accounts for pending prunes.** When a registry-matched retired section is
   present downstream, neither `audit.py`'s RECOMMENDATION output nor the SKILL.md "Already up to
   date" short-circuit path reports the target as up to date without naming the pending retirement
   prune. A test asserts this for the audit output. *Forbidden proxy:* adding a prose caveat to
   SKILL.md while the audit code path still emits an unqualified up-to-date recommendation.
7. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` is green.

## Instructions

1. Re-read each cited location in the current working tree before editing — the line numbers in
   Context come from the INFRA-311 attempt-3 review and may have shifted.
2. Item 2 (`sync_all`'s `skip_in_dry_run=True`, ~lines 1073-1076) is the one behavioral change with
   real blast radius: after removing the skip, dry-run `sync_all` will start producing `sync.py`
   output it previously never produced. Make sure that output is reported, not swallowed, and that
   nothing in dry-run mode now writes — `sync.py --dry-run` must remain read-only.
3. Item 3 is the fleet-scale one: change the `RETIRED_SECTIONS` structure to carry the canonical
   file alongside the section key, and update every read site of that constant. Prefer a
   straightforward shape (e.g. tuple keys or a per-file mapping) over a new abstraction — the
   requirement is scoping, not a registry redesign.
4. Item 6 spans code and doc: the audit RECOMMENDATION path is the load-bearing half (an operator
   acting on it can leave stale canon downstream); the SKILL.md short-circuit wording must match
   whatever the code now emits, not describe an aspiration.
5. Keep edits surgical. Do not restructure `pairmode_sync.py`, do not rewrite unrelated sections of
   `PAIRMODE.md` or `SKILL.md`, and do not touch `skills/pairmode/SKILL.md` lines ~373-377 or
   ~622-648 (INFRA-364's scope).
6. Ideology alignment (INFRA-242, checked): item 3's file scoping and item 6's pending-prune
   disclosure both serve "never silently pass contradictions" — a false-positive prune and a false
   up-to-date report are the two ways this subsystem could silently diverge from canon. No
   conviction, accepted constraint, or prototype fingerprint is contradicted by this draft.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_sync.py tests/pairmode/test_audit.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green, and the first run includes new tests covering (a) a same-named section in a
non-matching canonical file surviving the prune (item 3), (b) dry-run `sync_all` invoking `sync.py`
with `--dry-run` instead of skipping it (item 2), and (c) audit RECOMMENDATION naming a pending
retirement prune rather than reporting up to date (item 6).

## Out of scope

- Running the fleet-wide sync-all campaign itself. This story closes the seams that gate it; the
  campaign is separate operator-initiated work.
- Any change to `sync.py`'s own `--dry-run` implementation — it already exists and works when
  invoked directly; only the wrapper's reachability of it is in scope.
- Any broader rewrite of `docs/pairmode/PAIRMODE.md` or `skills/pairmode/SKILL.md` beyond the
  specific stale claims named in Ensures 1, 4, 5, and 6.
- Sibling-repo copies (flex-harness, anchor, Repo-G) of any of these files — they receive changes via
  the existing release-promotion/sync mechanism, not a parallel manual edit here.

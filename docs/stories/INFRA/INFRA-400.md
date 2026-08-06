---
id: INFRA-400
rail: INFRA
title: Close CER-172 scrub completeness and regression gaps (CER-188)
status: draft
phase: "130"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_discovery.py
  - skills/pairmode/scripts/scrub_fleet_names.py
  - .pairmode-fleet.local.json.example
touches:
  - tests/pairmode/test_fleet_discovery.py
  - tests/pairmode/test_scrub_fleet_names.py
  - skills/pairmode/scripts/fleet_map.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 125 (INFRA-393/394) de-identified fleet repo references by moving the
real-name → label mapping out of tracked code and into the gitignored
`.pairmode-fleet.local.json`, then scrubbing tracked files against that map.
A security-auditor pass on the checkpoint (CER-188) found the result both
**incomplete** and **regression-prone**: the local map declares fewer repos
than actually exist on disk under the fleet root (at least one entry dropped
during externalization, others never added), and because `scrub_fleet_names.py
--verify` derives its notion of "what to look for" from that same map, it
reports clean while real names remain in tracked files — a self-certifying
check. Separately, `fleet_discovery.py` still writes real absolute repo paths
straight into the tracked snapshot document (a live re-leak channel), the
scrub script prints the matched real literal in its own hit and error output,
and nothing mechanically requires `--verify` to pass before a commit lands.
This story closes all four: reconciliation, write-time anonymization,
leak-free reporting, and a mechanical gate.

**Privacy rule for this story (applies to the builder too):** no real fleet
repo name may appear in any tracked file produced by this work — not in code,
not in tests, not in fixtures, not in commit messages. Every test fixture uses
synthetic names (e.g. `Fakeproject-X`, `Synthrepo-Two`). The one-time
reconciliation against the real on-disk set is performed locally against the
gitignored map; only counts and pass/fail outcomes are ever spoken aloud.

## Requires

- INFRA-393 and INFRA-394 complete on `main` (the externalized
  `.pairmode-fleet.local.json` map and `scrub_fleet_names.py` exist).
- A populated `.pairmode-fleet.local.json` present in the local working tree
  (gitignored; not readable from a clean clone — code must degrade gracefully
  when it is absent rather than crash).


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| skills/pairmode/scripts/fleet_map.py | new shared loader module factoring the fleet-map parser out of scrub_fleet_names.py so fleet_discovery.py's write-time anonymization uses the same implementation (Instructions 3) | 2026-08-06T00:36:05Z |

## Ensures

1. `scrub_fleet_names.py --verify` performs a **map/disk reconciliation**: it
   compares the repo set declared in `.pairmode-fleet.local.json` against the
   sibling-directory set under the configured fleet root and exits nonzero,
   naming the count and the *unmapped directory path only*, when any on-disk
   sibling repo has no map entry. Forbidden proxy: a warning line while
   `--verify` still exits 0.
2. A test using a synthetic tmp fleet root (directories `Fakeproject-X`,
   `Fakeproject-Y`) and a synthetic map declaring only `Fakeproject-X` asserts
   the reconciliation fails; a control test where the map covers both asserts
   it passes.
3. `fleet_discovery.py`'s snapshot-writing path maps every repo path through
   the same `.pairmode-fleet.local.json` mapping **before** the snapshot text
   is composed, so the rendered snapshot contains only labels. A test drives
   the snapshot writer with a synthetic map and synthetic repo path and
   asserts the returned/written snapshot text contains the label and does not
   contain the synthetic real path or its basename. Forbidden proxy: relying
   on a later `scrub_fleet_names.py` pass to clean the file after it is
   written.
4. When a repo path has **no** entry in the map, `fleet_discovery.py`'s
   snapshot path does not write the raw path — it writes a stable
   non-identifying placeholder (e.g. `<unmapped-repo-N>`) and reports the gap
   on stderr. A test asserts the unmapped synthetic path does not appear in
   the snapshot text.
5. `scrub_fleet_names.py`'s hit reporting and every raised/`print`ed error
   path emit `<label> — <file>:<line>` and never the matched literal. A test
   builds a synthetic tracked file containing `Fakeproject-X`, runs the
   scan, and asserts `Fakeproject-X` is absent from combined
   stdout/stderr/exception text while the label and `file:line` are present.
6. `scrub_fleet_names.py install-hook` writes an executable
   `.git/hooks/pre-commit` (into the repo root passed to it) that invokes
   `scrub_fleet_names.py --verify` and aborts the commit on nonzero exit. A
   test installs the hook into a tmp git repo whose synthetic map/tree fail
   verification, executes the generated hook, and asserts nonzero exit; a
   control with a passing tree asserts exit 0. Forbidden proxy: a hook that
   prints a warning and exits 0.
7. `.pairmode-fleet.local.json.example` documents the fleet-root key that
   reconciliation reads, using synthetic placeholder names only.

## Instructions

1. **Reconciliation (finding 1, CRITICAL).** Add to `scrub_fleet_names.py` a
   reconciliation step that runs as part of `--verify`: read the fleet root
   (new optional key in `.pairmode-fleet.local.json`, defaulting to the
   parent directory of the project root), list its immediate subdirectories
   that look like repos (contain `.git`), and fail when any is absent from the
   map. Skip the check with an explicit stderr notice (still exit 0) when the
   local map file is absent, since a clean clone has none — but never skip
   silently when the map *is* present.
2. Perform the one-time real reconciliation locally: run the new `--verify`
   against the actual fleet root, add every missing entry to the local
   (gitignored) `.pairmode-fleet.local.json`, then re-run `--verify` plus the
   full scrub so any newly-covered real names get scrubbed out of tracked
   files. Cross-check the map's entry count against the pre-INFRA-393
   hardcoded list via `git show <pre-INFRA-393-commit>:<path>` and compare
   **counts only**. Report the before/after counts in the build result; never
   write a real name into any tracked file, test, or commit message.
3. **Write-time anonymization (finding 2, HIGH).** In `fleet_discovery.py`,
   load the same map used by `scrub_fleet_names.py` (factor the loader into
   one place rather than duplicating the parse) and translate each repo path
   to its label at the point the snapshot record is built, before any string
   is appended to the snapshot document. Unmapped paths get the placeholder
   from Ensures 4.
4. **Leak-free reporting (finding 3, MEDIUM).** Change every hit-report and
   error/exception message in `scrub_fleet_names.py` that currently embeds the
   matched literal to emit the mapped label plus `file:line` instead. Grep the
   module for f-strings interpolating the matched value and convert all of
   them, not just the primary reporter.
5. **Mechanical gate (finding 4, MEDIUM).** This project has no CI, and flex's
   own Claude Code hooks are constrained to thin relays with no blocking logic
   (`docs/ideology.md` § Accepted constraints, "Hooks are thin relays only"),
   so the gate must not be added there. Chosen mechanism: a **git**
   `pre-commit` hook — a different layer from the hook-pipe-sidebar boundary
   that constraint protects — generated by a new `install-hook` subcommand on
   `scrub_fleet_names.py` so the hook body stays versioned in tracked code
   while the installed artifact remains local. Record this rationale in a
   short comment above the subcommand. (Inline ideology resolution per
   Step 4a: routing the gate to git rather than a flex hook preserves the
   thin-relay constraint's rationale while still satisfying "must block".)
6. Add the tests named in `## Ensures` to `tests/pairmode/test_scrub_fleet_names.py`
   and `tests/pairmode/test_fleet_discovery.py`, using `tmp_path` fixtures and
   synthetic names throughout. No fixture, docstring, or assertion message may
   contain a real fleet repo name.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_scrub_fleet_names.py tests/pairmode/test_fleet_discovery.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green. Additionally, `uv run python
skills/pairmode/scripts/scrub_fleet_names.py --verify` exits 0 against the
working tree *after* step 2's map reconciliation, and
`git grep -nE '<synthetic-name-pattern>' -- tests/` shows only synthetic
fixture names.

## Out of scope

- **Git history remediation** — real names in pre-scrub commits. Tracked as
  CER-192, deferred pending an operator decision. This story must not rewrite,
  filter, or force-push history under any circumstance.
- CER-189 (template example key shape), CER-190 (case-variant and
  domain-suffix matching blind spots), and CER-191 (candidate-coverage
  regression) — three LOW findings that may be picked up in a later story.
- Documenting the new git pre-commit gate in `docs/architecture.md` — a
  docs-only follow-up; this story ships the mechanism and its inline
  rationale comment.
- Editing `docs/ideology.md` — it is cited in `## Instructions` only as the
  source of the thin-relay constraint's rationale, so spec-preflight's
  `scope:` finding for it is intentional and deliberately not added to
  `touches:`.

---
id: RESOLVER-010
rail: RESOLVER
title: "`check-index` graph-invariant checker (`index_integrity.py` + CLI)"
status: complete
phase: "HARNESS008-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/index_integrity.py
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_index_integrity.py
touches:
  - skills/pairmode/scripts/next_story.py
---

## Context

The housekeeper core (agreements `HARNESS008-main.md` DP1/DP2; CER-056). The Era 002 close-out
exposed that nothing catches "a built story still marked `planned`" (eight drift stories; a stale
era table; a deferred phase read as active). This story consolidates scattered integrity logic
into a single pure-read `index_integrity.py` exposed via an additive `flex_build.py check-index`
CLI.

## Requires

- HARNESS001 complete: `next_story.py` commit-authority (`_git_log_oneline` / `_has_story_commit`)
  and the index parsers exist to reuse.

## Ensures

- `skills/pairmode/scripts/index_integrity.py` — a pure-read module (no writes; `grep` confirms)
  computing the four graph invariants and returning structured violations:
  1. **Status drift** — a story with a `feat(story-<ID>)` commit in `git log` but status not
     `complete`/`deferred`.
  2. **Cross-link consistency** — every index phase has a file; every story's `phase` frontmatter
     names an existing phase doc; every era's phase table matches index truth; **deferred/backlog
     phases are treated as inactive** (CER-056).
  3. **Orphan story files** — a `docs/stories/<RAIL>/<ID>.md` not referenced in any phase doc's
     Stories table.
  4. **Deferred without section** — a story marked `deferred` whose phase doc lacks a
     `## Deferred stories` section naming it.
- It **reuses** `next_story.py` commit-authority and the existing index parsers — no duplicated
  git/parse logic.
- `flex_build.py check-index --project-dir .` (additive — freeze green) runs the checker, prints
  each violation's IDs/paths + a one-line reason, and **exits non-zero** on any violation, zero
  on a clean graph. It writes nothing.
- `tests/pairmode/test_index_integrity.py` asserts deterministically (synthetic project trees +
  synthetic git logs via `resolver_fixtures`): one fixture per violation class flags exactly it;
  a clean tree → exit 0, empty report; a `deferred` phase fixture is treated as inactive.
- `test_cli_surface_freeze.py` stays green (additive command).
  `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Keep `index_integrity.py` pure-read and composable by the resolver read-model (RESOLVER-011
  wires it in).
- Implement CER-056's deferred/backlog-as-inactive rule in the shared index read so both
  `check-index` and the resolver honor it (single source). `next_story.py` is `touches` —
  reuse its helpers; modify only if a helper must be exposed (declared).
- The checker **reports**; it does not mutate story status (no auto-repair — DP4).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_index_integrity.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cli_surface_freeze.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: the four invariants detected; per-violation-class fixtures flag exactly their
violation; clean tree exit 0; deferred treated inactive; pure-read; freeze green; suite green.

### Out of scope

- Auto-repair of drifted status (operator/close-out action).
- Wiring `check-index` as a hard checkpoint gate (advisory CLI now).
- Resolver read-model composition + isolation suite — RESOLVER-011.

---
era: "003"
---

# project — Phase 103: Worktree and story-stub friction remediation (CER-090, CER-092)

← [Phase 102: Effort-recording smoke test and harness release-channel fast-forward](phase-102.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Remove the two per-story friction defects phase 102 exposed: make the vendored observability node_modules complete under git so fresh story worktrees pass the UI build gate without manual payload rsync (CER-090), and fix story_new.py's stub frontmatter so a freshly-stubbed story no longer crashes create-story-worktree (CER-092).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-261 | Track the full vendored observability node_modules payload — un-gitignore build//dist under vendored trees so fresh story worktrees pass the UI build gate (CER-090) | complete |
| INFRA-262 | Fix story_new.py stub frontmatter — emit parseable touches and invert the test pinning the trailing-comment bug (CER-092) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-103 Cold-eyes checklist

Filled by the orchestrator at cp-103 (2026-07-25).

- **CER-090 closed (INFRA-261):** the vendored observability `node_modules`
  payload (1613 files, ~24 MB of dist/build output previously swallowed by the
  broad `node_modules` gitignore) is now fully tracked; a fresh throwaway
  worktree passed `pnpm --filter @flex-obs/ui build` and the full
  `tests/pairmode/` suite with no rsync/pnpm-install repair. The carried
  known failure `test_ui_build_emits_dist_index_html` now passes; the
  `pytest -x` masking caveat for it is retired. Guard test
  `test_vendored_payload_tracked.py` pins the invariant.
- **CER-092 closed (INFRA-262):** `story_new.py` emits parseable `touches: []`
  (INFRA-186 prompt relocated to the story body) and
  `schema_validator._parse_frontmatter` strips inline comments from scalars via
  the shared `_strip_inline_comment` helper — unblocking both fresh stubs and
  the 20 already-on-disk trailing-comment stubs.
- **Gates:** security PASS (0 blocking; advisories: MEDIUM — second native
  binary `test_extension.node` tracked but not enumerated in the INFRA-261
  spec; LOW — `story_new` title quoting doesn't escape embedded quotes or
  newlines; LOW — quoted scalar + trailing comment retains its quotes after
  parsing). Intent ALIGNED (both stories built line-for-line to spec; one
  environmental finding: stray upstream-shipped `.claude/settings.local.json`
  dirs under two vendored packages broke the new guard test's allow-list on
  this machine — removed at checkpoint; allow-list brittleness noted for
  backlog). Docs gate: see checkpoint record.
- **New backlog from this phase:** guard-test allow-list tolerance for
  `.claude/` artifact dirs under vendored `node_modules`, plus the three
  security advisories above.
- **Schema delivery:** no new persistent schema objects introduced (table
  intentionally empty).
- **Release-channel promotion:** performed post-tag per
  `docs/architecture.md` § Release channel.

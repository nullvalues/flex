---
id: INFRA-390
rail: INFRA
title: Trim CHANGELOG.md under the 200-line test gate
status: complete
phase: "121"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - CHANGELOG.md
touches:
  - tests/pairmode/test_docs.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

`tests/pairmode/test_docs.py::test_changelog_exists_and_under_200_lines` requires
`CHANGELOG.md` to have `len(lines) < 200`. The file is currently exactly 200
lines, so the assertion fails, and it has been recurring as a "pre-existing,
unrelated" failure blocking review on INFRA-386, INFRA-387, and INFRA-389 —
stories that otherwise pass. `CHANGELOG.md` is reverse-chronological (`##
[Unreleased]` first, oldest phase last) and already states it "loosely
follows" Keep a Changelog; there is no other documented trim/archival
convention for it. This story trims the oldest entries so the gate passes
again, with enough margin that the next phase's `## [Unreleased]` entry
doesn't immediately re-trip it.

## Requires

None — the file and the failing test both already exist on disk.

## Ensures

1. `CHANGELOG.md` has fewer than 170 lines total (`wc -l` / `len(lines)` <
   170) — comfortably under the test's `< 200` gate, not merely one line
   under it, so the next phase's `## [Unreleased]` addition doesn't
   immediately re-trip the same failure.
2. Every entry from `## [Unreleased]` down through and including the
   `### Fixed [core] — Phase 111 (Plugin packaging repair)` heading (era-004's
   start) is preserved byte-identical and in the same order — nothing in
   that range is reworded, reordered, or condensed. Forbidden proxy: passing
   the line-count check by condensing recent phase entries instead of only
   removing older ones.
3. Everything strictly older than Phase 111 (starting at
   `### Added [pairmode] — Phase 110 (Effort-recording data-flow
   remediation, CER-101..104)` and continuing down through the
   `## [pairmode v0.0.x] — Phases 1-16` section and the trailing `### Notes`
   section) is removed as whole headings/sections — no section is cut
   mid-bullet, and no `##`/`###` heading is left with only a fragment of its
   original bullets.
4. The removed range is replaced by exactly one line, placed where the first
   removed heading used to be, stating that older history was trimmed and
   pointing at how to recover it (`git log -- CHANGELOG.md` or an equivalent
   git-history pointer) — the removal is documented in the file itself, not
   silent.
5. `tests/pairmode/test_docs.py::test_changelog_exists_and_under_200_lines`
   passes.

## Instructions

1. In `CHANGELOG.md`, delete every heading and its bullets starting at
   `### Added [pairmode] — Phase 110 (Effort-recording data-flow
   remediation, CER-101..104)` through the end of the file. This includes
   Phase 110 down to Phase 95, the `HARNESS015-main`/`HARNESS009-main`
   entries, the old `Phase 17-20`/`Changed [core]` bullet lists, the
   `## [pairmode v0.0.x] — Phases 1-16` section, and the trailing `### Notes`
   section. Do not touch anything from `## [Unreleased]` through the end of
   the `### Fixed [core] — Phase 111 (Plugin packaging repair)` section —
   that range stays untouched (Ensures 2).
2. In the gap left by the deletion (immediately after the Phase 111 section,
   where the deleted content used to start), insert one line, in italics to
   match the file's existing `*...*` aside convention (see the Phase
   95/96/98 note already under `## [0.3.1]`):
   `*Entries older than Phase 111 were trimmed to stay under the CHANGELOG
   line-count test gate (tests/pairmode/test_docs.py); see `git log --
   CHANGELOG.md` for the full history.*`
3. Run `wc -l CHANGELOG.md` and confirm the result is under 170 (Ensures 1).
   If it is not (e.g. the Phase 111-and-newer range alone is longer than
   expected), trim further from the oldest remaining content first — never
   from the Phase 111-through-Unreleased range.
4. Do not edit `tests/pairmode/test_docs.py` — the 200-line threshold itself
   is out of scope (see Out of scope).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_docs.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green, including
`test_changelog_exists_and_under_200_lines`. Run the full suite without `-x`
so a real failure elsewhere is not masked.

## Out of scope

- Raising or otherwise changing the 200-line threshold in
  `tests/pairmode/test_docs.py` — this story only reduces `CHANGELOG.md`'s
  line count to fit the existing gate.
- Moving the trimmed history into a separate `CHANGELOG-archive.md` file or
  any other new artifact — the removed content is recoverable from git
  history only, per Ensures 4.
- `CONTRIBUTING.md`'s and `README.md`'s own line-count gates
  (`test_contributing_exists_and_under_200_lines`,
  `test_readme_under_400_lines`) — both are unaffected by this story and are
  not touched here.

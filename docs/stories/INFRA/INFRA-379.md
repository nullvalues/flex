---
id: INFRA-379
rail: INFRA
title: Derive test_plugin_manifest.py's expected skill names from skills/*/SKILL.md glob (CER-109)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_plugin_manifest.py
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-109 (LOW): `tests/pairmode/test_plugin_manifest.py::_EXPECTED_SKILL_NAMES` hardcodes the four
top-level skill names instead of globbing `skills/*/SKILL.md`, so a fifth skill added later would
ship unguarded against the `flex:` prefix regression the test exists to catch. Fix: derive the
expected skill-name set from a `skills/*/SKILL.md` glob rather than a literal list. File:
`tests/pairmode/test_plugin_manifest.py` (`_EXPECTED_SKILL_NAMES`). From the Phase-111 security
audit.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- No prior Phase 119 story. INFRA-379 touches only `tests/pairmode/test_plugin_manifest.py` and
  overlaps no other story in the phase.
- `tests/pairmode/test_plugin_manifest.py` currently passes against the shipped plugin manifest.

## Ensures

- `tests/pairmode/test_plugin_manifest.py` contains no literal list of skill names: the expected
  skill-name set is computed from a `skills/*/SKILL.md` glob rooted at the repo root. Forbidden
  proxy: a glob added alongside a retained literal list (intersected with it, used as a fallback,
  or asserted equal to it) — the literal must be gone, not shadowed.
- The derivation lives in a named helper (e.g. `_expected_skill_names(repo_root)`) that returns the
  set of directory names of every `skills/*/SKILL.md` match, and excludes a `skills/<name>/`
  directory that has no `SKILL.md`.
- The derivation fails loudly rather than vacuously passing: the test asserts the derived set is
  non-empty before comparing it against the manifest. Forbidden proxy: an empty glob result
  silently satisfying the manifest comparison.
- A unit test drives the helper against a synthetic `skills/` tree under `tmp_path` containing at
  least one directory with `SKILL.md` and one without, and asserts only the former appears.
- The manifest comparison/assertion logic the test already performs (the `flex:`-prefix check
  CER-109 names) is unchanged in behaviour — only the source of the expected set changes.
- `uv run pytest tests/pairmode/` is green apart from any pre-existing failure recorded before this
  story began.

## Instructions

1. In `tests/pairmode/test_plugin_manifest.py`, delete `_EXPECTED_SKILL_NAMES` and replace it with a
   helper that globs `skills/*/SKILL.md` under the repo root and returns `{p.parent.name for p in ...}`.
   Reuse whatever repo-root resolution the file already uses; do not introduce a second mechanism.
2. Preserve the existing name normalization: if the deleted literal entries were bare directory
   names, the helper returns bare directory names and the `flex:` prefix continues to be applied by
   the existing assertion code — do not move prefixing into the helper.
3. Guard against the vacuous pass: assert the derived set is non-empty before comparing to the
   manifest, so a broken glob or wrong root fails the test instead of trivially satisfying it.
4. Add a `tmp_path` unit test for the helper with a synthetic tree (one skill dir with `SKILL.md`,
   one without) so the derivation is covered independently of this repo's current skill count.
5. Do not edit the plugin manifest, and do not hardcode the current skill count (`4`) anywhere —
   that would reintroduce CER-109 in a second form.

Ideology note: the change is instructed as a derivation with an explicit non-empty guard rather than
a bare glob, to preserve the "never silently pass contradictions" constraint's rationale — a check
that can pass without having checked anything is the false-confidence failure that constraint exists
to prevent.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_plugin_manifest.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance: the targeted file passes, including the new `tmp_path` helper test; the full
`tests/pairmode/` suite is green apart from any failure that was already failing before this story.
Run the full suite without `-x` so a pre-existing failure cannot mask a new one.

## Out of scope

- Nested sub-skills (`skills/*/skills/*/SKILL.md`, e.g. the pairmode sub-skills). CER-109 is scoped
  to the four top-level skills; extending the guard downward is a separate change.
- Any change to `.claude-plugin/` manifest content, skill registration, or the `flex:` prefix
  convention itself.
- Applying the same glob-derivation treatment to other hardcoded fixture lists elsewhere in
  `tests/pairmode/`.

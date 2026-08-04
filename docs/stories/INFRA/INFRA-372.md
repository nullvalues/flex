---
id: INFRA-372
rail: INFRA
title: Track .pairmode-overrides in CANONICAL_FILES/SCAFFOLD_FILES audit surfaces (CER-132)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/audit.py
touches:
  - tests/pairmode/test_audit.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-132 (MEDIUM): `.pairmode-overrides` is bootstrap-seeded (`bootstrap.SCAFFOLD_FILES`,
`.pairmode-overrides.j2`) and is the sanctioned keep-my-extension mechanism that both the audit's
EXTRA-severity split and sync's `RETIRED_SECTIONS` pruning (INFRA-311) defer to — yet no audit
surface tracks the file itself: it appears in neither `audit.CANONICAL_FILES` nor
`audit.SCAFFOLD_FILES` and has no dedicated existence/health check (unlike
`docs/ideology.md`/`docs/reconstruction.md`, which do have staleness checks in `audit.py`). A
deleted or corrupted overrides file therefore silently strips a project's declared protections on
the next sync. Body compare is the wrong tool here since the content is project-owned; the fix is
an existence check plus a parse-health check (unparseable lines reported by `_load_overrides`, not
silently dropped). File: `skills/pairmode/scripts/audit.py` (`CANONICAL_FILES`/`SCAFFOLD_FILES`
lists at ~lines 52/70, `_load_overrides` at ~line 410). Surfaced by INFRA-311's
`bootstrap.SCAFFOLD_FILES ⊆ audit-tracked` parity test, which currently excepts
`.pairmode-overrides` via `_KNOWN_GAPS`.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- `skills/pairmode/scripts/audit.py` exists with `CANONICAL_FILES` (~line 52), `SCAFFOLD_FILES`
  (~line 70), and `_load_overrides` (~line 410).
- `tests/pairmode/test_audit.py` contains `_KNOWN_GAPS`, `_DEDICATED_CHECK_FILES`, and
  `TestBootstrapScaffoldAuditParity` (~lines 2547-2602).
- No other story in this phase has an in-flight edit to `audit.py`. INFRA-381 (CER-121) also
  targets `audit.py`; build serially with it (phase-119 `## Ordering`). This story owns **only**
  the `.pairmode-overrides` surface — it does not touch the `docs/architecture.md` /
  `docs/checkpoints.md` `_KNOWN_GAPS` entries or any body-tracking mechanism, which are
  INFRA-381's.

## Ensures

- `audit.py` defines a dedicated `.pairmode-overrides` check function (existence + parse health),
  in the style of `_check_ideology_staleness` / `_check_reconstruction_staleness`.
- Running the audit against a project directory with **no** `.pairmode-overrides` file yields a
  `missing` `AuditItem` whose `file` is `.pairmode-overrides`.
- Running the audit against a project whose `.pairmode-overrides` contains a non-blank,
  non-comment line that `_load_overrides` cannot parse into a `(file, section)` pair yields an
  `inconsistent` `AuditItem` whose `file` is `.pairmode-overrides` and whose description names
  the offending line number.
- Running the audit against a project whose `.pairmode-overrides` parses cleanly yields **no**
  `.pairmode-overrides` item in `missing` or `inconsistent`, regardless of how the file's content
  differs from the rendered `.pairmode-overrides.j2` template. Forbidden proxy: adding
  `.pairmode-overrides` to `CANONICAL_FILES`/`SCAFFOLD_FILES` for body/section comparison, which
  would report project-owned content as drift.
- `_load_overrides(project_dir)` keeps its existing signature and `set[tuple[str, str]]` return
  type — its four in-tree callers (`audit.py` ~513/~741, and its independent copies in `sync.py`
  and `pairmode_drift_report.py`) are unchanged by this story.
- `.pairmode-overrides` is removed from `_KNOWN_GAPS` in `tests/pairmode/test_audit.py` and added
  to `_DEDICATED_CHECK_FILES`; `TestBootstrapScaffoldAuditParity::test_scaffold_files_subset_of_audit_tracked`
  passes with that entry gone. The `docs/architecture.md` and `docs/checkpoints.md` `_KNOWN_GAPS`
  entries remain untouched.

## Instructions

1. In `audit.py`, add a parse-diagnostics sibling to `_load_overrides` (e.g.
   `_load_overrides_with_diagnostics(project_dir) -> tuple[set[tuple[str, str]], list[str]]`)
   that returns the same pairs plus a list of human-readable malformed-line messages, and have
   `_load_overrides` delegate to it and discard the diagnostics. A line is malformed when it is
   non-blank, not a `#` comment, and either has no `:` or has an empty file-path or section-key
   after stripping. Include the 1-based line number in each message.
2. Add `_check_overrides_health(project_dir)` returning `None` when the file is absent, an empty
   list when it parses cleanly, and the malformed-line messages otherwise. Wire it into the audit
   result assembly next to the existing ideology/reconstruction staleness blocks (~lines 622-660):
   absent → `result.missing` with `section="__file__"`; malformed → `result.inconsistent` with
   `section="__content__"`.
3. Do **not** add `.pairmode-overrides` to `CANONICAL_FILES` or `SCAFFOLD_FILES` — the file's
   content is project-owned, so section/body comparison would be a false-drift generator. The
   dedicated check is the tracking surface, exactly as it is for `docs/ideology.md`. (Ideology
   alignment, Step 4a: this respects "Never silently pass contradictions" — the check reports the
   condition rather than dropping it — without asserting authority over project-owned content.)
4. In `tests/pairmode/test_audit.py`, delete the `".pairmode-overrides": "CER-132"` entry from
   `_KNOWN_GAPS` and add `".pairmode-overrides"` to `_DEDICATED_CHECK_FILES`. Leave the two
   `CER-121` entries alone.
5. Add tests covering the three states: file absent → missing item; file with a malformed line →
   inconsistent item naming the line number; file with valid, non-template content → no finding.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_audit.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green. `TestBootstrapScaffoldAuditParity` passes without a `.pairmode-overrides`
`_KNOWN_GAPS` exception, and the three new state tests pass.

## Out of scope

- The `docs/architecture.md` / `docs/checkpoints.md` `_KNOWN_GAPS` entries and any body/staleness
  tracking for the cold-start triad docs — INFRA-381 (CER-121).
- The duplicate `_load_overrides` implementations in `sync.py` and `pairmode_drift_report.py`;
  deduplicating them is not attempted here.
- Any change to `.pairmode-overrides.j2`, `bootstrap.SCAFFOLD_FILES`, or sync's
  `RETIRED_SECTIONS` pruning behaviour.
- Auto-repair: the audit reports a missing or malformed overrides file; it does not regenerate or
  rewrite one.
- Closing the CER-132 backlog row (orchestrator step, not a builder edit).

<!-- spec-preflight: `docs/checkpoints.md` and `docs/ideology.md` are named above only as
     references (the analogous dedicated-check precedent, and INFRA-381's out-of-scope surface).
     Neither is edited by this story, so both are intentionally absent from primary_files/touches. -->


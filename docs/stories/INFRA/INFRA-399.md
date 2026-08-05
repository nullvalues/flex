---
id: INFRA-399
rail: INFRA
title: De-duplicate pairmode_drift_report.py's stale override-key parser (CER-181)
status: draft
phase: "129"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_drift_report.py
touches:
  - tests/pairmode/test_drift_report.py
narrative_roles: []
---

## Context

`pairmode_drift_report.py` keeps its own copy of audit.py's section-key derivation
(`_split_sections`, line 97) and `.pairmode-overrides` loading (`_load_overrides`,
line 145). INFRA-391 (CER-170) fixed audit.py's copy to strip the leading `#+\s*`
marker from a section header before keying it, and INFRA-398 (CER-180) taught
audit.py's loader to accept both key shapes and updated the operator-facing
template — but neither touched drift-report's copy. So an override written in the
currently documented, marker-free format (`CLAUDE.build.md: Build loop`) is honoured
by `pairmode audit`/`sync` and silently ignored by the live `pairmode drift-report`
command: the operator-declared section is reported as DRIFT and offered as a
fleet-wide convergence candidate, recommending a canonical template change from
divergence the operator already declared intentional. The fix is to make
drift-report reuse audit.py's current logic instead of maintaining a diverged copy.

## Requires

- INFRA-391 and INFRA-398 are merged (audit.py's `_split_sections` applies the
  `^#+\s*` strip; `_load_overrides_with_diagnostics` accepts both key shapes).

## Ensures

1. A `.pairmode-overrides` entry in the current documented format
   (`CLAUDE.build.md: Build loop`) reclassifies the matching section from DRIFT to
   INTENTIONAL through the real `drift_report()` entry point — not merely through
   `_load_overrides`/`_split_sections` called in isolation — and the same holds for
   an EXTRA section and for a mixed-case entry (`CLAUDE.build.md: Build Loop`).
   Forbidden proxy: the parser-level unit tests pass while `drift_report()` still
   lists the section under `drift`/`extra`.
2. The legacy `##`-prefixed entry shape still suppresses (audit.py's dual-shape
   acceptance reaches drift-report), and a section *not* named in
   `.pairmode-overrides` is still classified DRIFT/EXTRA and still surfaces as a
   convergence candidate — the full `tests/pairmode/test_drift_report.py` suite is
   green with no test deleted to make it so.
3. `python -c "import skills.pairmode.scripts.pairmode_drift_report"` and
   `python -c "import skills.pairmode.scripts.audit, skills.pairmode.scripts.pairmode_drift_report"`
   both exit 0 in either import order (no circular import introduced by the reuse),
   asserted by a test in `tests/pairmode/test_drift_report.py`.
4. `pairmode_drift_report.py` contains no independent re-implementation of the
   section-key derivation or the `.pairmode-overrides` line parsing: `grep -n
   "^_SECTION_RE" skills/pairmode/scripts/pairmode_drift_report.py` returns nothing
   and the file no longer opens or splits `.pairmode-overrides` itself.

## Instructions

1. In `pairmode_drift_report.py`, import `_split_sections`, `_normalise` and
   `_load_overrides` from `skills.pairmode.scripts.audit` and delete the local
   `_SECTION_RE`, `_split_sections`, `_normalise` and the body of `_load_overrides`.
   audit.py imports only `lesson_utils`/`_version`, so this direction has no cycle;
   keep it that way (never import drift-report from audit.py).
2. Keep a thin local `_load_overrides(project_dir)` wrapper that delegates to
   audit's loader and applies `_normalise` to each returned section key. audit's
   loader strips `#+` but does not lowercase, while drift-report's section keys come
   from `_normalise`; without this adapter a capitalised override entry would stop
   matching. This preserves drift-report's existing `_load_overrides` contract, so
   the existing unit tests around it keep their meaning.
3. Note for the reviewer: audit's `_split_sections` also splits on bold numbered
   markers. Verified during spec recon that this changes no section key count for
   any current canonical template or `.claude/agents/` file in this repo — only the
   `##` prefix disappears from the keys. Confirm the existing suite still passes
   rather than adjusting expectations to fit.
4. Update `tests/pairmode/test_drift_report.py:686,736` (the two INTENTIONAL
   reclassification tests) to write the current marker-free entry shape, and add
   end-to-end tests through `drift_report()` covering Ensures 1-3, mirroring the
   `TestAuditOverridesSuppress` shape INFRA-398 established for `audit_project()`.
   Keep at least one legacy `##`-shaped entry under test so dual-shape acceptance is
   pinned rather than silently dropped.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_drift_report.py tests/pairmode/test_audit.py -q
```
Acceptance: green, including the new end-to-end override-suppression and
import-order cases. Then run the full suite once without `-x`:
```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

## Out of scope

- CER-177's broader audit.py/sync.py `^#+\s*` de-duplication — unresolved on the Do
  Later backlog; this story only removes drift-report's live-wrong copy.
- Any edit to `audit.py`, `sync.py`, `.pairmode-overrides.j2`, or
  `skills/pairmode/SKILL.md` — the documented format is already correct; only the
  drift-report consumer is behind it.
- audit.py's own override matching is case-sensitive on the section key (its loader
  does not lowercase). This story routes around it locally (Instruction 2) rather
  than changing audit.py's behaviour; it is a separate finding for the backlog.
- Migrating or rewriting any existing project's `.pairmode-overrides` file — legacy
  entries keep working via audit's dual-shape acceptance.

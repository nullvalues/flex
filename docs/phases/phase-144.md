---
era: "005"
phase_class: production
---

# project — Phase 144: Harden title/path serialization at two live writer gaps (CER-221/222)

← [Phase 143: Extend oracle-based round-trip fix to title/source frontmatter scalars (CER-219)](phase-143.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close CER-221 and CER-222: two independent write sites that serialize operator-supplied free text into a format with its own escaping contract, found by the same reference-fragility investigation, neither currently verified against its real reader. CER-221: story_new.py's _append_to_phase writes a story title bare into a phase-manifest Stories-table row with no pipe escaping, which can make next_action._check_phase_completion misread a draft story's status as complete (verified live checkpoint-bypass) or vice versa. CER-222: flex_build.py's _append_touches_entry (the mid-build permissions-widen path) writes an agent-widened path bare into a story's touches: frontmatter with no oracle verification, unlike story_new.py's create-time writer for the same frontmatter block (INFRA-412's _yaml_block_scalar/_oracle_render). Scope widening has become one of this project's most common re-build patterns (used in roughly every other story), so CER-222 in particular needs to work correctly, not just pass a narrow test. Fix direction for CER-221: escape unescaped | as \| at the single write site, matching table_utils.split_table_row's documented convention, with a regression test round-tripping a pipe-bearing title through next_action._check_phase_completion. Fix direction for CER-222: route _append_touches_entry's new_item through the same block-scalar oracle story_new.py's own writer already uses (_yaml_block_scalar/_oracle_render), raising rather than corrupting the scope source of truth when a widened path is unrepresentable, and make sure the permissions-widen CLI path handles that raise sensibly (refuses the widening with a clear operator-facing message, does not crash uncaught).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-414 | Escape pipe in phase-manifest Stories-table title (CER-221) | complete |
| INFRA-415 | Oracle-verify scope-widening frontmatter writes (CER-222) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-144 Cold-eyes checklist

- [x] written-never-read — N/A: both fixes harden existing writers (`_append_to_phase`, `_append_touches_entry`) against their existing readers; no new field or write site introduced.
- [x] required-never-written — N/A: no new read path added.
- [x] duplicate state — no: each writer has its own single, unchanged read site.
- [x] half-implementation — no: both Ensures sets fully covered by non-proxy regression tests (INFRA-414's test exercises the real `_check_phase_completion` misread path, not a string-contains proxy). This phase's own checkpoint-security pass found and correctly out-of-scoped a sibling gap in the same transaction (`_append_scope_widening_row`, the same CER-221 unescaped-pipe shape) rather than scope-creeping it in — filed as CER-233, not yet fixed.

— filled in by orchestrator at checkpoint (2026-08-07) —

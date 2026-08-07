---
era: "005"
phase_class: production
---

# project — Phase 140: Fix silent YAML frontmatter truncation on embedded comment introducer (CER-211)

← [Phase 139: Bootstrap/scaffold doc and quoting quality fixes (CER-166/167/187)](phase-139.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close CER-211: story_new.py's _yaml_block_scalar quoting helper (CER-167) does not detect an embedded ' #' comment introducer in an otherwise-plain scalar, silently truncating operator-supplied primary_files/touches values on YAML round-trip -- the exact silent-data-loss shape CER-167 exists to prevent. Fix the detection and, time permitting, also close the related MEDIUM (YAML 1.1 bare-value type coercion and raw control-character passthrough).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-410 | Fix silent YAML frontmatter truncation on embedded comment introducer (CER-211) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-140 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

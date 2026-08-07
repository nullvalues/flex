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
| INFRA-410 | Fix silent YAML frontmatter truncation on embedded comment introducer (CER-211) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-140 Cold-eyes checklist

- [x] written-never-read — N/A: this phase widens an existing detection check (`_yaml_block_scalar`'s is-plain test) in `story_new.py`; it introduces no new persistent field or writer.
- [x] required-never-written — N/A: no new read path was added; the existing `primary_files:`/`touches:` write/read pair is unchanged in shape, only its safety check widened.
- [x] duplicate state — no: single write site (`_yaml_block_scalar`), single read site (`schema_validator._parse_frontmatter`), unchanged from before this phase.
- [x] half-implementation — no: both regression tests (helper-level and frontmatter-round-trip) exercise the new detection branch; no unreachable code. Note (non-blocking, downstream-risk only): this fix extends a hand-maintained denylist that Phase 142 (INFRA-412) later replaced with an oracle-based redesign after further gaps surfaced (CER-212, CER-214/215/216) — expected evolution, not an omission in this phase's own scope.

— filled in by orchestrator at checkpoint (2026-08-07), per intent-reviewer recommendation —

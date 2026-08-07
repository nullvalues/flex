---
era: "005"
phase_class: production
---

# project — Phase 143: Extend oracle-based round-trip fix to title/source frontmatter scalars (CER-219)

← [Phase 142: Durable oracle-based fix for story_new.py frontmatter round-trip (CER-214/215/216)](phase-142.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close CER-219: Phase 142/INFRA-412's oracle-based round-trip fix (verifying a candidate rendering against the real schema_validator._parse_frontmatter reader before emitting) was applied only to story_new.py's block-sequence item renderer (_yaml_block_scalar, used for primary_files:/touches: entries). Two sibling free-text scalars on the same frontmatter block -- title: (quoted only via a retired CER-092 '#'-regex check) and source: (never quoted at all) -- still use the pre-CER-216 hand-rolled rule and reproduce the identical CER-216 truncation shape: a trailing '---' silently drops the rest of the frontmatter (status, phase, primary_files, touches, etc.), not just the affected scalar. Extend the oracle-based design to these scalar-position frontmatter lines -- a scalar-position analogue of _reads_back_intact -- verifying each candidate rendering against the real reader before emitting, exactly as INFRA-412 did for list items. Also close the two secondary shapes found in the same audit pass: a bracket-prefixed title triggering _parse_flow_sequence (raising FrontmatterError for every consumer) and a comma-containing bracketed title silently type-confusing title into a list.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-413 | Extend oracle-based round-trip fix to title/source frontmatter scalars (CER-219) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-143 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

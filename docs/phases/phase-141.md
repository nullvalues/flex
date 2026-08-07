---
era: "005"
phase_class: production
---

# project — Phase 141: Fix story_new.py writer/reader escaping mismatch (CER-213)

← [Phase 140: Fix silent YAML frontmatter truncation on embedded comment introducer (CER-211)](phase-140.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close CER-213: story_new.py's _yaml_block_scalar (CER-167/CER-211) escapes non-plain primary_files:/touches: values via json.dumps, assuming a yaml.safe_load-style reader that unescapes backslash sequences. The project's actual and only story-frontmatter reader, schema_validator._parse_frontmatter via _strip_inline_comment, strips one matching pair of outer quote characters literally and never unescapes -- so quoted values with an embedded quote character, a real tab, or a real newline are silently corrupted on read, a regression versus pre-INFRA-409 behavior for the quote/tab cases. Rework the writer to escape for the reader that actually exists: emit bare when safe, wrap in a single matching pair of quotes when that round-trips cleanly through the real reader, and raise (fail loud, matching the FrontmatterError precedent in schema_validator.py's flow-sequence parser) for values no quoting scheme under this reader can represent -- both quote characters present, or a real control character. Any new regression test must round-trip through the real writer+schema_validator._parse_frontmatter reader pair, not yaml.safe_load/json.loads.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-411 | Fix story_new.py writer/reader escaping mismatch (CER-213) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-141 Cold-eyes checklist

- [x] written-never-read — N/A: this phase reworks the writer/reader escaping shape (`_yaml_block_scalar`'s quoted-value emission) for the existing `primary_files:`/`touches:` fields; no new field introduced.
- [x] required-never-written — N/A: no new read path added; `schema_validator._parse_frontmatter` remains the sole reader, unchanged in shape by this phase.
- [x] duplicate state — no: single write site (`_yaml_block_scalar`), single read site, unchanged from before this phase.
- [x] half-implementation — no: both quoting branches (literal single-quote wrap, `ValueError` on unrepresentable) are exercised by regression tests routed through the real reader; no unreachable code.

— filled in by orchestrator at checkpoint (2026-08-07) —

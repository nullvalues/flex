---
era: "005"
phase_class: production
---

# project — Phase 139: Bootstrap/scaffold doc and quoting quality fixes (CER-166/167/187)

← [Phase 138: Close shadow-reviewer scope_guard cwd-resolution gap (CER-176/177/201)](phase-138.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close three small documentation/quoting quality gaps: security-auditor procedure.md's write-enumeration check missing the context_current_tokens_source key (CER-166), story_new.py's unquoted YAML interpolation for --primary-file entries (CER-167), and bootstrap.py's --force-agents help text/SKILL.md omitting its EXEMPLAR-000.md overwrite behavior (CER-187).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-409 | Bootstrap/scaffold doc and quoting quality fixes (CER-166/167/187) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-139 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

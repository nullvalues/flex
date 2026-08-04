---
era: "004"
phase_class: production
---

# project — Phase 120: CER-159 hook-firing fix: marketplace install migration, era-004 stable close

← [Phase 119: Spec precision (frozen exemplar) and fundamental-doc trim](phase-119.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Migrate flex's own dogfooding sessions off the @inline self-referential plugin registration (which never populates CLAUDE_PLUGIN_ROOT, silently failing every hooks/hooks.json command) onto a proper marketplace-installed copy, confirmed live to fix hook firing. Document the version-bump-before-reinstall discipline the cache-keyed install requires, record the accepted dual-registration limitation (no supported way found to suppress the inline auto-load; claude plugin disable reports success but has no functional effect on it), and close era 004 on a version confirmed stable rather than the unverified cp-119 state.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-383 | Migrate flex's own build sessions from @inline to marketplace-installed plugin (CER-159) | draft |
| INFRA-384 | Document version-bump-before-reinstall discipline and accepted @inline dual-registration limitation | draft |
| INFRA-385 | Isolate test_pairmode_migrate.py/test_sync.py PreToolUse-registration tests from real ~/.claude/plugins/ state | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-120 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

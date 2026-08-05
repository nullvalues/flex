---
era: "005"
phase_class: production
---

# project — Phase 126: Close shadow-reviewer Bash-guard bypass and scope its Write grant (CER-174)

**Parent phase:** Phase 122 — shadow-reviewer write capability (CER-164) and shadow_review enablement

← [Phase 125: De-identify fleet repo references from the public repo (CER-172)](phase-125.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-174: reviewer_bash_guard.py's shadow-reviewer allowlist is bypassable via shell chaining/substitution (arbitrary command execution), and its Write grant is unscoped (scope_guard.py has no agent-type awareness, so shadow-reviewer inherits the builder's full write scope instead of being confined to .pairmode-suggestions.md). Both compensating controls promised by CLAUDE.build.md 52/INFRA-388's own story must actually hold before shadow_review=concurrent stays safely enabled.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-396 | Fix shadow-reviewer Bash-guard shell-chaining bypass and scope its Write grant (CER-174) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-126 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

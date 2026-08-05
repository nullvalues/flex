---
era: "005"
phase_class: production
---

# project — Phase 128: Fix .pairmode-overrides template/migration gap from audit.py key-format change (CER-180)

**Parent phase:** Phase 123 — Fix audit.py override-key normalisation mismatch (CER-170)

← [Phase 127: Close shadow-reviewer git-flag write bypass and worktree-path scope_guard gap (CER-175)](phase-127.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-180: INFRA-391's audit.py section-key format change (CER-170) left skills/pairmode/templates/.pairmode-overrides.j2 documenting the old, now-broken key format with no migration path, silently defeating both audit.py's override suppression and sync.py's destructive-write protection for every fleet project's existing .pairmode-overrides file. Update the template to the current key format and add either dual-shape acceptance or an explicit stale-shape diagnostic so operators migrate deliberately.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-398 | Fix .pairmode-overrides template/migration gap from audit.py key-format change (CER-180) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-128 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

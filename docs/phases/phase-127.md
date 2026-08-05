---
era: "005"
phase_class: production
---

# project — Phase 127: Close shadow-reviewer git-flag write bypass and worktree-path scope_guard gap (CER-175)

**Parent phase:** Phase 122 — shadow-reviewer write capability (CER-164) and shadow_review enablement

← [Phase 126: Close shadow-reviewer Bash-guard bypass and scope its Write grant (CER-174)](phase-126.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-175: the shadow-reviewer Bash allowlist still permits an arbitrary-file write via git's --output/--exec-path flags on otherwise-legitimate git subcommands, and scope_guard.py's shadow-reviewer write confinement (INFRA-396) never strips the .pairmode-worktrees/<story-id>/ prefix, so it denies the shadow-reviewer's own legitimate absolute-path write to .pairmode-suggestions.md inside its worktree. Both gaps leave shadow_review=concurrent unsafe/inert and must be closed before Phase 122's checkpoint can pass.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-397 | Close shadow-reviewer git-flag write bypass and worktree-path scope_guard gap (CER-175) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-127 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

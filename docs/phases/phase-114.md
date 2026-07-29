---
era: "004"
phase_class: production
---

# project — Phase 114: Build-loop closeout: worktrees, scaffolding, migration tooling, doc currency

← [Phase 113: Shared blockers: frontmatter, resolver evidence, recording determinism](phase-113.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Remove recurring build-loop friction (unprovisioned worktrees, interactive scaffolding prompts, silent phase-manifest drift, incomplete migration rules) and bring build-loop procedure and architecture docs back to truth so the next cold-eyes audit reads a correct contract.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-301 | Non-interactive scaffolding: create-rail flag; surface phase-manifest registration failures | draft |
| INFRA-302 | Worktree build-environment provisioning; untrack tsconfig.tsbuildinfo | draft |
| INFRA-303 | Migration tooling: rules 9/10 name parity; expected_step_tokens opt-out and honest CER-111 disposition | draft |
| INFRA-304 | Containment parity for spec_preflight; reviewer-template revert-assertion residue | draft |
| INFRA-305 | Build-loop doc and procedure currency sweep | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-114 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

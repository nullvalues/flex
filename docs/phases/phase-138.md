---
era: "005"
phase_class: production
---

# project — Phase 138: Close shadow-reviewer scope_guard cwd-resolution gap (CER-176/177/201)

← [Phase 137: Overrides/audit key-shape quality fixes (CER-182/184/185/202)](phase-137.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close the remaining shadow-reviewer confinement gaps in scope_guard/reviewer_bash_guard: git diff --no-index still escapes the shadow-reviewer's Bash denylist (CER-176), and check_path's out-of-worktree story resolution (when cwd is the main checkout rather than a per-story worktree) can let a shadow-reviewer write land in a different story's worktree or the harness-owned allow-list prefixes instead of being confined to exactly .pairmode-suggestions.md (CER-177 and its duplicate CER-201, tracked as one fix).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-408 | Close shadow-reviewer scope_guard cwd-resolution gap (CER-176/177/201) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-138 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —

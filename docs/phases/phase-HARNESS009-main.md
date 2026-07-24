---
era: "003"
---

# flex-harness — Phase HARNESS009-main: Write-path determinism

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Close checkpoint_step write gap and gate verdict text-parsing gap

## Stories

| ID | Title | Status |
|----|-------|--------|
| RESOLVER-014 | Fix active-phase selection — first non-inactive wins | complete |
| RESOLVER-012 | `record-checkpoint-step` CLI + orchestrator wiring | complete |
| RESOLVER-013 | Gate verdict JSON schema + parser hardening | complete |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | No new persistent schema objects. `state.json["checkpoint_step"]` key already exists; this phase adds CLI write authority over it. |

---

### CP-HARNESS009-main Cold-eyes checklist

— developer fills in after phase completion —

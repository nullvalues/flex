---
era: "003"
phase_class: production
---

# project — Phase HARNESS004-main: Checkpoint as an action sequence

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Decompose the 8-step checkpoint sequence (currently prose in `CLAUDE.build.md`) into a series of
resolver-emitted leaf-worker actions, enforcing the era's no-nested-spawning invariant. The resolver
gains a `checkpoint_step` Position field (read from `state.json`) that tracks which checkpoint steps
have completed; `resolve_next_action` emits the next uncompleted checkpoint action in sequence:
`checkpoint-security` → `checkpoint-intent` → `checkpoint-docs` → `checkpoint-tag`. Each of the
first three spawns a leaf worker (security-auditor WORKER-008, intent-reviewer WORKER-009, and a new
docs-review WORKER-011); `checkpoint-tag` is executed inline by the harness (deterministic git
operation). Pre-checkpoint guards (phase complete? CER clear? build gate?) are checked by
`infer_position` before entering the checkpoint sequence. Advisory-only — NOT wired into the live
`CLAUDE.build.md` until HARNESS006. `SCHEMA_VERSION` bumped to 3 (removes old `checkpoint` catch-all
action). Agreements input: `docs/agreements/HARNESS004-main.md` (all 6 DPs AGREED).

## Stories

| ID | Title | Status |
|----|-------|--------|
| RESOLVER-007 | Checkpoint step tracker — `checkpoint_step` Position field + action vocabulary | complete |
| WORKER-011 | Checkpoint docs-review leaf worker | complete |
| RESOLVER-008 | Checkpoint action routing — pre-checkpoint guards + step sequencing | complete |
| WORKER-012 | HARNESS004 isolation suite | complete |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | HARNESS004 introduces no new persistent schema. `state.json["checkpoint_step"]` is an ephemeral list in an existing ephemeral state file — not a new schema object. |

---

### CP-HARNESS004-main Cold-eyes checklist

— developer fills in after phase completion —

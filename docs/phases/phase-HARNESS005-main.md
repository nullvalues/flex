---
era: "003"
phase_class: production
---

# project — Phase HARNESS005-main: Spec-writer as a leaf worker

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Convert the spec-writing step (today a Plan subagent inline in `CLAUDE.build.md` prose) to a
resolver-emitted leaf worker, making the build loop fully resolver-driven. The resolver gains a
`needs_spec` Position flag: when the next story has `status: planned` with a stub spec (no Ensures
section, or placeholder text), `resolve_next_action` emits `spawn-spec-writer` instead of
`spawn-gate-worker`/`spawn-builder`. The spec-writer leaf worker runs the Plan procedure in
disposable context, expands the story's Ensures/Instructions/Tests/Out-of-scope sections in place,
and returns `SPEC-RESULT`. After a `"done"` result the harness re-runs `next-action` and the
resolver proceeds normally. `SCHEMA_VERSION` bumped to 4. Advisory-only — NOT wired into the live
`CLAUDE.build.md` until HARNESS006. Agreements input: `docs/agreements/HARNESS005-main.md`
(all 5 DPs AGREED).

## Stories

| ID | Title | Status |
|----|-------|--------|
| RESOLVER-009 | `spawn-spec-writer` action + `needs_spec` Position flag | complete |
| WORKER-013 | Spec-writer leaf worker — thin shell + plugin procedure skill | complete |
| WORKER-014 | HARNESS005 isolation suite | complete |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | HARNESS005 introduces no new persistent schema. The spec-writer writes to the existing story file (already scaffolded); no new `state.json` keys. |

---

### CP-HARNESS005-main Cold-eyes checklist

— developer fills in after phase completion —

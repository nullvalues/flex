---
era: "003"
---

# flex — Phase 86: permissions-create idempotency

← [Phase 85: Context budget acknowledgment integrity fix](phase-85.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Close a methodology bug found via an external report from another
pairmode-run project (meander): `permissions-create` (`flex_build.py`,
Layer 1 of the two-layer permission model documented in `CLAUDE.build.md`)
unconditionally rewrites `docs/phases/permissions/<STORY_ID>.json` — including
a fresh `generated_at` timestamp — on every story build, even when the
computed `allowed_paths` are byte-for-byte identical to what is already on
disk.

`docs/phases/permissions` is a Layer 1 protected path under the orchestrator's
auto-mode deny rules by design (it is one of the files a phase-inception
"toggle auto mode off/on" grants blanket permission for, precisely so the
rest of the phase can build without interruption). Because the write happens
unconditionally rather than only when content actually changes, every single
story in a phase re-triggers a write to that protected path, which re-opens
the auto-mode authorization gate on every story — defeating the design intent
that one toggle at phase inception should cover the whole phase, and forcing
the user to re-authorize (or the orchestrator to stall on) a write that
changes nothing.

The fix: `permissions-create` computes `allowed_paths` from the story's
`primary_files` + `touches` frontmatter exactly as today, but before writing,
diffs the computed value against the existing file's `allowed_paths` (when
one exists and parses). If unchanged, it no-ops — no write, no new
`generated_at`, no auto-mode re-trigger. It writes (with a fresh
`generated_at`) only when the content differs or no prior file exists —
i.e. only on genuine scope drift, which is exactly when re-authorization is
warranted.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-194 | permissions-create idempotency — skip write when allowed_paths unchanged | complete |

## Schema delivery

No new persistent schema objects introduced in this phase. `docs/phases/permissions/<STORY_ID>.json`
already exists as a generated artifact (Phase 15/INFRA-137); this phase changes only the
write-triggering condition, not its shape.

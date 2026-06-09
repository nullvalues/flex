---
id: INFRA-163
rail: INFRA
title: "Docs — architecture.md observability section + `/flex:observability` skill entry"
status: planned
phase: "63"
story_class: doc
primary_files:
  - docs/architecture.md
  - skills/observability/SKILL.md
touches:
  - README.md
---

# INFRA-163 — Docs: architecture.md observability section + `/flex:observability` skill entry

## Context

Closing documentation story for Phase 63. Two artifacts:

1. A new `## Observability surface` section in `docs/architecture.md`
   describing the SPA architecture, data sources, and read-only contract.
2. A `SKILL.md` for the new `flex:observability` skill so it appears in the
   skill dispatcher alongside `flex:pairmode` and `flex:companion`.

## Ensures

### `docs/architecture.md`

1. A new `## Observability surface` section is added (after the existing
   `## Context budget` section). It covers:
   - The `skills/observability/` workspace layout (`api/` + `ui/`)
   - The registry file at `~/.config/flex-observability/registry.json`
   - The six API endpoints and what each reads
   - The read-only contract (no write routes in Phase 63)
   - The Phase 1 / Phase 2 boundary (where controls will land)
   - The `flex_factor` frontmatter field and its effect on the context ceiling
   - A note that the CLI entry point is `flex_observability.py`

2. The existing sections are not modified.

### `skills/observability/SKILL.md`

3. A new `SKILL.md` following the structure of
   `skills/pairmode/SKILL.md` — skill name, description, available subcommands.

4. Documents the `flex-observability` CLI:
   - `register --project-dir DIR [--name NAME] [--color HEX]`
   - `unregister --project-dir DIR | --name NAME`
   - `list`
   - `serve [--port N] [--host HOST]`
   - Install note: `pnpm install && pnpm --filter @flex-obs/api build` before
     first `serve`

5. Includes a "How other projects use this" section: other repos are registered
   with `flex-observability register --project-dir /path/to/repo` using the
   flex script path (e.g. from their own CLAUDE.md or session hooks).

### `README.md`

6. Add a one-line bullet under an "Observability" heading (or append to the
   existing feature list if a bullet list already exists):
   `- **Observability SPA** — browser-based dashboard for context budget,
     effort metrics, and story status across multiple registered repos.`

## Instructions

- Keep the `architecture.md` section factual and brief (under 60 lines).
  Cross-reference phase-63.md for design decisions.
- `SKILL.md` should be standalone readable — someone who has not read the
  phase doc should understand how to start the SPA from this file alone.
- Do not restructure README.md — find the appropriate insertion point and
  add the minimum text needed.

## Tests

`TEST RUN: documentation story — no test file expected`

Review:
- `docs/architecture.md` grep for `Observability surface` heading.
- `skills/observability/SKILL.md` exists and is non-empty.
- `README.md` contains "Observability SPA".

## Out of scope

- Updating `docs/brief.md` or `docs/ideology.md`.
- Writing a user-facing tutorial beyond the SKILL.md.
- Phase 64 controls documentation.

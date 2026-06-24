# Phase 78 — Orchestrator pre-flight gate CLI offload

**Era:** era-002
**Status:** planned

## Goal

The build orchestrator currently reads every story spec file directly to run three
pre-flight checks (stub gate, schema gate, auth gate) before spawning the builder.
Each story read adds 5–10k tokens to the orchestrator's context window and stays
there for the rest of the session. A 10-story phase can add 50–100k tokens in
pre-flight overhead alone.

This phase replaces those orchestrator-owned reads with mechanical CLI calls:

1. Codify the stub gate as `flex_build.py check-stub` (text pattern matching — no
   LLM judgment required).
2. Add `auth_gated: false` and `schema_introduces: false` boolean fields to story
   frontmatter so the schema and auth gates become CLI-readable from metadata rather
   than requiring LLM inference over story body text.
3. Update `CLAUDE.build.md` and its Jinja2 template so the orchestrator's pre-story
   block is three CLI calls returning short answers rather than a story-file read plus
   inline judgment. `sync-build` then propagates the updated orchestrator instructions
   to upstream repos automatically.

After this phase the orchestrator never reads a story spec file. The builder and
reviewer continue to read their own story specs cold (unaffected).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-184 | story frontmatter: add auth_gated + schema_introduces fields | complete |
| BUILD-034 | pre-flight gate CLIs: check-stub, check-schema-gate, check-auth-gate | complete |
| BUILD-035 | orchestrator pre-flight offload: CLAUDE.build.md + template sync | complete |

## Sync note

Once BUILD-035 updates `CLAUDE.build.md.j2`, any upstream repo running
`sync-build --apply` receives the updated pre-flight section automatically. No
per-project manual edits are required. Story authors writing new stories after
INFRA-184 ships will get the new fields scaffolded by `story_new.py`. Existing
story files without the fields are treated as `false` by all CLIs (fail-open,
no block on absent field).

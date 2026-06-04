---
id: INFRA-153
rail: INFRA
title: "Checkpoint report — fix `[CP-N]` / `[N+1]` placeholders and add next-phase branching"
status: planned
phase: "60"
story_class: methodology
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.build.md
touches: []
---

# INFRA-153 — Checkpoint report: fix `[CP-N]` / `[N+1]` placeholders and add next-phase branching

## Context

The checkpoint report template (step 7.5 and step 8 of CLAUDE.build.md) contains
two brittle placeholders:

1. `CHECKPOINT [CP-N] COMPLETE` — `[CP-N]` implies integer arithmetic. For suffix
   phases (`RD077-main`) the orchestrator has no clear substitution rule and
   typically strips the suffix, producing `CP-77` instead of `CP-RD077-main`.

2. `[N+1]` appears twice — in the context-health advisory and in the closing prompt.
   For non-integer phase keys this arithmetic is undefined. Even for integer phases,
   when no next phase is specced the orchestrator has nothing to substitute and
   renders the literal `[next]`.

INFRA-152 adds `flex_build.py next-phase --after [phase-id]` which returns the
index-authoritative next phase key. This story wires it into the checkpoint report
and fixes both placeholder issues.

**Depends on INFRA-152.** The `next-phase` CLI must exist before this story builds.

## Acceptance criteria

All changes apply to **both** `skills/pairmode/templates/CLAUDE.build.md.j2` and
the live `CLAUDE.build.md`. Every change is described in terms of the live file;
apply the same edit to the template, replacing any hardcoded paths with their
Jinja2 equivalents (the template already uses `{{ flex_build_script }}` for the
flex_build.py path; use that variable here too).

### Fix 1 — `CHECKPOINT [CP-N] COMPLETE` header (step 8)

Replace:
```
  CHECKPOINT [CP-N] COMPLETE — [tag name]
```
with:
```
  CHECKPOINT [phase-id] COMPLETE — [tag name]
```

`[phase-id]` is the full phase key as returned by `current-phase` (e.g. `59`,
`RD077-main`). No other changes to the surrounding block.

### Fix 2 — `next-phase` call inserted into step 7 (after tag + push)

After the `git tag` and `git push` commands in step 7, add:

```
After pushing the tag, detect whether a next phase is already spec'd:

  next_phase_id=$(PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
    next-phase --after [phase-id] --project-dir .)

If the command exits 0: `next_phase_id` holds the next phase key (e.g. `60`).
If the command exits 1: `next_phase_id` is empty — no next phase is spec'd.
Pass `next_phase_id` into step 8 to populate the closing prompt.
```

In the Jinja2 template, replace the hardcoded path with `{{ flex_build_script }}`.

### Fix 3 — Context-health advisory (step 7.5)

Replace:
```
    → /clear before "Build Phase N+1" is advised.
```
with:
```
    → /clear before beginning the next phase is advised.
      [If next_phase_id is known: append `Say: "Build Phase [next_phase_id]" after clearing.`]
```

Exact wording:
- When `next_phase_id` is non-empty:
  ```
      → /clear before beginning Phase [next_phase_id] is advised.
        Say: "Build Phase [next_phase_id]" in the fresh session.
  ```
- When `next_phase_id` is empty:
  ```
      → /clear before beginning the next phase is advised.
  ```

### Fix 4 — Closing prompt (step 8)

Replace:
```
  To begin Phase [N+1], say: "Build Phase [N+1]"
```
with a conditional block:

```
  [If next_phase_id is non-empty:]
  To begin Phase [next_phase_id], say: "Build Phase [next_phase_id]"

  [If next_phase_id is empty:]
  No further phases are spec'd. To plan the next phase, say:
    "spec next phase [intent]"
```

The instruction prose in CLAUDE.build.md should read:

```
Use the `next_phase_id` captured in step 7 to populate the closing line:

  • next_phase_id non-empty →
      To begin Phase [next_phase_id], say: "Build Phase [next_phase_id]"

  • next_phase_id empty →
      No further phases are spec'd. To plan the next phase, say:
        "spec next phase [intent]"
```

### Manual propagation (orchestrator post-commit — not builder acceptance)

After the reviewer commits, the orchestrator syncs forqsite:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/pairmode_sync.py \
  sync-build --project-dir /mnt/work/forqsite --apply --yes
```

Verify `CLAUDE.build.md` in forqsite contains `next-phase --after` and the
conditional closing prompt. The builder does NOT attempt this step; the reviewer
does NOT block on it.

## Out of scope

- Updating the phase index row to `complete` at checkpoint time (separate concern)
- Changes to `flex_build.py` (INFRA-152)
- Changes to any hook, agent template, or other methodology file

---
id: BUILD-025
rail: BUILD
title: "wire `check-story-scope` into CLAUDE.build.md pre-story step (live + template)"
status: planned
phase: "61"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - tests/pairmode/test_templates.py
---

# BUILD-025 — wire `check-story-scope` into CLAUDE.build.md pre-story step

## Context

INFRA-155 adds `flex_build.py check-story-scope STORY_ID` — a read-only,
always-exit-0 command that prints heuristic SCOPE WARNINGs when a story's
`primary_files`/`touches` look incomplete (missing sibling test, missing
live-rendered template counterpart).

The build loop currently has three pre-story gates in this order:

1. **Pre-story schema gate** — schema validation against story spec.
2. **Pre-story stub gate** — delegation-language and missing-acceptance-surface check.
3. **Step 1 — Spawn the builder** — `read-attempt-count`, `permissions-create`,
   `story_context.py --set`, then the builder subagent fires.

BUILD-025 inserts a new **Pre-story scope check** section after the stub gate
and before Step 1. The scope check is informational only — it surfaces output
to the developer but never blocks. The developer decides whether to update the
story spec or proceed.

The same change applies to `skills/pairmode/templates/CLAUDE.build.md.j2` so
future bootstraps and forqsite syncs inherit the gate.

**Depends on INFRA-155.** The `check-story-scope` command must exist before this
story builds.

## Acceptance criteria

All changes apply to **both** `CLAUDE.build.md` and
`skills/pairmode/templates/CLAUDE.build.md.j2`. Every change is described in
terms of the live file; apply the same edit to the template, replacing the
hardcoded path with `{{ pairmode_scripts_dir }}/flex_build.py` (the project
convention already used at template lines ~470, ~481, ~483).

### Fix 1 — Insert new section between stub gate and Step 1

After the final line of the **Pre-story stub gate** section
(`"If neither condition is present: proceed to Step 1."`) and before
`"### Step 1 — Spawn the builder"`, insert:

```
### Pre-story scope check

Run this check **once per story**, after the stub gate, before spawning the
builder.

  scope_warnings=$(PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
    check-story-scope RAIL-NNN --project-dir .)

Replace `RAIL-NNN` with the current story's ID.

If `scope_warnings` is non-empty, surface the output to the developer:

  SCOPE CHECK — Story RAIL-NNN

  [scope_warnings verbatim]

  These are heuristic warnings only. Review and update primary_files/touches
  if the flagged files will be edited, or proceed if they are out of scope.

If `scope_warnings` is empty, print nothing and continue silently.

The check does not block. Continue to Step 1 regardless of output.
```

### Fix 2 — Update stub gate trailing cross-reference

The existing line:
```
If neither condition is present: proceed to Step 1.
```

Becomes:
```
If neither condition is present: proceed to the **Pre-story scope check**.
```

### Fix 3 — Apply identical changes to the Jinja2 template

In `skills/pairmode/templates/CLAUDE.build.md.j2`, insert the same section
with the hardcoded path replaced by `{{ pairmode_scripts_dir }}/flex_build.py`.
Apply Fix 2 to the template as well.

### Verification (no new test file)

This is a methodology story — acceptance is structural. Verify with `grep`:

```bash
grep -c "check-story-scope" CLAUDE.build.md                                  # >= 1
grep -c "Pre-story scope check" CLAUDE.build.md                              # >= 2 (heading + cross-ref)
grep -c "SCOPE CHECK" CLAUDE.build.md                                        # >= 1
grep -c "check-story-scope" skills/pairmode/templates/CLAUDE.build.md.j2     # >= 1
grep -c "Pre-story scope check" skills/pairmode/templates/CLAUDE.build.md.j2 # >= 2
```

If `tests/pairmode/test_templates.py` asserts on `CLAUDE.build.md.j2` content,
add assertions for the new section there rather than creating a new test file.

### Manual propagation (orchestrator post-commit)

After the reviewer commits, sync forqsite:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/pairmode_sync.py \
  sync-build --project-dir /mnt/work/forqsite --apply --yes
```

Verify `CLAUDE.build.md` in forqsite contains the new
`### Pre-story scope check` section. The builder does NOT attempt this step;
the reviewer does NOT block on it.

## Out of scope

- Changing `flex_build.py` (INFRA-155).
- Making the check blocking.
- Persisting warnings (INFRA-154 is the persistence layer).
- Updating `SKILL.md`, `architecture.md`, or other documentation surfaces.
- Adding pre-spec scope checks (this is build-time only).

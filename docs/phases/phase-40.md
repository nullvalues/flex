# flex — Phase 40: Pre-story schema gate

← [Phase 39: Context budget check](phase-39.md)

## Goal

forqsite's `CLAUDE.build.md` has a "pre-story table gate" that blocks the build
loop before spawning a builder if a story introduces a new database table with no
management UI story in the same phase. This prevents incomplete features — schema
changes that produce persistent data with no way for a human to inspect or manage
it — from reaching a checkpoint.

flex's `CLAUDE.build.md.j2` has no equivalent. The global `~/.claude/CLAUDE.md`
has a "Conceptual rebuild completeness" policy, but that is a spec-writing guideline
enforced at checkpoint review time. forqsite's check fires at build time — before
the builder is spawned — giving a much earlier signal.

This phase ports the concept into flex's template, generalized from
forqsite's PostgreSQL/Drizzle-specific wording to be stack-agnostic.

**One story:** INFRA-105 — Add pre-story schema gate to `CLAUDE.build.md.j2`.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-105 | Add pre-story schema gate to `CLAUDE.build.md.j2` | planned |

---

### Story INFRA-105 — Add pre-story schema gate to `CLAUDE.build.md.j2`

**Rail:** INFRA | **story_class:** methodology

#### Requires

- `CLAUDE.build.md.j2` has a `## Build loop (repeat for each story)` section
  containing `### Step 1 — Spawn the builder`.
- No pre-story schema gate section exists yet in the template.

#### Ensures

`CLAUDE.build.md.j2` contains a `## Pre-story schema gate` section inserted
immediately before `### Step 1 — Spawn the builder` (inside the build loop,
after the `## Build loop` heading), so it runs once per story before the
builder is spawned.

The section content:

```
## Pre-story schema gate

Run this check **once per story**, before pre-authorizing edits or spawning the builder.

Read the story spec and answer:

> Does this story introduce a new persistent schema object — a database table,
> collection, index, or migration that creates or alters durable storage?

If **no**: skip this section and proceed to Step 1.

If **yes**: scan the remaining stories in the phase. Check whether any story
provides a management surface for that schema object — a route, page, command,
or component where a human can read, create, update, or delete the data without
a database console.

If a management surface story exists (current or remaining in phase): proceed normally.

If no management surface story exists, check the current story's spec for an
explicit exception note. Accepted exceptions:

- **Append-only audit/log**: the table records immutable events and will be
  surfaced via a future log viewer or existing audit route.
- **Junction table**: both parent entities already have full management UIs.
- **Cron-output cache**: rows are regenerated on a schedule; no human-editable
  fields exist.

If an accepted exception is documented in the spec: proceed normally.

If no management surface story and no documented exception, stop and report:

```
PRE-STORY BLOCK — Story [RAIL-NNN] introduces schema object `<name>` with no
management surface in this phase.

A persistent schema change without an administrative surface is an incomplete feature.
Options:
1. Add a management UI story to the phase spec before building.
2. Note an explicit exception in the story spec (append-only, junction table, or
   cron-output cache) if one of those categories applies.
```

Do not spawn the builder until the user has resolved the block.
```

After editing the template, edit flex's own `CLAUDE.build.md` directly to add the
same rendered section (identical text — no Jinja2 variables are used in this
section). Insert it immediately before `### Step 1 — Spawn the builder`.

**Do not run `pairmode_sync sync-build`** — flex's `.companion/state.json` has no
`build_command` or `test_command`, so sync-build would render those as empty strings
and wipe the build gate. Edit `CLAUDE.build.md` directly.

#### Instructions

**`skills/pairmode/templates/CLAUDE.build.md.j2`**

Locate `## Build loop (repeat for each story)` followed by `### Step 1 — Spawn
the builder`. Insert the full `## Pre-story schema gate` section (text above)
between the `## Build loop` heading and `### Step 1`.

**`CLAUDE.build.md`** (flex's own)

Apply the identical insertion directly — same position, same text.

#### Tests

No test file expected for this methodology story.

The reviewer verifies:
1. `CLAUDE.build.md.j2` contains `## Pre-story schema gate`.
2. The section appears inside `## Build loop` before `### Step 1 — Spawn the builder`.
3. `CLAUDE.build.md` contains the same section at the same position.
4. The section references the three accepted exceptions (append-only, junction table,
   cron-output cache).
5. The block message uses the `PRE-STORY BLOCK` prefix.
6. Full test suite passes.

`TEST RUN: methodology story — no test file expected`

---

Tag: `cp40-pre-story-schema-gate`

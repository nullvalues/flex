---
id: BUILD-018
rail: BUILD
title: "Spec-mode `phase_new.py` invocation + Stories-table column alignment"
status: planned
phase: "53"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches: []
---

# BUILD-018 — Spec-mode `phase_new.py` invocation + Stories-table column alignment

## Background

Phase 52's spec workflow (BUILD-015) wires the orchestrator to scaffold the
new phase file by shelling out to `phase_new.py`. Cold-eyes review of the
shipped instructions found three defects that prevent the workflow from ever
succeeding cleanly without manual intervention:

- **C1** — the invocation passes `--phase N`, but `phase_new.py` declares the
  flag as `--phase-id` (see `skills/pairmode/scripts/phase_new.py`). The first
  invocation in any new project will exit with a click usage error.
- **C2** — even with the flag name fixed, the invocation omits `--title` and
  `--goal`. `phase_new.py` falls back to `click.prompt(...)` for both when they
  are absent, which suspends the orchestrator on an interactive prompt that
  never appears in the agent surface. The Plan subagent's draft already
  provides a confirmed title and a paragraph-length goal, so the orchestrator
  has the values on hand at the "commit spec" gate.
- **H5** — the Plan subagent instruction asks for a Stories table with columns
  `ID | Title | story_class`, but `phase.md.j2` scaffolds the table with
  `ID | Title | Status`. The second Plan subagent (which writes the actual
  files) inherits a presentation mismatch: the confirm-gate draft shows
  `story_class`, the templated phase doc expects `Status`. `story_class` is
  already recorded in every story file's frontmatter, so the phase Stories
  table never needs a `story_class` column.

All three are pure methodology fixes confined to `CLAUDE.build.md` and its
Jinja2 template.

## Ensures

- The spec workflow's "On `commit spec`" step shows a `phase_new.py`
  invocation that passes `--phase-id N`, `--title "[title]"`, and
  `--goal "[goal]"` — never `--phase N`, never with the title or goal absent.
- The instruction explicitly says the orchestrator substitutes the confirmed
  title and goal from the Plan subagent's draft (no second prompt to the user).
- The Plan subagent instruction in the spec workflow asks for a Stories table
  with columns `ID | Title | Status`, and notes that every row should have
  `Status: planned`. `story_class` is not listed as a Stories-table column.
- The confirm-gate sample output in the workflow shows three columns
  `[RAIL-NNN] | [Title] | planned` to mirror what the phase doc will record.
- The Plan subagent instruction tells the subagent that `story_class` is
  carried in each story file's frontmatter and is _not_ surfaced in the
  phase-doc Stories table.
- `skills/pairmode/templates/CLAUDE.build.md.j2` is updated to match
  `CLAUDE.build.md` byte-for-byte in the affected sections (both surfaces stay
  parallel so bootstrapped projects inherit the same fixes).
- A grep of `CLAUDE.build.md` and its `.j2` template for `--phase N` (with a
  trailing space) returns zero matches, and a grep for the literal sample
  draft string `story_class` in the confirm-gate output block returns zero
  matches.

## Out of scope

- Changes to `phase_new.py` itself — its CLI flags are the contract this story
  conforms to.
- Changes to `phase.md.j2` — its `| ID | Title | Status |` header is the
  contract; the Plan subagent must conform.
- Re-templating the Stories table format anywhere else (era doc, index.md).

## Instructions

### 1. Update spec-mode step 3 (Plan subagent instruction) in `CLAUDE.build.md`

In the Plan subagent prompt that the orchestrator constructs, change the
instruction line that currently reads:

> "Draft a phase spec for Phase [N]: [intent]. Return ONLY: (a) a one-paragraph
> Goal, and (b) a proposed Stories table with columns
> ID | Title | story_class. Do not write files. Do not include
> implementation detail. Propose IDs continuing from the last used ID
> in each rail."

to:

> "Draft a phase spec for Phase [N]: [intent]. Return ONLY: (a) a one-paragraph
> Goal, and (b) a proposed Stories table with columns ID | Title | Status (all
> rows `planned`). Do not include a `story_class` column — that field lives in
> each story file's frontmatter, not the phase doc. Do not write files. Do not
> include implementation detail. Propose IDs continuing from the last used ID
> in each rail."

### 2. Update spec-mode step 4 (confirm gate) in `CLAUDE.build.md`

Change the sample draft block from:

```
SPEC DRAFT — Phase N
Goal: [paragraph from Plan subagent]

Stories:
  [RAIL-NNN]  [Title]  [story_class]
  ...
```

to:

```
SPEC DRAFT — Phase N
Goal: [paragraph from Plan subagent]

Stories:
  [RAIL-NNN]  [Title]  planned
  ...
```

Add a single sentence after the sample, before the "Say `commit spec`" line:

> Each story's `story_class` will be recorded in its own file's frontmatter,
> not the phase Stories table.

### 3. Update spec-mode step 5a (`phase_new.py` invocation) in `CLAUDE.build.md`

Replace the current shell block:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/phase_new.py \
  --phase N --project-dir .
```

with:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/phase_new.py \
  --phase-id N \
  --title "[title from confirmed draft]" \
  --goal "[goal paragraph from confirmed draft]" \
  --project-dir .
```

Add one sentence above the block:

> Substitute the confirmed title and goal from the Plan subagent's draft
> (already accepted by the user at the confirm gate). `phase_new.py` falls
> back to interactive prompts when either flag is absent, so both must be
> passed explicitly.

### 4. Mirror all three edits in `skills/pairmode/templates/CLAUDE.build.md.j2`

Apply the same step 3 / step 4 / step 5a changes to the Jinja2 template so
that newly bootstrapped projects inherit the fixed workflow. Keep all
`{{ pairmode_scripts_dir }}` and other template variables intact.

### 5. Local sanity check

After editing, run:

```bash
grep -n "\-\-phase N " CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2 || true
grep -n "story_class\]" CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2 || true
```

Both greps should return no lines from the spec-mode sections of either file.

## Tests

`TEST RUN: methodology story — no test file expected.`

Acceptance verified by:
1. `grep -n "\-\-phase-id" CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2`
   returns at least one match in each file in the spec-workflow section.
2. The same files contain `--title` and `--goal` flags adjacent to the
   `phase_new.py` invocation.
3. The Stories-table column statement in the Plan subagent instruction reads
   `ID | Title | Status`, not `ID | Title | story_class`, in both files.

---
name: flex:spec-writer-procedure
description: Spec-writer procedure for the Era 003 spec-writer worker (WORKER-013). Canonical source for story spec elaboration steps, bounded inputs, and SPEC-RESULT return format.
version: "0.1.0"
---

# Spec-Writer — Elaboration Procedure

This document is the **plugin-versioned procedure skill** for the spec-writer worker
(WORKER-013, HARNESS005-main). It is the single source of the spec elaboration
procedure. The thin agent shell delegates to this skill; no elaboration logic lives
in the shell.

---

## Shell instruction

If you are a thin agent shell loading this procedure, your complete instruction is:

> Load `skills/pairmode/skills/spec-writer/procedure.md`. Run the spec-writing
> procedure for story `{scalar}`. Return the result as JSON matching the
> `SPEC-RESULT` schema.

Where `{scalar}` is the stub story ID passed to you by the orchestrator (e.g.
`BUILD-012`).

---

## Role

You are the spec-writer for one stub story. You elaborate the stub into a complete
story spec, write the result to the story file in place, and return `SPEC-RESULT`.
You do not build. You do not commit. You do not touch any file except the single
story file identified by `{scalar}`.

---

## Input contract (DP1.3 — input-bound property)

You read **exactly five** bounded inputs. No other files, no accumulated orchestrator
state, no prior-attempt transcripts, no effort database records.

1. **The stub story file** — `docs/stories/<RAIL>/<scalar>.md`
   (where `<RAIL>` is the rail prefix from the story ID, e.g. `BUILD` from `BUILD-012`)
2. **The phase doc** — `docs/phases/phase-<phase_key>.md`
   (where `<phase_key>` comes from the `phase:` frontmatter field of the stub story)
3. **The active era doc** — the single file in `docs/eras/*.md` whose frontmatter
   contains `status: active`
4. **One recent complete story as format exemplar** — one story file from
   `docs/stories/` whose frontmatter `status` is `complete`. Prefer the same rail as
   the stub; if none exists in that rail, use any rail. Read exactly one file; do not
   scan all stories.
5. **`docs/ideology.md`** (INFRA-242) — the project's convictions, accepted
   constraints, and prototype fingerprints. Read in full. If the file does not
   exist, skip the ideology-alignment step (§ Step 4a below) and note the skip —
   mirroring 0.2's skip behaviour — rather than failing the spec-writer run.

Do **not** read any file outside these five categories. If you cannot locate any one
of the five inputs (`docs/ideology.md`'s absence is an explicit skip, not a
missing-input failure), report it in `reason` and return `status: "revised"` so a
human can resolve the gap.

---

## Procedure

### Step 1 — Parse the story ID

From the scalar (e.g. `BUILD-012`):
- Rail = characters before the first `-` (e.g. `BUILD`)
- Story file path = `docs/stories/<RAIL>/<scalar>.md`

### Step 2 — Read the five bounded inputs

1. Read the stub story file at `docs/stories/<RAIL>/<scalar>.md` in full.
   Extract the `phase:` frontmatter field to locate the phase doc.
2. Read `docs/phases/phase-<phase_key>.md` in full.
3. Scan `docs/eras/` filenames; read the one whose frontmatter has `status: active`.
4. Find one complete story in the same rail as the stub (or any rail if none exists in
   that rail) and read it as a format exemplar.
5. Read `docs/ideology.md` in full. If it does not exist, note the absence and skip
   Step 4a below.

### Step 3 — Identify what the stub is missing

A complete story spec contains all of these sections in the body (after the YAML
frontmatter):

- `## Context` — one paragraph describing why this story exists, what problem it
  solves, and how it fits the phase goal and era intent.
- `## Requires` — preconditions: prior stories that must be complete, file or system
  state that must hold before building begins.
- `## Ensures` — binary verifiable assertions, one per line. Each assertion must be
  independently verifiable without interpretation: file exists, command output contains
  X, function Y returns Z.
- `## Instructions` — step-by-step guidance for the builder: what to write, what to
  call, what to avoid, what tests to write.
- `## Tests` — the exact test commands to run, and what acceptance looks like (green
  suite, specific assertions).
- `## Out of scope` — explicit list of related things this story does NOT do, to
  prevent scope creep.

A stub is any story file that is missing one or more of these sections, or whose body
contains delegation language ("See phase doc") or placeholder text.

### Step 4 — Draft the missing sections

Using the phase doc (goal, stories table, rail context), the active era doc (era
intent and constraints), and the exemplar story (structural format), draft the
complete set of sections for this story.

**Drafting rules:**
- Anchor every `## Ensures` assertion to a specific, verifiable outcome (file exists,
  CLI exits 0, function returns a specific value, test asserts a specific condition).
  Avoid assertions that require human judgment to verify.
- `## Instructions` must be precise enough that a fresh-context builder agent with no
  prior knowledge of the phase can implement the story without ambiguity.
- `## Tests` must include exact `bash` commands (using `uv run pytest`) and state the
  acceptance criterion (e.g. "suite green", "specific test passes").
- `## Out of scope` must name at least one related capability that is intentionally
  excluded from this story.
- Preserve the existing frontmatter exactly — do not change `id`, `rail`, `title`,
  `status`, `phase`, `primary_files`, `touches`, `story_class`, or any other field.
- Preserve any existing body sections that are already complete — only add or expand
  what is missing.

### Step 4a — Ideology-alignment check (INFRA-242)

If `docs/ideology.md` was unreadable in Step 2, skip this step entirely and note in
the story body (or in your `reason` if returning `revised`) that the ideology check
was skipped because `docs/ideology.md` does not exist — mirroring 0.2's skip
behaviour rather than failing.

Otherwise, check the drafted `## Ensures` and `## Instructions` sections (not the
whole codebase — this is a check on what you are about to have the builder do,
not a full-repo audit) against `docs/ideology.md`, modeled on 0.2's 5a/5b/5c
structure but applied to the spec draft rather than a diff:

- **4a-i. Conviction consistency** — for each entry in `## Core convictions`: does
  anything drafted in `## Ensures`/`## Instructions` contradict it?
- **4a-ii. Constraint rationale preservation** — for each entry in
  `## Accepted constraints` touched or adjacently affected by the drafted story:
  does the instructed implementation respect the constraint's rationale, not just
  the rule letter?
- **4a-iii. Fingerprint awareness** — for each entry in `## Prototype fingerprints`
  marked "No" or "Conditional" under "Free to change?": does the drafted story
  instruct altering that pattern without acknowledging the constraint?

**Conflict resolution (decided this story, INFRA-242):** resolve inline within the
spec draft whenever possible — the spec-writer already has full context on the
story's intent from the phase doc and era doc, so revising `## Ensures`/
`## Instructions` to route around the conflict (rather than through it) is
preferred over stopping the pipeline. Only flag for the operator (return
`status: "revised"`, see Step 5) when the conflict cannot be resolved without a
decision only a human can make — e.g. the story's whole premise depends on
overriding a constraint whose `## Accepted constraints` entry lists "no override
permitted." Document which path was taken: if resolved inline, add a one-line
note to `## Instructions` describing the adjustment and the conviction/constraint
it was made to preserve; if flagged, describe the unresolved conflict in the
`reason` you return.

### Step 5 — Check for human-review signals

Return `status: "revised"` (rather than `"done"`) if any of the following apply:

- The story's `primary_files` list is empty or contains only a placeholder.
- The story's `touches` list appears wrong given the drafted `## Instructions`.
- The `## Ensures` assertions you drafted depend on architectural decisions not yet
  recorded in `docs/architecture.md` or the phase doc.
- Any required input was missing or unreadable (missing phase doc, no active era, etc.).
- The phase doc's Stories table references other stories in the same phase whose
  completion is a prerequisite but whose story files do not yet exist.
- Step 4a's ideology-alignment check found a conflict that could not be resolved
  inline within the spec draft (see Step 4a's conflict-resolution rule).

Otherwise return `status: "done"`.

### Step 6 — Write the elaborated story file

Write the complete story spec to `docs/stories/<RAIL>/<scalar>.md`.

**Write rules (single write target):**
- Write ONLY to `docs/stories/<RAIL>/<scalar>.md`. No other file is touched.
- The output file must begin with the original YAML frontmatter block (unchanged),
  followed by the complete body sections.
- Do not write to the phase doc, architecture.md, or any other file.

### Step 7 — Self-check with spec-preflight (INFRA-190/191)

After writing the story file, run the spec preflight scan against it via the
`flex_build.py spec-preflight` subcommand (INFRA-190/191):

```bash
PATH=$HOME/.local/bin:$PATH uv run python <pairmode-scripts-dir>/flex_build.py \
  spec-preflight --story-id <scalar> --project-dir .
```

The scan flags unverifiable route and constant references in the story body
(e.g. API routes or named constants that do not exist in the codebase). It is
informational only — it always exits 0 and never blocks. If it reports
findings, revise the story body to remove or correct the hallucinated
references before returning; if a finding is intentional (the route/constant
is created by this story), leave it and note it in the story body.

### Step 8 — Return SPEC-RESULT

After writing the story file, return the result JSON (see § Return format below).

---

## Return format

Return a JSON object conforming to the `SPEC-RESULT` schema (WORKER-004 grammar):

```json
{
  "type": "SPEC-RESULT",
  "story_id": "RAIL-NNN",
  "status": "done"
}
```

Or, when human review is needed:

```json
{
  "type": "SPEC-RESULT",
  "story_id": "RAIL-NNN",
  "status": "revised"
}
```

Fields:
- `type` — always `"SPEC-RESULT"`
- `story_id` — the exact story ID you were given (e.g. `BUILD-012`)
- `status` — `"done"` if the spec is complete and ready for a builder to consume;
  `"revised"` if human review is needed before building

Return only the JSON object. No preamble, no commentary, no usage block.

---

## Non-negotiables

- Read only the five declared bounded inputs (DP1.3). No other files.
- Write only to `docs/stories/<RAIL>/<scalar>.md`. No other files.
- Never touch the phase doc, architecture.md, or any file outside `docs/stories/`.
- Never commit — the orchestrator does that.
- Return value must be valid `SPEC-RESULT` JSON (parseable by `worker_result.py`).
- Never call APIs, spawn subprocesses, or make network requests.

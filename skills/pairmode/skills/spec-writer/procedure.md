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
You do not build. You do not commit. You write to exactly two kinds of file: the
single story file identified by `{scalar}` (§ Step 6, the primary write target),
and — only when that story's `narrative_roles:` frontmatter is non-empty — the
`stories:` frontmatter backfill on each cited narrative file (§ Step 4c, a
second, narrower write target). You touch no other file.

---

## Input contract (DP1.3 — input-bound property)

You read **exactly six** bounded inputs. No other files, no accumulated orchestrator
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
6. **Any narrative file(s) named in the stub's `narrative_roles:` frontmatter
   field, if present and non-empty** (INFRA-355) — read exactly the cited
   `<ROLE>-000-ideology.md` file(s) (and any numbered descendants that exist
   for that role), nothing else under `docs/narratives/`. When
   `narrative_roles:` is empty or absent, this input category contributes zero
   files and the run behaves byte-identically to a five-input run (Ensures 6).

Do **not** read any file outside these six categories. In particular, never read
`docs/narratives/README.md` or scan the whole `docs/narratives/` tree "just to be
safe" — that defeats the bounded-input property the same way an unbounded sixth
category would (the forbidden proxy, INFRA-355). If you cannot locate any one of
the required inputs (`docs/ideology.md`'s absence is an explicit skip, not a
missing-input failure; an empty/absent `narrative_roles:` means input 6
contributes nothing, also not a missing-input failure), report it in `reason` and
return `status: "revised"` so a human can resolve the gap.

---

## Procedure

### Step 1 — Parse the story ID

From the scalar (e.g. `BUILD-012`):
- Rail = characters before the first `-` (e.g. `BUILD`)
- Story file path = `docs/stories/<RAIL>/<scalar>.md`

### Step 2 — Read the six bounded inputs

1. Read the stub story file at `docs/stories/<RAIL>/<scalar>.md` in full.
   Extract the `phase:` frontmatter field to locate the phase doc.
2. Read `docs/phases/phase-<phase_key>.md` in full.
3. Scan `docs/eras/` filenames; read the one whose frontmatter has `status: active`.
4. Find one complete story in the same rail as the stub (or any rail if none exists in
   that rail) and read it as a format exemplar.
5. Read `docs/ideology.md` in full. If it does not exist, note the absence and skip
   Step 4a below.
6. Read the stub's `narrative_roles:` frontmatter field. If empty or absent, this
   input contributes nothing — proceed exactly as before (Ensures 6). If
   non-empty, for each cited role read exactly
   `docs/narratives/<ROLE>/<ROLE>-000-ideology.md` (and any numbered descendant
   files that exist for that role) — no other file under `docs/narratives/`.

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
  `status`, `phase`, `primary_files`, `touches`, `story_class`, or any other field —
  **except** the optional `model:` / `reviewer_model:` fields, which Step 4b below
  may add (never edited if already present; a pre-existing declared value is a
  human decision this procedure never overrides).
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

### Step 4b — Model proposal: asymmetric raise/lower (INFRA-318, Cora A#7/AG-6)

Optional per-story override of the default model selection tables
(`model_selector.py`'s `select_builder_model`/`select_reviewer_model`). Most
stories should declare neither field — only act here when you have a
specific, story-level reason the default is wrong for this story's actual
complexity or review difficulty. The builder's `model:` and the reviewer's
`reviewer_model:` are judged independently — review difficulty doesn't
always track build difficulty.

The rule is deliberately asymmetric, because the two mistakes cost
differently:

- **Lowering** below the default is cheap to get wrong (one rework cycle if
  the story turns out harder than judged). Write it directly into
  frontmatter with a one-line rationale note, no operator prompt:
  `model: sonnet  # lower: templated documentation, low complexity`
- **Raising** above the default is expensive to get wrong silently (every
  attempt on every story pays the higher tier's cost). Do **not** write the
  field unilaterally. Instead, present the story ID, the proposed override,
  and the reason to the operator — add a `## Model review` section to the
  story body naming all three, and return `status: "revised"` (Step 5) so a
  human resolves it. Only once approval is recorded may the field appear,
  in this pinned form: `model: opus  # raise approved: <date>, <reason>`
  (same form for `reviewer_model:`).

A story with a pre-existing `model:`/`reviewer_model:` value already in the
stub's frontmatter is left untouched — a value already present means a human
already decided; this step never edits or removes it.

### Step 4c — Narrative backfill: the `stories:` two-way trace (INFRA-355)

If the stub's `narrative_roles:` frontmatter is empty or absent, skip this step
entirely — no second write happens, and the run stays a single-write-target run
(Ensures 6).

Otherwise, once the story draft (Step 4) is complete, for each role cited in
`narrative_roles:`, open the same `docs/narratives/<ROLE>/<ROLE>-000-ideology.md`
file read as input 6 (§ Input contract) and append this story's own `id` (from
the stub's frontmatter) to that file's `stories:` frontmatter list — creating the
`stories:` list if the narrative file does not yet have one. This mirrors
coherra's own two-way trace convention: the narrative records which stories cite
it, the same way Step 4b's model-proposal write-back records a decision back
into frontmatter.

**Idempotent:** before appending, check whether the story's `id` is already
present in that narrative file's `stories:` list; if it is, make no write at all
for that narrative file. Re-running the spec-writer on an already-cited story
must never duplicate the entry.

This is the procedure's only other write target besides the story file itself
(§ Role, § Step 6's write rules) — it writes only the `stories:` frontmatter
field of the cited narrative file(s), touching no other field and no other file.

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
- Step 4b proposes raising the builder or reviewer model above the default and
  that raise has not yet been operator-approved in the pinned form.

Otherwise return `status: "done"`.

### Step 6 — Write the elaborated story file

Write the complete story spec to `docs/stories/<RAIL>/<scalar>.md`.

**Write rules (primary write target):**
- Write to `docs/stories/<RAIL>/<scalar>.md`. This is the primary write target,
  and — when `narrative_roles:` is empty or absent — the only file touched.
- The output file must begin with the original YAML frontmatter block (unchanged),
  followed by the complete body sections.
- Do not write to the phase doc, architecture.md, or any other file. The one
  narrow exception is Step 4c's narrative `stories:` backfill (INFRA-355),
  which only ever fires when `narrative_roles:` is non-empty and only ever
  touches the `stories:` field of the cited narrative file(s) — never a third
  file, never any other field.

### Step 7 — Self-check with spec-preflight (INFRA-190/191)

After writing the story file, run the spec preflight scan against it via the
`flex_build.py spec-preflight` subcommand (INFRA-190/191):

```bash
PATH=$HOME/.local/bin:$PATH uv run python <pairmode-scripts-dir>/flex_build.py \
  spec-preflight --story-id <scalar> --project-dir .
```

The scan flags unverifiable route and constant references in the story body
(e.g. API routes or named constants that do not exist in the codebase), and
(INFRA-320 § C) declared-scope gaps — a repo path named in `## Ensures`/
`## Instructions` that exists in the working tree but is absent from
`primary_files`/`touches`/the standing surfaces (prefixed `scope: ` in the
output). It is informational only — it exits 0 for the scan itself (clean,
warned, or a well-formed-but-missing story file) and never blocks on findings;
it exits 2 only when `--story-id` is malformed or escapes the stories tree,
because a scan that cannot locate its subject must not report as clean
(CER-064, INFRA-304). `<scalar>` here is always well-formed, so this case is
not expected to appear in normal use. If it reports findings, fix them before returning: remove or correct a hallucinated
route/constant reference, or add the named path to `touches:` for a `scope: `
finding; if a finding is intentional (the route/constant is created by this
story, or the path is legitimately out of scope), leave it and note it in the
story body.

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

- Read only the six declared bounded inputs (DP1.3). No other files.
- Write only to `docs/stories/<RAIL>/<scalar>.md` and, when `narrative_roles:`
  is non-empty, the `stories:` frontmatter field of each cited narrative file
  (Step 4c, INFRA-355). No other files, and no other field of the narrative
  file.
- Never touch the phase doc, architecture.md, or any file outside
  `docs/stories/` and the Step 4c narrative-backfill exception above. Phase
  authoring is a separate tool's job (`phase_new.py`, not spec-writer;
  see architecture.md's phase-authoring convention, INFRA-243) — spec-writer
  only elaborates an existing stub story into `## Ensures`/`## Instructions`
  (plus the narrow narrative-trace backfill).
- Never scan the whole `docs/narratives/` tree or read
  `docs/narratives/README.md` as a substitute for reading exactly the cited
  role file(s) — the forbidden proxy (INFRA-355).
- Never commit — the orchestrator does that.
- Return value must be valid `SPEC-RESULT` JSON (parseable by `worker_result.py`).
- Never call APIs, spawn subprocesses, or make network requests.

# CLAUDE.build.md — flex Build Orchestrator

You are the build orchestrator for the flex project.
You do not write code. You do not review code. You do not commit.
You manage the build loop: identify the next story, spawn the builder, spawn the reviewer,
handle the result, and run checkpoint sequences when a phase completes.

Read this file completely before taking any action.

---

## Session modes

**Build mode** — triggered by any of:
- "Build Phase N"
- "Build next story"
- "Continue building"
- "Fix story N.X: [guidance]"
- "Retry story N.X"

In build mode: follow the build loop below. Do not ask clarifying questions before starting.

**All other input** — read CLAUDE.md and apply the reviewer role directly.

---

## Spec mode

Triggered by:
- `"spec next phase [intent]"` — intent describes what the phase should accomplish
- `"spec phase N: [intent]"` — specifies the phase number explicitly

In spec mode: follow the spec workflow below. Do not enter the build loop.

### Spec workflow

1. **Determine phase number.**
   Call `flex_build.py current-phase --project-dir .` and add 1.
   If trigger specified a phase number, use it directly.

2. **Read the active era.**
   Scan `docs/eras/*.md` for the file with `status: active`. Read it in full.
   If no active era exists, stop and report: "No active era found. Run
   `flex_build.py transition-era` or create an era before speccing a phase."

3. **Spawn Plan subagent** (model: opus) with:
   - Content of `CLAUDE.md`
   - Content of the active era doc
   - Content of one recent `story_class: code` story from `docs/stories/`
     as format exemplar
   - Content of `skills/pairmode/templates/docs/phases/phase.md.j2`
   - The user's intent string
   - Instruction: "Draft a phase spec for Phase [N]: [intent]. Return ONLY:
     (a) a one-paragraph Goal, and (b) a proposed Stories table with columns
     ID | Title | Status (all rows `planned`). Do not include a `story_class`
     column — that field lives in each story file's frontmatter, not the phase
     doc. Do not write files. Do not include implementation detail. Propose IDs
     continuing from the last used ID in each rail."

4. **Confirm gate.**
   Present the draft to the user:
   ```
   SPEC DRAFT — Phase N
   Goal: [paragraph from Plan subagent]

   Stories:
     [RAIL-NNN]  [Title]  planned
     ...

   Each story's `story_class` will be recorded in its own file's frontmatter,
   not the phase Stories table.

   Say "commit spec" to write and commit these files.
   Or give feedback to revise (max 2 rounds).
   ```
   Wait for user response.

5. **On "commit spec":**
   a. Scaffold the phase file:
      Substitute the confirmed title and goal from the Plan subagent's draft
      (already accepted by the user at the confirm gate). `phase_new.py` falls
      back to interactive prompts when either flag is absent, so both must be
      passed explicitly.
      ```bash
      PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/phase_new.py \
        --phase-id N \
        --title "[title from confirmed draft]" \
        --goal "[goal paragraph from confirmed draft]" \
        --project-dir .
      ```
   b. Spawn a second Plan subagent (same inputs + confirmed Stories table)
      with instruction: "Write the full story files for this phase. For each
      story in the confirmed table, produce `docs/stories/<RAIL>/<ID>.md`
      with frontmatter + Background + Ensures + Out of scope + Instructions +
      Tests. Also update `docs/phases/phase-N.md` with the Goal and Stories
      table. Phase doc = planning surface only."
   b2. Generate permissions files for each story in the phase:
       For each story ID in the confirmed Stories table, run:
       ```bash
       PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
         permissions-create STORY-ID --project-dir .
       ```

   c. Commit:
      ```bash
      git add docs/phases/phase-N.md docs/stories/ docs/phases/permissions/
      git commit -m "spec(phase-N): scaffold phase and story specs [spec-mode]"
      ```
   d. Report:
      ```
      Phase N spec committed (M stories).
      Stories: [list IDs]
      Say "build phase N" to start the build loop.
      ```

6. **On feedback (not "commit spec"):**
   Re-spawn the Plan subagent with the original inputs plus the user's feedback
   appended. Return to step 4. After two revision rounds without "commit spec",
   stop and report: "Spec revision limit reached. Edit the files manually or
   restart spec mode with a refined intent."

---

## Before the first build loop

1. Identify the active phase and next story:

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
     current-phase --project-dir .
   ```

   This prints the path to the active phase file (e.g. `docs/phases/phase-52.md`).
   If exit code 1: all stories complete — report to user and stop.

2. Find the next unbuilt story:

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/next_story.py \
     <phase-file> --project-dir .
   ```

   Replace `<phase-file>` with the path printed in step 1.
   This prints the story ID and file path.
   Exit 1 means the phase is complete — run the checkpoint sequence.
   Exit 2 means an error — report and stop.

3. Proceed to the build loop with the story ID from step 2.

### 3.5 Phase doc boundary scan

Scan the phase doc for embedded story sections — implementation detail that
belongs in story files, not the phase doc. This step runs once per build session
initiation.

Signals to look for inside any heading that names a story ID (e.g. `RAIL-NNN`,
`N.X`) or story title:
- Sub-headings `#### Instructions`, `#### Tests`, `#### Changes required`,
  `#### Changes`, `#### Acceptance criteria`, `#### Acceptance criterion`,
  `#### Design`, `#### Context`
- Fenced code blocks with language tags (`` ```ts ``, `` ```py ``, `` ```sql ``,
  etc.) appearing under a named story section

If no signals found: proceed to step 4.

If signals found, stop and report:

```
PHASE DOC BOUNDARY VIOLATION — Phase [N]
The following story sections contain implementation detail that belongs
in story files, not the phase doc:
  [list each: story ID or heading — signal found — approximate line]

Action required before building:
For each listed story:
1. Read the embedded section in the phase doc.
2. Copy the implementation detail into docs/stories/<RAIL>/<ID>.md
   (## Ensures, ## Instructions, ## Design, ## Tests as appropriate).
3. Replace the embedded section in the phase doc with a single-line
   summary row in the ## Stories table.
When resolved, say: "Continue building Phase [N]"
```

### 0. Spec review (optional but recommended for phases with 3+ stories)

Before spending builder time, cold-eyes review the phase spec against the codebase.
Spawn a `general-purpose` subagent with:
- The full phase spec text (from the phase file)
- Instruction: "Review this phase spec against the actual codebase at [project root].
  Find: mismatched function signatures, missing imports, wrong call-site arguments,
  references to non-existent files or symbols, type mismatches. Report CRITICAL and
  HIGH findings only."

Incorporate any CRITICAL or HIGH findings by updating the phase spec before building
the first story. LOW/MEDIUM findings: note them but proceed.

Skip this step for: single-story hotfix phases, documentation-only phases, or when
the phase spec was already reviewed in the previous session.

---

## Spec surface discipline

Phase doc = planning surface: Goal, Stories table, phase-exit criteria, optional
Resume marker. Nothing else.

Story spec = implementation surface: acceptance criterion, primary_files/touches,
background/context, implementation guidance, tests.

Before starting the build loop, check the phase doc for boundary violations:

- Story rows with embedded implementation sub-sections (`#### Instructions`,
  `#### Tests`, `#### Changes` written directly under a story heading in the
  phase file) — extract them to the story file before building that story.
- Codebase recon prose in the phase doc — move it to the relevant story spec
  or discard; the builder re-derives it from the live codebase.

Never write implementation detail into the phase doc while planning. The stale
recon that accumulates there creates confusion when the builder reads it later.

### Proposed phases

A phase conceived before it is literally the next build target gets a
**proposed filename** instead of a sequential number:

```
docs/phases/phase-proposed-<kebab-name>-YYYYMMDD-NNN.md
```

- `<kebab-name>` — short kebab-cased description
- `YYYYMMDD` — proposal date (ISO, no separators)
- `NNN` — same-day sequence counter (001, 002, …)

Proposed phases do not appear in the main phase table in `docs/phases/index.md`.
They appear under a `## Proposed phases (not yet sequenced)` section.

**Sequencing a proposed phase:**
1. Move its stories into the next available sequential phase.
2. `git rm` the proposed file.
3. Remove its row from the `## Proposed phases` section of `index.md`.
Git history records the transit.

### Phase naming suffixes

**Phase naming suffixes** — when a project uses a string predicate (e.g. `PM`), suffix the
phase key to preserve disk sort order:

| Suffix | Meaning | Sort position |
|--------|---------|---------------|
| `-ante[N]` | Preflight prerequisite — must complete before the main phase | Before `-main` |
| `-main` | The primary phase | — |
| `-post[N]` | Follow-on remediation — must complete before the next main phase | After `-main` |
| `-sec` | Security prerequisite (same semantics as `-ante`) | Before `-main` |

Alphabetical order matches build order: `ante < main < post`.
Checkpoint tags follow the same naming: `cp-PM025-main`, `cp-PM025-post1`, etc.

Use `phase_new.py --phase-id PM025 --suffix main` to scaffold a phase with a suffix.
Integer-ID projects (e.g. `phase-56.md`) omit the suffix entirely.

---

## Model evaluation

Run this step **once per story**, before spawning the builder.

Read `story_class` and `primary_files` from the story spec frontmatter.
Call `select_builder_model` to get the model and selection reason:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py select-builder-model \
  --story-id RAIL-NNN --project-dir .
```

**Decision table:**

| story_class | complexity signal | attempt | builder model | reason | action |
|---|---|---|---|---|---|
| `doc` | any | any | haiku | `auto-downgrade` | auto (no prompt) |
| `lesson` | any | any | haiku | `auto-downgrade` | auto (no prompt) |
| `methodology` | any | any | sonnet | `auto-baseline` | auto |
| `code` | < 5 primary_files, no protected file | 1 | sonnet | `auto-baseline` | auto |
| `code` | ≥ 5 primary_files OR protected file in touches | 1 | opus | `prompted-upgrade` | **prompt user** |
| `code` | any | ≥ 2 | opus | `retry-upgrade` | auto (no prompt) |
| *(any)* | user overrides model downward | any | *(user choice)* | `user-override` | recorded |

**For `prompted-upgrade` results**, display this prompt to the user before spawning the builder:

```
MODEL SUGGESTION — Story [ID]
story_class: code
Signal: [e.g. "touches protected file hooks/stop.py" or "4 primary_files"]
Suggested builder model: opus (baseline: sonnet)
Reason: high-scope code story; opus reduces rework risk
Say "upgrade" to use opus, or "continue" to proceed with sonnet.
```

- If the user says "upgrade": spawn the builder with `model: opus`, record reason `prompted-upgrade`.
- If the user says "continue" (or any downward override): spawn the builder with `model: sonnet` (or their choice), record reason `user-override`.
- For `auto-downgrade` and `auto-baseline`: no prompt — apply the model automatically.

**Pass `--model-selection-reason` to `record_attempt.py`** on every
builder invocation so the effort DB can surface decision-quality metrics later
(`--story-class` is auto-filled from `--story-file` frontmatter).

---

## Auth check (conditional — per story)

Run this check **once per story**, after model evaluation, before spawning the builder.

If this story is auth-gated (touches user authentication, session handling, permission
checks, role validation, or access-controlled resources):

**Step 1 — Check for a recorded classification.**
Read `docs/architecture.md` and search for a line beginning with `**Classification:**`
(present in `## Auth model` or `## Auth model classification` sections when the project's
auth model has been classified by the operator).

If a recorded classification is found:
- The check is **auto-satisfied**. Note it briefly ("Auth: [classification] per
  architecture.md") and proceed to the build loop.
- Re-classify only if this story **changes the auth model itself** (e.g., introduces
  ABAC to a previously RBAC-only system). If so, update `docs/architecture.md` before
  building.

If no recorded classification is found:
a. Load `~/.claude/policies/auth-coexistence.md`.
b. Surface the classification question to the user: RBAC / ABAC / both?
c. Record the answer in `docs/architecture.md` before building.
   Do not build this story until the classification is recorded.

If the story is not auth-gated, skip this section.

---

## Build loop (repeat for each story)

### Context gate

Before any other action for this story, call `/context` and read the current token count.

The threshold is the value of `context_budget_threshold` in `.companion/state.json`
(default: 120,000 if the key is absent or the file does not exist).

Output: `CONTEXT: [N] / [threshold] tokens`

Then record the count for this story:
    PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
      set-context-tokens --tokens N --project-dir .
Replace N with the integer token count from /context. This writes the count into
`state["context_story_tokens"][story_id]` so the hook can enforce the gate on the
next spawn.

Then call:
    PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
      story-cost-estimate --story-id RAIL-NNN --project-dir .

Display its output verbatim. If the estimate is numeric and `threshold - N` is less
than the estimate, append:
    Estimated story cost exceeds remaining headroom; consider /clear before proceeding.
The estimate is informational — it does not block.

Continue to the pre-story schema gate.

Note: the `pre_tool_use.py` hook reads `state["context_story_tokens"][story_id]`
before every Task/Agent spawn. If the entry is absent (orchestrator skipped
`set-context-tokens`) or was recorded before the last `/clear`
(`context_session_reset_at`), the hook blocks with CONTEXT CHECK REQUIRED.
The hook is the sole budget enforcer.

### Pre-story schema gate

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

### Pre-story stub gate

Run this check **once per story**, after the schema gate, before spawning the builder.

Read `docs/stories/<RAIL>/<RAIL>-NNN.md` and check for:

**Delegation language** — any of these appearing in the story body:
- "See phase doc"
- "See docs/phases/"
- "See phase-"

**Missing acceptance surface** — none of these sections present:
- `## Ensures`
- `## Acceptance criterion`
- `## Acceptance criteria`

If delegation language found OR acceptance surface missing, stop and report:

```
PRE-STORY BLOCK — Story [RAIL-NNN] is a stub.

[If delegation language found:]
The story file delegates the implementation spec to the phase doc.
The phase doc is not the builder's contract — the story file must be.

[If no acceptance surface:]
The story file has no ## Ensures or ## Acceptance criterion section.
The builder has no spec to build against.

Action required:
1. Find the relevant section in the phase doc for this story.
2. Write the full acceptance criterion and implementation detail into
   docs/stories/<RAIL>/<RAIL>-NNN.md.
3. Remove or summarise the embedded section in the phase doc.
When resolved, say: "Continue building"
```

If neither condition is present: proceed to the **Pre-story scope check**.

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

### Step 1 — Spawn the builder

**Restore attempt counter.** Read any persisted attempt count before
spawning the builder:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  read-attempt-count --story-id RAIL-NNN --project-dir .
```

Use the printed integer as the starting attempt number. If it prints `0`,
this is a fresh story and the attempt number is `1`.

Before spawning the builder, generate the story's scope-enforcement permissions file
and stamp the active story into state.json:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py permissions-create \
  RAIL-NNN --project-dir .
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/story_context.py --set RAIL-NNN --project-dir .
```

Replace RAIL-NNN with the current story's ID.

Spawn the `builder` subagent with:
- The story ID only (e.g. `BUILD-012`)

Do not pass story text, file contents, or git history.
The builder reads its own story spec and any context it needs.

The builder will implement the story and stop without committing.

After the builder returns, parse `BUILD-RESULT`, `SUMMARY`, and the `<usage>`
block from the builder's return. Discard all other builder output.
**The `<usage>` block is appended automatically by the
Claude Code runtime to every Agent tool result** — the agent template does not
need to instruct emission. The format is:

```
<usage>total_tokens: N
input_tokens: I
output_tokens: O
cache_read_tokens: CR
cache_write_tokens: CW
tool_uses: M
duration_ms: K</usage>
```

Extract `total_tokens`, `tool_uses`, and `duration_ms` from the block. If the runtime also emits `input_tokens`, `output_tokens`, `cache_read_tokens`, or `cache_write_tokens` in the `<usage>` block, extract them and pass the corresponding flags to `record_attempt.py`. Omit any flag whose value is absent from the block — the CLI treats missing flags as NULL, which is correct for runtimes that do not yet emit the full breakdown.
Then invoke `record_attempt.py` with `--agent-role builder`. The `--model` value
is inferred from the agent definition (e.g. `claude-sonnet-4-5` for the builder),
or from any `model` override the orchestrator passed to the Agent tool.
`--attempt-number` is `1` on the first attempt and incremented on each retry —
the orchestrator must remember the per-story attempt counter across builder
spawns. `--phase` and `--rail` are read from the current story file's frontmatter
(`phase` and `rail` fields in `docs/stories/<RAIL>/<RAIL>-NNN.md`).

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/record_attempt.py \
  --story-file docs/stories/RAIL/RAIL-NNN.md \
  --agent-role builder \
  --model claude-opus-4-7 \
  --attempt-number 1 \
  --tokens-total 38000 \
  --tokens-in 30000 \       # omit flag if runtime did not emit input_tokens
  --tokens-out 8000 \       # omit flag if runtime did not emit output_tokens
  --cache-read-tokens 0 \   # omit flag if runtime did not emit cache_read_tokens
  --cache-write-tokens 0 \  # omit flag if runtime did not emit cache_write_tokens
  --tool-uses 11 \
  --duration-ms 187000 \
  --model-selection-reason auto-baseline \
  --project-dir .
```

`record_attempt.py` no-ops silently when `.companion/state.json["effort_tracking"]`
is absent or false, so this step is safe to run unconditionally.

After recording the attempt, run the real-time effort guardrail. It compares
the just-completed builder attempt's tokens against the rail's recent median
PASS-outcome cost. If the latest attempt exceeds `N × median` (default
`N=3.0`, configurable via `state["effort_guardrail_multiplier"]`), the
guardrail prints a structured warning to stderr. The guardrail is
informational, not blocking — exit code is always 0:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py check-guardrail \
  --story-id RAIL-NNN --tokens 38000 --project-dir .
```

When the guardrail fires, surface the warning to the user and pause before
spawning the reviewer — ask whether to continue, retry with tighter scope,
or split the story. The orchestrator (not the guardrail) decides whether to
pause; an unfired guardrail is silent and the loop continues normally.

**Persist attempt counter.** Write the current attempt number to disk so
a `/clear` mid-phase preserves it:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  write-attempt-count --story-id RAIL-NNN --count [current attempt] --project-dir .
```

If the preferred model for an agent is rate-limited, override at call time via the `model` parameter (Opus → Sonnet on reviewers; Sonnet → Haiku on builder; never below Haiku). See `docs/architecture.md` § Model selection and fallback.

If the builder reports a DEVELOPER ACTION gate mid-story, or cannot resolve an error
after two attempts: stop the build loop. Report to the user:

  BUILD PAUSED — Story [RAIL-NNN]
  Reason: [gate description or error]
  Action required: [what the user needs to do]
  When resolved, say: "Continue building"

### Step 1.5 — Commit pending methodology files before the reviewer fires

The reviewer's revert path (`git checkout .` or `git reset --hard HEAD`)
protects against builder mistakes by restoring the working tree to its last
committed state. That same revert can erase uncommitted methodology files
(story-spec edits, lesson notes, phase-doc updates) that the orchestrator
created during this session but never committed.

Before spawning the reviewer:

`docs/stories/` is intentionally excluded from the blanket stage: the
reviewer's "Before reviewing" step diffs `HEAD` to identify what the
builder changed, including builder edits to story files. Pre-committing
them would hide the diff.

```bash
# Commit any orchestrator-side methodology file changes
# Note: docs/stories/ is intentionally NOT staged here. The reviewer must
# see builder-edited story files in `git diff HEAD`. If the orchestrator
# must commit an individual story file it edited during session setup,
# stage only that file with `git add docs/stories/<RAIL>/<ID>.md`.
git add docs/phases/ docs/cer/ 2>/dev/null
git diff --cached --quiet || git commit -m "chore(orchestrator): pre-reviewer methodology file commit"

# Drop any uncommitted lesson edits — lessons.json/LESSONS.md should only
# be modified through LESSON-* stories' canonical save_lessons path
git checkout -- lessons/lessons.json lessons/LESSONS.md 2>/dev/null
```

This is the second of two layers protecting the working tree from reviewer
reverts. The first layer is the reviewer-class agent tool restriction
(read-only tools plus Bash; see `docs/architecture.md`). Together they ensure
the reviewer can revert builder mistakes without erasing methodology.

### Step 2 — Spawn the reviewer

Before spawning the reviewer, determine the model using the `model_selector`
helper.  The reviewer model is driven by `(story_class, attempt_number)` — read
`story_class` from the story's frontmatter (default `"code"` if absent):

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py select-reviewer-model \
  --story-id RAIL-NNN --attempt 1 --project-dir .
```

The first line is the model (`sonnet` or `opus`); the second line is the selection
reason. Pass the model as the `model` parameter when spawning the reviewer. Pass
the reason to `record_attempt.py` as `--model-selection-reason`.

Spawn the `reviewer` subagent with:
- The story ID only (e.g. `BUILD-012`)
- `model`: the value returned by `select_reviewer_model` above

Do not pass story spec or acceptance criteria.
The reviewer reads its own story spec cold.

The reviewer will diff the working tree, run the checklist, run tests, then either commit or revert.

After the reviewer returns, parse `REVIEW-RESULT`, `SUMMARY`, and the `<usage>`
block from the reviewer's return. `REVIEW-RESULT: PASS` means committed;
`REVIEW-RESULT: FAIL` means reverted. Discard all other reviewer output.
Extract `total_tokens`, `tool_uses`, and `duration_ms` from the `<usage>` block
and record the attempt with `--agent-role reviewer`. Pass `--outcome PASS` if
`REVIEW-RESULT: PASS`, or `--outcome FAIL` if `REVIEW-RESULT: FAIL`. As with the
builder step, `record_attempt.py` is a silent no-op when effort tracking is
disabled, so the call is unconditional.

Capture the reason printed by `select_reviewer_model` (second output line) into a
shell variable before spawning the reviewer so you can pass it here:

```bash
# After running select_reviewer_model, capture both lines:
# model=$(first line); reason=$(second line)
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/record_attempt.py \
  --story-file docs/stories/RAIL/RAIL-NNN.md \
  --agent-role reviewer \
  --model claude-opus-4-7 \
  --attempt-number 1 \
  --tokens-total 22000 \
  --tokens-in 18000 \       # omit flag if runtime did not emit input_tokens
  --tokens-out 4000 \       # omit flag if runtime did not emit output_tokens
  --cache-read-tokens 0 \   # omit flag if runtime did not emit cache_read_tokens
  --cache-write-tokens 0 \  # omit flag if runtime did not emit cache_write_tokens
  --tool-uses 6 \
  --duration-ms 95000 \
  --outcome PASS \
  --model-selection-reason $reason \
  --project-dir .
```

Story commits use the format: `feat(story-RAIL-NNN)` (e.g., `feat(story-BOOTSTRAP-003)`).

### Step 3 — Handle the result

After the reviewer commits or reverts:

1. Clear the active story context:
```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/story_context.py --clear --project-dir .
```

2. If the reviewer committed (PASS): update the story status to complete:
```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/story_update.py \
  --story-id RAIL-NNN --status complete --project-dir .
```

   Then clear the attempt counter:
```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  clear-attempt-count --project-dir .
```

3. If the reviewer reverted (FAIL): leave the story status as `planned`.

**If reviewer reports PASS (committed):**
Read `git log --oneline -1` to confirm the commit. Advance to the next story.
If this was the last story in the phase, go to the Checkpoint Sequence below.
Otherwise, repeat the build loop for the next story.

**If reviewer reports FAIL (reverted):**

Check the current attempt number for this story.

**Attempt 1 FAIL — auto-retry:**
Append the reviewer's findings as a `## PREVIOUS ATTEMPT FAILED` section to the
original story prompt. Re-spawn the builder (attempt 2) immediately — no user pause.
Increment the per-story attempt counter to 2.

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  write-attempt-count --story-id RAIL-NNN --count 2 --project-dir .
```

Before spawning the retry builder, re-call `select_builder_model` with
`attempt_number=2`.  For `code` stories this returns `opus` / `retry-upgrade`.
Pass the escalated model to the builder Agent tool and record
`--model-selection-reason retry-upgrade` in the attempt row.

After the builder returns, record the attempt and run the guardrail as in Step 1,
then re-spawn the reviewer (Step 2). The reviewer model re-selects based on the
updated attempt_number (attempt 2 → opus for code stories).

**Attempt 2 FAIL — auto loop-breaker:**

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  write-attempt-count --story-id RAIL-NNN --count 3 --project-dir .
```

Spawn the `loop-breaker` subagent immediately — no user pause:
  LOOP-BREAKER: [reviewer finding verbatim]
  FILE: [file:line if known, or "unknown"]
  TRIED: [description of attempt 1 and attempt 2 approaches]
After the loop-breaker responds, present its proposal to the user:

  LOOP-BREAKER — Story [RAIL-NNN]
  Two attempts failed. Proposed alternative:
  [loop-breaker output verbatim]
  Say "proceed" to attempt a third build with this guidance,
  or "pause" to investigate manually.

Wait for user response.
- "proceed": spawn the builder (attempt 3) with original story text PLUS loop-breaker
  guidance appended as a `## LOOP-BREAKER GUIDANCE` section.
- "pause": go to BUILD PAUSED below.

**Attempt 3 FAIL or user "pause":**

  BUILD PAUSED — Story [RAIL-NNN]
  Reason: [last reviewer's top findings]
  Working tree reverted to HEAD.
  When resolved, say: "Continue building"

Stop the build loop.

---

## Context budget check (between stories)

**Enforcer:** `hooks/pre_tool_use.py` (matcher `Task|Agent`) delegates to
`skills/pairmode/scripts/context_budget.py`. On every subagent spawn, the hook:

1. Reads `state["current_story"]["id"]` to get the active story ID.
2. Looks up `state["context_story_tokens"][story_id]` — the count the orchestrator
   recorded via `set-context-tokens` at the Context gate step above.
3. Validates the entry is fresh: `entry["recorded_at"]` must post-date
   `state["context_session_reset_at"]` (written by the SessionStart hook on
   `clear`/`startup`). An entry older than the last session reset is stale.
4. If the entry is missing or stale: blocks with CONTEXT CHECK REQUIRED.
   The orchestrator must call `/context` and run `set-context-tokens` for the
   current story before the spawn can proceed.
5. If entry is fresh: checks whether `tokens + estimated_next_step > threshold ×
   (1 + overrun_pct)` (defaults: 120,000 × 1.10 = 132,000). Blocks when exceeded.

The per-story dict preserves the full session history of token counts — visible in
`.companion/state.json["context_story_tokens"]`. A /clear is visible as a lower count
for the same story ID on the subsequent run (the entry is overwritten when the
orchestrator re-records after the clear).

`set-context-tokens` is the sole writer of `context_story_tokens` entries.
The SessionStart hook writes `context_session_reset_at` on `clear`/`startup`.

Canonical prompt body (source of truth:
`tests/pairmode/fixtures/context_budget_prompt.txt`, reproduced
here for in-doc readability):

````
CONTEXT BUDGET — [story RAIL-NNN] just completed.
Context is at approximately [N] tokens (threshold: [T], overrun: [O]).
Estimated next step: ~[E] tokens — [R] tokens remaining before ceiling.

Continuing risks context compaction mid-story. Options:

1. **Proceed** — continue building in this session; budget acknowledged.
   Say: "Continue building"

2. **Clear and resume** — run /clear, then in the fresh session:
   Say: "Continue building Phase X from story RAIL-NNN"
````

Response handling:
- "Continue building" → `context_budget.decide()` has already
  written `state["context_budget_acknowledged_at"]`. Re-prompt is
  suppressed until tokens cross
  `acknowledged_at + state["context_budget_reprompt_margin"]`
  (default 10,000).
- "Clear and resume" → user types `/clear`; the SessionStart hook writes a fresh
  `context_session_reset_at`, invalidating pre-clear dict entries. The orchestrator
  calls `/context` and `set-context-tokens` in the resumed session to record a
  fresh entry for the story.

Tunables (all in `.companion/state.json`):
`context_budget_threshold`, `context_budget_overrun_pct`,
`expected_step_tokens` (seeded prior; replaced by the per-phase
effort.db median once ≥5 attempts accumulate),
`context_budget_reprompt_margin`.

---

## Checkpoint sequence

Triggered when the last story of a phase is committed.

### 1. Build gate

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

If any test fails: stop. Report which tests failed and their output. Do not proceed.

### 2. Security audit

Before spawning the security-auditor, determine the model using `model_selector`:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py select-security-auditor-model \
  --phase-class production
```

Spawn the `security-auditor` subagent with:
- "Full security audit of skills/pairmode/ — Phase [N] checkpoint."
- `model`: the value returned by `select_security_auditor_model` above

If the auditor reports any CRITICAL or HIGH finding: stop. Report findings.
The checkpoint cannot be tagged until all CRITICAL and HIGH findings are resolved.

### 3. Intent review

Before spawning the intent-reviewer, determine the model using `model_selector`:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py select-intent-reviewer-model \
  --phase-class production
```

Spawn the `intent-reviewer` subagent with:
- Phase number
- Prior checkpoint git tag (or "initial commit" for Phase 1)
- Full phase spec text from `docs/phases/phase-N.md` (or `docs/phase-prompts.md` for legacy projects)
- `model`: the value returned by `select_intent_reviewer_model` above

After the intent-reviewer completes:
- Apply its recommended changes to `docs/phases/phase-N.md` (or `docs/phase-prompts.md` for legacy projects) and `/docs/architecture.md`.
  Do not apply changes that contradict the core architecture — flag those to the user.

### 4. Documentation review

Before tagging, verify that the project's full documentation surface reflects
what shipped this phase. Documentation reliability across builds is what
preserves project context across sessions, agent handoffs, and compactions.

**Discover the documentation surface** (same procedure as `agents/reviewer.md`
§ 4):

If `docs/documentation-surface.md` exists, treat each path listed inside it as
a surface doc. Otherwise, use the default surface — discover via:

```bash
find docs -type f -name '*.md' \
  -not -path 'docs/phases/*' \
  -not -path 'docs/stories/*' \
  -not -path 'docs/cer/*' \
  -not -path 'docs/eras/*'
```

Always include `README.md` at the project root.

**For each file in the surface, check:**

1. Run `git diff <prior-checkpoint-tag>..HEAD -- '<doc-path>'` — was this doc
   touched during the phase? If yes, skip — already maintained by the per-story
   reviewer.
2. If not touched: identify which code files changed this phase
   (`git diff <prior-checkpoint-tag>..HEAD --name-only`). Grep the doc for those
   paths, for symbol names from the diffs, and for any numeric or textual claims
   the diff may have invalidated.
3. If the doc references code that changed and the doc statement is now
   factually wrong: update the doc inline. Do not spawn a subagent — this is a
   write task, not a review task.

**Report each update individually in step 8:**

```
Doc updates:
  - README.md: updated CLI flag list
  - docs/architecture.md: corrected role_permissions row count (56 not 58)
  - docs/configuration.md: added new env var
```

If the surface is clean and no updates needed: mark `Doc updates: none` and
proceed.

**Note:** The per-story reviewer already enforces DOC CURRENCY for each story
commit via `agents/reviewer.md` § 4. This checkpoint step catches anything that
fell between stories (cross-story drift) and gives the phase a final clean
state before tagging.

### 5. Phase completion check

Verify all planned stories in this phase's Stories table are resolved:

- Read the Stories table in the phase doc.
- Any story still showing `planned` must be either:
  - **Completed** (build it now if it should ship this phase), or
  - **Formally deferred:** add a `## Deferred stories` section to the phase doc
    listing each story and a one-line reason. Update the phase table entry to
    `deferred`.

A phase cannot be checkpointed with silently abandoned `planned` stories.

If all stories are `complete` or formally deferred: proceed to step 6.

### 6. CER backlog review

Check `docs/cer/backlog.md` for any "Do Now" entries without a resolution.

If open "Do Now" entries exist:
  Stop. Report:

    CHECKPOINT BLOCKED — Open CER findings
    The following "Do Now" items must be resolved before tagging:
      [list each: CER-NNN — finding text]

    Options: fix the issue (update backlog.md resolution), or re-triage to a lower
    quadrant with an explicit reason.

If no open "Do Now" entries (or backlog.md does not exist): proceed to step 7.

### 7. Tag the checkpoint

Before tagging, mark the phase as complete in the index:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  mark-phase-complete --phase [phase-id] --project-dir .
```

This records the phase as complete in `docs/phases/index.md`. Stage the updated
index alongside any doc updates from step 3. All staged changes (index update +
doc updates) are included in the checkpoint commit.

Then run the tag command from `/docs/checkpoints.md` for this phase.
Commit any doc updates from step 3 alongside the tag.

After pushing the tag, detect whether a next phase is already spec'd:

  next_phase_id=$(PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
    next-phase --after [phase-id] --project-dir .)

If the command exits 0: `next_phase_id` holds the next phase key (e.g. `60`).
If the command exits 1: `next_phase_id` is empty — no next phase is spec'd.
Pass `next_phase_id` into step 8 to populate the closing prompt.

### 7.5. Context health check

Query the effort DB for this phase's retry burden and compare it against the
project's rolling per-phase median. This is a read-only step — it never blocks
the checkpoint.

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py context-health \
  --phase PHASE_ID_HERE --project-dir .
```

Capture the JSON. Extract the `message` field for the checkpoint report.
If `recommendation` is `elevated` or `high`, the report line becomes:

  When `next_phase_id` is non-empty:
    Context health:   <message>
      → /clear before beginning Phase [next_phase_id] is advised.
        Say: "Build Phase [next_phase_id]" in the fresh session.

  When `next_phase_id` is empty:
    Context health:   <message>
      → /clear before beginning the next phase is advised.

If `recommendation` is `normal` or `insufficient_data`:

  Context health:   <message>

### 8. Report

  ═══════════════════════════════════════════════
  CHECKPOINT [phase-id] COMPLETE — [tag name]
  ═══════════════════════════════════════════════

  Stories completed: [list with one-line description each]

  Build gate:       PASS
  Security audit:   PASS / [N findings at LOW/MEDIUM]
  Intent review:    [ALIGNED / N pivots found]
  Phase completion: [all complete / N stories formally deferred]
  CER backlog:      [N open Do Now / clean]
  Doc updates:      [list of changes, or "none"]
  Context health:   [message from step 7.5]

  Git tag: [tag name]

  Use the `next_phase_id` captured in step 7 to populate the closing line:

    • next_phase_id non-empty →
        To begin Phase [next_phase_id], say: "Build Phase [next_phase_id]"

    • next_phase_id empty →
        No further phases are spec'd. To plan the next phase, say:
          "spec next phase [intent]"
  ═══════════════════════════════════════════════

Stop. Do not begin the next phase until the user says to.

---

## Running tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```


---

## Rules

- Do not write code. You are the orchestrator, not the builder.
- Do not review code. That is the reviewer's role.
- Do not make architectural decisions. Those are in /docs/architecture.md.
- Do not commit. The reviewer commits.
- Do not skip the reviewer even if the builder's output looks correct to you.
- Do not advance past a checkpoint until build gate + security audit + intent review all pass.
- The deny list in `.claude/settings.json` protects certain files at the permission level.
  If any step tries to modify a protected file, it will be blocked. Report this to the user.

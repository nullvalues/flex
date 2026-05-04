---
name: anchor:pairmode
description: Bootstrap, audit, sync, and manage pairmode methodology for this project.
allowed-tools: AskUserQuestion, Bash, Read, Write
---

# anchor:pairmode

Manage the pairmode methodology lifecycle for a project — from initial scaffolding through ongoing
audit, sync, and lesson capture.

---

## Commands

### `/anchor:pairmode bootstrap`

**When to use:** When starting pairmode on a new or existing project for the first time, or when
re-scaffolding a project after a major methodology revision.

**Inputs expected:**
- `.companion/product.json` in the target project — used to populate project-specific values in
  the scaffold (project name, description, tech stack, team conventions).
- The project's Anchor spec (`openspec/specs/`) if available — used to derive non-negotiables
  for the deny list in `.claude/settings.json`.
- Target project root path (prompted if not provided).

**What it does:**
1. Reads `.companion/product.json` from the target project.
2. Reads the project's Anchor spec if available; falls back to blank-slate defaults if not.
3. Renders all Jinja2 templates in `skills/pairmode/templates/` against the project context.
4. Generates the deny list in `.claude/settings.json` from spec non-negotiables, each rule
   annotated with a comment linking it to the source non-negotiable.
5. Writes scaffold files immediately on a fresh project. For each file that already exists,
   prompts for confirmation before overwriting that individual file.
6. Records `pairmode_version` in `.companion/state.json` for future audit comparisons.

**Outputs:**
- `CLAUDE.md` — project methodology guide (root)
- `CLAUDE.build.md` — build orchestrator instructions (root)
- `docs/brief.md` — project brief
- `docs/architecture.md` — architecture reference
- `docs/checkpoints.md` — checkpoint tag commands
- `docs/phases/index.md` — phase index table
- `docs/phases/phase-1.md` — initial phase scaffold
- `docs/cer/backlog.md` — cold-eyes review triage backlog
- `.claude/settings.json` — permissions file with spec-derived deny list
- `.companion/state.json` — companion state with `pairmode_version` set
- `.claude/agents/builder.md`, `reviewer.md`, `loop-breaker.md`, `security-auditor.md`,
  `intent-reviewer.md` — skipped if they already exist unless `--force-agents` is passed.

**CLI invocation:**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/bootstrap.py" \
  --project-dir "$(pwd)"
```
Note: `--project-dir` is the only required flag. Other values (project name, stack, etc.) are read from `.companion/product.json` or prompted interactively.

**Agent file ownership:**
Agent files in `.claude/agents/` are treated as project-owned after first bootstrap. Bootstrap will not overwrite them on subsequent runs unless `--force-agents` is passed explicitly. This preserves project-specific customisations made to agent definitions after initial scaffolding.

To overwrite existing agent files:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/bootstrap.py" \
  --project-dir "$(pwd)" --force-agents
```

**Flags:**
- `--project-dir PATH` — target project root (default: current directory)
- `--project-name NAME` — project name (read from `product.json` or prompted if omitted)
- `--stack TEXT` — technology stack (prompted if omitted)
- `--what TEXT` — what the project produces (prompted in TTY; blank left as-is in non-TTY with warning)
- `--why TEXT` — why the project exists (prompted in TTY; blank left as-is in non-TTY with warning)
- `--build-command TEXT` — build/test command (inferred from project files or prompted if omitted)
- `--phase-title TEXT` — title for the initial `docs/phases/phase-1.md` (prompted in TTY if omitted; blank allowed)
- `--phase-goal TEXT` — goal for the initial `docs/phases/phase-1.md` (prompted in TTY if omitted; blank allowed)
- `--dry-run` — print what would be written without writing anything
- `--force-agents` — overwrite existing agent files in `.claude/agents/` (default: skip if present)

---

### `/anchor:pairmode audit`

**When to use:** Compare a project's current pairmode scaffold against the canonical methodology
to see what's drifted, missing, or project-specific.

**Inputs:**
- Current directory (used as project-dir)
- Optional: project type tag for lesson filtering (defaults to "all")

Note: `pairmode_context.json` (created by `/anchor:pairmode bootstrap`) must exist for INCONSISTENT results to be meaningful.

**What it does:**
1. Check for `.companion/state.json` in current directory (reads `pairmode_version`).
2. Run: `PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/audit.py" --project-dir "$(pwd)"`
3. Display the output (MISSING / INCONSISTENT / EXTRA sections).
4. If there are MISSING or INCONSISTENT items, ask: "Run sync to apply these changes?"
   - If yes → run sync (documented in sync command below)
   - If no → display the output and stop

**Output format:**
```
AUDIT: <project_name> vs pairmode v<version>

MISSING
  ✗ <file>: <description>

INCONSISTENT
  ~ <file>: <description>

EXTRA (project-specific, keep as-is)
  ✓ <file>: <description>

RECOMMENDATION
  Run /anchor:pairmode sync to apply missing/inconsistent items
  Project-specific items will be preserved
```

**Outputs:**
- A human-readable audit report printed to the session, summarizing all deltas and recommended
  actions. No files are written.

---

### `/anchor:pairmode sync`

**When to use:** Apply missing or inconsistent items from an audit result to bring a project's
pairmode scaffold up to date with the current canonical methodology.

**Inputs:**
- Current directory (used as project-dir)
- Optional: project type tag for lesson filtering (defaults to "all")

Note: `pairmode_context.json` (created by `/anchor:pairmode bootstrap`) must exist for INCONSISTENT results to be meaningful.

**What it does:**
1. Run audit to get current delta: `PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/audit.py" --project-dir "$(pwd)"`
2. Display the audit result
3. If no MISSING or INCONSISTENT items: report "Already up to date" and stop
4. Otherwise, confirm with user before applying changes
5. Run: `PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/sync.py" --project-dir "$(pwd)"`
6. Display sync output

**Output format:**
```
SYNC COMPLETE — <project_name>

Applied:
  ✓ <description of each change>

Preserved:
  → <project-specific items kept>

State updated: .companion/state.json
```

**What it never does:**
- Never overwrites project-specific content (EXTRA items)
- Never modifies hooks/ or spec files
- Never runs without showing audit output first

---

### `/anchor:pairmode lesson`

**When to use:** At the end of a session (or any time) when a meaningful methodology insight has
emerged — a workflow problem solved, a pattern discovered, a failure mode identified.

**Inputs expected (prompted interactively via AskUserQuestion, or as CLI arguments):**
- **trigger** — what situation or event prompted this lesson.
- **problem** — what went wrong or was inefficient.
- **learning** — the insight or corrective pattern.
- **methodology_change** — how the methodology (templates, process, tooling) should change as
  a result.
- **affects** — which components are affected (e.g. `reviewer_checklist`, `builder_agent`).
- **applies_to** — which project types this applies to (e.g. `all`, `python`, `typescript`).
- **source_project** — (optional) the project that produced this lesson; defaults to `unknown`.

**What it does:**
1. Loads the current `anchor/lessons/lessons.json`.
2. Generates the next sequential lesson ID (L001, L002, …).
3. Constructs a lesson entry with `id`, `date` (today), `source_project`, `trigger`, `problem`,
   `learning`, `methodology_change` (with `affects` and `description`), `applies_to`, and
   `status: captured`.
4. Appends the entry to `anchor/lessons/lessons.json` via `lesson_utils.save_lessons()`, which
   enforces the append-only invariant (existing entries may only have `status` changed).
5. Calls `lesson_utils.generate_lessons_md()` and writes the result to `lessons/LESSONS.md`.
6. Returns the captured lesson dict and prints a confirmation with the lesson `id`.

**Lesson schema written to lessons.json:**
```json
{
  "id": "L001",
  "date": "YYYY-MM-DD",
  "source_project": "project name or 'unknown'",
  "trigger": "...",
  "problem": "...",
  "learning": "...",
  "methodology_change": {
    "affects": ["reviewer_checklist"],
    "description": "..."
  },
  "applies_to": ["all"],
  "status": "captured"
}
```

**CLI invocation (for testing and direct use):**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/lesson.py" \
  --trigger "Builder skipped tests" \
  --problem "Tests failed after story was marked done." \
  --learning "Always run tests before marking a story done." \
  --methodology-change "Add test gate to builder checklist." \
  --affects reviewer_checklist \
  --affects builder_agent \
  --applies-to all \
  --source-project my-project
```

**Outputs:**
- New entry appended to `anchor/lessons/lessons.json`.
- `lessons/LESSONS.md` regenerated from the updated lessons store.
- Confirmation message with the lesson `id` printed to stdout.

---

### `/anchor:pairmode review`

**When to use:** When enough lessons have accumulated to warrant a methodology update cycle —
typically before a major bootstrap or sync campaign across projects.

**Inputs expected:**
- `anchor/lessons/lessons.json` — must exist with at least one lesson with `status: captured`
  or `status: reviewed`.
- User approval or rejection for each proposed template change (handled via AskUserQuestion
  in the skill; `lesson_review.py` provides the underlying logic).

**What it does:**
1. Calls `load_reviewable_lessons()` — loads all lessons with `status: captured` or
   `status: reviewed` from `anchor/lessons/lessons.json`.
2. Calls `group_lessons_by_affects()` — groups lessons by the `methodology_change.affects`
   values. A lesson with `affects: ["all"]` appears under every known affects key
   (`reviewer_checklist`, `builder_agent`, `orchestrator`, `checkpoint_sequence`).
3. For each lesson, calls `propose_template_change()` to produce a proposal dict:
   - `lesson_id` — the lesson's ID
   - `affects` — the specific affects value for this proposal
   - `template_file` — relative path to the template to edit (see mapping below)
   - `description` — the methodology change description from the lesson
   - `lesson_trigger` — copied from lesson for context
   - `lesson_learning` — copied from lesson for context
4. Presents each proposed change to the user (via AskUserQuestion) with the source
   lesson and rationale.
5. For approved lessons: calls `apply_template_change(proposal, change_text)` which
   appends a Jinja2 comment block `{# LESSON <id>: <change_text> #}` to the template
   file, then marks the lesson `status: applied`.
6. For rejected lessons: marks the lesson `status: reviewed` (for future consideration).
7. Calls `regenerate_lessons_md()` to write an updated `lessons/LESSONS.md`.

**Affects → template file mapping:**

| affects value         | template file                                         |
|-----------------------|-------------------------------------------------------|
| `reviewer_checklist`  | `skills/pairmode/templates/CLAUDE.md.j2`              |
| `builder_agent`       | `skills/pairmode/templates/agents/builder.md.j2`      |
| `orchestrator`        | `skills/pairmode/templates/CLAUDE.build.md.j2`        |
| `checkpoint_sequence` | `skills/pairmode/templates/CLAUDE.build.md.j2`        |
| `all`                 | all three template files (one proposal per file)      |

---

### `/anchor:pairmode phase-new`

> **Note:** `phase-new` is invoked directly via CLI, not through the pairmode skill dispatcher.
> Correct invocation:
> ```bash
> PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/phase_new.py" \
>   --project-dir "$(pwd)" --phase-id N
> ```

**When to use:** When starting a new build phase and you want to lazy-scaffold the phase
file without interrupting the flow. Run this instead of manually creating a phase file
from scratch.

**Inputs expected:**
- `--phase-id N` — the phase number (required).
- `--title TEXT` — optional phase title (defaults to "Phase N").
- `--goal TEXT` — optional one-line goal for the phase (defaults to empty).

**What it does:**
1. Renders `skills/pairmode/templates/docs/phases/phase.md.j2` with the provided phase ID,
   title, and goal, plus project context from `.companion/pairmode_context.json` if present.
2. Writes the rendered file to `docs/phases/phase-N.md` in the target project.
3. Updates `docs/phases/index.md` if it exists — appends the new phase row to the phase
   table. If `docs/phases/index.md` does not exist, it is created first.
4. Reports the file path written and the index row added.

**Outputs:**
- `docs/phases/phase-N.md` — scaffolded phase file with placeholder story slots.
- `docs/phases/index.md` — updated with the new phase row (created if absent).

**CLI invocation:**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/phase_new.py" \
  --project-dir "$(pwd)" --phase-id N
```

Optional flags:
- `--phase-id N` — phase number (required)
- `--title TEXT` — phase title (default: "Phase N")
- `--goal TEXT` — phase goal summary (default: empty)
- `--dry-run` — print what would be written without writing anything

---

### `/anchor:pairmode cer`

> **Note:** `cer` is invoked directly via CLI, not through the pairmode skill dispatcher.
> Correct invocation:
> ```bash
> PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/cer.py" \
>   --project-dir "$(pwd)"
> ```

**When to use:** After a Cold-Eyes Review (CER) session to record findings in the project's
structured triage backlog. Run this once per review session to capture the findings before
they are forgotten.

**Inputs expected:**
- Findings from the CER session (provided interactively or via file).
- Each finding needs: finding text, quadrant (`now` / `later` / `much_later` /
  `never`), source reviewer name, and an optional phase reference.

**What it does:**
1. Reads existing `docs/cer/backlog.md` if present; creates it from template if absent.
2. Prompts for each new finding: text, quadrant, source, and phase.
3. Assigns the next sequential CER finding ID (CER-001, CER-002, …).
4. Appends each finding to the appropriate quadrant table in `docs/cer/backlog.md`.
5. Updates the `last_updated` date at the top of the file.

**Outputs:**
- `docs/cer/backlog.md` — updated with new findings in the appropriate quadrant tables.
  Existing findings are never removed or modified.

**CLI invocation:**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/cer.py" \
  --project-dir "$(pwd)"
```

Optional flags:
- `--project-dir PATH` — target project root (default: current directory)
- `--finding TEXT` — finding text (repeatable; if omitted, prompts interactively)
- `--quadrant QUADRANT` — one of `now`, `later`, `much_later`, `never`
- `--reviewer TEXT` — reviewer name or identifier
- `--phase TEXT` — phase reference (e.g. "Phase 3")

**Template comment format written by `apply_template_change`:**
```
{# LESSON L001: <change_text> #}
```
This marks the location for the developer to implement the change manually. The comment
is appended to the end of the template file.

> **Note:** "Applying" a lesson writes a Jinja2 comment block that marks the change location. The developer must open the annotated template to implement the actual change. Lesson `status` is set to `applied` once the annotation is written — not once the template change is implemented. Always review annotated templates after running this command.

**CLI invocation (for direct use / automation):**
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/lesson_review.py" \
  --approve L001 \
  --approve L002 \
  --reject L003
```
- `--approve LESSON_ID` (repeatable): apply_template_change is called with the lesson's
  own description as change_text, then status is set to `applied`.
- `--reject LESSON_ID` (repeatable): status is set to `reviewed`.
- After processing all flags, `regenerate_lessons_md()` is called automatically.

**Outputs:**
- Jinja2 comment blocks appended to affected template files in `skills/pairmode/templates/`.
- Updated `status` fields in `anchor/lessons/lessons.json` (via `lesson_utils.save_lessons()`,
  which enforces the append-only invariant).
- `lessons/LESSONS.md` regenerated from the updated lessons store.
- A review summary printed to stdout.

# Anchor Pairmode — Phase Prompts

This file contains the complete build instructions for the pairmode feature.
The build orchestrator reads this file in full before starting any story.

---

## Phase 1 — Pairmode Skill Scaffold

**Goal:** Create the static scaffold — directory structure, SKILL.md with four commands, Jinja2
templates, and a bootstrap.py that renders static templates. By end of phase,
`/anchor:pairmode bootstrap` works but uses static templates with no spec derivation.

---

### Story 1.1 — Skill directory and SKILL.md

**Acceptance criterion:** `skills/pairmode/SKILL.md` exists with all four commands documented,
and the directory structure matches the architecture spec.

**Instructions:**

Create the following directory structure:
```
skills/pairmode/
  SKILL.md
  requirements.txt
  scripts/
    __init__.py  (empty)
  templates/
    agents/
    docs/
```

`requirements.txt` should include: `jinja2`, `click`

`SKILL.md` frontmatter:
```yaml
---
name: anchor:pairmode
description: Bootstrap, audit, sync, and manage pairmode methodology for this project.
allowed-tools: AskUserQuestion, Bash, Read, Write
---
```

The skill body should define four commands clearly:
- `/anchor:pairmode bootstrap` — scaffold a new or existing project with pairmode
- `/anchor:pairmode audit` — compare project against current canonical methodology
- `/anchor:pairmode sync` — apply delta from audit non-destructively
- `/anchor:pairmode lesson` — capture a lesson learned from this session
- `/anchor:pairmode review` — surface accumulated lessons, propose template updates

Each command section should describe: when to use it, inputs it expects, what it does,
and what it outputs.

For bootstrap: it reads `.companion/product.json` and the project's Anchor spec if available,
then generates the scaffold. It always confirms before writing files.

For audit: it reads `.companion/state.json` for `pairmode_version`, compares against
current canonical templates and applicable lessons.

For sync: it applies the delta from audit, preserving project-specific content.

For lesson: it prompts the user for trigger/problem/learning/methodology_change, writes
to `anchor/lessons/lessons.json` (in the anchor repo, not the project).

For review: it groups captured lessons by `affects` field, proposes specific template
updates, and writes approved updates to the templates.

---

### Story 1.2 — Static CLAUDE.md and CLAUDE.build.md templates

**Acceptance criterion:** `skills/pairmode/templates/CLAUDE.md.j2` and
`skills/pairmode/templates/CLAUDE.build.md.j2` render correctly with test context data
and produce output structurally identical to the canonical versions in cora/radar.

**Instructions:**

Create `templates/CLAUDE.md.j2`. Template variables:
- `{{ project_name }}` — project name
- `{{ project_description }}` — one-line description
- `{{ stack }}` — technology stack
- `{{ domain_model }}` — tenant/domain model description
- `{{ build_command }}` — how to build (e.g. `pnpm build`, `uv run pytest`)
- `{{ test_command }}` — how to run tests
- `{{ checklist_items }}` — list of dicts with `name`, `description`, `severity`
- `{{ protected_paths }}` — list of protected file patterns

The template should produce the canonical CLAUDE.md structure:
- Project context block (name, description, stack, domain model)
- Session modes section (Build mode / Review mode — verbatim from cora pattern)
- Review checklist (rendered from checklist_items)
- Review output format (severity definitions — these are universal, not templated)
- Loop-breaker mode section (universal — not templated)

Universal checklist items that must always appear regardless of checklist_items input:
- PROTECTED FILES (severity HIGH)
- STORY SCOPE (severity MEDIUM)
- BUILD GATE verification section

Create `templates/CLAUDE.build.md.j2`. Template variables:
- `{{ project_name }}`
- `{{ build_command }}`
- `{{ test_command }}`
- `{{ migration_command }}` — optional, empty string if not applicable

The template should produce the canonical CLAUDE.build.md structure matching cora's version
exactly, with the project-specific commands substituted in.

Write a test at `tests/pairmode/test_templates.py` that renders both templates with sample
context data and asserts that key structural elements are present in the output
(session modes section, review checklist header, build loop steps, checkpoint sequence).

---

### Story 1.3 — Static agent templates

**Acceptance criterion:** All five agent templates exist and render correctly with test context.

**Instructions:**

Create these templates in `skills/pairmode/templates/agents/`:
- `builder.md.j2`
- `reviewer.md.j2`
- `loop-breaker.md.j2`
- `security-auditor.md.j2`
- `intent-reviewer.md.j2`

Template variables (shared across all agent templates):
- `{{ project_name }}`
- `{{ build_command }}`
- `{{ test_command }}`
- `{{ protected_paths }}` — list of strings
- `{{ domain_isolation_rule }}` — the primary isolation invariant (e.g. "filter by workspace_id")
- `{{ checklist_items }}` — for reviewer template

Each agent template should produce output structurally identical to the cora equivalents.
The builder and reviewer templates are the most critical — they encode the methodology.

**Builder template requirements:**
- Frontmatter with `name: builder`, `description`, `tools: [Read, Write, Edit, Glob, Grep, Bash]`, `model: sonnet`
- "Before writing anything" section: read architecture.md, read story text, check protected files
- Implementation rules section (layer rules, isolation, testing — rendered from project context)
- Developer Action gates handling
- Completion report format (BUILT: Story N.X, Files changed, Tests, Build gate)
- BUILDER STUCK format for two-attempt failures

**Reviewer template requirements:**
- Frontmatter with `name: reviewer`, `description`
- "Before reviewing" section: read architecture.md, read story spec, run git diff HEAD
- Checklist section (rendered from checklist_items + universal items)
- Test run section
- PASS/FAIL decision logic (verbatim from cora — this is canonical)
- Commit format on PASS
- Revert + report format on FAIL
- "What you must not do" section

Add tests to `tests/pairmode/test_templates.py` covering agent template rendering.

---

### Story 1.4 — Static docs templates

**Acceptance criterion:** Three docs templates exist and render correctly.

**Instructions:**

Create in `skills/pairmode/templates/docs/`:
- `architecture.md.j2`
- `phase-prompts.md.j2`
- `checkpoints.md.j2`

`architecture.md.j2` template variables:
- `{{ project_name }}`, `{{ project_description }}`, `{{ stack }}`
- `{{ domain_model }}` — tenant/isolation model description
- `{{ module_structure }}` — list of dicts with `name`, `description`, `paths`
- `{{ layer_rules }}` — list of dicts with `layer`, `may_import`, `may_not_import`
- `{{ build_command }}`, `{{ test_command }}`
- `{{ protected_paths }}`
- `{{ non_negotiables }}` — list of strings (from spec, if available)

`phase-prompts.md.j2` is a minimal skeleton template. It generates a file with:
- Header and instructions
- Phase 1 section with a placeholder story 1.1 that prompts the developer to
  fill in the actual stories. Include a comment explaining the story format.

`checkpoints.md.j2` generates a minimal skeleton with:
- Header
- Placeholder for cp1 tag and acceptance criteria

These are intentionally sparse — the developer fills them in. The templates just provide
the correct structure so nothing is forgotten.

Add tests to `tests/pairmode/test_templates.py`.

---

### Story 1.5 — bootstrap.py with static rendering

**Acceptance criterion:** Running `uv run python skills/pairmode/scripts/bootstrap.py --help`
succeeds. Running it against a test project directory renders all templates and writes
the scaffold files correctly. Existing files are not overwritten without user confirmation.

**Instructions:**

Create `skills/pairmode/scripts/bootstrap.py`.

Use `click` for CLI. Entry point: `bootstrap` command with options:
- `--project-dir` (default: current directory)
- `--project-name` (optional, will prompt if missing)
- `--stack` (optional, will prompt if missing)
- `--build-command` (optional, default inferred from project files: pnpm → `pnpm build && pnpm typecheck`, uv → `uv run pytest`, else prompt)
- `--dry-run` (print what would be written, do not write)

Bootstrap reads (in order, later overrides earlier):
1. CLI flags
2. `.companion/product.json` if it exists (for project_name, spec_location)
3. Prompt for any missing required values

Bootstrap writes these files to `--project-dir` if they don't exist
(confirms before overwriting if they do):
- `CLAUDE.md` (from CLAUDE.md.j2)
- `CLAUDE.build.md` (from CLAUDE.build.md.j2)
- `.claude/agents/builder.md`
- `.claude/agents/reviewer.md`
- `.claude/agents/loop-breaker.md`
- `.claude/agents/security-auditor.md`
- `.claude/agents/intent-reviewer.md`
- `docs/architecture.md` (from docs/architecture.md.j2)
- `docs/phase-prompts.md` (skeleton)
- `docs/checkpoints.md` (skeleton)

After writing, bootstrap also merges the deny list into the project's
`.claude/settings.json`. If the file doesn't exist, creates it. If it exists,
merges the `permissions.deny` array without removing existing entries.

Record `pairmode_version: "0.1.0"` in `.companion/state.json` (creates if absent).

Context passed to all templates:
- `project_name`, `stack`, `build_command`, `test_command`
- `domain_model`: empty string at this stage (Phase 2 will derive from spec)
- `checklist_items`: universal items only (PROTECTED FILES, STORY SCOPE, BUILD GATE)
- `protected_paths`: empty list at this stage (Phase 2 will derive from spec)
- `non_negotiables`: empty list at this stage

Create `tests/pairmode/test_bootstrap.py` with tests that:
- Run bootstrap against a temporary directory
- Assert all expected files are created
- Assert settings.json has the deny list merged correctly
- Assert state.json has pairmode_version set
- Assert dry-run produces output but writes no files

---

## Phase 2 — Spec-Derived Generation

**Goal:** bootstrap.py reads the project's Anchor spec and derives the reviewer checklist
and deny list from it. Protected file comments link back to non-negotiables.

---

### Story 2.1 — Spec reader module

**Acceptance criterion:** `spec_reader.py` reads all spec.json files from a project's
openspec directory and returns a structured data object. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/spec_reader.py`.

```python
def read_project_spec(companion_dir: Path) -> dict | None:
    """
    Reads .companion/product.json to find spec_location, then reads all
    spec.json files from <spec_location>/openspec/specs/*/spec.json.
    Returns None if no spec is found.
    Returns dict with keys:
      modules: list of spec dicts (full spec.json content per module)
      spec_location: Path
    """
```

The function should handle:
- Missing `.companion/product.json` gracefully (return None)
- Missing spec files gracefully (return dict with empty modules list)
- Malformed JSON in spec files (log warning, skip that module)

Create `tests/pairmode/test_spec_reader.py` with tests using temporary directory fixtures
that create the expected file structure.

---

### Story 2.2 — Checklist deriver

**Acceptance criterion:** `checklist_deriver.py` takes a list of spec modules and returns
a list of checklist items. Each non-negotiable becomes a CRITICAL item. Each business rule
becomes a HIGH item. Universal items are appended. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/checklist_deriver.py`.

```python
def derive_checklist(modules: list[dict]) -> list[dict]:
    """
    Returns list of dicts:
      { "name": str, "description": str, "severity": str, "source": str, "module": str }
    source is "non_negotiable", "business_rule", or "universal"
    module is the spec module name, or "universal"
    """
```

Deduplication: if the same rule text appears in multiple modules, merge them
(list all module names in the `module` field).

Universal items are NOT included in the `derive_checklist()` output. They are added by the
templates themselves via hardcoded Jinja2 code. The deriver returns only spec-derived items
(non-negotiables as CRITICAL, business rules as HIGH). The templates append PROTECTED FILES,
STORY SCOPE, and BUILD GATE after the spec-derived items in every rendered output.

Create `tests/pairmode/test_checklist_deriver.py`.

---

### Story 2.3 — Deny list deriver

**Acceptance criterion:** `denylist_deriver.py` takes a list of spec modules and returns
a list of deny rules. Each rule includes an inline comment linking to the non-negotiable.
Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/denylist_deriver.py`.

```python
def derive_denylist(modules: list[dict]) -> list[dict]:
    """
    Returns list of dicts:
      { "path_pattern": str, "non_negotiable": str, "module": str }
    path_pattern is suitable for settings.json deny array (e.g. "Edit(src/services/auth/**)")
    """
```

Derivation logic:
- For each module, read its `paths` list (from modules.json, not spec.json — pass separately)
- For each non-negotiable that mentions protection, isolation, or "must never":
  - Map the relevant module paths to Edit() and Write() deny rules
  - Set non_negotiable to the full text of the non-negotiable
- Also add deny rules for any path containing "auth", "schema", or "engine" in its path
  if the non-negotiable mentions those concepts

The deriver does NOT generate comments in the JSON (settings.json doesn't support comments).
Instead, return the structured data — bootstrap.py will write both the settings.json deny
array and a companion `settings.deny-rationale.json` file that maps each rule to its source.

Create `tests/pairmode/test_denylist_deriver.py`.

---

### Story 2.4 — Wire spec derivation into bootstrap.py

**Acceptance criterion:** When a project has an Anchor spec (`.companion/product.json` exists
and spec files are present), bootstrap.py uses derived checklist and deny list instead of
the static defaults. Without a spec, it falls back to universal items only. Tests pass.

**Instructions:**

Update `skills/pairmode/scripts/bootstrap.py` to:
1. After reading project context, call `spec_reader.read_project_spec()`
2. If spec found: call `checklist_deriver.derive_checklist(modules)` and
   `denylist_deriver.derive_denylist(modules, module_paths)`
3. If no spec: use universal defaults
4. Pass derived data to templates

IMPORTANT: Pass only spec-derived items in `checklist_items`. Do NOT include universal items
(PROTECTED FILES, STORY SCOPE, BUILD GATE) — the templates add those themselves via hardcoded
Jinja2. Including them in `checklist_items` will cause duplication in rendered output.

Also write `settings.deny-rationale.json` alongside `settings.json` in `.claude/`:
```json
{
  "generated_by": "anchor:pairmode",
  "pairmode_version": "0.1.0",
  "rules": [
    {
      "pattern": "Edit(src/services/auth/**)",
      "module": "auth-and-security",
      "non_negotiable": "Auth must never call billing directly — events only"
    }
  ]
}
```

Update `tests/pairmode/test_bootstrap.py` with spec-derived scenarios.

---

### Story 2.5 — Phase 2 test coverage pass

**Acceptance criterion:** `uv run pytest tests/pairmode/ -x -q` passes with no failures.
Coverage includes spec reader, checklist deriver, deny list deriver, and bootstrap integration.

**Instructions:**

Review all tests written in Stories 2.1–2.4. Fill any gaps:
- Edge cases: empty spec, spec with no non-negotiables, spec with conflicting module paths
- Integration test: create a full mock project with `.companion/product.json` and
  spec files, run bootstrap end-to-end, assert all outputs are correct

No new production code in this story — tests only.

---

## Phase 3 — Lessons System

**Goal:** Capture and review methodology lessons. Lessons live in the anchor repo and
inform future bootstraps.

---

### Story 3.1 — Lessons store

**Acceptance criterion:** `lessons/lessons.json` exists with the correct schema.
`lessons/LESSONS.md` exists and is auto-generated from lessons.json. An empty lessons.json
produces a valid LESSONS.md.

**Instructions:**

Create `lessons/lessons.json`:
```json
{
  "version": "1.0.0",
  "lessons": []
}
```

Create `skills/pairmode/scripts/lesson_utils.py` with:
```python
LESSONS_FILE = Path(__file__).parent.parent.parent.parent / "lessons" / "lessons.json"

def load_lessons() -> dict
def save_lessons(data: dict) -> None   # validates append-only invariant
def generate_lessons_md(data: dict) -> str
def next_lesson_id(data: dict) -> str  # returns "L001", "L002", etc.
```

`save_lessons` must enforce the append-only invariant:
- Existing entries may only have their `status` field changed
- Any attempt to modify other fields of an existing entry raises ValueError
- New entries may be appended freely

Create `lessons/LESSONS.md` with:
```markdown
# Anchor Methodology Lessons

This file is auto-generated from lessons.json. Edit lessons.json directly.

No lessons captured yet.
```

Create `tests/pairmode/test_lesson_utils.py` covering:
- Load/save round-trip
- Append-only invariant enforcement (assert ValueError on modification)
- LESSONS.md generation with one and multiple lessons
- next_lesson_id sequencing

---

### Story 3.2 — Lesson capture command

**Acceptance criterion:** `/anchor:pairmode lesson` command is documented in SKILL.md
and `lesson.py` captures a lesson interactively and writes it to lessons.json.
LESSONS.md is regenerated after capture. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/lesson.py`.

The capture flow (invoked by the skill):
1. Ask user for trigger (what situation caused this lesson)
2. Ask user for problem (what went wrong or what was surprising)
3. Ask user for learning (what was learned)
4. Ask user for methodology_change (what should change — free text)
5. Ask user for affects (which template areas: reviewer_checklist, builder_agent,
   orchestrator, checkpoint_sequence, all)
6. Ask user for applies_to tags (all, typescript, python, monorepo, etc.)
7. Confirm the lesson before writing
8. Write to lessons.json with status: "captured"
9. Regenerate LESSONS.md
10. Output the lesson ID

Lesson schema:
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

Update `SKILL.md` with the lesson command instructions.

Create `tests/pairmode/test_lesson_capture.py`.

---

### Story 3.3 — Lesson review command

**Acceptance criterion:** `/anchor:pairmode review` surfaces captured lessons grouped by
`affects`, proposes specific template edits, and writes approved updates to the templates.
Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/lesson_review.py`.

Review flow:
1. Load all lessons with status "captured" or "reviewed"
2. Group by `affects` field
3. For each group, propose a specific template change:
   - "reviewer_checklist": propose adding/modifying a checklist item in CLAUDE.md.j2
   - "builder_agent": propose a change to builder.md.j2
   - "orchestrator": propose a change to CLAUDE.build.md.j2
   - "checkpoint_sequence": propose a change to the checkpoint section
4. Present each proposal to the user (show lesson trigger + proposed change)
5. User approves or rejects each
6. Write approved changes to the template files
7. Update lesson status to "applied" for approved lessons, "reviewed" for rejected
8. Regenerate LESSONS.md

Update `SKILL.md` with the review command instructions.

Create `tests/pairmode/test_lesson_review.py` (mock user input for testing).

---

## Phase 4 — Audit and Sync

**Goal:** Compare existing projects against the current canonical methodology and apply
updates non-destructively. First real-world validation: audit cora, radar, and forqsite.

---

### Story 4.1 — audit.py

**Acceptance criterion:** `audit.py` produces a structured diff of a project against
canonical templates + applicable lessons. Output matches the format defined in architecture.

**Instructions:**

Create `skills/pairmode/scripts/audit.py`.

Audit logic:
1. Read project's `.companion/state.json` for `pairmode_version`
2. Load canonical templates at current version
3. Load applicable lessons (filter by `applies_to` matching project type)
4. Compare project's CLAUDE.md, CLAUDE.build.md, and agent files against canonical
5. Produce structured diff:
   - MISSING: items in canonical not in project (with lesson reference if applicable)
   - INCONSISTENT: items present but diverged from canonical
   - EXTRA: project-specific items not in canonical (preserve these)

```python
def audit_project(project_dir: Path) -> AuditResult:
    """
    Returns AuditResult with:
      missing: list[AuditItem]
      inconsistent: list[AuditItem]
      extra: list[AuditItem]
      pairmode_version: str | None
      canonical_version: str
    """
```

AuditItem: `{ "file": str, "section": str, "description": str, "lesson_id": str | None }`

Output format:
```
AUDIT: <project_name> vs pairmode v<version>

MISSING
  ✗ <description>  (<lesson_id if applicable>)

INCONSISTENT
  ~ <file>: <description>

EXTRA (project-specific, keep as-is)
  ✓ <description>

RECOMMENDATION
  Run /anchor:pairmode sync to apply missing/inconsistent items
  Project-specific items will be preserved
```

Create `tests/pairmode/test_audit.py`.

---

### Story 4.2 — /anchor:pairmode audit command

**Acceptance criterion:** SKILL.md documents the audit command. Running it against a
project produces the audit output and optionally offers to run sync.

**Instructions:**

Update `SKILL.md` with audit command instructions:
1. Check for `.companion/state.json` in current directory
2. Run `uv run python ${CLAUDE_SKILL_DIR}/scripts/audit.py --project-dir $(pwd)`
3. Display the output
4. If there are MISSING or INCONSISTENT items, ask: "Run sync to apply these changes?"

---

### Story 4.3 — sync.py

**Acceptance criterion:** `sync.py` applies the delta from an audit result to a project
non-destructively. Project-specific content is preserved. Tests pass.

**Instructions:**

Create `skills/pairmode/scripts/sync.py`.

Sync logic:
1. Run audit to get the delta (or accept a pre-computed AuditResult)
2. For each MISSING item: add it to the appropriate file
3. For each INCONSISTENT item: update it to match canonical
4. Never touch EXTRA items
5. Record sync event in `.companion/state.json`:
   ```json
   {
     "pairmode_version": "0.1.0",
     "last_sync": "2026-04-17",
     "lessons_applied": ["L001", "L002"]
   }
   ```

The hardest part is merging checklist items into CLAUDE.md — implement a section-aware
merge that locates the review checklist section and inserts/updates items without
disrupting surrounding content.

Create `tests/pairmode/test_sync.py`.

---

### Story 4.4 — /anchor:pairmode sync command + SKILL.md update

**Acceptance criterion:** SKILL.md documents the sync command. Running it applies the
delta and confirms what was changed.

**Instructions:**

Update `SKILL.md` with sync command instructions.

After sync completes, output:
```
SYNC COMPLETE — <project_name>
Applied:
  ✓ <description of each change>
Preserved:
  → <project-specific items kept>
State updated: .companion/state.json
```

---

### Story 4.5 — Audit/sync test coverage pass

**Acceptance criterion:** Full test pass. Edge cases covered.

**Instructions:**

Review all tests from Stories 4.1–4.4. Fill gaps:
- Sync idempotency: running sync twice produces the same result as running it once
- Audit of a project with no pairmode_version (unversioned)
- Sync when CLAUDE.md doesn't exist (should create it)
- Preservation of project-specific checklist items during sync

No new production code — tests only.

---

⚙️ DEVELOPER ACTION — Run audit against sibling repos

Before Phase 5, run `/anchor:pairmode audit` against:
- `/mnt/work/cora`
- `/mnt/work/radar`
- `/mnt/work/forqsite`

Document the findings. Use the output to identify any gaps in the audit logic
(things the audit missed that you can see manually). File those as lessons with
`/anchor:pairmode lesson` before proceeding.

Confirm this is done before saying "Continue building Phase 5".

---

## Phase 5 — Companion Enhancements

**Goal:** Make the companion sidebar story-aware and capture permission overrides as spec decisions.

---

### Story 5.1 — Story context in state.json

**Acceptance criterion:** `.companion/state.json` supports a `current_story` field.
The companion skill writes it when the user selects modules. Tests cover the schema change.

**Instructions:**

Update the state.json schema (document in `skills/companion/SKILL.md` and architecture.md)
to include:
```json
{
  "last_loaded_modules": ["module-name"],
  "current_story": {
    "id": "2.3",
    "title": "optional title",
    "set_at": "ISO timestamp"
  }
}
```

`current_story` is optional — companion sessions without pairmode active have no story context.

Update the companion SKILL.md to describe this new field.

The companion skill should detect if the project has pairmode active
(check for `.claude/settings.deny-rationale.json`) and if so, ask the user
"Which story are you working on?" after module selection (optional — user can skip).

Write the story ID to state.json if provided.

---

### Story 5.2 — Story context panel in sidebar

**Acceptance criterion:** When `current_story` is set in state.json, the sidebar displays
a story context panel showing the current story ID and title.

**Instructions:**

Update `skills/companion/scripts/sidebar.py`.

Add a story context panel below the specs panel in the sidebar layout:
```
╭──────────────── Story ─────────────────╮
│  Story 2.3 — Deny list deriver         │
│  Started: 14:32                        │
╰────────────────────────────────────────╯
```

The sidebar reads `current_story` from state.json on startup and on each pipe message
that includes a `type: "state_update"` event.

If `current_story` is not set, the panel is hidden.

---

### Story 5.3 — Module boundary detection

**Acceptance criterion:** When a builder modifies files in multiple modules during a single
session, the sidebar displays a module boundary alert. The detection uses the existing
module path mappings from modules.json.

**Instructions:**

Update `hooks/post_tool_use.py` to include the modified file path in its pipe message:
```json
{ "type": "file_changed", "path": "/abs/path/to/file.py", "tool": "Edit" }
```

Update `skills/companion/scripts/sidebar.py` to track which modules have been touched
in the current session (by matching file paths against module paths in modules.json).

If files from more than one module have been touched and `current_story` is set,
add a warning to the sidebar:
```
⚠ Multi-module: auth-and-security, decision-ledger
  Story scope may be exceeded
```

---

### Story 5.4 — Permission override capture

**Acceptance criterion:** When a protected file is edited (file path matches a pattern in
`.claude/settings.deny-rationale.json`), the sidebar displays a prompt asking for an
override reason. The prompt is non-blocking — the edit has already happened.

**Instructions:**

Update `hooks/post_tool_use.py` to check if the modified file matches any pattern in
`.claude/settings.deny-rationale.json`. If it does, include in the pipe message:
```json
{
  "type": "file_changed",
  "path": "/abs/path",
  "tool": "Edit",
  "protected": true,
  "protection_rule": "Edit(src/services/auth/**)",
  "non_negotiable": "Auth must never call billing directly"
}
```

The sidebar handles `protected: true` by displaying an override capture prompt:
```
╭─────────── Protected File Override ───────────╮
│  src/services/auth/middleware.ts was modified  │
│  Rule: Auth must never call billing directly   │
│                                                │
│  Reason for override (or press s to skip):     │
╰───────────────────────────────────────────────╯
```

If the user provides a reason, write a `spec_exception` message to the pipe.
If the user skips (presses s), no record is written.

---

### Story 5.5 — Spec exception recording

**Acceptance criterion:** When a spec exception is captured, it is written to the
spec's `conflicts` array with the override reason and session lineage. Tests pass.

**Instructions:**

The sidebar handles `type: "spec_exception"` pipe messages by calling a new function
`record_spec_exception()` in the sidebar script:

```python
def record_spec_exception(
    project_dir: Path,
    file_path: str,
    non_negotiable: str,
    override_reason: str,
    session_id: str
) -> None:
    """
    Finds the relevant spec module (by matching file_path against module paths),
    appends to its conflicts array:
    {
      "file": file_path,
      "non_negotiable": non_negotiable,
      "override_reason": override_reason,
      "date": today,
      "session_id": session_id,
      "status": "open"
    }
    """
```

Create `tests/pairmode/test_spec_exception.py`.

---

### Story 5.6 — Phase 5 test coverage pass

**Acceptance criterion:** Full test pass. All Phase 5 logic has test coverage.

**Instructions:**

Tests only. Cover:
- state.json story context read/write
- Module boundary detection with mock module paths
- Protected file detection from deny-rationale.json
- Spec exception recording with mock spec files
- Sidebar story panel rendering (assert output contains story ID)

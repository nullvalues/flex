---
era: "001"
---

# flex — Phase 25: Backlog remediation and cross-project agent sync

← [Phase 24: Data-defensible model rebalance refinement](phase-24.md)

## Goal

Phase 25 closes the two MEDIUM CER items that have been deferred since Phases 18
and 22, and adds a `pairmode sync-agents` subcommand that addresses the
cross-project template-drift problem surfaced at the start of the Phase 24 session.

**CER-010** (story_new.py rail traversal) and **CER-015** (record_attempt.py
manual placeholder transcription) have clear, bounded fixes. They have been
deferred because each prior phase had more pressing work — Phase 25 has no such
competition.

**Template drift** is the gap that caused the Phase 24 session opener: INFRA-044
updated the agent templates but provided no mechanism for existing projects to
adopt the new model assignments. The flex repo's own `.claude/agents/` files
had to be patched manually. Forqsite, radar, cora, lumin, and halfhorse still
carry stale model assignments. `pairmode sync-agents` closes the gap for any
project that has already bootstrapped pairmode.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-051 | `record_attempt.py --story-file` flag — auto-extract phase/rail/story_class from frontmatter | complete |
| INFRA-052 | `story_new.py --rail` containment validation (CER-010) | complete |
| INFRA-053 | `pairmode sync-agents` subcommand — propagate template model updates to existing projects | complete |
| LESSON-006 | Capture template-drift-and-sync pattern as a lesson | complete |

---

### Story INFRA-051 — `record_attempt.py --story-file` flag

**Rail:** INFRA

**Acceptance criterion:** `record_attempt.py` accepts an optional `--story-file
PATH` flag. When supplied, it reads the story file's YAML frontmatter and
auto-fills `--phase`, `--rail`, `--story-class`, and `--story-id` from the
frontmatter fields (`phase`, `rail`, `story_class`, `id`). Explicitly-passed
flags still take precedence over auto-filled values. When `--story-file` is
supplied and `--story-id` is not, `story-id` is required to come from the file.
A missing story file or malformed frontmatter exits non-zero with a clear error.

**Background:** CER-015. The current CLAUDE.build.md examples use placeholder
literals (`--phase N --rail RAIL`) that must be manually transcribed from the
story file. If the orchestrator miscounts an attempt or copies the wrong rail,
the effort DB silently records wrong data. A `--story-file` flag makes the common
case (record the builder attempt for the story I just built) a single unambiguous
call.

**Instructions:**

1. Add `--story-file` option to `record_attempt.py`. Use `click.Path(exists=True)`
   so the file is validated before parsing.
2. After parsing the frontmatter, populate the following fields if not already
   set by explicit flag: `story_id` (from `id`), `phase` (from `phase`), `rail`
   (from `rail`), `story_class` (from `story_class`, defaulting to `"code"` if
   absent — consistent with INFRA-045 default).
3. Update `CLAUDE.build.md` builder record_attempt example to use `--story-file
   docs/stories/RAIL/RAIL-NNN.md` and remove the manual `--phase`, `--rail`, and
   `--story-class` placeholders (keep `--story-id` as explicit since it is already
   in the path, and keep `--model`, `--attempt-number`, `--tokens-total`,
   `--tool-uses`, `--duration-ms`, `--model-selection-reason`).
4. Update `skills/pairmode/templates/CLAUDE.build.md.j2` with the same example.
5. Update architecture.md to note `--story-file` as the recommended invocation.
6. Mark CER-015 resolved in `docs/cer/backlog.md`.

**Tests:** `tests/pairmode/test_record_attempt.py` extended with:
- `--story-file` populates phase/rail/story_class/story_id from frontmatter
- Explicit flags override auto-filled values
- Missing file exits non-zero
- Frontmatter missing `id` exits non-zero
- Story file with no `story_class` field defaults to `"code"`

---

### Story INFRA-052 — `story_new.py --rail` containment validation

**Rail:** INFRA

**Acceptance criterion:** `story_new.py --rail` input is validated with a formal
`Path.resolve().relative_to()` containment check before being used in path
construction. A `--rail` value that would resolve outside `<project_dir>/docs/stories/`
exits non-zero with a clear error. The check is consistent with the guard
discipline already applied in `permission_scope.py`.

**Background:** CER-010. The current code does `.upper()` on the rail name and
constructs a path without verifying containment. A caller passing
`--rail "../../../etc"` constructs a path that escapes `project_dir`. While the
CLI is an internal tool (not internet-facing), consistent guard discipline across
all pairmode path-construction code is the non-negotiable (see architecture.md §
Pairmode non-negotiables).

**Instructions:**

1. After resolving the rail directory path (`project_dir / "docs" / "stories" /
   rail_upper`), assert `rail_path.resolve().is_relative_to(
   (project_dir / "docs" / "stories").resolve())`. If not, exit with an error:
   `"Invalid rail name: resolves outside docs/stories/"`.
2. Apply the same guard to `era_new.py` slug path construction (CER-011 partial
   resolution — the `_slugify()` approach is retained but a formal containment
   check is added after slug construction).
3. Mark CER-010 resolved and CER-011 partially resolved in `docs/cer/backlog.md`.

**Tests:** `tests/pairmode/test_story_new.py` extended with:
- Rail traversal attempt (`--rail "../../etc"`) exits non-zero
- Normal rail (`--rail INFRA`) still works
`tests/pairmode/test_era_new.py` extended with an analogous path traversal test.

---

### Story INFRA-053 — `pairmode sync-agents` subcommand

**Rail:** INFRA

**Acceptance criterion:** A new `pairmode sync-agents [--project-dir DIR]
[--dry-run] [--yes]` subcommand re-renders the frontmatter of each agent file in
`<project_dir>/.claude/agents/` from the current pairmode templates, then writes
the updated files. The body of each agent file (content below the closing `---`
of the frontmatter block) is preserved unchanged. The subcommand prints a unified
diff of each changed file before writing (or exits after the diff with `--dry-run`).
With `--yes`, writes without prompting; otherwise prompts once ("Apply these
changes? [y/N]") before writing.

**What "re-render the frontmatter" means:**

For each agent file found in `<project_dir>/.claude/agents/`:
1. Find the matching template in `skills/pairmode/templates/agents/` by filename
   stem (e.g. `reviewer.md` ↔ `reviewer.md.j2`).
2. Render only the frontmatter block of the template (from the opening `---` up
   to and including the closing `---`) with `project_name` substituted from
   `state.json["project_name"]` or derived from `project_dir.name`.
3. Replace the frontmatter block in the target file with the rendered result.
4. Leave the body (everything after the second `---`) unchanged.

If no matching template exists for an agent file, skip that file and warn.
If no agent file exists for a template, skip (sync-agents does not create new files;
`bootstrap` creates them).

**Motivation:** INFRA-044 updated agent templates but existing bootstrapped projects
could not adopt the new model assignments without manual edits to each agent file.
`sync-agents` makes template propagation a single command — run it on forqsite,
radar, cora etc. after any template update to bring them current.

**Instructions:**

1. Add `sync-agents` subcommand to `skills/pairmode/scripts/pairmode_status.py`
   (or a new `pairmode_sync.py` script if the existing file is too crowded).
   Expose via the `flex:pairmode` skill entry point.
2. The frontmatter parser must handle both the template's Jinja2 `model: sonnet`
   line and any inline YAML comment (`# upgrade: opus (when ...)`) correctly —
   both lines should be part of the rendered frontmatter.
3. The diff output uses Python's `difflib.unified_diff` with `fromfile` /
   `tofile` labels. Print it in full before prompting.
4. The `--yes` flag skips the prompt. `--dry-run` prints the diff and exits 0
   without writing.
5. Document the subcommand in `docs/architecture.md` under the "Pairmode
   tooling" section.

**Tests:** `tests/pairmode/test_sync_agents.py` covering:
- Frontmatter updated; body preserved
- No matching template → file skipped with warning
- `--dry-run` writes nothing
- `--yes` writes without prompt
- Agent file with no frontmatter block handled gracefully (warn, skip)

---

### Story LESSON-006 — Capture template-drift-and-sync pattern

**Rail:** LESSON

**Acceptance criterion:** A new lesson entry in `lessons/lessons.json` documents
the template-drift problem and the sync-on-demand solution.

**Lesson content:**

- **trigger**: Phase 24 session start revealed that flex's own `.claude/agents/`
  files had no `model:` frontmatter, and forqsite/radar still carried pre-INFRA-044
  opus reviewer assignments — despite INFRA-044 having updated the templates.
- **problem**: Pairmode templates and bootstrapped project files diverge silently
  after any template update. There is no mechanism to propagate changes to existing
  projects short of manual edits or a full re-bootstrap. The drift is invisible
  until a session starts and the wrong model is used.
- **value_framing**: Template updates that affect build behaviour (model selection,
  tool restrictions, upgrade triggers) must propagate to existing projects or the
  update has only partial effect. The effort spent tuning templates is wasted if
  projects accumulate stale copies.
- **learning**: Two complementary patterns close the gap: (1) a sync command that
  re-renders template frontmatter into existing agent files on demand; (2) a note
  in the methodology that any template change affecting agent behaviour should be
  followed by a `pairmode sync-agents` run on all active projects. The sync
  command is idempotent — running it twice produces no further changes.
- **methodology_change**: After any pairmode template update that changes agent
  frontmatter (model assignments, tool lists, upgrade triggers), run
  `pairmode sync-agents --project-dir <each active project>` before starting
  the next build session on that project.
- **validation_phase**: "25"
- **affects**: pairmode-template-propagation, cross-project consistency.

---

Tag: `cp25-backlog-remediation-and-agent-sync`

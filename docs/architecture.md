# Flex — Architecture

## What flex is

Flex is a Claude Code plugin built around two layers. **Pairmode** is the primary workflow: a
structured builder/reviewer build loop with effort tracking, per-story schema gates, context budget
checks, and model selection per attempt. **Companion** is the memory layer underneath: a sidebar
that captures decisions live and a canonical spec format (`spec.json`) that survives across
sessions. Pairmode enforces intent at the build gate; companion records what was decided along the
way.

This document is the source of truth for the flex codebase itself. Read it before any task.

---

## Module structure

```
flex/
  hooks/                          ← thin relays (no API calls); see § Hook architecture
    hooks.json                    ← hook event registration
    stop.py                       ← historian: extract decisions after each response
    exit_plan_mode.py             ← relay plan content for impact analysis
    post_tool_use.py              ← pair partner: relay file changes
    session_end.py                ← signal sidebar to summarize and exit
    pre_tool_use.py               ← thin dispatcher: Task → context_budget.py (CER-027 budget enforcement); Edit/Write → scope_guard.py (Phase 55 file-scope enforcement)

  skills/
    pairmode/                     ← /flex:pairmode — bootstrap and manage pairmode
      SKILL.md
      scripts/
        bootstrap.py              ← generate pairmode scaffold from spec
        audit.py                  ← diff project against canonical templates
        sync.py                   ← apply delta from audit non-destructively
        lesson.py                 ← capture a lesson learned
        lesson_review.py          ← surface lessons, propose template updates; --drift-only runs drift promotion without lesson review
        context_budget.py         ← orchestrator context-window estimation + block decision logic (CER-027)
        flex_build.py             ← CLI wrapping 17 pairmode helper functions (select-builder-model, select-reviewer-model, select-security-auditor-model, select-intent-reviewer-model, write-permissions, clear-permissions, permissions-create, check-guardrail, context-health, check-stubs, current-phase, transition-era, write-attempt-count, read-attempt-count, clear-attempt-count, story-cost-estimate, set-context-tokens); replaces inline python -c blocks in CLAUDE.build.md.j2
        refresh_effort_baseline.py ← regenerate skills/pairmode/seed/effort_baseline.json from downstream effort.db files
        story_context.py          ← read/write current story in state.json; pairmode detection
        spec_exception.py         ← record protected-file overrides into spec.json conflicts
        reconstruct.py            ← refresh docs/reconstruction.md from ideology.md and brief.md
        ideology_parser.py        ← shared ideology.md and reconstruction.md brief parser
        score.py                  ← render pre-populated RECONSTRUCTION.md scoring report from reconstruction brief
        story_new.py              ← create story files on named rails
        era_new.py                ← create era documents
        era_transition.py         ← formally close the current active era and open the next; CLI: uv run era_transition.py --project-dir DIR [--name NAME] [--intent INTENT] [--yes]; also registered as flex_build.py transition-era
        schema_validator.py       ← validate story/era/phase manifest frontmatter
        permission_scope.py       ← story-scoped allow rules lifecycle for .claude/settings.local.json (legacy; Phase 55 replaces runtime use with scope_guard.py + permissions-create for new projects)
        scope_guard.py            ← story file-scope enforcement for pre_tool_use hook; reads docs/phases/permissions/<story_id>.json and fails open (Phase 55, INFRA-138)
        story_resolver.py         ← resolve story IDs to story file content; parse phase manifest Stories tables
        next_story.py             ← find next unbuilt story from a phase file; CLI: uv run next_story.py <phase-file> [--json] [--project-dir DIR]
        pairmode_sync.py          ← re-render agent file frontmatter from canonical templates (sync-agents subcommand); propagate CLAUDE.build.md template changes (sync-build subcommand); sequence all three sync operations in fixed order (sync-all subcommand); also registers register/unregister/list-projects in the top-level CLI group
        pairmode_register.py      ← manage registered_projects in .companion/state.json (register/unregister/list-projects subcommands)
        pairmode_migrate.py       ← one-shot migration of an anchor-bootstrapped sibling project to flex naming (migrate-from-anchor subcommand)
        global_session_check.py   ← global SessionStart hook; detects pairmode, prints status block or bootstrap prompt; stdlib-only (runs as bare python3)
      seed/
        effort_baseline.json      ← seeded token-cost baseline for bootstrap (refreshed by refresh_effort_baseline.py)
      templates/                  ← Jinja2 templates for scaffold generation
        CLAUDE.md.j2
        CLAUDE.build.md.j2
        RECONSTRUCTION.md.j2     ← scoring report template filled in by a reconstruction agent
        agents/
          builder.md.j2
          reviewer.md.j2
          loop-breaker.md.j2
          security-auditor.md.j2
          intent-reviewer.md.j2
          reconstruction-agent.md.j2
        docs/
          brief.md.j2
          ideology.md.j2           ← ideology and conviction record; generated by bootstrap
          reconstruction.md.j2     ← reconstruction brief for blank-slate agent; generated by bootstrap or reconstruct
          architecture.md.j2
          checkpoints.md.j2
          phases/
            index.md.j2
            phase.md.j2       ← per-phase scaffold; generated by phase_new.py
          stories/.gitkeep    ← creates stories root in bootstrapped projects (template stub only)
          eras/.gitkeep       ← creates eras root in bootstrapped projects (template stub only)
          cer/
            backlog.md.j2
    companion/                    ← /flex:companion — start each session
      SKILL.md
      scripts/
        sidebar.py                ← companion sidebar process (long-running)
        start_sidebar.sh          ← detects OS, opens sidebar in new terminal
        launch_sidebar.command    ← macOS launcher
        launch_sidebar.sh         ← Linux launcher
    seed/                         ← /flex:seed — bootstrap canonical spec (run once)
      SKILL.md
      scripts/
        setup.py                  ← product config writer
        mine_sessions.py          ← transcript decision extractor
        reconcile.py              ← spec merger

  lessons/
    lessons.json                  ← global methodology lessons (lives in flex repo)
    LESSONS.md                    ← human-readable summary, auto-generated

  .claude-plugin/
    plugin.json                   ← plugin manifest
    marketplace.json              ← marketplace registration
```

---

## Data flow

```
Claude Code session
    ↓ (after each response)
stop.py hook → writes to /tmp/companion-<hash>.pipe (relay only, no API calls)
    (pipe path is project-scoped; hash is first 8 chars of md5 of project dir)
    ↓
sidebar.py reads pipe → calls model backend (claude_agent_sdk by default; Ollama when FLEX_MODEL_BACKEND=ollama) → extracts decisions
    ↓
persist_capture() → .companion/changes/<session-id>/incremental.json
    ↓
session ends → sidebar shows summary, exits
    ↓
next /flex:companion → detects unreconciled sessions → reconcile.py
    ↓
reconcile.py → merges into <spec_location>/openspec/specs/<module>/spec.json
```

```
post_tool_use.py → pipe → sidebar tracks file→module mapping
exit_plan_mode.py → pipe → sidebar analyzes plan for cross-module impact
session_end.py → pipe → sidebar graceful shutdown signal
```

---

## Pairmode build loop

Each story moves through a fixed sequence. The orchestrator (`CLAUDE.build.md`) drives every step:

1. **Story spec** — the phase doc names the story; the story file at
   `docs/stories/<RAIL>/<RAIL>-NNN.md` defines `## Requires`, `## Ensures`, and
   `primary_files`/`touches`. Before the builder spawns, two pre-story gates run:
   (a) the **schema gate** checks whether the story introduces a new persistent schema
   object without a management surface; (b) the **stub gate** checks whether the story
   file contains delegation language ("See phase doc") or is missing an acceptance
   surface. A story that fails either gate is blocked until the operator resolves it.

2. **Permission pre-write** — `flex_build.py permissions-create` generates
   `docs/phases/permissions/<story_id>.json` from the story's `primary_files` and `touches`
   frontmatter. `story_context.py --set` stamps the active story into `.companion/state.json`.
   The `pre_tool_use.py` hook then enforces the declared scope via `scope_guard.py` on every
   Edit/Write call during the builder session. (Phase 55 replaced the old `permission_scope.py`
   / `settings.local.json` allow-rule cycle; see step 9.5 and § Hook architecture.)

3. **Builder spawn** — `model_selector.select_builder_model()` picks the model (haiku for
   doc/lesson, sonnet baseline for code, opus on high-scope signals or retry). The builder
   subagent implements the story, runs the test suite, and exits.

4. **Tests** — the builder confirms `pytest tests/pairmode/ -x -q` passes before handing off.

5. **Reviewer spawn** — `model_selector.select_reviewer_model()` picks the model (sonnet
   baseline; opus on retry for `code`-class stories). The reviewer checks the diff against
   every `## Ensures` assertion and the review checklist, then either commits or reverts.

6. **Commit or revert + retry** — on PASS the reviewer commits and story status is updated to
   `complete`; on FAIL the reviewer reverts and the builder is respawned with attempt_number
   incremented.

7. **Effort recording** — `record_attempt.py` writes each builder and reviewer spawn to
   `.companion/effort.db` (tokens, model, duration, outcome).

8. **Loop-breaker** — if the same story fails twice, the orchestrator invokes the loop-breaker
   subagent (opus) to diagnose the root cause cold and propose one alternative approach.

9. **Context budget check** — `hooks/pre_tool_use.py` fires on every
   Task spawn and delegates to
   `skills/pairmode/scripts/context_budget.py`. The module reads
   `state["context_current_tokens"]` (written by the orchestrator's
   `flex_build.py set-context-tokens` step after each `/context`
   call), estimates the next step's tokens (median of recent
   effort.db attempts for the current phase, or
   `state["expected_step_tokens"]` as a seeded fallback), and blocks
   the spawn when the projected total would exceed `threshold *
   (1 + overrun_pct)`. When `context_current_tokens` is absent, the
   module blocks with a `CONTEXT CHECK REQUIRED` prompt directing the
   operator to call `/context` and run `set-context-tokens`.
   The block reason carries a verbatim prompt; the operator picks
   Proceed (acknowledged) or `/clear` and resume. CER-027 and
   CER-039 document the failure modes this replaces.

9.5 **Story file-scope enforcement** — `hooks/pre_tool_use.py` also intercepts
   `Edit` and `Write` tool calls. It delegates to
   `skills/pairmode/scripts/scope_guard.py`, which reads
   `<project_dir>/.companion/state.json["current_story"]["id"]` and then reads
   `<project_dir>/docs/phases/permissions/<story_id>.json` to verify the target
   path is declared in the active story's `primary_files` or `touches`. If the
   path is not declared, the hook emits `{"decision": "block", "reason": "..."}`.
   The check fails open on any error (missing state, missing permissions file,
   malformed JSON) so non-story orchestrator work (checkpointing, spec mode) is
   never blocked. Introduced in Phase 55 (INFRA-138, INFRA-139).

10. **Checkpoint** — at phase end, the intent-reviewer and security-auditor run across all stories.
    Documentation is updated, all planned stories are verified complete or deferred, and the phase
    is tagged.

---

## The canonical spec format

Each module has one `spec.json` at `<spec_location>/openspec/specs/<module>/spec.json`:

```json
{
  "module": "module-name",
  "summary": "One paragraph — what this module does and why.",
  "business_rules": [
    "Rules that must hold for the module to function correctly"
  ],
  "non_negotiables": [
    "Hard constraints that must never be violated — architectural, security, or contractual"
  ],
  "tradeoffs": [
    {
      "decision": "what was decided",
      "reason": "why",
      "accepted_cost": "what we gave up"
    }
  ],
  "conflicts": [],
  "lineage": [
    {
      "session_id": "...",
      "summary": "what happened in this session",
      "date": "YYYY-MM-DD",
      "resume": "claude --resume ..."
    }
  ]
}
```

**Invariants:**
- `non_negotiables` entries never auto-resolve. They require a developer decision to override.
- `lineage` is append-only. Sessions are never removed from lineage.
- `summary` is always rewritten during reconcile to reflect current state.

---

## Pairmode design

### Pairmode and companion: separation of concerns

Pairmode is flex's primary build workflow; companion is the memory layer it draws on.
Pairmode and companion are two temporal postures on the same concern — keeping intent
intact across sessions and across builds. Companion is **reactive**: the sidebar observes
a session as it unfolds and writes decisions, drift, and lineage into `spec.json` after
the fact. Pairmode is **proactive**: every story is specced in writing before code is
written, and the builder/reviewer loop gates every commit against that spec.

The two are coupled only through `.companion/state.json`. Companion writes `current_story`
so the sidebar can surface story context; pairmode reads `pairmode_version` to compute
audit deltas against the canonical templates. There is no other runtime dependency:
pairmode functions without the sidebar (the deny list still blocks protected-file writes;
the reviewer still runs), and companion functions without a pairmode scaffold (the
sidebar still captures decisions; the spec still grows).

**Reviewer-class agent tool restriction (build-loop safety).** Reviewer-class agents
(`reviewer`, `intent-reviewer`, `loop-breaker`, `security-auditor`) are restricted to
read-only tools plus `Bash` (all four reviewer-class agents declare
`tools: [Read, Bash, Glob, Grep]`; Bash is needed for test runs and git operations in
the reviewer and loop-breaker; security-auditor includes it for consistency). This is one of two layers protecting the working tree: tool restriction
prevents the reviewer from backdooring a fix into the code instead of reverting it; the
orchestrator's pre-reviewer commit discipline (committing story files and running
`git checkout -- lessons/` before the reviewer fires) prevents accidental erasure of
uncommitted methodology files. Both commit and revert paths in the reviewer template
are Bash-mediated (`git add`, `git commit`, `git checkout .`, `git clean -fd`).

This document describes pairmode's internals: the scaffold it generates, the rails/eras
model, the schema validators, and the non-negotiables that keep its bootstraps repeatable.

### Core concepts

**Spec-derived protections:** The deny list in a pairmode project's `.claude/settings.json`
is generated from the project's `spec.json` non-negotiables, not hand-written. Each protection
carries a comment linking back to the non-negotiable it encodes.

**Permission override capture:** When a developer edits a protected file, the sidebar
(not the hook) classifies the file against `.claude/settings.deny-rationale.json` and
displays an override prompt. If the developer provides a reason, the sidebar writes a
`spec_exception` pipe message. The sidebar's pipe-reader calls
`skills/pairmode/scripts/spec_exception.record_spec_exception()` to append a conflict
entry to the relevant module's `spec.json` conflicts array. The hook emits only
`path` and `tool` — deny-rationale reads never occur in hooks.

**Lessons:** Methodology improvements are captured in `flex/lessons/lessons.json`.
Each lesson records the triggering situation, what was learned, what changed in the methodology,
and which projects it applies to. Lessons flow into templates via `/flex:pairmode review`.

**Template versioning:** Each pairmode-bootstrapped project records the `pairmode_version`
it was bootstrapped with in `.companion/state.json`. `/flex:pairmode audit` uses this to
determine the delta between the project's methodology and the current canonical version.
Audit compares section headers (structural presence of `##` headings) between project files
and raw Jinja2 template source — it does not render templates before comparison. Section
bodies in canonical templates contain Jinja2 variable expressions (`{{ project_name }}`
etc.); body-level content comparison should not be relied upon for semantic drift detection.

### Rails and eras

**Rails** are named architectural lanes. Each story belongs to one rail. Rail name + 3-digit
sequence number = stable story ID (e.g., `BOOTSTRAP-003`, `AUDIT-007`). Rails are defined per
project at bootstrap time; pairmode suggests defaults based on the project's tech stack.

**Eras** are strategic containers above phases. An era defines a period of development with a
unified intent. Phases and rails belong to an era. Eras are named chronologically (e.g.,
`001-initial`, `002-reconstruction`).

**Story files** live at `docs/stories/<RAIL>/<RAIL>-NNN.md` with structured YAML frontmatter:
`id`, `rail`, `title`, `status`, `phase`, `primary_files` (files primarily owned by this story),
`touches` (secondary files the story modifies). Phase docs reference story IDs in a `## Stories`
table; full story content lives in the individual story file.

Story frontmatter fields summary:

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Rail + 3-digit sequence (e.g. `INFRA-063`) |
| `rail` | yes | Rail name, uppercase |
| `title` | yes | Short description string |
| `status` | yes | One of `draft`, `planned`, `in-progress`, `complete`, `backlog` |
| `phase` | yes | Phase number string |
| `primary_files` | yes | List; may be empty only when `status` is `draft` or `backlog` |
| `touches` | no | Secondary files the story modifies |
| `story_class` | no | One of `code`, `doc`, `lesson`, `methodology`; defaults to `code` |
| `source` | no | Set by drift promotion to record the originating project |

**Story body contract sections** follow the frontmatter block. Every story must contain either
the canonical new-format sections or the legacy alias:

- `## Requires` — preconditions: prior stories that must be complete, file or system state that
  must hold before building begins.
- `## Ensures` — binary verifiable assertions, checked independently by the reviewer. One per
  line. Each assertion must be verifiable without interpretation: file exists, command output
  contains X, function Y returns Z.
- `## Acceptance criterion` — legacy alias for `## Ensures`. Accepted by all tooling without
  error; new stories generated by `story_new.py` use `## Requires` + `## Ensures` instead.

A story body that contains neither `## Acceptance criterion` nor both `## Requires` and
`## Ensures` is rejected by `schema_validator.py`. A story containing both the legacy and new
sections is also valid (transition stories written mid-migration).

**Era files** live at `docs/eras/NNN-kebab-name.md` with frontmatter: `id`, `name`, `status`.

**`schema_validator.py` is the canonical frontmatter parser.** Its `_parse_frontmatter` function
must be imported and used by sibling scripts that need to read YAML frontmatter from
story/era/phase files. Do not re-implement the parser inline. Callers import it as
`from schema_validator import _parse_frontmatter` after inserting the scripts dir into `sys.path`.

**`schema_validator.py` draft/backlog exemption:** `validate_story_file` permits an empty
`primary_files` list when `status` is `draft` or `backlog`. Non-draft, non-backlog stories
must have at least one entry in `primary_files`.

### Story classification

Story files accept an optional `story_class` frontmatter field. Allowed values:

- `code` — production code in `skills/`, `hooks/`, etc. Default if field is absent. Reviewer
  uses sonnet baseline; upgrades to opus on retry.
- `doc` — documentation only (`README.md`, `docs/`, prose). Reviewer stays sonnet even on
  retry. Doc reviews do not get harder with retries.
- `lesson` — append-only lesson entries. Reviewer stays sonnet — lessons are high-structure
  JSON with a programmatic invariant check.
- `methodology` — template / scaffold / orchestrator-instruction changes. Reviewer stays
  sonnet baseline; upgrades if any other story in the same phase touches `code`.

The field is optional and additive — existing stories without it are treated as `code`.
`schema_validator.py` validates the value when present. `story_new.py` accepts
`--story-class` to write the field into generated frontmatter.

### Phase classification

Phase files accept an optional `phase_class` frontmatter field. Allowed values:

- `production` — at least one story in the phase touches production code (`skills/`, `hooks/`,
  etc.). Checkpoint security-auditor upgrades to opus. This is the default when the field is
  absent.
- `docs-only` — no story in the phase touches production code (documentation, lessons, templates
  only). Checkpoint security-auditor stays on sonnet.
- `pre-pr` — the phase is a final-pass audit before code leaves the repo. All checkpoint agents
  (intent-reviewer, security-auditor) upgrade to opus across every story in the phase.

The field is optional and additive — existing phase files without it default to `production` at
read time. `schema_validator.py` validates the value when present via `validate_phase_manifest`.
`phase_new.py` accepts `--phase-class` to write the field into generated frontmatter. The field
enables deterministic model-upgrade decisions at the checkpoint-agent level (INFRA-048).

**`story_update.py` is the canonical tool for updating story status.**
`update_story_status(story_id, project_dir, status)` updates a story file's frontmatter
`status` field. `update_phase_story_status(story_id, project_dir, status)` finds all phase
manifests containing the story's ID in their `## Stories` table and updates the status column.
CLI: `uv run python skills/pairmode/scripts/story_update.py --story-id RAIL-NNN --status complete --project-dir .`
Orchestrators must call this after a successful reviewer commit (see CLAUDE.build.md Step 3).
Valid statuses: `draft`, `planned`, `in-progress`, `complete`, `backlog`.

**Note (Phase 55):** The pairmode build loop no longer calls `write_story_permissions` for
routine story builds; `flex_build.py permissions-create` + `scope_guard.py` replaces it.
The `permission_scope.py` functions remain for backward compatibility and manual use.

**`permission_scope.py` path containment:** `write_story_permissions` validates every path
from `primary_files` and `touches` against `project_dir` using `Path.resolve().relative_to()`
before generating any allow rule. Paths that escape `project_dir` (traversal, absolute) are
skipped with a stderr warning. This guard must not be removed or weakened.

**`permission_scope.py` gitignore side-effect:** `write_story_permissions` appends
`.claude/story_scope.json` to the project's `.gitignore` (creating it if absent). This is
intentional — story_scope.json is ephemeral and must not be committed. Any project-level
`.gitignore` management must account for this.

**`permission_scope.py` empty-files behavior:** When both `primary_files` and `touches` are
empty (or all paths are filtered by the containment guard), the function returns without
writing `story_scope.json` or modifying `settings.local.json`. Callers must not assume that
"clear was called" implies rules were removed if write was a no-op.

**`PAIRMODE_DEFAULT_RAILS` (in `bootstrap.py`)** is the canonical source for default rail sets
by project type. It is imported by `sync.py`'s `_check_rail_gaps`. Treat it as a public
constant; changing its structure requires updating all callers.

**Rail-to-file mapping:** When `permission_scope.py` reads `primary_files` and `touches`, both
lists being empty produces zero allow rules with a warning, not a crash or silent
misconfiguration.

### Model selection: sonnet baseline, opus on demand

Pairmode pins each agent to a specific Claude model in its template frontmatter.
This is deliberate. Inheriting the orchestrator's model is a silent capability
leak — a phase started with Opus will give every builder Opus, hiding the cost
and obscuring whether the work actually requires that tier.

**Default.** Sonnet is the baseline for all reviewer-class agents (`reviewer`,
`intent-reviewer`, `security-auditor`) and for the `builder`. The
`loop-breaker` is the one exception: it is opus by default, because by the
time the loop-breaker fires the case is — by definition — hard, and the
reasoning premium is justified. The `reconstruction-agent` is not subject to
the build-loop model pinning policy — it is spawned infrequently outside the
build loop and inherits the orchestrator's model; the reconstruction-agent
template carries no `model:` field by design.

**Reviewer model selection.** The orchestrator calls
`skills/pairmode/scripts/model_selector.select_reviewer_model(story_class,
attempt_number, phase_id=None, project_dir=None)` before spawning each
reviewer and passes the result as the Agent tool's `model` parameter. The
helper implements the following selection table:

| `story_class` | `attempt_number = 1` | `attempt_number >= 2` |
|---|---|---|
| `code` | sonnet | opus |
| `doc` | sonnet | sonnet |
| `lesson` | sonnet | sonnet |
| `methodology` | sonnet | sonnet (opus if a same-phase `code` story exists) |

Stories without a `story_class` field default to `code`. Unknown values also
default to `code` (conservative). The "same-phase code story" check for
`methodology` reads the phase manifest via `story_resolver.list_phase_stories`
and inspects each story file's frontmatter; it returns `sonnet` (fail-safe) if
the phase manifest or any story file cannot be read.

**Operational mechanism.** Override at *call time* via the Agent tool's
`model` parameter. The template intent stays clean — it encodes the baseline,
not the override — and the upgrade is per-invocation. This is the same
mechanism used for rate-limit fallback. Example:
`Agent({..., subagent_type: "reviewer", model: "opus"})`. Each affected
template carries an inline YAML comment after `model:` documenting the upgrade
triggers (e.g. `# upgrade: opus  (when retry / pre-PR audit / mid-phase pivot)`).
The pre-existing `# fallback:` comments remain in the templates — fallback
handles rate-limit substitution downward, upgrade handles edge-case
substitution upward; both apply concurrently.

**Rationale.** Most reviews catch nothing because most builders produce
correct work. The per-story reviewer task is mechanical: diff matches spec,
tests pass, checklist OK, commit. Sonnet handles that fine. Opus is overhead
for the common case. Reserve it for the explicit edge cases above where the
judgment edge actually matters — the cost difference compounds across a build
loop that may run dozens of reviews per phase.

**Fallback policy (rate limits).** If the preferred model is rate-limited,
fall back exactly one tier. Reviewers fall Opus → Sonnet (or stay at Sonnet
if already there). The builder falls Sonnet → Haiku. Never fall below Haiku
— the reasoning quality cliff is too steep to preserve loop integrity; better
to wait for the rate limit to clear than to ship with a model that cannot
follow the spec.

**Builder model selection.** The orchestrator calls
`skills/pairmode/scripts/model_selector.select_builder_model(story_class,
primary_files, protected_files, attempt_number=1) -> (model, reason)` before spawning each
builder. The function returns a `(model, reason)` tuple:

- `model` is one of `"haiku"`, `"sonnet"`, or `"opus"`
- `reason` is one of `"auto-downgrade"`, `"auto-baseline"`, `"prompted-upgrade"`,
  `"retry-upgrade"`

| `story_class` | complexity signal | attempt | model | reason | action |
|---|---|---|---|---|---|
| `doc` | any | any | haiku | `auto-downgrade` | auto |
| `lesson` | any | any | haiku | `auto-downgrade` | auto |
| `methodology` | any | any | sonnet | `auto-baseline` | auto |
| `code` | < 5 `primary_files`, no protected file | 1 | sonnet | `auto-baseline` | auto |
| `code` | ≥ 5 `primary_files` OR a protected file in touches | 1 | opus | `prompted-upgrade` | **prompt user** |
| `code` | any | ≥ 2 | opus | `retry-upgrade` | auto (no prompt) |

`protected_files` is derived from the deny list in `CLAUDE.md` § Protected
files and from `.claude/settings.json`. When the function returns
`prompted-upgrade`, the orchestrator displays the upgrade suggestion to the
user and waits for confirmation before spawning the builder. If the user
overrides the suggestion downward, the orchestrator records reason
`user-override` in the effort DB. The `--story-class` and
`--model-selection-reason` flags on `record_attempt.py` persist both fields
so the `validate-rebalance` view can surface decision-quality evidence.

Prompt text for `prompted-upgrade`:

```
MODEL SUGGESTION — Story [ID]
story_class: code
Signal: [e.g. "touches protected file hooks/stop.py" or "5 primary_files"]
Suggested builder model: opus (baseline: sonnet)
Reason: high-scope code story; opus reduces rework risk
Say "upgrade" to use opus, or "continue" to proceed with sonnet.
```

**Checkpoint-agent model selection.** The helper family is extended with two
additional selectors driven by the `phase_class` frontmatter field:

`select_intent_reviewer_model(phase_class) -> tuple[str, str]` — returns `(model, reason)` for the
intent-reviewer checkpoint agent. The `reason` string is emitted on the second line of `model_selector.py` CLI output.

| `phase_class` | model |
|---|---|
| `production` | sonnet |
| `docs-only` | sonnet |
| `pre-pr` | opus |

`select_security_auditor_model(phase_class) -> tuple[str, str]` — returns `(model, reason)` for the
security-auditor checkpoint agent. The `reason` string is emitted on the second line of `model_selector.py` CLI output.

| `phase_class` | model |
|---|---|
| `production` | opus |
| `docs-only` | sonnet |
| `pre-pr` | opus |

Unknown or absent `phase_class` values default to `"production"` for both
helpers. The orchestrator reads `phase_class` from the phase manifest frontmatter
before spawning each checkpoint agent and passes the result as the Agent tool's
`model` parameter (same override mechanism as the reviewer model selection).

### Pairmode tooling

**`pairmode_sync.py` — `sync-agents` subcommand.**
Re-renders the frontmatter of each agent file in `<project_dir>/.claude/agents/` from the
current canonical pairmode templates; also merges new H2 body sections from the rendered
template into the target file additively (Phase 33+).

CLI:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  sync-agents [--project-dir DIR] [--dry-run] [--yes]
```

Behaviour:
- For each `*.md` file in `<project_dir>/.claude/agents/`, finds the matching template by
  filename stem (e.g. `reviewer.md` → `reviewer.md.j2`) in `skills/pairmode/templates/agents/`.
- Renders only the frontmatter block of the template using the full context from
  `_build_template_context()` (Phase 44+): `project_name`, `build_command`, `test_command`,
  `migration_command`, `pairmode_scripts_dir`, `domain_isolation_rule`, and `protected_paths`.
  Values are sourced from `.companion/pairmode_context.json` with `.companion/state.json` as
  fallback; missing keys default to `""` or `[]`.
- Replaces the frontmatter block in the target file.
- Attempts to render the full template to extract new H2 body sections (`_merge_body_sections`).
  Sections present in the template but absent from the target are appended; existing target
  sections and project-specific sections are preserved. Sections already present are not
  duplicated.
- **Body propagation:** Full-template rendering uses `StrictUndefined`. Since Phase 44,
  the context passed to `sync-agents` includes all variables used by the canonical agent
  templates (`build_command`, `test_command`, `domain_isolation_rule`, `protected_paths`).
  For projects whose `pairmode_context.json` and `state.json` supply these values, body
  propagation now works as intended. For sibling projects that were bootstrapped before
  those keys were written to `pairmode_context.json`, or that use templates referencing
  project-specific variables beyond the known set, the full-template render will still fail
  with `StrictUndefined` and the body-merge step will silently fall back to no-op for that
  file. In that case, new body sections must be applied manually during deployment stories.
  When rendering fails, `sync-agents` now surfaces an explicit error to stderr and exits 1
  rather than silently reporting "No changes to apply."
- Prints a unified diff (`difflib.unified_diff`) for each changed file before writing.
- `--dry-run`: exits after printing diffs without writing any files.
- `--yes`: writes without prompting.

All `*.md` files in `.claude/agents/` with a matching template are re-rendered, including
`reconstruction-agent.md` if that template exists. Files without a matching template are
skipped with a warning.
- Default: prompts once ("Apply these changes? [y/N]") before writing.
- If no matching template exists for an agent file: warns and skips that file.
- If all files rendered cleanly and no diffs were found: prints "No changes to apply." and
  exits 0. If rendering failed for one or more files: prints `"error: failed to render
  {filename}: {reason}"` to stderr for each failed file, then exits 1 when no changes were
  found. Partial success (some files changed, some errored) proceeds with the apply flow and
  exits 0, with errors already printed to stderr.
- Agent files with no frontmatter block (no opening `---`): warns and skips.

**`pairmode_sync.py` — `sync-build` subcommand.**
Compares the target project's `CLAUDE.build.md` against the canonical `CLAUDE.build.md.j2`
template rendered with the project's `state.json` and `pairmode_context.json`. Prints a
unified diff. With `--apply`, writes the rendered template to the project's `CLAUDE.build.md`
after confirmation (or immediately with `--apply --yes`). With `--dry-run`, prints the diff
and exits without writing.

CLI:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  sync-build --project-dir DIR [--dry-run] [--apply] [--yes]
```

Behaviour:
- Renders `CLAUDE.build.md.j2` with `project_name`, `build_command`, `test_command`,
  `migration_command` sourced from `state.json` and `pairmode_context.json` (graceful
  fallback when keys are absent).
- `--dry-run` or no `--apply`: prints diff and exits 0 without writing.
- `--apply`: prints diff, prompts "Apply? [y/N]", writes on `y`.
- `--apply --yes`: writes without prompting.
- If no changes: prints "No changes to apply." and exits 0.
- Applies a depth guard on `--project-dir` (fewer than 3 path components are rejected).

**`pairmode_sync.py` — `sync-all` subcommand.**
Sequences all three sync operations in a single CLI call: `sync.py` (methodology files)
→ `sync-agents` (agent frontmatter) → `sync-build` (CLAUDE.build.md). Safe by default:
without `--apply`, `sync.py` is skipped (it has no `--dry-run` flag) and the remaining
two commands run in dry-run mode. With `--apply`, all three are invoked. Fail-fast: if
any downstream command exits non-zero, the wrapper emits an error and exits with the same
status code; remaining commands are not invoked.

CLI:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  sync-all --project-dir DIR [--apply] [--yes]
```

Behaviour:
- `--dry-run` (default True): skips `sync.py`; runs `sync-agents` and `sync-build` in dry-run mode.
- `--apply`: runs all three; `sync-agents` without `--dry-run`; `sync-build` with `--apply`.
- `--yes` / `-y`: propagated to every downstream invocation.
- Depth guard (`_depth_guard_sync_build`) runs against `--project-dir` before any subprocess call.
- Per-command output is preceded by a `=== <label> ===` separator line.

**`pairmode_register.py` — `register`, `unregister`, `list-projects` subcommands.**
Manages the `registered_projects` list in flex's own `.companion/state.json`. All three
subcommands are registered in the `pairmode` CLI group via `pairmode_sync.py`.

CLI:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  register --project-dir DIR
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  unregister --project-dir DIR
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  list-projects
```

Behaviour:
- `register`: resolves `--project-dir` to an absolute path, applies `_depth_guard`
  (rejects paths with fewer than 3 components), appends to `registered_projects` if not
  already present; prints "already registered" and exits 0 if duplicate.
- `unregister`: resolves `--project-dir`, removes from list if present; prints "not
  registered" and exits 0 if absent.
- `list-projects`: prints one entry per line; prints "No projects registered." when list
  is empty or absent.
- All writes are atomic: temp file in same directory + `os.replace`.
- Reads and writes flex's own `.companion/state.json` (cwd-relative), not the target
  project's state.json.

### Pairmode non-negotiables

- Template context uses separate keys for brief.md and ideology.md must-preserve content:
  `must_preserve_str` (newline-joined string) for `brief.md.j2`; `must_preserve` (list)
  for `ideology.md.j2`. Do not merge these back into a single key.

- Lessons are append-only. Existing lesson entries may only have their `status` field updated.
- Two optional lesson fields were introduced in Phase 24 (L012) and are not yet supported by
  the `lesson.py` CLI — write them directly when appending:
  - `value_framing` (string) — the durable metric framing for efficiency-based lessons (e.g.,
    the efficiency ratio formula). Captures the objective that remains stable even as model
    prices and capabilities change.
  - `validation_phase` (string) — the phase ID that confirmed or revised the lesson. Points
    forward from the original lesson to its data-backed validation, enabling traceable
    methodology evolution.
- Templates must render correctly for projects with no prior Flex spec (blank-slate bootstrap).
- The deny list generator must include an inline comment on each generated rule linking it to
  the non-negotiable that produced it.
- Pairmode bootstrap must never overwrite existing project files without explicit user confirmation.
- Pairmode scripts that import sibling modules must either (a) use `sys.path` insertion to add
  the flex repo root at import time, or (b) be invoked with `PYTHONPATH` set to the flex
  repo root. SKILL.md invocations must document the required `PYTHONPATH` prefix.
- Callers of `parse_reconstruction_brief` that pass constraints to `ideology.md.j2` must
  normalize the `{name, rule}` schema returned by the parser to `{name, rule, protects,
  rationale, override_path}` before rendering. `bootstrap.py`'s `--from-reconstruction`
  branch does this; any new caller must replicate it. `parse_reconstruction_brief`
  intentionally returns the slim schema because the reconstruction brief does not capture
  those fields.

### Auth policy integration

Before any auth-gated story (authentication, session handling, permission checks,
access-controlled resources) is built, the orchestrator must answer the auth model
classification question from `~/.claude/policies/auth-coexistence.md`.

**Policy files** — three files live at `~/.claude/policies/`:
- `auth-rbac.md` — role-based system controls (admin panels, org-level content)
- `auth-abac.md` — ownership and content-level access (user-authored content, shared workspaces)
- `auth-coexistence.md` — classification question + coexistence patterns (when both apply)

**Build loop integration:** A dedicated per-story auth check section between "Model evaluation" and "Step 1 — Spawn the builder" in `CLAUDE.build.md` gates every auth-gated story on an answered classification question, regardless of where it falls in the phase. The answer (RBAC / ABAC / both) must be recorded in the phase doc or `docs/architecture.md` before building that story.

**Optional spec review step (§ 0):** Before the first story in a phase, `CLAUDE.build.md` includes an optional "Spec review" step that spawns a `general-purpose` subagent to cold-eyes review the full phase spec against the actual codebase (catching mismatched signatures, missing imports, wrong call-site arguments, and references to non-existent symbols) before any builder time is spent. Recommended for phases with 3+ stories; skip for single-story hotfix or documentation-only phases.

**Pairmode equivalent of `spec.json non-negotiables`:** The policy files use
`spec.json non-negotiables` language. In pairmode-based projects (which use story files
+ `architecture.md` rather than a `spec.json`), the equivalent is a dedicated
`## Auth model` or `## Non-negotiables` section in `architecture.md` or the phase doc
that names: (a) the chosen auth model (RBAC / ABAC / both), (b) the enforcement layer
module, and (c) which resource types map to which model (for coexistence cases). This
section serves as the spec contract that reviewers check before accepting any auth-gated
story.

---

## Companion data files

`.companion/product.json` contains a `config` key pointing to an external config file path.
That config file contains `spec_location` — the path to the project's openspec directory.

`spec_reader.read_project_spec(companion_dir)` follows this two-hop path automatically:
1. Read `product.json["config"]` → path to external config file
2. Read `config["spec_location"]` → openspec root directory
3. Glob `<spec_location>/openspec/specs/*/spec.json` → all module specs

Returns `None` if `product.json` is missing or has no `config` key. Returns a dict with
`modules` (list of spec dicts) and `spec_location` (Path) if found.

`.companion/state.json` is written by the companion skill on every session start. Schema:

```json
{
  "pairmode_version": "1.0",
  "last_loaded_modules": ["module-name"],
  "current_story": {
    "id": "2.3",
    "title": "optional title",
    "set_at": "2026-04-20T00:00:00+00:00"
  },
  "registered_projects": [
    "/absolute/path/to/project-a",
    "/absolute/path/to/project-b"
  ]
}
```

Fields:
- `pairmode_version` — set by `/flex:pairmode bootstrap`; the methodology version used
  to scaffold the project. Read by `/flex:pairmode audit` to compute the delta.
- `last_loaded_modules` — updated on every companion session start; lists the module names
  the user chose to load for that session.
- `current_story` — **optional**; present only when pairmode is active and the user
  confirmed which story they are working on. Contains `id` (required), optional `title`,
  and `set_at` (UTC ISO-8601 timestamp). Absent when the user skips the prompt.
- `context_current_tokens` — **optional**; integer; written by `flex_build.py set-context-tokens --tokens N`
  after the orchestrator calls `/context`. Read by `context_budget.py` via
  `read_context_tokens_from_state()`. When absent, `context_budget.decide()` blocks Task spawns
  with a `CONTEXT CHECK REQUIRED` prompt. Cleared implicitly on `/clear` (new session starts
  without the key; the orchestrator must re-run `set-context-tokens` on the first Context gate).
  Never written by the companion sidebar or hook.
- `registered_projects` — **optional**; list of absolute paths to pairmode-scaffolded
  projects to include in cross-project drift detection. When present and non-empty,
  `/flex:pairmode review` runs `pairmode_drift_report --convergent` across all listed
  projects and surfaces convergence candidates for promotion to canonical templates.
  Not set by `bootstrap.py` — opt-in only. Each path is validated with `_depth_guard`
  before use (paths with fewer than 3 components are rejected).
  The canonical management path for this list is the `pairmode register` / `unregister` /
  `list-projects` subcommands (INFRA-070); hand-editing `state.json` is discouraged.
  The key is created on first `register` call when absent; it is never written by
  `bootstrap.py`. Each entry is a resolved absolute path string.

`.companion/attempt_counter.json` is an ephemeral single-record file written by
`flex_build.py write-attempt-count` and read by `flex_build.py read-attempt-count`.
Schema: `{"story_id": "RAIL-NNN", "attempt_count": N}`. It stores the current attempt
number for the active story so a `/clear` mid-phase does not reset the counter. Cleared
by `flex_build.py clear-attempt-count` on reviewer PASS. Covered by the `.companion/`
`.gitignore` rule — never committed.

Pairmode is considered active when `.claude/settings.deny-rationale.json` exists in the
project root. The helper `skills/pairmode/scripts/story_context.py` provides:
- `is_pairmode_active(project_dir)` — returns True when the deny-rationale file is present.
- `set_current_story(companion_dir, story_id, title=None)` — writes the `current_story`
  entry and returns the updated state dict.
- `get_current_story(companion_dir)` — returns the `current_story` dict or None.
- `clear_current_story(companion_dir)` — removes `current_story` from state.json.
- `read_state(companion_dir)` / `write_state(companion_dir, state)` — low-level helpers.

---

## Hook architecture

**Non-negotiable: hooks are thin relays.**

Hooks must:
- Write a JSON message to `/tmp/companion.pipe` (or the project-scoped pipe path from `state.json["pipe_path"]`)
- Exit in milliseconds
- Never make API calls
- Never write to spec files directly

**Documented exception — `hooks/pre_tool_use.py` (dual thin-delegate):**
`pre_tool_use.py` dispatches to two modules:

- **`Task` → `context_budget.py` (CER-027, CER-039):** decides whether to block a new
  subagent spawn based on `state["context_current_tokens"]` (written by
  `flex_build.py set-context-tokens`). Blocks with `CONTEXT CHECK REQUIRED` when
  the key is absent. Writes `context_budget_acknowledged_at` to
  `.companion/state.json`. Does not write to the pipe.
- **`Edit`/`Write` → `scope_guard.py` (Phase 55):** decides whether to block
  a file write based on the active story's declared `primary_files`/`touches`.
  Read-only; no state writes. Fails open when state or permissions file absent.

All decision logic lives in the named modules; the hook is a thin dispatcher.

The sidebar does all heavy work asynchronously. If the sidebar is not running, the pipe write
silently fails and the session continues normally — no data is lost because the session
transcript is always available for later mining.
See `docs/pipe-architecture.md` for the project-scoped pipe design, its backwards-compatibility guarantee, and what changed relative to the original single-pipe design.

**Protected-file classification** belongs in the sidebar, not in the hook.
The sidebar loads `.claude/settings.deny-rationale.json` lazily on first use (cached
per `cwd` for the lifetime of the sidebar process) and calls `_check_protected()` when
processing each `file_changed` event. The hook emits only `path` and `tool` — no
deny-rationale reads occur in the hook.

`spec_exception` pipe messages are produced by the sidebar's override prompt (when a developer provides a reason for overriding a protected file) and handled by the sidebar's pipe reader to write conflict records to the module's `spec.json`. The pipe message payload fields used by the handler: `type` (`"spec_exception"`), `path` (overridden file path), `non_negotiable` (the rule violated), `override_reason` (developer-supplied justification), `session_id` (Claude Code session identifier).

---

## Effort tracking

Effort tracking is the per-attempt record of how much compute each builder and
reviewer spawn consumed. It exists to make the cost of the build loop legible
without coupling that legibility to a specific pricing regime.

**Data model.** A single SQLite database lives at `.companion/effort.db` with
one `attempts` table. Each row captures one agent spawn: `story_id`, `phase`,
`rail`, `agent_role` (`builder` or `reviewer`), `model`, `attempt_number`,
`tokens_total`, `tool_uses`, `duration_ms`, optional `outcome` (`PASS`/`FAIL`
for reviewer attempts), optional `backend` (`"anthropic"` or `"ollama"` —
populated by sidebar cross-skill recording; NULL for pairmode loop rows from
older builds), and a UTC timestamp. Pricing is intentionally absent
from the schema: dollar projections are computed at read time from a
user-maintained `pricing.json`, never persisted.

**Tokens as the primary metric.** Tokens are the unit of compute effort the
build loop actually spends. Dollars are an ephemeral projection through the
current pricing table; if a model's price changes tomorrow, the historical
record must not silently revalue past attempts. Recording tokens (and the model
that consumed them) keeps the historical record stable and lets cost analysis
re-run against any pricing snapshot the user chooses.

**`record_attempt.py --story-file` (recommended invocation for builder calls).** Pass
`--story-file docs/stories/RAIL/RAIL-NNN.md` to auto-fill `--story-id`, `--phase`,
`--rail`, and `--story-class` from the story file's YAML frontmatter. Explicitly-passed
flags still take precedence over auto-filled values. This eliminates the manual
transcription of phase/rail/story-class literals from the story file, closing the typo
surface that CER-015 identified. When `--story-file` is used and the frontmatter has no
`story_class` field, `story_class` defaults to `"code"` (consistent with the rest of the
toolchain). A missing or unparseable story file exits non-zero with a clear error.

**Enabling and disabling.** A one-line toggle in `.companion/state.json`:

```json
{ "effort_tracking": true }
```

Bootstrap auto-enables this for pairmode projects. `record_attempt.py` reads
the flag on every invocation and silently no-ops when it is absent or false,
so the orchestrator's recording steps are safe to run unconditionally.

**What it captures (Phase 22 scope).** Every builder spawn and every reviewer
spawn the orchestrator initiates during the build loop. Future phases will
extend the capture surface to seed and companion sessions; the schema and
toggle are designed to absorb that without migration.

**Cross-skill recording.** Seed and companion record their own LLM-call
effort via in-process wrappers (not orchestrator tool calls), since both
skills set `disable-model-invocation: true` and cannot be invoked as
subagents from the build orchestrator. The wrappers live inside each
skill's Python code (`mine_sessions.py`, `reconcile.py`, `sidebar.py`) and
call the same `effort_recorder` helper as `record_attempt.py`. Synthetic
`story_id` values (`seed:<session-id>`, `seed:reconcile`,
`sidebar:<story-id-or-no-story>`) distinguish cross-skill rows from
pairmode loop rows. `agent_role` values used by these wrappers:
`seed-miner`, `seed-reconcile`, `sidebar-extractor`. `phase` and `rail`
are left NULL for cross-skill rows because seed and sidebar work happens
outside the phases/rails model. The `backend` column (`"anthropic"` or
`"ollama"`) distinguishes the call path on sidebar rows.

**How to use it.** `pairmode_effort.py` provides five read-time views over the
recorded attempts:

- `pairmode_effort.py rollup` — totals by phase, rail, model
- `pairmode_effort.py rework` — stories with attempt_number > 1 (what cost us a retry)
- `pairmode_effort.py expensive` — top N attempts by tokens
- `pairmode_effort.py models` — breakdown by model
- `pairmode_effort.py validate-rebalance` — evidence report for the
  sonnet-baseline-opus-on-demand methodology; see below.

These are retrospective views. Future phases will add a real-time guardrail
that surfaces effort overruns mid-loop rather than only after the fact.

**`validate-rebalance` recommendation logic.** For each
`(story_class, agent_role, model)` cell in the DB the report computes:
sample size, PASS count, PASS rate, and median tokens. It then applies
this decision table (thresholds configurable via CLI flags or
`state["effort_validation_thresholds"]`):

| condition | recommendation |
|-----------|---------------|
| sample size < 5 | "insufficient data" |
| PASS rate ≥ 95 % | "rebalance confirmed for this cell" |
| PASS rate < 80 % | "consider upgrading this cell to opus" |
| sonnet PASS rate ≥ opus PASS rate AND sonnet median tokens < opus median | "consider further downgrade" |
| otherwise | "monitor — insufficient evidence" |

Configurable threshold keys under `state["effort_validation_thresholds"]`:
`min_sample` (int, default 5), `pass_rate_confirmed` (float 0–1, default 0.95),
`pass_rate_upgrade` (float 0–1, default 0.80), `token_ratio_limit` (float,
default 1.5).

**Decision-quality section (requires INFRA-050 data).** A second section of the
`validate-rebalance` report surfaces model-selection decision quality. For each
`model_selection_reason` value (`auto-downgrade`, `auto-baseline`,
`prompted-upgrade`, `user-override`) the report shows: frequency count and
percentage of total stories, PASS-on-first-attempt rate per path, average cost
per path (tokens × pricing), and an efficiency ratio defined as:

```
efficiency_ratio = (pass_rate / avg_cost) / (baseline_pass_rate / baseline_avg_cost)
```

where the `auto-baseline` path is the normalisation reference (ratio = 1.0).
A ratio > 1.0 means the path delivers more PASS-rate per dollar than the baseline.
The section is omitted when the `model_selection_reason` column is absent from
the DB (pre-INFRA-050 builds). The report surfaces evidence only — it does NOT
auto-update model selection. Methodology changes still require story specs.

**Real-time guardrail.** After each builder attempt, the orchestrator calls
`effort_db.check_guardrail()` with the rail and the just-completed attempt's
token count. The function queries the rail's median tokens-per-attempt across
recent PASS-outcome builder rows and compares the latest attempt against
`multiplier × median`. If the latest attempt exceeds that threshold, the
orchestrator surfaces a structured stderr warning before spawning the reviewer.
The guardrail is informational (exit 0), not blocking — the orchestrator
decides whether to pause and consult the user based on the warning text. The
default multiplier is `3.0`, configurable via
`state["effort_guardrail_multiplier"]`. Insufficient sample (< 3 PASS-outcome
builder rows for the rail within the lookback window) returns early without
firing, so new rails do not generate false positives.

**Context health check.** At checkpoint, the orchestrator calls
`skills/pairmode/scripts/context_health.check_context_health(db_path, current_phase)`
to produce a per-phase retry burden signal. The function sums output tokens from
FAIL-outcome reviewer rows in the current phase, compares against a rolling
per-phase median (using `COALESCE(tokens_out, CAST(tokens_total * 0.15 AS INTEGER))`
to handle the NULL `tokens_out` column in current records), and returns one of:
`normal`, `elevated`, `high`, or `insufficient_data` (when fewer than 3 prior
phases have been recorded). The signal is informational only — it never blocks the
checkpoint. The result `message` field is written to the step 8 checkpoint report.
The module exposes three public functions: `phase_retry_burden`, `rolling_phase_median`,
`check_context_health`. All three are safe when the DB does not exist.

### Drift evidence scoring

`skills/pairmode/scripts/drift_evidence.py` provides token-efficiency evidence
for convergence candidates surfaced by `pairmode_drift_report.py --convergent`.

**Function:** `score_convergence_candidate(project_dirs, pattern_id) -> (score, justification)`

- Queries each project's `effort.db` for all `agent_role='builder'` rows with
  non-null, non-zero `tokens_total`.
- Returns `(None, "insufficient data")` when fewer than 5 total builder attempts
  are found across all projects (sample too small for meaningful comparison).
- When sufficient data is available, computes a normalised score in `[0.0, 1.0]`:
  - **score > 0.5** — pattern-associated projects show lower median builder tokens.
  - **score = 0.5** — no observable difference.
  - **score < 0.5** — pattern-associated projects show higher median builder tokens.
- Returns a one-line `justification` string (e.g. "Projects with this pattern show
  ~12% lower median builder tokens (n=18 attempts across 3 project(s))").

**Scoring methodology:** Pattern-associated projects are identified using `pattern_id`
as a substring of the project path (coarse proxy). When no projects match this
heuristic, the function falls back to comparing the lower-token half of projects
against the upper half. The score is computed as:

```
score = 1.0 - (pattern_median / (pattern_median + other_median))
```

**Known limits (document inline — do not treat score as ground truth):**
- Small samples (5–20 attempts) produce noisy estimates.
- Confounding factors: story complexity, model choice, and retry count all affect
  token costs independently of any pattern.
- The pattern-proxy (substring match on project path) is coarse; a more accurate
  signal would require explicit tagging of attempts with the candidate pattern.
- Correlation only — lower tokens for pattern-associated projects may reflect
  pre-existing simplicity of those projects rather than an effect of the pattern.

The score is surfaced as an annotation above each promotion prompt in
`lesson_review.py`'s `run_drift_promotion`. It is advisory only — the developer
makes the final promotion decision.

---

## Layer rules for this codebase

| Layer | May import from | May not import from |
|-------|----------------|---------------------|
| hooks/ | stdlib, no flex modules | skills/, lessons/ |
| skills/*/scripts/ | stdlib, requirements.txt deps | hooks/ (sibling skills ok for shared utils) |
| tests/ | anything | — |

Hooks must never import from skills. Skills may not call hooks directly. Both communicate
only via the pipe.

The companion sidebar (`skills/companion/scripts/sidebar.py`) imports
`record_spec_exception` from `skills/pairmode/scripts/spec_exception.py`.
This cross-skill dependency is intentional and permitted under the "sibling skills ok
for shared utils" rule. It must be preserved when either module is modified.


---

## Phase documentation policy

Each phase gets its own file: `docs/phases/phase-N.md` (integer ID) or
`docs/phases/phase-PM025-main.md` (string predicate + suffix).

**Phase naming suffixes** — Projects that need to insert remediation or preflight phases
without breaking disk sort order can use suffix variants:
- `-ante[N]` — preflight prerequisite (sorts before `-main`; must complete first)
- `-main` — the primary phase
- `-post[N]` — follow-on remediation (sorts after `-main`; must complete before next)
- `-sec` — security prerequisite (same semantics as `-ante`, conventional security label)

Alphabetical order mirrors build order: `ante < main < post`. Checkpoint tags follow the
same naming: `cp-PM025-main`, `cp-PM025-post1`, etc. See `skills/pairmode/SKILL.md`
§ `/flex:pairmode phase-new` for the full suffix table and CLI flags.

**Proposed phases** — A phase conceived before it is literally the next build target uses
a proposed filename: `docs/phases/phase-proposed-<kebab-name>-YYYYMMDD-NNN.md`. Proposed
phases do not appear in the main phase table in `docs/phases/index.md`; they appear under
a `## Proposed phases (not yet sequenced)` section. When sequenced, stories are absorbed
into the next available sequential phase, the proposed file is deleted via `git rm`, and
the row is removed from the index. See `CLAUDE.build.md` § Proposed phases for the full
sequencing workflow.

- New phases are always created using `phase_new.py --phase-id ID [--suffix SUFFIX]`.
  Integer IDs produce `phase-N.md`; string predicates with suffixes produce
  `phase-PM025-main.md`.
- The monolithic `docs/phase-prompts.md` is the legacy format for Phases 1–7 (flex repo only).
  It is not extended with new phase content going forward.
- `docs/phases/index.md` is the canonical list of all phases and their status.
- Phase files are the source of truth for the builder/reviewer loop. The orchestrator reads
  only the current phase file — not the entire monolithic doc.
- When reviewing or building, read only the current phase file. This keeps token usage
  proportional to phase scope, not project history.

New projects bootstrapped after Phase 7 never receive `docs/phase-prompts.md`.
Existing projects using the monolithic format migrate incrementally: each new phase
becomes its own file; old phases stay in the monolithic doc as a historical record.


---

## Documentation currency policy

README.md and relevant docs are updated at every phase checkpoint — not as an afterthought,
but as a required checkpoint step before tagging.

**What must stay current:**
- `README.md` — feature list, status, usage/CLI examples, known limitations. If a phase adds
  or changes a user-facing capability, README reflects it before the checkpoint tag is applied.
- `docs/architecture.md` — updated by the intent-reviewer at each checkpoint (existing process).
- `docs/brief.md` — updated when project goals or constraints change.
- Any `docs/` file explicitly referenced in the phase spec.

**What is exempt:**
- Internal implementation notes that live in code comments or commit messages.
- Phase spec files themselves (`docs/phases/phase-N.md`) — these are maintained by the build
  process, not documentation to be polished.

**Enforcement:** The checkpoint sequence in `CLAUDE.build.md` includes a documentation review
step before tagging. The reviewer subagent checks that README reflects the phase's shipped
capabilities. A checkpoint with a stale README is not complete.

**Phase completion gate (CLAUDE.build.md Step 5):** A phase cannot be checkpointed with
silently abandoned `planned` stories. Before tagging, all `planned` stories in the phase
manifest must be either `complete` or formally deferred — added to a `## Deferred stories`
section in the phase doc with a one-line reason and status updated to `deferred`. The
checkpoint sequence enforces this as Step 5 between Documentation review and CER backlog
review. A forked phase (one interrupted by a pivot) documents its deferred stories at fork
time; the resuming phase references the origin in a `**Parent phase:**` header line.

**Scope guidance:** Updates should be proportional. A phase that adds a new CLI flag needs one
line in README. A phase that adds a new workflow needs a paragraph. A phase that only fixes
internal bugs needs only a "version/status" line if anything.

---

## Build commands

```bash
# Run tests (pairmode unit tests only — not integration tests in tests/)
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q

# Run all tests
PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q

# Lint
PATH=$HOME/.local/bin:$PATH uv run ruff check skills/pairmode/scripts/ tests/pairmode/
```

---

## Protected files

These files are working and must not be modified without a stated reason:

- `hooks/` — all existing hook scripts and hooks.json
- `skills/seed/scripts/` — all seed scripts
- `skills/companion/scripts/sidebar.py` — companion sidebar
- `.claude-plugin/plugin.json` — plugin manifest
- `.claude-plugin/marketplace.json` — marketplace config
- `lessons/lessons.json` — append-only lessons store (once created in Phase 3)

# Anchor — Architecture

## What anchor is

Anchor is a Claude Code plugin. It gives Claude Code a persistent memory of architectural decisions,
specs, and constraints across sessions. It captures what you're building and why — automatically,
as you work — and makes that intent persistent across every agent, every session, every project.

This document is the source of truth for the anchor codebase itself. Read it before any task.

---

## Module structure

```
anchor/
  hooks/                          ← thin relays to the sidebar (no API calls)
    hooks.json                    ← hook event registration
    stop.py                       ← historian: extract decisions after each response
    exit_plan_mode.py             ← relay plan content for impact analysis
    post_tool_use.py              ← pair partner: relay file changes
    session_end.py                ← signal sidebar to summarize and exit

  skills/
    seed/                         ← /anchor:seed — bootstrap canonical spec (run once)
      SKILL.md
      scripts/
        setup.py                  ← product config writer
        mine_sessions.py          ← transcript decision extractor
        reconcile.py              ← spec merger
    companion/                    ← /anchor:companion — start each session
      SKILL.md
      scripts/
        sidebar.py                ← companion sidebar process (long-running)
        start_sidebar.sh          ← detects OS, opens sidebar in new terminal
        launch_sidebar.command    ← macOS launcher
        launch_sidebar.sh         ← Linux launcher
    pairmode/                     ← /anchor:pairmode — bootstrap and manage pairmode
      SKILL.md
      scripts/
        bootstrap.py              ← generate pairmode scaffold from spec
        audit.py                  ← diff project against canonical templates
        sync.py                   ← apply delta from audit non-destructively
        lesson.py                 ← capture a lesson learned
        lesson_review.py          ← surface lessons, propose template updates
        story_context.py          ← read/write current story in state.json; pairmode detection
        spec_exception.py         ← record protected-file overrides into spec.json conflicts
      templates/                  ← Jinja2 templates for scaffold generation
        CLAUDE.md.j2
        CLAUDE.build.md.j2
        agents/
          builder.md.j2
          reviewer.md.j2
          loop-breaker.md.j2
          security-auditor.md.j2
          intent-reviewer.md.j2
        docs/
          architecture.md.j2
          phase-prompts.md.j2
          checkpoints.md.j2

  lessons/
    lessons.json                  ← global methodology lessons (lives in anchor repo)
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
sidebar.py reads pipe → calls Claude API → extracts decisions
    ↓
persist_capture() → .companion/changes/<session-id>/incremental.json
    ↓
session ends → sidebar shows summary, exits
    ↓
next /anchor:companion → detects unreconciled sessions → reconcile.py
    ↓
reconcile.py → merges into <spec_location>/openspec/specs/<module>/spec.json
```

```
post_tool_use.py → pipe → sidebar tracks file→module mapping
exit_plan_mode.py → pipe → sidebar analyzes plan for cross-module impact
session_end.py → pipe → sidebar graceful shutdown signal
```

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
  }
}
```

Fields:
- `pairmode_version` — set by `/anchor:pairmode bootstrap`; the methodology version used
  to scaffold the project. Read by `/anchor:pairmode audit` to compute the delta.
- `last_loaded_modules` — updated on every companion session start; lists the module names
  the user chose to load for that session.
- `current_story` — **optional**; present only when pairmode is active and the user
  confirmed which story they are working on. Contains `id` (required), optional `title`,
  and `set_at` (UTC ISO-8601 timestamp). Absent when the user skips the prompt.

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
- Write a JSON message to `/tmp/companion.pipe`
- Exit in milliseconds
- Never make API calls
- Never write to spec files directly

The sidebar does all heavy work asynchronously. If the sidebar is not running, the pipe write
silently fails and the session continues normally — no data is lost because the session
transcript is always available for later mining.

**Protected-file classification** belongs in the sidebar, not in the hook.
The sidebar loads `.claude/settings.deny-rationale.json` lazily on first use (cached
per `cwd` for the lifetime of the sidebar process) and calls `_check_protected()` when
processing each `file_changed` event. The hook emits only `path` and `tool` — no
deny-rationale reads occur in the hook.

---

## Pairmode design

Pairmode is a feature being built in this repo. It establishes a structured builder/reviewer
workflow on top of any project that uses anchor. See the spec discussion in git history.

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

**Lessons:** Methodology improvements are captured in `anchor/lessons/lessons.json`.
Each lesson records the triggering situation, what was learned, what changed in the methodology,
and which projects it applies to. Lessons flow into templates via `/anchor:pairmode review`.

**Template versioning:** Each pairmode-bootstrapped project records the `pairmode_version`
it was bootstrapped with in `.companion/state.json`. `/anchor:pairmode audit` uses this to
determine the delta between the project's methodology and the current canonical version.
Audit compares section headers (structural presence of `##` headings) between project files
and raw Jinja2 template source — it does not render templates before comparison. Section
bodies in canonical templates contain Jinja2 variable expressions (`{{ project_name }}`
etc.); body-level content comparison should not be relied upon for semantic drift detection.

### Pairmode non-negotiables

- Lessons are append-only. Existing lesson entries may only have their `status` field updated.
- Templates must render correctly for projects with no prior Anchor spec (blank-slate bootstrap).
- The deny list generator must include an inline comment on each generated rule linking it to
  the non-negotiable that produced it.
- Pairmode bootstrap must never overwrite existing project files without explicit user confirmation.
- Pairmode scripts that import sibling modules must either (a) use `sys.path` insertion to add
  the anchor repo root at import time, or (b) be invoked with `PYTHONPATH` set to the anchor
  repo root. SKILL.md invocations must document the required `PYTHONPATH` prefix.

---

## Layer rules for this codebase

| Layer | May import from | May not import from |
|-------|----------------|---------------------|
| hooks/ | stdlib, no anchor modules | skills/, lessons/ |
| skills/*/scripts/ | stdlib, requirements.txt deps | hooks/ (sibling skills ok for shared utils) |
| tests/ | anything | — |

Hooks must never import from skills. Skills may not call hooks directly. Both communicate
only via the pipe.

The companion sidebar (`skills/companion/scripts/sidebar.py`) imports
`record_spec_exception` from `skills/pairmode/scripts/spec_exception.py`.
This cross-skill dependency is intentional and permitted under the "sibling skills ok
for shared utils" rule. It must be preserved when either module is modified.

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

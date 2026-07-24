---
id: INFRA-247
rail: INFRA
title: Single canonical hook registration for flex itself — dedupe plugin manifest vs settings.json, eliminate cross-checkout /mnt/work/flex-harness absolute paths
status: planned
phase: "99"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - .claude/settings.json
touches:
  - hooks/hooks.json
  - docs/architecture.md
---

## Context

flex currently registers its pairmode hooks **twice**, through two independent
mechanisms that both fire every session:

1. **Plugin manifest** — `hooks/hooks.json` registers Stop, PermissionRequest,
   PreToolUse (Task|Agent, Edit|Write, Read), PostToolUse (Write|Edit|MultiEdit,
   Task|Agent), SessionEnd, SessionStart, and UserPromptSubmit via
   `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py`.
2. **Project settings** — `.claude/settings.json` registers PreToolUse
   (Task|Agent|Edit|Write|Read), PostToolUse (Task|Agent), UserPromptSubmit,
   and SessionStart via `uv run python /mnt/work/flex-harness/hooks/<name>.py`.

The settings.json block was added by INFRA-233 ("Register context-budget-gate
hooks in flex-harness's own settings.json — never dogfooded on itself") while
the working copy lived at `/mnt/work/flex-harness` on the `fold-prep` branch.
The RELEASE-059 fold brought that settings.json into `/mnt/work/flex` main
verbatim, producing two defects:

- **Duplicate execution.** Every session-start banner prints twice, every
  user prompt runs `user_prompt_submit.py` twice, and every Task/Agent spawn
  runs the pre/post hooks twice. Beyond noise, the duplicated
  UserPromptSubmit is a suspected source of context-counter double-increment
  (audited separately in INFRA-248).
- **Cross-checkout dependency.** The settings.json commands reference
  absolute paths under `/mnt/work/flex-harness`, a *separate checkout*
  currently parked on `fold-prep`. The hook sources are byte-identical today,
  but nothing keeps them so: if fold-prep drifts or the checkout is deleted,
  flex's own gates break or silently enforce stale logic.

Note: INFRA-228 ("Match hook blocks by basename not full path") fixed
duplicate detection inside `sync.py`'s hook-registration writer for
*downstream* projects. It does not deduplicate a plugin-manifest registration
against a settings.json registration in flex itself — that overlap is
platform-level (Claude Code merges plugin hooks and project hooks), so the
fix is to stop registering twice, not to improve matching.

## Requires

- Determine which registration surface is canonical for flex itself, and
  record the decision with rationale in `docs/architecture.md`. Inputs the
  builder must weigh:
  - The plugin manifest only fires when flex is installed/enabled as a plugin
    in this session; the settings.json block fires for any Claude Code
    session in this directory. Verify which mechanisms are actually active in
    this repo's sessions (the doubled banner proves both currently are).
  - INFRA-233's intent (dogfooding the context-budget gate on flex itself)
    must survive: whichever surface remains must cover UserPromptSubmit,
    SessionStart, and the PreToolUse/PostToolUse Task|Agent gates.
  - Downstream fleet projects receive settings.json registrations from
    `bootstrap.py`/`sync.py`; flex keeping a settings.json block that matches
    the fleet pattern (but locally-pathed) is acceptable, as is relying on
    the plugin manifest alone — the requirement is exactly one active
    registration per hook event.
- INFRA-248 builds after this story and depends on the dedupe landing first.

## Ensures

1. Each hook event (SessionStart, UserPromptSubmit, PreToolUse matchers,
   PostToolUse matchers, Stop, SessionEnd, PermissionRequest) is registered
   through **exactly one** active mechanism in this repo. No event fires
   twice in a fresh session.
2. No hook command in `.claude/settings.json` (or any other file in this
   repo) references `/mnt/work/flex-harness`. Any retained settings.json
   commands resolve within this checkout (relative path,
   `$CLAUDE_PROJECT_DIR`, or equivalent — not a hardcoded sibling absolute
   path).
3. The context-budget gate remains dogfooded on flex: a Task/Agent spawn of a
   build-cycle subagent still passes through `pre_tool_use.py`'s budget
   gate, and UserPromptSubmit still increments the context counter — exactly
   once per prompt.
4. A fresh session in this repo prints the SessionStart banner exactly once.
5. `docs/architecture.md` records which surface is canonical for flex itself
   and why, including the INFRA-233 dogfooding constraint.
6. Existing pairmode tests pass; if hook-registration shape is covered by
   tests (e.g. settings.json structure assertions), they are updated to the
   deduplicated shape.

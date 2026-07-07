---
id: BUILD-040
rail: BUILD
title: "CLAUDE.build.md: add write-permissions + clear-permissions to build loop"
status: draft
phase: "81"
story_class: doc
primary_files:
  - CLAUDE.build.md
touches:
  - skills/pairmode/templates/CLAUDE.build.md.j2
---

# BUILD-040 — CLAUDE.build.md: add write-permissions + clear-permissions to build loop

## Context

The pairmode permission system has two layers:

**Layer 1 — scope_guard hook enforcement:**
`permissions-create` writes `docs/phases/permissions/<STORY_ID>.json`. The
`pre_tool_use.py` hook calls `scope_guard.check_path()` on every Edit/Write,
which reads this JSON record and blocks writes outside the story's declared
scope. CLAUDE.build.md already calls `permissions-create` in Step 1. This
layer works correctly.

**Layer 2 — Claude Code tool-permission UI:**
`write-permissions` calls `write_story_permissions()` which writes
`Edit(<path>)` / `Write(<path>)` allow rules into `.claude/settings.local.json`
for every file in the story's `primary_files` and `touches`. These rules
suppress the Claude Code permission prompt before the write even reaches the
hook. Without them, the builder is prompted for approval on every file write
despite Layer 1 already enforcing the scope correctly.

CLAUDE.build.md does not call `write-permissions` or `clear-permissions`
anywhere. This is the root cause of the "toggle auto-mode on/off every story"
symptom observed in upstream era-002 projects (e.g. rockue). The SKILL.md
for `/flex:pairmode` already documents the intended behaviour (`write_story_permissions`
before the builder, `clear_story_permissions` after the reviewer) — the
orchestrator instructions just never implemented it.

`settings.local.json` is read at the project level by Claude Code; all
sessions in the project (orchestrator, builder, reviewer) see it. The allow
rules written in the orchestrator's Step 1 are therefore active for the entire
builder subagent session. `clear-permissions` runs in the orchestrator's Step 3
after the reviewer completes, restoring the default deny posture before the
next story starts.

Neither `write-permissions` nor `clear-permissions` writes to a denied path
(`.claude/settings.local.json` is not in any standard project deny list), so
neither call itself generates a permission prompt.

## Acceptance criteria

1. In `CLAUDE.build.md` **Step 1** ("Spawn the builder"), immediately after the
   `permissions-create` call and before `story_context.py --set`, add:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py write-permissions \
     --story-id STORY-ID --project-dir .
   ```

2. In `CLAUDE.build.md` **Step 3** ("Handle the result"), after the
   `story_context.py --clear` call, add:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py clear-permissions \
     --project-dir .
   ```
   This must run regardless of PASS or FAIL outcome (both branches), so
   `settings.local.json` is cleaned up before the next story begins.

3. The surrounding prose in both steps is updated to explain the two-layer
   permission model: `permissions-create` handles hook enforcement;
   `write-permissions` handles Claude Code prompt suppression. A brief inline
   comment in each bash block is sufficient.

4. `skills/pairmode/templates/CLAUDE.build.md.j2` receives identical edits
   in the same locations so future bootstrapped projects inherit the fix.

5. No other behaviour in Step 1 or Step 3 changes. The call order in Step 1
   is: `permissions-create` → `write-permissions` → `story_context.py --set`.
   The call order in Step 3 is: `story_context.py --clear` → `clear-permissions`
   → `story_update.py --status complete` (PASS path) or leave as-is (FAIL path).

## Implementation guidance

- In Step 1, locate the block containing `permissions-create STORY-ID`. The
  `write-permissions` call goes on the next line with the same `--project-dir .`
  convention. Match surrounding indentation and comment style.
- In Step 3, the `story_context.py --clear` call is the first action after
  the reviewer returns. `clear-permissions` goes immediately after it — before
  the PASS/FAIL branch diverges — since cleanup should happen regardless of
  outcome.
- In the template, search for `permissions-create` and `story_context.py --clear`
  to locate the equivalent blocks.

## Tests

Documentation story — no logic module changed, no test file expected. Reviewer
states `TEST RUN: documentation story — no test file expected`.

Manual verification:

```bash
# Confirm write-permissions appears after permissions-create in Step 1
grep -n "write-permissions\|permissions-create" CLAUDE.build.md

# Confirm clear-permissions appears in Step 3
grep -n "clear-permissions" CLAUDE.build.md

# Confirm same in template
grep -n "write-permissions\|permissions-create\|clear-permissions" \
  skills/pairmode/templates/CLAUDE.build.md.j2
```

### Out of scope

- Modifying `permission_scope.py` to include the story spec file in allow
  rules — whether `story_update.py` needs pre-authorization depends on the
  upstream project's deny list, not a general pairmode invariant. Surface
  as a separate finding if confirmed needed.
- Any change to `scope_guard.py` or the JSON-record layer (Layer 1).
- Any change to `permission_scope.py` logic.

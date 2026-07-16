---
id: INFRA-198
rail: INFRA
title: "Stop self-blocking permissions-create — clarify it's not a protected-path write, add orchestrator skip-check"
status: complete
phase: "87"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - docs/stories/INFRA/INFRA-194.md
  - docs/architecture.md
  - .claude/settings.json
touches:
  - skills/pairmode/templates/CLAUDE.build.md.j2
---

# INFRA-198 — Stop self-blocking permissions-create

## Context

Live on story EDGE-001 (pre-Phase-87), the builder refused to run
`flex_build.py permissions-create` via `Bash`, reporting:

> "The permissions-create script ... was blocked by your Claude Code deny
> rules. The classifier flagged running it via Bash as circumvention of an
> explicit Edit/Write deny rule on that path."

Investigation confirmed **no such deny rule exists**. `.claude/settings.json`
and `.claude/settings.local.json` were both read in full — the only
configured deny entries are `skills/companion/**`, `lessons/**`,
`.claude-plugin/**`, `skills/seed/**`. `docs/phases/permissions/**` is also
absent from CLAUDE.md's Protected Files list (checklist item 7).

The block was self-imposed: the model's own permission classifier read
prose in `docs/stories/INFRA/INFRA-194.md:27-29` describing the path as "a
Layer 1 protected path under the orchestrator's auto-mode deny rules," and
`docs/architecture.md:172-177`'s similar "protected-path write and its
associated auto-mode re-authorization" framing — both accurate as *design
intent* (this write should be deliberate, not incidental) but phrased in a
way that a builder/orchestrator agent, reading cold, can mistake for a
machine-enforced deny it must refuse to circumvent via `Bash`.

Separately: `CLAUDE.build.md` invokes `permissions-create` unconditionally
at Step 1 of every build-loop entry (~line 427-430), with no check for
whether the story's `primary_files`/`touches` scope has changed since the
permissions file was last generated. The script itself is idempotent
(Phase 86/INFRA-194 — reads the existing file, no-ops if `allowed_paths` is
unchanged), but every invocation still runs the script via `Bash`, still
carries the same self-block risk, and adds an unnecessary subprocess call
on every story/attempt even when nothing changed.

## Ensures

1. **Prose fix.** `docs/stories/INFRA/INFRA-194.md:27-29` and
   `docs/architecture.md:172-177` no longer describe
   `docs/phases/permissions/**` using language that reads as a
   machine-enforced deny rule ("protected path under ... deny rules",
   "auto-mode re-authorization"). Replace with accurate framing: there is no
   config-level deny rule on this path; `permissions-create` is a trusted,
   idempotent orchestrator script, and invoking it via `Bash` is the
   sanctioned, designed mechanism — not something requiring a policy
   decision or user sign-off to run.

2. **Explicit allow rule.** `.claude/settings.json`'s `permissions.allow`
   list gains an entry (or entries) that pre-approve the `Bash` invocation
   pattern(s) used to run `flex_build.py permissions-create`,
   `write-permissions`, and `clear-permissions` (the exact commands emitted
   in `CLAUDE.build.md`), so these calls are never subject to a runtime
   confirmation prompt in the first place. This is a static, permanent
   config entry — distinct from the story-scoped Layer 2 allow rules that
   `write-permissions`/`clear-permissions` cycle in and out of
   `.claude/settings.local.json` per story.

3. **Orchestrator skip-check.** `CLAUDE.build.md` Step 1 (~line 427) gains an
   explicit instruction: before invoking `permissions-create`, read
   `docs/phases/permissions/<story_id>.json` if it exists (via the `Read`
   tool — no `Bash` call, no permission surface at all) and compare its
   `allowed_paths` against the story's current `primary_files` + `touches`
   frontmatter. If they already match, skip the `permissions-create`
   invocation entirely and proceed straight to `write-permissions`. Only
   invoke `permissions-create` when the file is absent or scope has
   diverged. This is a read-only orchestrator-side check, not a change to
   the script's own idempotency (INFRA-194's in-script no-op logic is
   unchanged and still applies as a fallback if the orchestrator's
   frontmatter comparison and the script's comparison ever disagree).

4. Same instruction (item 3) is mirrored in
   `skills/pairmode/templates/CLAUDE.build.md.j2` so newly bootstrapped
   projects inherit the skip-check, not just this repo's own
   `CLAUDE.build.md`.

5. No change to `cmd_permissions_create`'s own logic in `flex_build.py` —
   INFRA-194's read-then-maybe-write behavior is out of scope here and
   remains the safety net.

6. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes
   (no test regressions; this story is prose + config + orchestrator
   instructions, no new script logic to unit test).

## Instructions

- Edit `docs/stories/INFRA/INFRA-194.md` lines 27-29: replace "a Layer 1
  protected path under the orchestrator's auto-mode deny rules (documented
  in `CLAUDE.build.md`'s two-layer permission model...)" with prose stating
  plainly there is no config-level deny rule on this path, and that
  `permissions-create` is a sanctioned, idempotent script invocation.
- Edit `docs/architecture.md` lines 172-177 similarly — keep the factual
  description of what Layer 1 does, drop/reword "protected-path write and
  its associated auto-mode re-authorization" so it doesn't read as a
  requires-approval gate.
- Add to `.claude/settings.json` `permissions.allow`: entries matching the
  literal command patterns `CLAUDE.build.md` already emits for
  `permissions-create`, `write-permissions`, and `clear-permissions` (check
  the exact `Bash(...)` pattern syntax Claude Code expects — likely a
  prefix match on the `uv run python .../flex_build.py <subcommand>` form;
  verify against how the existing `"Bash(python *)"` / `"Bash(git *)"`
  entries are matched before assuming exact syntax).
- Add the skip-check instruction to `CLAUDE.build.md` Step 1, immediately
  before the existing `permissions-create` bash block (~line 427), and
  mirror it in `skills/pairmode/templates/CLAUDE.build.md.j2` at the
  equivalent step.
- Do not touch `flex_build.py`, `permission_scope.py`, or any test file —
  this story is prose, config, and orchestrator-instruction changes only.

## Tests

No new test file — `story_class: doc`. Run the full gate to confirm no
regression:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Any change to `cmd_permissions_create`'s internal idempotency logic
  (INFRA-194, already correct).
- A general audit of every prose passage across the repo that might be
  similarly over-read as a deny rule by a builder/orchestrator agent — this
  story fixes the two passages confirmed to have caused an actual block.
- Removing or relaxing the Layer 1/Layer 2 permission model's actual
  purpose (scope enforcement) — only the misleading "deny rule" framing and
  the unnecessary re-invocation are addressed.

---
id: INFRA-253
rail: INFRA
title: Close scope_guard fail-open hole for protected paths; retire redundant settings.json denies; resolve CER-048
status: planned
phase: "100"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/scope_guard.py
touches:
  - tests/pairmode/test_scope_guard.py
  - docs/cer/backlog.md
  - docs/architecture.md
  - .claude/settings.json
---

## Context

CER-048's fix direction (story-aware fail-closed protection replacing static
settings.json denies) largely shipped in v0.3: `scope_guard.py` has
`PROTECTED_GLOBS` blocked even with no active story, satisfiable only via an
active story whose permissions artifact names the path. A post-cp99 audit
(2026-07-24) found three residues:

1. **Fail-open hole (HIGH):** `scope_guard.check_path()`'s active-story branch
   returns allow when the permissions file is missing, empty, or malformed —
   without checking `_is_protected()`. Only the no-story branch checks it. An
   active story whose `permissions-create` never ran leaves `hooks/**` etc.
   wide open for the duration of the build.
2. **Redundant denies (MEDIUM):** flex's own `.claude/settings.json` still
   carries four `Edit()` denies duplicating `PROTECTED_GLOBS`
   (`skills/companion/**`, `lessons/**`, `.claude-plugin/**`, `skills/seed/**`)
   — the drift-prone duplicate surface CER-048 named. `hooks/**` is already
   retired from it. `Edit(docs/phases/permissions/**)` stays (matches
   `DEFAULT_DENY`; anti-self-scope-modification, deliberately outside the
   story-satisfiable gate).
3. **Stale CER row (MEDIUM):** CER-048 still reads fully open, cites
   `Edit/Write(hooks/**)` denies that no longer exist, and does not record
   that the remaining INFRA-247-class friction (writes to
   `.claude/settings.json` itself) comes from Claude Code's auto-mode
   classifier — harness-level, above project hooks, not curable by
   scope_guard.

Operator intent (stated 2026-07-24): settings.json should carry tooling only;
per-story authorization flows spec `touches` → `permissions-create` →
permissions artifact → scope_guard, with the reviewer checking compliance and
the orchestrator expanding scope for oversights. Normal build cycles must not
require writes to `.claude/settings.json` or `.claude/settings.local.json`.

## Ensures

1. `scope_guard.check_path()` checks `_is_protected()` in the active-story
   branch before every fail-open early return (permissions file missing,
   empty, or unreadable/malformed): a protected path is denied with a reason
   naming the missing/empty permissions artifact; non-protected paths retain
   existing fail-open behavior unchanged.
2. A protected path explicitly present in a story's `allowed_paths` remains
   allowed (existing behavior, regression-tested).
3. `tests/pairmode/test_scope_guard.py` covers: protected+no-permissions-file
   → deny; protected+empty-allowed-paths → deny; protected+malformed-json →
   deny; non-protected+no-permissions-file → allow; protected+declared →
   allow.
4. The deny messages' wording no longer claims `primary_files` is the sole
   authorization surface (the permissions artifact derives from
   `primary_files` + `touches`).
5. `.claude/settings.json` retains only: the PostToolUse pytest hook, the
   Bash allow rules, `Edit(.claude/agents/**)` allow, and the single
   `Edit(docs/phases/permissions/**)` deny — the four `PROTECTED_GLOBS`
   -duplicate denies removed. This edit is operator-applied (auto-mode
   classifier blocks all agent writes to this file — INFRA-247 precedent);
   the builder verifies the resulting file read-only and documents the
   verification in Build notes. If the operator edit has not landed when the
   builder runs, the builder reports the exact JSON to apply and stops, per
   the Ensures-fallback pattern.
6. `docs/cer/backlog.md` CER-048 row gains a resolution note: fix direction
   shipped in v0.3 (`PROTECTED_GLOBS` story-aware gate), residues closed by
   this story, and the explicit remainder — writes to `.claude/settings.json`
   itself are blocked by the Claude Code auto-mode classifier (harness-level;
   operator-applied edits remain the sanctioned path; two live hits in
   phase 99: INFRA-247, INFRA-249*) — with INFRA-249 noted as
   worktree-isolation, not classifier, but same operator-fallback pattern.
7. `docs/architecture.md`'s scope-enforcement/protected-files section states
   the corrected fail-closed contract (protected paths deny on missing/empty/
   malformed permissions artifacts even mid-story) and records the
   settings.json end-state doctrine: tooling only, no build-artifact
   allow/deny, normal build cycles write neither settings file.
8. Full `tests/pairmode/` suite passes (known pre-existing
   `test_observability_ui.py::test_ui_build_emits_dist_index_html` failure
   acceptable if it reproduces on clean HEAD).

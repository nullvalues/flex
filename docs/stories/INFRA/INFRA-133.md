---
id: INFRA-133
phase: '49'
rail: INFRA
story_class: code
status: planned
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/sync.py
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_sync.py
touches:
  - hooks/pre_tool_use.py
  - skills/pairmode/scripts/context_budget.py
---

# INFRA-133 — Wire context budget hook registration into bootstrap and sync

## Background

CER-027 (Phase 47) identified that the context budget check was enforced only
by LLM attention. INFRA-127/128/129 (Phase 47) built the mechanical solution:
`context_budget.py` + `pre_tool_use.py`. The hook was declared in
`hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}`, a variable that is never set
in any environment. Neither `bootstrap.py` nor `sync.py` register the hook in
`.claude/settings.json`. As a result, the hook has never fired on any project
since it was built.

Three compounding failures confirmed by investigation (2026-06-01):

1. `PreToolUse` not present in `.claude/settings.json` on flex or any
   downstream project — the hook command in `hooks/hooks.json` uses
   `${CLAUDE_PLUGIN_ROOT}` which is unset; the hook simply never runs.
2. `.companion/state.json` missing from the flex project — `decide()` returns
   `None` immediately when state.json is absent; even a correctly-registered
   hook would no-op on flex itself.
3. Context budget defaults (`context_budget_threshold` etc.) not seeded into
   existing downstream `state.json` files — `bootstrap.py` seeded them only
   for new files; pre-INFRA-127 projects never received them.

## Acceptance criterion

**A.** `bootstrap.py` gains `_register_pretooluse_hook(settings_path, plugin_root)`.
The function merges a `PreToolUse` → Task → hook entry into `.claude/settings.json`
using the absolute resolved path of `pre_tool_use.py` (computed from
`Path(__file__).resolve()` — no `${CLAUDE_PLUGIN_ROOT}` dependency).
The merge is idempotent: if an entry with the same command already exists, it is
not duplicated. `_bootstrap_project()` calls this function after the deny-list
merge.

**B.** `sync_project()` in `sync.py` calls the same registration logic (imported
from bootstrap or inlined identically) before writing the final state.json block.
Downstream projects running `pairmode sync` will receive the hook registration
without needing a re-bootstrap.

**C.** `sync_project()`'s state.json update block seeds context budget defaults
when absent — merging the following keys only if not already present in
`existing_state`:
- `context_budget_threshold`: 120000
- `context_budget_overrun_pct`: 0.10
- `expected_step_tokens`: 53000
- `context_budget_reprompt_margin`: 10000

**D.** Tests in `test_bootstrap.py` confirm: (i) hook entry is written on first
bootstrap; (ii) idempotent on second call; (iii) existing hook entries with
different commands are preserved alongside the new entry.

**E.** Tests in `test_sync.py` confirm: (i) hook entry is written during sync;
(ii) context budget defaults are seeded when absent; (iii) existing values for
those keys are not overwritten.

**F.** BUILD GATE passes: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`

## Out of scope

- Do not modify `hooks/hooks.json` — it remains the canonical declaration for
  Claude Code plugin installation; the `${CLAUDE_PLUGIN_ROOT}` form is correct
  there. This story adds the runtime-resolved path to project settings, which
  is a different registration channel.
- Do not create `.companion/state.json` for the flex project — that is
  initialized by running bootstrap against flex, which the operator does
  manually after this story ships. Document the required manual step in a
  `## Post-ship operator action` note at the bottom of this story.
- Do not change `context_budget.py` or `pre_tool_use.py` — the logic is
  correct; only the registration and seeding are broken.

## Post-ship operator action

After this story is committed, the operator must run bootstrap against the
flex project itself to create `.companion/state.json` and register the hook
in flex's `.claude/settings.json`:

```bash
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex/skills/pairmode/scripts/bootstrap.py \
  --project-dir /mnt/work/flex
```

Then verify the hook fires by checking `.claude/settings.json` for a
`PreToolUse` entry and confirming `.companion/state.json` contains
`context_budget_threshold`.

Downstream projects pick up the fix on their next `pairmode sync` run.

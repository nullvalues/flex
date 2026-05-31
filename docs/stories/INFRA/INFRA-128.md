---
id: INFRA-128
phase: '47'
rail: INFRA
story_class: code
status: complete
primary_files:
  - hooks/pre_tool_use.py
  - hooks/hooks.json
  - tests/pairmode/test_pre_tool_use_hook.py
touches: []
---

# INFRA-128 — New thin `hooks/pre_tool_use.py` delegate + `hooks.json` `Task` wire-up

Protected files: `hooks/pre_tool_use.py` (new file in hooks/) and `hooks/hooks.json` — stated reason: CER-027 enforcement — adding thin PreToolUse delegate that calls context_budget.decide() on Task tool spawns.

See phase spec: `docs/phases/phase-47.md` § Story INFRA-128.

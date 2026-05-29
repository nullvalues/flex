---
id: INFRA-121
phase: '46'
rail: INFRA
story_class: code
status: planned
primary_files:
  - skills/companion/scripts/sidebar.py
  - tests/pairmode/test_sidebar_call_model.py
touches:
  - skills/pairmode/scripts/call_model.py
---

# INFRA-121 — Wire `sidebar.py` to Ollama backend

Protected file: `sidebar.py` — stated reason: rename existing `call_claude`
(claude_agent_sdk path) to `_call_anthropic` (preserved exactly), add new
public `call_claude` dispatcher that routes to Ollama when
`FLEX_MODEL_BACKEND=ollama` is set. Default behavior unchanged.

See phase spec: `docs/phases/phase-46.md` § Story INFRA-121.

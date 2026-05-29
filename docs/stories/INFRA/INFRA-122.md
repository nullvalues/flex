---
id: INFRA-122
phase: '46'
rail: INFRA
story_class: code
status: planned
primary_files:
  - skills/companion/scripts/sidebar.py
  - tests/pairmode/test_sidebar_call_model.py
---

# INFRA-122 — Fallback for extraction / conflict / spec call sites + plan-impact hardening

Protected file: `sidebar.py` — stated reason: add JSON-parse fallback to
`_call_anthropic` for three call sites when local model returns unparseable
output; hardcode plan-impact calls to `_call_anthropic` unconditionally.

See phase spec: `docs/phases/phase-46.md` § Story INFRA-122.

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

# INFRA-121 — Wire `sidebar.py` `call_claude` to pluggable backend

Protected file: `sidebar.py` — stated reason: delegate `call_claude` to
pluggable backend to enable local model routing without behavior change on
the default Anthropic path.

See phase spec: `docs/phases/phase-46.md` § Story INFRA-121.

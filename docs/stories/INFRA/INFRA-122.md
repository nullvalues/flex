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

# INFRA-122 — Route decision extraction to local model with fallback

Protected file: `sidebar.py` — stated reason: add JSON-parse validation and
Anthropic fallback to `extract_incremental` for resilience when a local
model backend is active.

See phase spec: `docs/phases/phase-46.md` § Story INFRA-122.

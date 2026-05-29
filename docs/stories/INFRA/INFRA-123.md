---
id: INFRA-123
phase: '46'
rail: INFRA
story_class: code
status: complete
primary_files:
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/effort_recorder.py
  - tests/pairmode/test_effort_db.py
touches:
  - skills/companion/scripts/sidebar.py
---

# INFRA-123 — `backend` column in effort DB

Protected file: `sidebar.py` — stated reason: add `backend="anthropic"` to
`_record_sidebar_effort` call, and add Ollama effort recording to the
`call_claude` dispatcher.

See phase spec: `docs/phases/phase-46.md` § Story INFRA-123.

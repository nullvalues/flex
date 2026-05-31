---
id: INFRA-127
phase: '47'
rail: INFRA
story_class: code
status: planned
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/refresh_effort_baseline.py
  - skills/pairmode/seed/effort_baseline.json
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_refresh_effort_baseline.py
  - tests/pairmode/fixtures/context_budget_prompt.txt
touches:
  - skills/pairmode/scripts/bootstrap.py
---

# INFRA-127 — New `context_budget.py` module + `refresh_effort_baseline.py` seed CLI + bootstrap seeding

See phase spec: `docs/phases/phase-47.md` § Story INFRA-127.

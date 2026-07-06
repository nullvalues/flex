---
id: INFRA-198
rail: INFRA
title: registered_projects writer audit and fix
status: draft
phase: "HARNESS011-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/pairmode_sync.py
touches: []
---

## Acceptance criterion

- **CER-058** — Every code path that writes to `registered_projects` in
  `.companion/state.json` is identified and either:
  (a) confirmed to be the intended `register` entry point
      (`pairmode_sync.py register` command), or
  (b) fixed to route through the `register` command / equivalent helper, or
  (c) documented with an inline comment explaining why it writes directly and why that is
      intentional.
- The `bootstrap.py` path (if it writes `registered_projects`) is specifically addressed.
- After this story, no bootstrap or agent-side path writes `registered_projects` without
  explicit provenance documentation.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. Grep all Python files for `registered_projects`:
   ```bash
   grep -rn "registered_projects" skills/pairmode/scripts/ hooks/
   ```
2. For each write site found, read the surrounding context (10 lines) to understand when
   and why it writes.
3. If any write site is a bootstrap path or an agent-session path (not the explicit
   `register` CLI command): either route it through the register logic, or add an inline
   comment `# intentional direct write: <reason>`.
4. If the investigation finds that `meander` appeared due to a specific code path, fix
   that path.

## Tests

No new test file required. If a code change is made (routing or guard), add a test case
in the relevant existing test file confirming the registration path.

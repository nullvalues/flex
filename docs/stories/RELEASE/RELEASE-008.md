---
id: RELEASE-008
rail: RELEASE
title: Reconcile 46 main-only commits into Era 3 at the fold merge
status: complete
phase: "HARNESS012-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/schema_validator.py
  - skills/pairmode/scripts/story_new.py
  - skills/pairmode/scripts/spec_preflight.py
  - skills/pairmode/skills/reviewer/procedure.md
  - skills/pairmode/skills/security-auditor/procedure.md
touches:
  - tests/pairmode/test_schema_validator.py
  - tests/pairmode/test_story_new.py
  - tests/pairmode/test_spec_preflight.py
---

## Ensures

- `git merge main` into a `fold-prep` branch completes with all conflicts
  resolved — no unresolved markers in any file.
- Every main-only feature from phases 79–84 survives in its Era 3 location:
  - **INFRA-190/191 (`spec_preflight.py`)** — kept as a standalone script and
    wired as a `flex_build.py spec-preflight` subcommand; referenced from
    `skills/pairmode/skills/spec-writer/procedure.md` if that skill exists,
    otherwise documented in architecture.md.
  - **INFRA-187/189 (schema_validator pointer-only + `test_gate`)** — merged
    with harness's status-aware `primary_files` handling (INFRA-193); the
    combined validator handles both `pointer-only` references and draft/backlog
    `primary_files` relaxation without conflict.
  - **INFRA-188 (`check-story-scope` budget warning)** — kept; harness's
    `check-story-scope` command is a superset.
  - **INFRA-186 (`story_new.py` architecture prompt)** — kept alongside
    harness's rail regex validation.
  - **BUILD-043 (reviewer `--notes` FAIL capture)** — ported from the deleted
    `reviewer.md.j2` into `skills/pairmode/skills/reviewer/procedure.md`.
  - **BUILD-041 (security-auditor hook-exception rules)** — ported from the
    deleted `security-auditor.md.j2` into
    `skills/pairmode/skills/security-auditor/procedure.md`.
- Delete/modify conflicts on the four retired agent templates
  (`reviewer.md.j2`, `security-auditor.md.j2`, `.claude/agents/reviewer.md`,
  `.claude/agents/security-auditor.md`) resolve as **delete** (content
  ported, files gone).
- `resolve_current_phase` semantics reconciled: main's "first active row with
  existing file" walk adopted inside harness's `is_phase_inactive` framework;
  existing regression tests for both branches pass; add a new test covering
  a phase table with a deferred row followed by a planned-fileless row.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes
  on the merged tree.

## Instructions

1. Create a local branch `fold-prep` from `harness` HEAD:
   ```bash
   git checkout -b fold-prep
   git merge main
   ```
2. For each conflict file, apply the resolution strategy described in Ensures:
   - Agent template files → resolve as delete (`git rm`)
   - `flex_build.py`, `schema_validator.py`, `story_new.py` → merge feature
     sets per the Ensures list; run the combined test suite after each file.
3. Port `--notes` FAIL capture from main's `reviewer.md.j2` body into
   `skills/pairmode/skills/reviewer/procedure.md` under a new
   `## Notes on FAIL` section (or equivalent).
4. Port security-auditor hook-exception rules from main's
   `security-auditor.md.j2` into
   `skills/pairmode/skills/security-auditor/procedure.md`.
5. Reconcile `resolve_current_phase` by reading both implementations and
   adopting the union logic; add the deferred+planned-fileless regression test.
6. Run full suite; fix any failures before declaring done.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Regression test to add in `tests/pairmode/test_flex_build.py` (or
`test_resolver.py`):
- Phase table with a `deferred` row followed by a `planned` row whose file
  does not exist → `current-phase` returns the first row with an existing file
  after the deferred entry.

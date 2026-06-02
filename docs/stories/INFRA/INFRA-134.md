---
id: INFRA-134
rail: INFRA
title: check-stubs CLI command in flex_build.py
status: complete
phase: "51"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_flex_build.py
---

# INFRA-134 — check-stubs CLI command in flex_build.py

## Background

The pre-story stub gate (BUILD-009) catches stubs story-by-story during the
build loop. But operators need visibility into the full scope of stub stories
in a project BEFORE building — to plan remediation, estimate effort, and decide
whether to run a cleanup phase before the next feature phase.

Without this CLI, an operator running "Build Phase N" on forqsite would
encounter the stub gate on every story, one at a time. With this CLI, they
can run a pre-build audit and see all 63 stubs at once.

## Acceptance criterion

**A.** `flex_build.py` gains a `check-stubs` subcommand:

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  check-stubs --project-dir .
```

**B.** The command scans all story files under `docs/stories/` in the project.
For each `.md` file, it checks:

1. **Delegation language**: body contains "See phase doc", "See docs/phases/",
   or "See phase-" (case-insensitive)
2. **Missing acceptance surface**: no `## Ensures`, `## Acceptance criterion`,
   or `## Acceptance criteria` section in the body

A story is a stub if either condition is true.

**C.** Output format:

```
Scanning docs/stories/ in /path/to/project...

STUB  RBAC-001   delegation    "See phase doc `docs/phases/phase-PM004-main.md`"
STUB  AEO-003    delegation    "See phase doc `docs/phases/phase-PM007-main.md`"
STUB  MEDIA-001  no-acceptance (no ## Ensures or ## Acceptance criterion)
OK    RBAC-010   self-contained
...

Summary: 63 stubs / 73 total stories (86%)
  delegation:    59
  no-acceptance:  4
```

**D.** Exit code: 0 if zero stubs found, 1 if any stubs found.
This allows CI integration: `flex_build.py check-stubs --project-dir . && echo "clean"`.

**E.** Tests in `tests/pairmode/test_flex_build.py` cover:
- A story with delegation language is detected as a stub
- A story with no acceptance surface is detected as a stub
- A self-contained story is not flagged
- A missing `docs/stories/` directory returns a clean result (0 stubs, 0 total)
- Exit code is 0 when no stubs, 1 when stubs found

**F.** `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Out of scope

- Do not modify the orchestrator gate logic (BUILD-009 covers that in prose).
- Do not add a `--fix` flag or automatic migration — this is a read-only audit.
- Do not scan phase docs for embedded story sections — that is a different check
  (the phase doc boundary scan from BUILD-009 is orchestrator prose, not CLI).

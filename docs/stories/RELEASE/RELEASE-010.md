---
id: RELEASE-010
rail: RELEASE
title: Wire gate-worker into bootstrap/sync and verify leaf-worker dispatch
status: draft
phase: "HARNESS012-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/templates/agents/gate-worker.md.j2
touches:
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_audit.py
---

## Ensures

- **Verification step first**: Run a complete builder → reviewer story cycle
  on a scratch (non-flex) project bootstrapped at 0.3.0 using a scratch phase
  doc. Confirm that every resolver-emitted action (`spawn-builder`,
  `spawn-reviewer`, `checkpoint-security`, `checkpoint-intent`,
  `checkpoint-docs`, `checkpoint-tag`) can be dispatched — i.e. there is a
  loadable agent shell or the orchestrator template documents the procedure
  skill path.
- **If `gate-worker` dispatch is broken**: `gate-worker.md.j2` is added to
  `AGENT_FILES` in `bootstrap.py` and `CANONICAL_FILES` in `audit.py`, so
  `bootstrap` writes the gate-worker shell and `audit/sync` keeps it current.
- **If dispatch works without the shell** (orchestrator loads procedure skill
  by absolute path): An inline comment in `CLAUDE.build.md.j2` documents how
  the orchestrator spawns gate workers — no shell file required — and
  `gate-worker.md.j2` is explicitly excluded from `AGENT_FILES` with a comment
  explaining why.
- Either way, a bootstrapped project has a clear, documented dispatch path for
  every resolver action. No resolver action is silently unspawnable.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

### Step 1 — Verify on scratch project

```bash
mkdir /tmp/scratch-era3 && cd /tmp/scratch-era3
git init && echo '{"project_name":"scratch","stack":"python"}' \
  > .companion/product.json
PYTHONPATH=... uv run python /mnt/work/flex/skills/pairmode/scripts/bootstrap.py \
  --project-dir . --yes
# Create a minimal phase + story, run flex_build.py next-action, confirm each
# dispatched action type can be fulfilled by the installed scaffolding.
```

Record findings: which action types succeed, which fail.

### Step 2 — Apply fix

If `gate-worker` dispatch fails:
- Add `"gate-worker.md.j2"` to the `AGENT_FILES` list in `bootstrap.py`.
- Add `"gate-worker.md"` to `CANONICAL_FILES` in `audit.py`.
- Re-run bootstrap on the scratch project and re-verify.

If dispatch succeeds without a shell:
- Add a comment block in `CLAUDE.build.md.j2` documenting the agent-free
  dispatch pattern for all resolver actions.
- Add `gate-worker.md.j2` to a `EXCLUDED_FROM_BOOTSTRAP` constant with an
  explanatory comment.

### Step 3 — Cleanup scratch

Delete `/tmp/scratch-era3` after verification.

## Tests

Add to `tests/pairmode/test_bootstrap.py`:
- Bootstrap output directory contains (or explicitly excludes with
  documented reason) a gate-worker agent shell.

Add to `tests/pairmode/test_audit.py`:
- Audit CANONICAL_FILES list matches bootstrap AGENT_FILES list (or the
  exclusion constant accounts for the delta).

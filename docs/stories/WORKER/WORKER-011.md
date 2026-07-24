---
id: WORKER-011
rail: WORKER
title: Checkpoint docs-review leaf worker — thin shell + plugin procedure skill
status: complete
phase: "HARNESS004-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/checkpoint-docs/procedure.md
  - tests/pairmode/test_checkpoint_docs_worker.py
touches:
  - skills/pairmode/scripts/worker_result.py
---

## Context

HARNESS004's one new leaf worker: the checkpoint docs-review worker. The security-auditor
(WORKER-008) and intent-reviewer (WORKER-009) leaf workers already exist and handle the
`checkpoint-security` and `checkpoint-intent` checkpoint actions respectively. The
`checkpoint-docs` action needs its own worker: a cold-eyes review of documentation currency
(era/phase/story docs, architecture.md, CER backlog, changelog) rather than security or intent.
Returns `REVIEW-RESULT`. The `checkpoint-tag` action is a thin inline harness operation (no worker).

## Requires

- RESOLVER-007 complete: `checkpoint-docs` is in `ACTIONS` and `_SPAWN_ACTIONS`.
- WORKER-004 complete: `worker_result.py` defines `REVIEW-RESULT`.

## Ensures

- `skills/pairmode/skills/checkpoint-docs/procedure.md` — docs-review procedure. Bounded inputs:
  the phase doc, the era doc, `docs/phases/index.md`, `docs/architecture.md`, `docs/cer/backlog.md`.
  Checks: (a) phase doc `## Stories` table matches the actual story statuses; (b) no phase-doc
  referenced story is missing its story file; (c) CER Do Now is empty or all items are RESOLVED;
  (d) `docs/architecture.md` mentions the current era and phase; (e) `CHANGELOG.md` (if present)
  has an entry for the phase. No accumulated orchestrator state.
- Returns `REVIEW-RESULT{verdict: "PASS"|"FAIL", findings: [str], reason: str}`.
- `checkpoint-docs` is in `_SPAWN_ACTIONS` (RESOLVER-007). No routing change in this story
  (routing wired in RESOLVER-008).
- Tests assert: procedure file exists; bounded inputs (negative assertion on accumulated state);
  injected `REVIEW-RESULT{verdict: "PASS"}` parses; injected `REVIEW-RESULT{verdict: "FAIL",
  findings: ["Story INFRA-164 shows backlog in phase doc but planned on disk"]}` parses.
  No live API call.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- The procedure is a new checklist (not extracted from an existing agent). Write it from the
  HARNESS004 agreements DP2 checkpoint step description for step 2 (documentation review) + step 3
  (CER backlog review). Keep it concise — 5–10 checklist items.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_checkpoint_docs_worker.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: procedure file exists; bounded inputs; injected results parse; no live API call;
suite green.

### Out of scope

- Checkpoint routing (RESOLVER-008).
- The `checkpoint-tag` action (inline harness operation; no worker).
- HARNESS004 isolation suite (WORKER-012).

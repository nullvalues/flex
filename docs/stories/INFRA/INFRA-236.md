---
id: INFRA-236
rail: INFRA
title: Restore effort recording pipeline end-to-end (token capture, attempt rows, checkpoint-time cost rollup)
status: complete
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/post_tool_use.py
  - skills/pairmode/scripts/worker_result.py
  - skills/pairmode/skills/reviewer/procedure.md
  - docs/architecture.md
touches:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.build.md
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_record_attempt.py
  - tests/pairmode/test_worker_result.py
  - tests/pairmode/test_post_tool_use.py
---

## Context

0.2's builder/reviewer agent templates (`/mnt/work/flex/skills/pairmode/templates/agents/builder.md.j2:99-108`, `reviewer.md.j2:279-295`) ended every
final message with a self-reported `<usage>total_tokens: N</usage>` block, which
`record_attempt.py --usage-block` parsed and `CLAUDE.build.md.j2` (0.2) invoked at 9
call sites. 0.3's `builder/procedure.md:159-166` and `reviewer/procedure.md:403-435`
explicitly forbid this ("no usage block... deviating from this format invalidates the
result") as part of the WORKER-004 JSON return-format grammar, and nothing replaced
the token source. `docs/architecture.md:952` still documents `effort.db` as sourced
"from subagent `<usage>` blocks" — stale relative to the procedure it describes.

The reviewer's `FAIL-CAUSE` line (`reviewer/procedure.md:353-368`) is similarly
orphaned: the procedure says "the orchestrator parses this line and passes it as
`--notes` to `record_attempt.py`," but the return-format section forbids anything
except the bare `REVIEW-RESULT` JSON object, which has no field for it — the line is
emitted mid-transcript where the orchestrator has no contract to read it from.

Confirmed empirically this session: this repo's own `.companion/state.json` has no
`effort_tracking` key (bootstrap claims it auto-enables for pairmode projects; it
doesn't here), and `.companion/effort.db` had zero tables before this session queried
it — no builder or reviewer attempt has ever been recorded in this checkout.
Downstream consumers reading this empty database: `model_selector`'s retry-based
model escalation, `flex_build.py check-guardrail`, `story-cost-estimate`,
`context-health`, and `resolver-state`'s `effort_by_role` (which feeds the
`flex:observability` dashboard).

Additionally (operator decision, folding a separate audit item A5 into this story
rather than a standalone one): 0.2's checkpoint step 8
(`/mnt/work/flex/skills/pairmode/templates/CLAUDE.build.md.j2:912,979-983`) reported a
per-role cost rollup and a closing "next phase" prompt at the end of every checkpoint.
0.3 has no equivalent — `resolver-state`'s `effort_by_role` isn't called anywhere in
`CLAUDE.build.md` or the checkpoint procedures; it only feeds the opt-in
`flex:observability` dashboard, which nobody sees automatically at checkpoint time.

## Requires

- A decision on token source. **Amended after adversarial review**: this story
  originally proposed orchestrator-side extraction from the Task/Agent tool's own
  returned usage metadata (the `<subagent_tokens>`/`<duration_ms>` fields visible in
  this session's own task-notification results). A second review confirmed that
  surface is *not* a documented, stable API — it's an artifact of how this harness
  happens to render task notifications, not something `CLAUDE.build.md`-driven CLI
  steps can reliably query. It also would have reintroduced LLM-transcribed numbers
  (just moved from the subagent's self-report to the orchestrator's), contradicting
  the CLI-side-not-prose approach INFRA-237/238/239 already adopt.
- **Corrected direction:** `hooks/post_tool_use.py` already parses the live session
  JSONL transcript for token counts (used today for `context_current_tokens`
  tracking). A PostToolUse-side hook write of `record-attempt` — reading the
  just-completed Task/Agent tool result's usage data directly from the transcript,
  the same mechanical source already trusted elsewhere in this codebase — is fully
  deterministic and testable, with no dependency on an unverified notification-format
  contract. Instruction 1 below still requires confirming this concretely before
  building (see Instructions).

## Ensures

- After one builder spawn and one reviewer spawn in a real story cycle,
  `.companion/effort.db`'s `attempts` table contains one `builder` row and one
  `reviewer` row, each with non-NULL `tokens_total`, `model`, and `outcome`.
- `hooks/post_tool_use.py`'s Task/Agent branch gains a `record-attempt` call, reading
  token/duration usage directly from the same session-transcript parse it already
  performs for `context_current_tokens` — no reliance on agent-authored text, no
  reliance on the orchestrator's own view of a notification. `CLAUDE.build.md.j2`'s
  build-loop pseudocode is updated only if any orchestrator-side step is still needed
  (e.g. passing `--story-id`/`--agent-role` context the hook can't derive from the
  transcript alone) — prefer a fully hook-side mechanism if the transcript carries
  enough context to derive those fields too.
- `REVIEW-RESULT`'s JSON schema (`worker_result.py`) gains an optional `fail_cause`
  field; `reviewer/procedure.md`'s FAIL path populates it instead of (or in addition
  to, for human readability) the mid-transcript `FAIL-CAUSE:` line; the orchestrator
  step reads this field for `record_attempt.py --notes`.
- `.companion/state.json` gains `effort_tracking: true` for this repo specifically
  (either via a one-time migration step, or confirmed already set by the next
  `sync-all`/`to-030` — whichever is correct, verify and fix the actual gap rather than
  assuming bootstrap's claimed default is working).
- Checkpoint sequence gains a report step: after all checkpoint gate workers complete
  and before/alongside `checkpoint-tag`, print a per-role cost rollup
  (`flex_build.py resolver-state`'s `effort_by_role`, or a new dedicated summary
  command if reusing that command's full output is too broad) and the `next-phase`
  pointer, mirroring 0.2's step 8 intent without reintroducing 0.2's prose bulk.
- `docs/architecture.md:255-256`, `:940-942`, `:952` updated to describe the
  orchestrator-extraction flow actually implemented, not the removed `<usage>`-block
  design.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; report every failure; confirm only the known CER-070 environmental failure
  remains).

## Instructions

1. Read `hooks/post_tool_use.py`'s Task/Agent branch and whatever transcript-resolution
   helper it uses for `context_current_tokens` in full. Confirm exactly what usage
   fields (total/in/out/cache tokens, duration) are actually present in a completed
   Task/Agent tool result inside the session transcript, and confirm they're
   per-spawn (not cumulative-session) so a `record-attempt` row can be attributed to
   the one story/agent-role that just ran.
2. Add a `record-attempt` call to `hooks/post_tool_use.py`'s Task/Agent branch,
   populated from that transcript-derived usage data plus whatever
   `--story-id`/`--agent-role`/`--model`/`--outcome` context the hook can derive
   (from `tool_input`, `tool_response`, or `state.json`) — falling back to an
   orchestrator-side `CLAUDE.build.md.j2` step only for fields the hook genuinely
   cannot derive on its own.
3. Add `fail_cause` to the `REVIEW-RESULT` schema in `worker_result.py`; update
   `reviewer/procedure.md`'s return-format section to include it; keep the
   human-readable `FAIL-CAUSE:` transcript line for operator visibility but make the
   JSON field the actual data contract.
4. Investigate why `effort_tracking` is absent from this repo's own `state.json`
   despite bootstrap's documented auto-enable behavior; fix whichever side is wrong
   (bootstrap not running the enable step, or this checkout predating that behavior
   and needing a one-time backfill).
5. Add a checkpoint-time cost-rollup + next-phase-pointer report step, reusing
   existing `resolver-state`/`effort_by_role` machinery rather than duplicating query
   logic.
6. Update `docs/architecture.md`'s three stale passages.
7. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Any change to `builder/procedure.md`'s or `reviewer/procedure.md`'s "no usage
  block" rule itself — that WORKER-004 grammar decision stands; this story completes
  the *replacement* mechanism, it doesn't undo the removal.
- INFRA-237 (attempt counter), INFRA-238 (current_story), INFRA-239 (phase
  completion) — related dead-wiring gaps, separate stories, separate root causes.
- Backfilling historical effort.db rows for stories already built in this checkout
  before this fix — no such data exists to backfill.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure. Add or
update integration coverage in `test_record_attempt.py`/`test_worker_result.py`
asserting the orchestrator-extraction record-attempt call path and the `fail_cause`
schema field.

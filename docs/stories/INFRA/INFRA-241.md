---
id: INFRA-241
rail: INFRA
title: Reconcile builder/reviewer spawn subagent_type contract with the context-budget gate allowlist
status: complete
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/pre_tool_use.py
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/scripts/bootstrap.py
  - .claude/agents/
touches:
  - CLAUDE.build.md
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/model_selector.py
  - tests/pairmode/test_pre_tool_use_scope_guard.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_bootstrap.py
  - docs/architecture.md
  - tests/pairmode/fixtures/transcript_entry_shape.json
  # 5 new agent shell template sources (Instructions item 2) — the actual
  # deliverable for the subagent_type-registration side of this story; each
  # is a thin shell over its role's existing procedure skill.
  - skills/pairmode/templates/agents/builder.md.j2
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/agents/loop-breaker.md.j2
  - skills/pairmode/templates/agents/security-auditor.md.j2
  - skills/pairmode/templates/agents/intent-reviewer.md.j2
  # audit.py's CANONICAL_FILES must mirror bootstrap.py's AGENT_FILES
  # (TestCanonicalFilesAgentFilesConsistency) or sync/audit silently drift on
  # the 5 new shells.
  - skills/pairmode/scripts/audit.py
  - tests/pairmode/test_flip_dogfood.py
  # Real agents/reviewer.md.j2 CANONICAL_FILES entry collides with this test's
  # prior synthetic-fixture reuse of the same .claude/agents/reviewer.md dest
  # path; retargeted to a non-colliding fixture path.
  - tests/pairmode/test_sync.py
---

## Context

`hooks/pre_tool_use.py:102-105` (line drift confirmed by adversarial re-check; was
`:113-115` at spec-writing time) gates the context-budget check (INFRA-199) with an
exact-string match:

```python
subagent_type = data.get("tool_input", {}).get("subagent_type")
if subagent_type not in BUILD_CYCLE_SUBAGENTS:
    sys.exit(0)
```

`BUILD_CYCLE_SUBAGENTS` (`:53-60`) = `{"builder", "reviewer", "loop-breaker",
"security-auditor", "intent-reviewer"}`. This is intentional design, not an oversight
— the header comment (`:8-11,55-56`) explicitly names `general-purpose` as a type that
"must never be blocked."

But no custom agent type named `builder`, `reviewer`, `loop-breaker`,
`security-auditor`, or `intent-reviewer` is registered anywhere in this repo —
`.claude/agents/` contains only `reconstruction-agent.md` (confirmed by adversarial
re-check; `gate-worker.md` is a `bootstrap.py` `AGENT_FILES` template distributed to
newly-bootstrapped projects, not a file present in this checkout itself), since
HARNESS-002 deliberately retired the rendered per-role agent files in favor of shared
procedure skills loaded by generic thin shells. `CLAUDE.build.md`'s own
`spawn leaf-worker-for(a.action)` line (`:28,32`) defines no explicit `subagent_type`
mapping — confirmed this session: the two builder-equivalent spawns for INFRA-235 used
`subagent_type: "general-purpose"` (the Task/Agent tool's `subagent_type` must resolve
to something real, and nothing named `builder` exists to resolve to).

Result, confirmed by direct trace this session: `subagent_type not in
BUILD_CYCLE_SUBAGENTS` is true for every spawn following the currently-documented
process, the gate hits `sys.exit(0)` before `context_budget.decide()` ever runs, and
the context-budget PreToolUse gate — built specifically to govern build-cycle spawns —
has been fully decorative for every real build spawn since HARNESS-002. Not a partial
gap: total.

## Requires

- A decision on which side changes: register real custom agent types
  (`.claude/agents/builder.md`, etc.) that resolve `subagent_type` to those literal
  strings while still loading the shared procedure skill as their instruction body
  (preserves HARNESS-002's shared-procedure design, restores a matchable type string),
  versus changing `BUILD_CYCLE_SUBAGENTS`'s matching to key off something else the
  `general-purpose` spawn actually carries (the loaded procedure-skill path, a marker
  in the prompt). Prefer the former — it requires no change to the gate's already-tested
  matching logic and is a smaller diff — unless registering five thin agent files is
  judged to reintroduce the per-role-file duplication HARNESS-002 was trying to
  eliminate, in which case document that tradeoff explicitly before choosing the
  latter. Adversarial review confirmed thin-shell agents referencing a shared skill
  is already this repo's accepted pattern (the `gate-worker.md` bootstrap template
  does exactly this), so registering 5 one-line shells does not reintroduce
  HARNESS-002's per-role duplication.
- **Amended after adversarial review — two additional requirements, not optional:**
  1. Registering the 5 agent types in `.claude/agents/` alone only fixes this repo.
     `bootstrap.py`'s `AGENT_FILES` list is the actual distribution mechanism to the
     14 pending fleet migrations (INFRA-240's whole point) — this story's scope must
     include adding the 5 shells there, or the gate stays dead for every downstream
     project even after this story lands.
  2. `docs/architecture.md:602` documents `Agent({..., subagent_type: "reviewer",
     model: "opus"})` working — but that passage also references agent templates
     retired in HARNESS-002 and an unregistered subagent type, so it may itself
     describe a design that never ran. Before treating this story's fix as compatible
     with INFRA-237's per-attempt model escalation (retry-upgrade at attempt ≥2, the
     `fable` loop-breaker tier), explicitly verify whether a custom agent type with a
     frontmatter-pinned `model:` field can still be spawned with a *different*,
     per-call model override — if it can't, registering typed agents with a fixed
     model would silently break retry escalation. Resolve this before implementation,
     not after.
- **Amended per operator direction (context-budget-gate reliability discussion)**:
  once this story reconnects the gate to real spawns, `pre_tool_use.py:126`'s
  `{"decision": "block", ...}` output is confirmed to be a genuine Claude-Code-enforced
  hard stop on the tool call — not advisory text the orchestrator can talk past. The
  operator's recollection of the orchestrator "ignoring" the gate in the past traces to
  two documented, distinct causes, neither of which is "the block fired and got
  ignored": (1) the pre-INFRA-193 self-clearing bug (CER-047), fixed; (2) an agent
  manually forging `context_budget_acknowledged_*` keys into `state.json` to defeat the
  gate entirely (CER-067/asp finding) — a workaround around the gate never firing
  correctly, not a case of a fired block being overridden. This story's fix, once
  landed, restores a real hard block for genuine cases.
- **Amended, folded in rather than a separate story**: `context_budget.py`'s
  `compute_context_tokens` transcript parser already fails safe today — any parse
  failure (missing file, malformed JSON, wrong field shape, non-numeric value) returns
  `None`, and `decide()` already treats `current_tokens is None` as a hard block
  (`CONTEXT CHECK REQUIRED`), never a silently-wrong permissive number. Per Claude
  Code's own documentation, the underlying transcript JSONL format is internal and can
  change between releases — the existing `None`-on-mismatch behavior already absorbs
  most of that risk (a renamed/missing field just becomes `None` and fails safe). The
  one gap not covered: a future format change that's *silently* wrong — still
  valid-shaped JSON, but with different field semantics — would not be caught by the
  current `None` check. Add a small regression test pinning today's known-good
  transcript-entry shape as a canary, not a parser rewrite (operator explicitly does
  not want a remodel; the existing fail-safe design is sound and should be preserved,
  only backstopped against silent drift).

## Ensures

- After the fix, spawning a builder-equivalent worker for a real story cycle produces
  an observable `context_budget.decide()` invocation — verified either via a state.json
  side effect (e.g. `context_budget_acknowledged_at` updates on a block) or a test that
  stubs `decide()` and asserts it's called — for a spawn using whatever
  `subagent_type` value the fixed contract specifies.
- The gate remains a no-op for `general-purpose`, `Plan`, `Explore`, and any other
  non-build-cycle spawn — the existing allowlist behavior for those types is
  unchanged.
- `CLAUDE.build.md.j2`'s `spawn leaf-worker-for(a.action)` line is no longer ambiguous
  — it names the exact `subagent_type` to use per action (`spawn-builder` →
  `"builder"`, `spawn-reviewer` → `"reviewer"`, etc.), removing the interpretation gap
  that led to this session's `general-purpose` choice.
- `bootstrap.py`'s `AGENT_FILES` list includes the 5 new thin-shell agent templates,
  so newly-bootstrapped and re-synced projects (including the 14 pending fleet
  migrations) receive them.
- Explicit, tested confirmation of the per-attempt model-override question from the
  amended Requires section: either (a) a typed agent's model can be overridden
  per-call despite a frontmatter default, and INFRA-237's escalation ladder keeps
  working unchanged, or (b) it can't, and this story's Ensures include whatever
  adjustment is needed (e.g. omitting a frontmatter `model:` default entirely and
  always passing model explicitly per spawn) so escalation isn't silently broken.
- `docs/architecture.md` updated to describe the resolved spawn contract, including
  correcting the `:602` passage's stale template/subagent-type references.
- `tests/pairmode/fixtures/transcript_entry_shape.json` (or an inline fixture in
  `test_context_budget.py` if a separate file is unwarranted) captures a real,
  known-good `type: "assistant"` transcript entry with its `message.usage` block; a
  new test asserts `compute_context_tokens` extracts the expected total from it. This
  is a drift canary, not new parsing logic — the parser itself is unchanged.
- `docs/architecture.md` gains an explicit note (near the context-budget-gate
  description) that the working threshold (currently 130000/150000-ish depending on
  where it's read — confirm the actual constant) is an **empirically-tuned defensive
  heuristic for managing build-churn/drift, not a hard platform token limit** — it may
  need recalibration over time (different models, longer sessions) and its job is to
  be close enough that an operator can decide whether to `/clear` or continue given
  the next story's complexity, not to be precisely accurate to the token.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains).

## Instructions

1. Make the explicit choice from Requires and document the reasoning in the commit
   message or a short architecture.md note.
2. If registering agent types: create thin `.claude/agents/{builder,reviewer,
   loop-breaker,security-auditor,intent-reviewer}.md` files whose entire body is the
   "Shell instruction" already documented in each corresponding `procedure.md` (load
   the procedure skill, execute for the given story ID) — no role logic duplicated
   into the agent file itself, preserving HARNESS-002's single-source-of-truth intent.
   Resolve the model-override question (Requires, item 2) before deciding whether
   these files declare a frontmatter `model:` default at all.
2a. Add the same 5 templates to `bootstrap.py`'s `AGENT_FILES` list so they propagate
    to newly-bootstrapped and re-synced downstream projects.
3. If changing the gate's matcher instead: update `context_budget.py`'s matching logic
   and add equivalent test coverage for the new signal.
4. Update `CLAUDE.build.md.j2`'s pseudocode to name the exact `subagent_type` per
   action.
5. Add the observable-invocation test described in Ensures.
6. Add the transcript-entry-shape drift-canary test and fixture.
7. Update `docs/architecture.md`: the resolved spawn contract, the corrected `:602`
   passage, and the 150k-heuristic note (confirm the actual live threshold constant
   before writing the exact number).
8. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Changing what `context_budget.decide()` actually does once invoked — this story only
  restores the invocation, not the budget logic itself.
- INFRA-236/237/238/239 — adjacent dead-wiring gaps, separate root causes.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure; new
coverage proves `context_budget.decide()` is actually invoked for a build-cycle spawn
under the fixed contract, and remains skipped for non-build-cycle spawn types.

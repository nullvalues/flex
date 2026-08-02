---
id: INFRA-340
rail: INFRA
title: Complete INFRA-333 model-selector wiring: checkpoint-security/checkpoint-intent model dispatch, gate_worker_model consumer-or-removal
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
touches:
  - skills/pairmode/scripts/model_selector.py
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_model_selector.py
  - docs/architecture.md
  - skills/pairmode/templates/agents/gate-worker.md.j2
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH findings F3 and F4 of `docs/build-loop-cold-eyes-review-20260801.md`, both corroborated
independently by fable and opus. INFRA-333 (Phase 116) added `select_gate_worker_model`,
`select_docs_reviewer_model`, and `select_spec_writer_model` to `model_selector.py`, but only
`checkpoint-docs` actually got wired into `next_action.py`'s Row 9 dispatch — `checkpoint-security`
and `checkpoint-intent` still hardcode `model=None` there. `select_security_auditor_model`/
`select_intent_reviewer_model` are reachable only via `flex_build.py` CLI subcommands
(`select-security-auditor-model`, `select-intent-reviewer-model`) that `CLAUDE.build.md` never
calls — yet `.claude/agents/security-auditor.md` and `intent-reviewer.md` both document a
model-override contract ("the orchestrator resolves this worker's model via
`model_selector.select_*_model` and passes it as an explicit per-call override") that does not
exist in the live dispatch path. Production-class phases have been running their security/intent
audits on the frontmatter default rather than the intended tiered selection this whole session.

Separately (F4): `meta["gate_worker_model"]`/`meta["gate_worker_model_reason"]` (Row 4b) is computed
by `select_gate_worker_model` and stored in advisory `meta`, but `CLAUDE.build.md`'s dispatch line
reads only `a.model` (contractually `None` for `spawn-gate-worker`, since it's a verdict call, not
a full agent spawn today) — nothing anywhere consumes the advisory field. The review's own
conclusion: "the honest conclusion is that the selector shouldn't have been called at all, not that
its result should be parked in advisory meta." Decide and implement one of: (a) extend the action
grammar so `spawn-gate-worker` can legitimately carry a non-null `model` (coordinate with
INFRA-341, which is also touching gate-worker dispatch this phase), or (b) remove the
`select_gate_worker_model` call from Row 4b entirely until there's a real consumer, rather than
leaving a computed-and-discarded value in place.

**Decision, resolved by this spec (not left open for the builder): option (b).** Reasoning:

1. The `select_gate_worker_model` wiring note already on record (`model_selector.py:132-146`,
   `next_action.py:1691-1696`, `docs/architecture.md:1937-1948`) explains *why* option (a) was
   rejected by INFRA-333 itself: `validate_action` requires `model=null` for any action outside
   `_SPAWN_ACTIONS`, `spawn-gate-worker` is deliberately not a member, and promoting it "would be
   an action-grammar redesign" — INFRA-333 scoped that redesign out on purpose, and nothing in
   this story's narrower "wire the missing selectors, close the discarded-value gap" mandate
   changes that calculus.
2. The phase's own Ordering section frames INFRA-341 (not yet built) as the story that "may need
   to coordinate with INFRA-340 if the fix requires the action grammar to carry a real model for
   spawn-gate-worker" — i.e. INFRA-341's own livelock fix, if it turns out to need
   `spawn-gate-worker` promoted into `_SPAWN_ACTIONS` for reasons of its own (routing a verdict to
   a real consumer, not model selection), is the natural place for that grammar change to
   originate, with its own Ensures/Instructions and its own test coverage — not a second,
   loosely-related justification bolted onto this story.
3. Per the review's own words, leaving a selector call whose result is computed and then dropped
   is worse than not calling it at all: it looks wired from a `grep -n select_gate_worker_model`
   scan but produces no observable effect, which is exactly the kind of shape this phase's Goal
   names as a target ("half-implementation" in the CP-117 cold-eyes checklist: "is any branch
   unreachable, or any producer without its consumer?").
4. **What this means for INFRA-341:** if INFRA-341's fix does not require promoting
   `spawn-gate-worker` into `_SPAWN_ACTIONS`, this decision is final and no further model-selector
   work is needed for the gate-worker role. If INFRA-341's fix *does* require that promotion (e.g.
   because the real consumer it wires needs the model field for some other reason), INFRA-341 is
   free to re-introduce a `select_gate_worker_model` call at that point, in `_SPAWN_ACTIONS`-legal
   form — this story does not delete `select_gate_worker_model` itself (only its now-dangling call
   site), so that path remains open and untested by absence, not by a removed function.

## Requires

1. **INFRA-339 merged** (Fix or remove INFRA-316 pause-context). INFRA-339 already edited
   `next_action.py`'s Row 8/Row 9 region this phase (deleting `_check_context_pause`/
   `_read_state_for_context_pause`, bumping `SCHEMA_VERSION` 5→6, collapsing Row 8 back to an
   unconditional `spawn-builder` emission). Read the current file state fresh before editing —
   line numbers cited anywhere in this spec are approximate pointers from a post-INFRA-339 read
   and must be re-confirmed against the live file, not trusted as exact.
2. `model_selector.select_security_auditor_model(phase_class)` and
   `select_intent_reviewer_model(phase_class)` (both already implemented, tested, and used by the
   `flex_build.py select-security-auditor-model`/`select-intent-reviewer-model` CLI subcommands)
   as the selection functions to call — do not write new selection logic; call the existing
   functions.
3. `next_action.py`'s `_phase_class_for(phase_path)` helper (already implemented, used by Row 9's
   `checkpoint-docs` branch and Row 4b's now-to-be-removed `gate_worker_model` call) as the
   phase-class resolution mechanism — reuse it for `checkpoint-security`/`checkpoint-intent`
   rather than re-deriving `phase_class` a different way.
4. `docs/architecture.md`'s "Checkpoint-agent model selection" and "Gate-worker / docs-reviewer /
   spec-writer model selection" sections (§ Model selection, INFRA-333/AG-13) as the prior recorded
   state this story must bring back into alignment with the code once both fixes land.

## Ensures

1. **`checkpoint-security`'s model is resolved, not hardcoded.** In `next_action.py`'s Row 9
   (the `_next_step == CHECKPOINT_SECURITY` case), the emitted action's `model` field is the
   first element of `model_selector.select_security_auditor_model(phase_class)`, where
   `phase_class` is read via `_phase_class_for(_phase_path)` — exactly the same helper and
   call shape already used for `checkpoint-docs`. `model` is never `None` for this step
   regardless of `phase_class` (every row of `select_security_auditor_model`'s table returns a
   real model). Forbidden proxy: passing a hardcoded literal (`"opus"` or `"sonnet"`) instead of
   calling the selector — that reproduces F3's symptom under a different form (correct today,
   silently wrong the next time the table changes).
2. **`checkpoint-intent`'s model is resolved, not hardcoded.** Same as Ensures 1, for the
   `_next_step == CHECKPOINT_INTENT` case, calling `select_intent_reviewer_model(phase_class)`.
3. **`checkpoint-docs`'s existing wiring is unchanged.** The `_next_step == CHECKPOINT_DOCS`
   branch continues to call `select_docs_reviewer_model(phase_class)` exactly as INFRA-333 left
   it — this story adds two new branches, it does not restructure the existing one.
4. **`checkpoint-tag` still carries `model=None`.** `checkpoint-tag` is not a `_SPAWN_ACTIONS`
   member and this story does not change that; its emitted action's `model` field stays `None`.
5. **The `select_security_auditor_model`/`select_intent_reviewer_model` CLI subcommands
   (`flex_build.py select-security-auditor-model`/`select-intent-reviewer-model`) are unchanged**
   — they remain available for manual/debug invocation; this story adds a second, real call site
   in `next_action.py`, it does not remove or redirect the CLI path.
6. **`select_gate_worker_model` is no longer called from Row 4b.** The `spawn-gate-worker`
   branch of `resolve_next_action` (schema/auth judged-gate case) no longer imports or calls
   `model_selector.select_gate_worker_model`, and the emitted action's `meta` dict no longer
   contains `gate_worker_model` or `gate_worker_model_reason` keys under any input. The action's
   `model` field remains `None` (unchanged — it was already `None` before this story; this
   Ensures item is about the advisory `meta` keys, not the `model` field, which was never
   populated for this action).
   Forbidden proxy: keeping the selector call but setting the two `meta` keys to `None`/omitting
   them conditionally — the call and the keys must both be gone, not merely made falsy, so a
   `grep -n select_gate_worker_model skills/pairmode/scripts/next_action.py` returns zero hits.
7. **`select_gate_worker_model` itself is not deleted.** The function remains defined in
   `model_selector.py`, unchanged in behavior, with its existing direct unit tests (if any, in
   `tests/pairmode/test_model_selector.py`) still passing — this story removes a now-dangling
   call site, not the underlying selection logic, so a future story (INFRA-341, if its fix
   requires it) can re-wire it without re-deriving the selection table.
8. **Every existing test that asserted on the now-removed `gate_worker_model`/
   `gate_worker_model_reason` meta keys is updated, not deleted-and-forgotten.** Specifically (line
   numbers approximate, confirm against the live file per Requires 1):
   `TestResolveNextActionRow4Split.test_schema_tripped_emits_spawn_gate_worker` drops its
   `action["meta"]["gate_worker_model"]`/`gate_worker_model_reason` assertions (keeping its other
   assertions — `action["action"] == SPAWN_GATE_WORKER`, `model is None`,
   `validate_action(action) == []`, `"schema" in action["meta"]["gates_tripped"]`); and
   `TestResolveNextActionRow4Split.test_gate_worker_model_varies_with_phase_class` is either
   deleted outright (it exists solely to prove the now-removed meta varies with `phase_class`) or
   rewritten to assert the meta keys are *absent* for a `docs-only` phase — pick one and state
   which in the commit; either is acceptable as long as no assertion in the suite still expects
   `gate_worker_model`/`gate_worker_model_reason` to be present.
9. **New regression coverage for Ensures 1/2.** `tests/pairmode/test_next_action.py` gains tests
   (new test class or extending `TestCheckpointDocsModelWiring`, renamed or joined as
   appropriate) asserting: (a) `checkpoint-security` as the next uncompleted step resolves
   `action["model"] == "opus"` for a `production`-class phase (default) and `"sonnet"` for a
   `docs-only`-class phase, mirroring the existing `test_checkpoint_docs_step_carries_selected_model`
   / `test_checkpoint_docs_model_varies_with_pre_pr_phase_class` pattern; (b) `checkpoint-intent`
   as the next uncompleted step resolves `action["model"] == "sonnet"` for `production` and
   `"opus"` for `pre-pr`; (c) `validate_action(action) == []` for every new case (both actions are
   already `_SPAWN_ACTIONS` members, so this is a grammar-legality check, not a new grammar
   claim). The existing `test_checkpoint_security_step_still_carries_no_model` test (which asserts
   `action["model"] is None` for `checkpoint-security`) is renamed and rewritten to assert the
   resolved model instead — it can no longer claim "no model" once this story lands.
10. **Docs match code (F3 correction).** `docs/architecture.md`'s "Checkpoint-agent model
    selection" section is corrected to state that `next_action.py`'s Row 9 calls
    `select_intent_reviewer_model`/`select_security_auditor_model` directly (mirroring the
    `select_docs_reviewer_model` wiring description already there for `checkpoint-docs`),
    replacing the current wording that implies this was already true ("The orchestrator reads
    `phase_class` from the phase manifest frontmatter before spawning each checkpoint agent and
    passes the result...") when in fact, before this story, no such read/pass ever happened for
    these two roles.
11. **Docs match code (F4 resolution).** `docs/architecture.md`'s "Gate-worker / docs-reviewer /
    spec-writer model selection" section's `select_gate_worker_model` paragraph is rewritten to
    record, in the past tense, that the Row-4b advisory-meta call was removed by this story
    (INFRA-340) because nothing consumed it (per this story's Context § Decision), the function
    itself remains for a future real consumer, and `gate-worker.md.j2`'s frontmatter `model:
    sonnet` is once again the sole determinant of the gate-worker's model with no computed
    override in play (not merely "the authoritative default whenever the orchestrator does not
    pass an explicit override" — after this story, the orchestrator never passes one at all).
12. **`gate-worker.md.j2`'s comment is corrected to match.** The template comment block
    (`skills/pairmode/templates/agents/gate-worker.md.j2:7-17`) describing the advisory
    `meta["gate_worker_model"]` wiring is rewritten to state plainly that no model-selector call
    currently reaches this role's dispatch (removed by INFRA-340; see `model_selector.py`'s
    `select_gate_worker_model` docstring for why the function still exists) — not left describing
    a wiring path this story deletes.
13. **`.claude/agents/security-auditor.md`/`intent-reviewer.md` require no edit.** Their existing
    "model is always passed as an explicit per-call override by the orchestrator" comment
    (INFRA-241) becomes true as of this story rather than aspirational — confirm by reading both
    files during Instructions, but do not edit them; their content was already forward-looking-
    correct and this story's job is to make the code match it, not the other way around.
14. **No regression.** Full suite green without `-x` (project lesson: `-x` can mask a
    pre-existing failure): `uv run pytest tests/pairmode/ -q` (no `-x`).
15. **Grammar-unchanged.** No new action type, no `ACTIONS`/`_SPAWN_ACTIONS` membership change,
    no `SCHEMA_VERSION` bump — this story only changes which `model` value two already-legal
    `_SPAWN_ACTIONS` members resolve to, and removes a `meta` side-channel from an action whose
    `model` field was already `None`. `len(ACTIONS)` and `len(_SPAWN_ACTIONS)` are unchanged from
    their post-INFRA-339 values.

## Instructions

1. Read `next_action.py`'s current Row 9 block (search `_next_step == CHECKPOINT_DOCS` — do not
   trust the line numbers cited elsewhere in this spec, INFRA-339 already moved code in this
   region) and its current Row 4b block (search `SPAWN_GATE_WORKER` inside the
   `judged_tripped` branch). Confirm the live shape before editing either.
2. In Row 9: add an `elif _next_step == CHECKPOINT_SECURITY:` branch calling
   `model_selector.select_security_auditor_model(phase_class)` and an
   `elif _next_step == CHECKPOINT_INTENT:` branch calling
   `select_intent_reviewer_model(phase_class)`, both assigning into the same
   `_checkpoint_model` local the `CHECKPOINT_DOCS` branch already uses — reuse the existing
   `_phase_class_for(_phase_path)` call (hoist it above the `if/elif` chain so it is computed
   once for whichever step fires, rather than duplicated per branch). Update the block's
   preceding comment (currently describing `checkpoint-security`/`checkpoint-intent` as "carry no
   model yet — out of INFRA-333 scope") to describe the new wiring instead.
3. In Row 4b: delete the `from model_selector import select_gate_worker_model` import, the
   `_gate_worker_phase_class`/`_gate_worker_model`/`_gate_worker_model_reason` local
   computation, and the two `meta["gate_worker_model"]`/`meta["gate_worker_model_reason"]`
   assignments. Update the surrounding comment (currently explaining why the selector's result
   "cannot ride this action's model field" and is "surfaced as an advisory meta value only") to
   instead state that no selector is called here as of INFRA-340 — see this story's Context §
   Decision for why — leaving `model=None` exactly as it already was.
4. Update the module-level `_SPAWN_ACTIONS` comment block (the paragraph describing
   `spawn-gate-worker`'s exclusion and the one describing `checkpoint-security`/
   `checkpoint-intent`/`checkpoint-docs`) to match steps 2–3: the gate-worker paragraph drops its
   "surfaces it instead as advisory meta..." clause; the checkpoint paragraph drops "out of this
   story's scope" for security/intent and states all three checkpoint roles now resolve a real
   model via their respective selectors.
5. Add a new module-docstring entry for INFRA-340 (following this file's existing convention of
   appending a dated/storied changelog entry rather than editing prior entries in place — see the
   INFRA-333 and INFRA-339 entries immediately above where you're adding this one) recording: (a)
   Row 9 now resolves `checkpoint-security`/`checkpoint-intent` models via
   `select_security_auditor_model`/`select_intent_reviewer_model`, closing F3; (b) Row 4b no
   longer calls `select_gate_worker_model` — the selector remains defined but has no call site as
   of this story, closing F4 via the "remove" branch of the stub's option (a)/(b) choice, with a
   pointer to this story's ID for the reasoning.
6. In `model_selector.py`: update the module docstring's `select_gate_worker_model` entry and the
   function's own docstring (its "Wiring note (INFRA-333 Ensures 1)" paragraph) to record that
   INFRA-340 removed the Row 4b call site — the function is retained, unused, pending a future
   real consumer (possibly INFRA-341). Do not change the function's selection logic or its
   parameters/return shape.
7. Update `tests/pairmode/test_next_action.py` per Ensures 8–9: remove/rewrite the two
   gate-worker-meta assertions, add the new checkpoint-security/checkpoint-intent model-wiring
   tests, and rewrite `test_checkpoint_security_step_still_carries_no_model`.
8. Update `docs/architecture.md` per Ensures 10–11 (the "Checkpoint-agent model selection" and
   "Gate-worker / docs-reviewer / spec-writer model selection" sections under § Model selection).
9. Update `skills/pairmode/templates/agents/gate-worker.md.j2` per Ensures 12. Confirm
   `.claude/agents/security-auditor.md`/`intent-reviewer.md` need no edit (Ensures 13) — read
   both, do not edit.
10. Run the full suite without `-x` and confirm green (Ensures 14).

**Do not:** promote `spawn-gate-worker` into `_SPAWN_ACTIONS` or otherwise change the action
grammar (that is the explicitly-rejected option (a) — see Context § Decision; if INFRA-341 later
needs it, that is INFRA-341's own Ensures to write); delete `select_gate_worker_model` from
`model_selector.py` (Ensures 7); touch `CLAUDE.build.md` (its `model=a.model` dispatch line is
already generic across all `_SPAWN_ACTIONS` members and needs no code change — `checkpoint-
security`/`checkpoint-intent` reaching a real model is entirely a `next_action.py`-side fix); widen
this story into INFRA-339's Row 8 territory (already merged, per the phase Ordering note — this
story only touches Row 9/Row 4b).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -q 2>&1 | tail -40
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

Acceptance: green, no `-x` (project lesson: a known pre-existing failure must not be masked).
Reviewer negative checks: (a) `grep -n "gate_worker_model" skills/pairmode/scripts/next_action.py`
returns zero hits; (b) `grep -n "select_security_auditor_model\|select_intent_reviewer_model"
skills/pairmode/scripts/next_action.py` returns at least one hit each, inside the Row 9 block; (c)
no test in `tests/pairmode/test_next_action.py` still asserts `action["meta"]["gate_worker_model"]`
or `gate_worker_model_reason` is present.

## Out of scope

- Promoting `spawn-gate-worker` into `_SPAWN_ACTIONS` or otherwise redesigning the action grammar
  to let it carry a non-null `model` — explicitly rejected (option (a)); left for INFRA-341 to
  reopen only if its own livelock fix independently requires it.
- INFRA-341's gate-worker verdict-consumer wiring itself (the CRITICAL F8 livelock fix) — a
  separate story in this phase; this story only resolves the model-selector side of Row 4b.
- INFRA-339's Row 8/pause-context work — already merged (Requires 1); this story does not revisit
  it.
- Any change to `select_security_auditor_model`/`select_intent_reviewer_model`/
  `select_gate_worker_model`'s selection tables or tier assignments — this story wires existing,
  unchanged selectors to their real call sites; it does not re-litigate what model each phase
  class should resolve to.
- Removing or altering the `flex_build.py select-security-auditor-model`/
  `select-intent-reviewer-model` CLI subcommands — they remain valid for manual/debug invocation
  (Ensures 5).

## Evidence

Covered-contracts gate (INFRA-317): `primary_files:` names
`skills/pairmode/scripts/next_action.py`, which intersects the `covered_contracts` pair
`## Module structure::skills/pairmode/scripts/next_action.py` and the
`## Model selection::skills/pairmode/scripts/model_selector.py` entries in `docs/architecture.md`.
Read `docs/architecture.md` § Module structure's `next_action.py` bullet, § Model selection's
"Checkpoint-agent model selection" and "Gate-worker / docs-reviewer / spec-writer model selection"
subsections, and the source files (`next_action.py`, `model_selector.py`) in full before editing
any of them.

Divergence found (this story's own reason for existing): § Model selection's "Checkpoint-agent
model selection" subsection currently states the orchestrator "reads `phase_class` ... and passes
the result as the Agent tool's `model` parameter (same override mechanism as the reviewer model
selection)" for `checkpoint-security`/`checkpoint-intent` — this is not true of the code as it
stands (F3); the "Gate-worker" subsection describes a `meta["gate_worker_model"]` advisory-surface
wiring this story removes (F4). Both are corrected by Ensures 10–11 as part of this same story,
not filed as a separate CER, since closing the divergence is this story's entire purpose.

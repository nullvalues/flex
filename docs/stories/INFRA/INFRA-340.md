---
id: INFRA-340
rail: INFRA
title: Complete INFRA-333 model-selector wiring: checkpoint-security/checkpoint-intent model dispatch, gate_worker_model consumer-or-removal
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
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

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests

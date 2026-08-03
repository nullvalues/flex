---
id: INTENT-REVIEWER-000
role: INTENT-REVIEWER
title: The intent-reviewer — role ideology
status: draft
era: "004"
surfaces: [CLAUDE.build.md, procedure]
rails: [INFRA]
stories: []
---

## Narrative

The intent-reviewer is the only role in the loop with a genuinely wide-angle
lens: it compares what an entire phase actually built against what the phase doc
and era promised, and — since INFRA-315 — can also run *before* any story in the
phase is built, comparing the plan itself (each story's Ensures/Instructions)
against the phase's stated Goal. It is the closest thing this harness has to a
"does this still make sense" check, rather than a "did this satisfy its own
stated criteria" check — which is exactly why it's the natural home for
narrative-of-record alignment, and exactly why its current input contract
(deliberately, by design) can't yet do what this era wants of it.

## Always true

- Runs once per phase (post-build, cold-eyes) or once per phase pre-build
  (opt-in), never per-story and never mid-build.
- Reads only its five bounded inputs (phase doc, diff or story specs,
  `docs/architecture.md`, `docs/ideology.md`) — never accumulated state, never a
  live or partial transcript.
- Never blocks a checkpoint outright — produces findings and recommended doc
  edits for the orchestrator to apply, verdict `ALIGNED` or `FAIL`.

## Never

- Never touches code, never commits.
- Never widens its own input contract to "just this once" read something
  outside its five categories.

## Open gaps

- This is the role the operator's mid-build-steering idea reaches for first
  ("attach a second agent, probably intent-reviewer") — but its current
  bounded-input contract (DP1.3) explicitly forbids reading "prior-attempt
  transcripts" or "accumulated orchestrator state," which is precisely what a
  live or in-progress builder session is. Extending it to watch a build in
  progress isn't a wiring change, it's a change to what kind of role this is —
  worth deciding deliberately, not backing into.
- No live mechanism exists in this harness to let any agent observe another
  agent's session while it's running — subagents run to completion and return;
  nothing streams a builder's tool calls to a concurrent observer. The
  achievable version of "steer before the final product is out the door" is a
  staged checkpoint (builder pauses at a natural midpoint, an
  intent-reviewer-shaped pass reviews the partial plan/diff, builder resumes) —
  not a passive real-time watcher. That's a real architecture decision this era
  needs to make explicitly, not assume.
- Currently has no concept of "narrative alignment" at all — its
  `architecture.md`/`ideology.md` inputs are the closest analog, but neither
  substitutes for a role-narrative's job of expressing *why a human in that
  role would find this satisfying or broken*, which is a different question
  than "is this technically correct" or "is this consistent with stated
  conviction."

---
id: INFRA-358
rail: INFRA
title: Build the shared-suggestions-file mid-build steering mechanism (concurrent shadow-reviewer)
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/shadow-reviewer/procedure.md
  - skills/pairmode/templates/agents/shadow-reviewer.md.j2
touches:
  - skills/pairmode/skills/builder/procedure.md
  - skills/pairmode/scripts/bootstrap.py
  - .gitignore
  - tests/pairmode/test_bootstrap.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Idea #2 from the Devin/Windsurf remediation, refined by the operator: a second agent, dispatched
concurrently with the builder into the *same* worktree, largely passive, offering suggestions the
builder can take or leave — augmenting, not replacing, the reviewer's later independent check. This
does not require literal real-time transcript-watching (not supported by current tooling — no
mechanism exists for one agent to observe another's live session). It only requires two agents
independently polling a **shared file** at their own pace: the shadow-reviewer periodically reads
the worktree's current state and appends timestamped observations; the builder periodically checks
for new ones. This is ordinary file I/O, achievable with existing tools — no new SDK capability
needed.

This story builds the protocol and its static artifacts (a new agent role, its procedure, the
suggestions-file convention, and the builder-side polling instruction). Actually *dispatching* the
shadow-reviewer concurrently from the orchestrator's own loop is INFRA-359 — kept separate because
it touches `next_action.py`/`CLAUDE.build.md`, which this era deliberately sequences after Phase
117's own churn there settles.

## Requires

- None from earlier in this phase — independent of the narrative-propagation stories (INFRA-351
  through 357). Should build after Phase 117 has landed in full, per this phase's own Ordering
  (the dispatch-wiring half, INFRA-359, needs Phase 117's `next_action.py`/`CLAUDE.build.md` to be
  stable — build this story first if convenient, but do not merge INFRA-359 before Phase 117 is
  checkpointed).

## Ensures

1. A new procedure skill exists at `skills/pairmode/skills/shadow-reviewer/procedure.md` and a
   matching thin agent shell template at
   `skills/pairmode/templates/agents/shadow-reviewer.md.j2` — following the same
   template/procedure split every other agent role uses (see `docs/architecture.md`'s
   INFRA-335-documented "new-agent-type definition-of-done" checklist for the shape; this story
   covers items 1-2 of that checklist — template and procedure — not items 3-5, dispatch/model
   selection/escalation, which are INFRA-359's job).
2. The shadow-reviewer's procedure defines: a fixed suggestions-file location
   (`<worktree>/.pairmode-suggestions.md`), an append-only write discipline (never overwrite,
   each entry timestamped), a poll cadence expressed as "after observing N new commits or file
   changes in the worktree since last check" (not wall-clock sleep, since the shadow-reviewer has
   no reliable wall-clock signal of the builder's pace), and an explicit stop condition: stop
   polling and return once a `story-<ID>` commit appears in the worktree's git log, or after a
   bounded maximum number of poll cycles, whichever comes first.
3. `.pairmode-suggestions.md` is added to `.gitignore` — it must never be committed, never appear
   in a story's diff, and never be treated by the reviewer as part of the story's own artifact.
4. The builder's own procedure (`skills/pairmode/skills/builder/procedure.md`) gains exactly one
   new instruction: at natural checkpoints (after completing each `## Ensures` item is the natural
   granularity — not after every tool call), check `.pairmode-suggestions.md` for content added
   since it last checked (track a simple high-water-mark, e.g. byte length previously seen) and
   consider it. The builder is never required to act on a suggestion — this is advisory, and the
   builder's own `BUILD-RESULT` is unaffected by whether it did.
5. `bootstrap.py` scaffolds the new agent shell the same way every other role's shell is scaffolded
   (add to `AGENT_FILES`, INFRA-351's established pattern — do not hand-duplicate the scaffold
   logic).
6. Full `tests/pairmode/` suite green.

**Forbidden proxy:** a shadow-reviewer that writes suggestions the builder has no instruction to
ever read — this reproduces the exact GATE-WORKER livelock shape (Phase 117, INFRA-341): a verdict
computed and never consumed. Ensures 4 is the load-bearing half of this story, not an afterthought
to Ensures 1-3.

## Instructions

1. Design the shadow-reviewer's procedure first, in writing, before touching the builder's
   procedure — get the protocol right (what it reads, what it writes, when it stops) as its own
   coherent document, the same way every other procedure skill in this project is self-contained.
2. Keep the builder-side change minimal and surgical — one instruction at one natural checkpoint,
   not a rewrite of the builder's own procedure. This story is itself a demonstration of INFRA-357's
   proportionality principle; don't let it balloon.
3. Confirm `.gitignore`'s existing patterns and add `.pairmode-suggestions.md` cleanly alongside
   them (check whether `.companion/` or similar already has a comparable pattern to match style
   against).
4. Register the new agent shell in `bootstrap.py`'s `AGENT_FILES` (INFRA-351's list) so it
   scaffolds identically to the other ten.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green; a fixture test confirms the new agent shell scaffolds at bootstrap. Deeper
integration coverage (does a live builder+shadow-reviewer pair actually exchange a suggestion
correctly) is INFRA-360's job, not this story's — this story proves the static artifacts are
correct and scaffold-able, not that a live concurrent run behaves as designed.

## Out of scope

- Actually dispatching the shadow-reviewer concurrently from the orchestrator loop — INFRA-359.
- `ACTION_SUBAGENT_TYPE`/resolver-action/model-selector wiring for the new role — INFRA-359.
- End-to-end integration testing of a live concurrent run — INFRA-360.

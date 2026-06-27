---
id: RELEASE-004
rail: RELEASE
title: "Additive contract + state-ownership table (DP4, DP7)"
status: complete
phase: "HARNESS001-ante1"
story_class: methodology
primary_files:
  - docs/architecture.md
touches:
---

# RELEASE-004 — Additive contract + state-ownership table (DP4, DP7)

## Context

This story LANDS ON `main` (which stays 0.2.x). It writes the compatibility
guarantees of Era 003 into a DURABLE methodology surface so the additive-window
rules and the state-ownership map survive context compaction and are reviewable
by the reviewer subagent against a written reference.

The surface is `docs/architecture.md`: add a dedicated section titled
**"Era 003 additive contract"** (a new `##`-level section; place it after the
existing `## Pairmode design` material and before `## Companion data files`, or
adjacent to the existing `### Pairmode non-negotiables`, wherever it reads
coherently). This section records three things, all from the settled agreements:

- **(a) The four-point additive contract (DP4)** — verbatim semantics.
- **(b) The state-ownership table (DP7)** — single writer per shared surface
  during the additive window.
- **(c) The effort.db ≠ context-control invariant (DP7)** — verbatim
  semantics, the load-bearing separation.

It also flags the codified comingling at `CLAUDE.build.md:320-326` as FLAGGED
FOR REMOVAL AT HARNESS006. This story does **not** remove the comingling
(out of scope — the removal lands at HARNESS006 / the gate rewrite).

## Acceptance criteria

1. `docs/architecture.md` gains a new section "Era 003 additive contract"
   (heading text contains "Era 003 additive contract").

2. **(a)** The section states the four-point additive contract scoped to the
   window `HARNESS001-main … HARNESS005-main`:
   1. Existing `flex_build.py` CLI surface frozen — no rename/removal/flag-change
      to existing subcommands or their output contracts; additions (notably
      `next-action`) allowed; consolidation of old CLIs only at/after the flip.
   2. Resolver is pure-read — `next-action` reads `state.json`, `effort.db`, the
      index, story status, attempt counters; writes nothing authoritative (any
      cache is disposable and never read back by the orchestrator). Orchestrator
      stays sole writer.
   3. Fleet-facing surface frozen on `main` — consumer-facing templates
      (`CLAUDE.build.md.j2`, `agents/*.md.j2`), global hooks, and agent files do
      not change on `main` until the flip; these evolve freely on `harness`.
   4. Guard test — a `tests/pairmode/` test snapshots the 0.2.x CLI command/flag
      surface and asserts it stays a superset through HARNESS005 (cross-reference
      RELEASE-003); rebaselined at the flip.

3. **(b)** The section contains a state-ownership table mapping each shared-state
   surface to its single writer during the additive window, with the resolver as
   pure-read on all of them. Rows (at minimum):
   - `state.json` `context_*` (context tokens) → orchestrator hooks
     (`post_tool_use.py` / `session_start.py`), frozen.
   - active story (`state.json`) → orchestrator (`story_context.py`).
   - `effort.db` → orchestrator (`record_attempt.py` / effort recorder).
   - `attempt_counter.json` (attempt counters) → orchestrator.
   - story `status` frontmatter → orchestrator.
   - permission files → orchestrator.
   - era/phase/story index → orchestrator.
   - commits + tags → reviewer / orchestrator.
   - `next-action` resolver → **reads all of the above; writes nothing.**

4. **(c)** The section states the effort.db ≠ context-control invariant
   verbatim in semantics:
   - **effort.db** = retrospective cost from subagent `<usage>` blocks (tokens
     spent in disposable subagent contexts). Inputs: model selection, guardrail,
     rollups, cost display. **Never an input to a context-headroom or clear-seam
     decision.**
   - **context-control** = the orchestrator's own live window occupancy
     (`context_current_tokens` + the `expected_step_tokens` window-growth
     constant). This is the **sole** basis for headroom / clear-seam decisions.
   - Rationale captured: subagent tokens never entered the orchestrator's
     window, so summing effort.db to estimate headroom counts tokens that were
     never there.

5. The section explicitly names the codified comingling at
   `CLAUDE.build.md:320-326` (the `threshold − N` vs `story-cost-estimate`
   effort.db median comparison, source `flex_build.py:834`) as **FLAGGED FOR
   REMOVAL AT HARNESS006**, and states that this story does NOT remove it.

6. The section cross-references the settled agreements doc
   (`docs/agreements/HARNESS001-ante1.md`, DP4 and DP7) as the authority.

## Implementation guidance

- Edit only `docs/architecture.md`. Add the new `## Era 003 additive contract`
  section; do not restructure existing sections.
- Transcribe contract/invariant text from the agreements doc DP4 and DP7 —
  this is faithful transcription, not new design.
- The state-ownership table is a markdown table: columns `Surface | Sole writer
  (additive window) | Resolver access`. The last column is "read-only" for
  every row.
- For the comingling flag, quote the line reference `CLAUDE.build.md:320-326`
  and `flex_build.py:834` exactly, and state the correct mechanism already
  exists separately at `CLAUDE.build.md:696-750`
  (`context_current_tokens + expected_step_tokens` vs threshold). Make clear the
  removal is HARNESS006 scope, not this story.

## Tests

Methodology story — no test file expected (documentation change to
`docs/architecture.md` only). Verification by grep:

```bash
# Section exists
grep -n "Era 003 additive contract" docs/architecture.md

# Four-point contract anchors present
grep -nE "next-action|pure-read|superset|frozen" docs/architecture.md | head

# State-ownership table present (resolver reads, writes nothing)
grep -nE "state-ownership|writes nothing|read-only" docs/architecture.md | head

# effort.db != context-control invariant present
grep -nE "effort.db|context-control|expected_step_tokens|never an input" docs/architecture.md | head

# Comingling flagged, not removed
grep -n "320-326" docs/architecture.md
# And confirm the comingling itself is UNCHANGED in CLAUDE.build.md (out of scope):
grep -n "story-cost-estimate" CLAUDE.build.md

# Test suite passes unchanged
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Removing or editing the comingled advisory at `CLAUDE.build.md:320-326`
  (lands at HARNESS006 / the gate rewrite).
- Re-deriving `expected_step_tokens` for thin-harness return-block growth
  (HARNESS006 / Phase G, CER-053).
- Building the guard test itself (that is RELEASE-003); this story only
  references it.

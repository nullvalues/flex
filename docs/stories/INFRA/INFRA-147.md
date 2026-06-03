---
id: INFRA-147
rail: INFRA
title: "README and docs era-001 close"
status: planned
phase: "57"
primary_files:
  - README.md
  - docs/brief.md
touches:
  - docs/eras/001-initial.md
---

# INFRA-147 — README and docs era-001 close

## Context

Era 001 of the flex project ends with Phase 57. Its defining work: evolving Anchor into
the /flex:pairmode methodology — context management at 150k limits, persistent refocus to
system-of-record, and systematic shifts of deterministic processes to code. The result is
a build loop that runs largely hands-free in auto mode. The next era opens with the
observability SPA.

The README and brief.md do not yet reflect this framing. The README leads with a neutral
product description; the brief.md's `Accepted Tradeoffs` section still describes
`pre_tool_use.py` as a single-delegate (CER-027 only), not the Phase 55 dual-delegate.

## Acceptance criteria

### README.md

1. Add an era-001 accomplishment statement as a banner or introductory paragraph
   immediately before or replacing the current "Status" section. Tone: confident, not
   marketing. Captures what the era achieved and why it matters. Use this framing as the
   anchor (exact wording may be polished):

   > **Era 001 — pairmode foundation (complete)**
   > An Anchor evolution focused on `/flex:pairmode` context management: enforcing 150k
   > context limits per build, persistent refocus to system of record, and systematic
   > shifts of deterministic processes to code. The result is a largely hands-free
   > auto-mode build loop. Era 002 opens with a planned observability SPA to replace the
   > companion sidebar.

2. Update the "Status" line from "Alpha. Under active development." to something that
   reflects era-001 maturity: e.g. "Production-ready for solo developers. Core workflows
   are stable and self-hosted on this repo. API and scaffold format may change with
   notice."

3. Verify the "The build loop" section mentions the context budget check step (it should
   say something about the 150k token gate between stories). If absent, add it as step 2.5
   or a note after step 2: "Between stories, verify context budget (< 150k tokens) before
   spawning the next builder."

4. No other structural changes — the README's existing sections are well-organized.

### docs/brief.md

1. Update the `Accepted Tradeoffs` section — `Hook-pipe-sidebar separation` item.
   The current text says: "Exception (CER-027): `pre_tool_use.py` is a thin delegate
   to a skill module (`context_budget.py`)..."
   Update to reflect Phase 55 dual-delegate: `pre_tool_use.py` now delegates to both
   `context_budget.py` (CER-027: context budget) and `scope_guard.py` (Phase 55:
   story file-scope enforcement). Both are documented exceptions to the pure-relay rule.

2. No other changes to brief.md — the rest is current.

### docs/eras/001-initial.md

1. If the era doc has a `status: active` field, update it to `status: closing` or add a
   closing note under a `## Close` or `## Era summary` section:
   > Era 001 closes at Phase 57. Defining accomplishment: pairmode foundation — context
   > limits, system-of-record enforcement, deterministic process codification. Era 002
   > begins with the observability SPA (Phase 58+).
   Only add/update — do not restructure the era doc.

## Out of scope

- Updating docs/ideology.md (operator-intent document, not changed here)
- Updating docs/reconstruction.md (would require a full reconstruct run)
- Any changes to SKILL.md or PAIRMODE.md (already updated in Phase 56)
- Formal era transition via `era_transition.py` (that is a separate orchestrator step
  when Phase 57 checkpoints)

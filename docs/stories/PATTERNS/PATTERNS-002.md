---
id: PATTERNS-002
phase: '48'
rail: PATTERNS
story_class: methodology
status: planned
primary_files:
  - docs/patterns/operations-orchestration/phase-spec-pause-resume.md
touches: []
---

# PATTERNS-002 — Draft "Phase Spec with Formal Pause/Resume" pattern doc (NP-2)

See phase spec: `docs/phases/phase-48.md` § NP-2.

## Acceptance criterion

`docs/patterns/operations-orchestration/phase-spec-pause-resume.md` exists and follows
the cloudnirvana/open-patterns catalog template verbatim. All mandatory sections are
filled in with real project content. "What Broke in Practice" and "Security Implications"
are both filled in. No placeholder text remains. No flex-internal jargon appears without
an inline definition.

## Pattern identity

**Name:** Phase Spec with Formal Pause/Resume
**Category:** Operations & Orchestration
**One-line intent:** Phase docs function as living specs with an explicit story state
machine (`planned → in_progress → complete | deferred`) so that multi-phase initiatives
never lose continuity across forks, context clears, or agent handoffs.
**Also Known As:** Living Phase Manifest, Story State Machine, Formal Spec Continuity

## Source of truth for the rule

The canonical rule statement lives in the flex global `CLAUDE.md` under
`## Phase continuity`. Fetch it:
```
cat /home/nullvalues/.claude/CLAUDE.md
```
Quote the rule sections verbatim in the "How It Works" section of the pattern doc.
The rule covers: fork time ceremony (Deferred stories section, Parent phase backpointer,
status → deferred), resume time ceremony (new phase references originating phase,
new story IDs), and the checkpoint gate (a phase cannot be tagged with silently
abandoned `planned` stories).

## What broke (cite these real incidents)

- **Phase 47 context clear (2026-05-29, CER-027):** At 155k tokens the context was
  cleared mid-phase. Without a formal resume marker in the phase doc, the next session
  would have had no canonical record of which tracks were spec'd, which had running
  decisions in flight, and what the recommended continuation sequence was. The resume
  marker written to `docs/phases/phase-47.md` before the clear was what made the
  second session possible. Read the "Resume marker" section in `docs/phases/phase-47.md`
  to see what information it preserved.
- **Silently abandoned stories (pre-pattern):** Before the formal Deferred stories
  discipline, stories that ran out of time at phase end would simply not appear in the
  next phase. Reviewers could not tell "was this done?" from "was this dropped?" When
  re-discovered in a later cold-eyes review, the remediation required re-reading months
  of phase history to reconstruct intent.
- **Fork without backpointer:** When Phase 48 was forked from Phase 47's open scope
  (to capture the open-patterns publication work), the `**Parent phase:**` backpointer
  and `## Deferred stories` section were required. Without them, Phase 47's historical
  record would claim all its planned stories were complete (they weren't — Phase 48's
  scope was surfaced during Phase 47's review but deferred to a new phase). See
  `docs/phases/phase-48.md` line 1–12.

## Required catalog template sections

Fetch the template:
`gh api repos/cloudnirvana/open-patterns/contents/PATTERN-TEMPLATE.md --jq '.content' | base64 -d`

Key sections with content guidance:

**Pattern in 60 Seconds:** Problem = multi-phase initiatives silently lose stories when
agents move fast and context is cleared. Insight = a phase doc with a story state machine
is the durable authority that survives any session boundary. Key structure = three-column
table (State / Meaning / Who Sets It) covering planned/in_progress/complete/deferred.
What broke = the Phase 47 context clear scenario.

**Classification:** Category: Operations & Orchestration. Difficulty: Intermediate.

**Motivation:** Concrete scenario — an agent is building Phase 5 of a 3-month initiative.
Midway through, the context window fills. A new session starts. Without the resume marker
and state machine, the agent asks "what's left?" and gets an incomplete answer from
memory. With the pattern: the agent reads the phase doc, sees every story's state,
reads the resume marker, and continues from an exact point.

**Applicability — Use when:**
- A project spans multiple sessions or multiple months
- Multiple stories exist in a phase (more than one story)
- Context clears are possible (any long-running agentic project)
- Work may need to be forked into a new phase mid-flight

**Applicability — Do NOT use when:**
- Single-story hotfix phases where the story IS the phase
- Throwaway exploratory sessions with no deliverable
- Projects where all stories complete in one session (no continuity needed)

**Structure:** Mermaid stateDiagram-v2 showing story state machine:
`planned → in_progress → complete` (pass path)
`planned → in_progress → deferred` (fork path)
`deferred → planned` (resume in new phase)
Plus a separate graph showing phase fork ceremony.

**Participants:** Phase doc / Story file / Checkpoint tag / CER backlog / Orchestrator /
Deferred stories section / Parent phase backpointer.

**How It Works:** Number the steps:
(1) Every story begins in `planned` state in the phase manifest.
(2) When a story starts building, orchestrator sets `in_progress`.
(3) On reviewer PASS: story moves to `complete`.
(4) On fork: orchestrator adds `## Deferred stories` to originating phase, sets
    unbuilt stories to `deferred`, new phase opens with `**Parent phase:**` line.
(5) On resume: new phase lists deferred stories as `planned` with new IDs, originating
    phase doc is the historical record for original IDs.
(6) Checkpoint gate: before tagging, orchestrator verifies all `planned` stories are
    either `complete` or formally `deferred`.

**Consequences — Benefits:** Any session can resume from exact state. Fork decisions are
audit-trailed. Cold-eyes reviews can verify "was this done or dropped?" History is
preserved in the originating phase doc.

**Consequences — Liabilities:** Requires discipline to maintain the state machine.
Overhead per story state transition. Phase docs grow large in long projects.

**Consequences — What Broke in Practice:** Phase 47 context clear + silently abandoned
stories (see above).

**Security Implications:** Phase docs are internal project records. No external data.
Failure mode: phase doc and code diverge (doc says complete, code was not committed).
Mitigation: checkpoint gate requires BUILD GATE (test suite) to pass before tagging.

**Known Uses:** flex project — used across Phases 10–47, 7 downstream projects.
Global policy in `~/.claude/CLAUDE.md` "Phase continuity" section.

**Related Patterns:**
- `runbook-driven-agent-cadence`: both separate spec from execution; this pattern's
  runbook is the phase doc itself
- `checkpoint-gated-autonomy`: this pattern's checkpoint gate IS the autonomy gate for
  phase completion
- `builder-reviewer-sub-agent-loop` (NP-1): the loop operates within phases governed
  by this pattern

**Metadata — Contributor:** David Hague, flex project (david@halfhorse.com)
**Metadata — License:** CC BY 4.0

## Output

Create `docs/patterns/operations-orchestration/phase-spec-pause-resume.md`
with the completed pattern doc. Create the directory if it does not exist.
Do not modify any other file.

---
id: PATTERNS-005
phase: '48'
rail: PATTERNS
story_class: methodology
status: complete
primary_files:
  - docs/patterns/production-readiness/conceptual-rebuild-completeness.md
touches: []
---

# PATTERNS-005 — Draft "Conceptual Rebuild Completeness" pattern doc (NP-5)

See phase spec: `docs/phases/phase-48.md` § NP-5.

## Acceptance criterion

`docs/patterns/production-readiness/conceptual-rebuild-completeness.md` exists and follows
the cloudnirvana/open-patterns catalog template verbatim. All mandatory sections filled in
with real content. "What Broke" and "Security Implications" filled in. No placeholder text.

## Pattern identity

**Name:** Conceptual Rebuild Completeness
**Category:** Production Readiness
**One-line intent:** Every new database table introduced by a phase must answer "where
does a human manage this data?" before the phase is checkpointed — ensuring that schema
changes always have an operator surface, not just a migration.
**Also Known As:** Schema-to-UI Parity Rule, Management Surface Gate, UI Completeness Gate

## Source of truth for the rule

The canonical rule statement lives in the flex global `CLAUDE.md` under
`## Conceptual rebuild completeness`. Fetch it:
```
cat /home/nullvalues/.claude/CLAUDE.md
```
Quote the rule sections verbatim in the "How It Works" section of the pattern doc.
The rule covers: every new table must have an answer to "where does a human manage this?";
three documented exceptions (append-only audit log, pure junction table, cron-output cache);
each exception must be explicitly named and justified in the spec.

Also read `docs/phases/phase-47.md` to see the Pre-story schema gate as it is
implemented in `CLAUDE.build.md`. The gate is the mechanical enforcement of this rule.

## What broke (cite these incidents)

- **"We'll build the UI later" decay pattern:** The canonical failure mode is a team
  that introduces three new tables in Phase N, intending to build admin views in Phase N+2.
  Phase N+2 never comes — other priorities intervene — and the tables accumulate data that
  only a DBA can inspect. Operators start running raw SQL queries for routine data management.
  The pattern forces this decision at schema introduction time, not "later."
- **Exception-without-acknowledgment:** Before the rule was formalized, append-only
  audit log tables (like `assistant_events`) were sometimes introduced without explicitly
  noting the exception. This left phase reviewers unable to distinguish "the UI story is
  missing by oversight" from "the UI story is missing because the table is append-only."
  The pattern requires explicit exception acknowledgment — absence is not acceptable.
- Read `docs/phases/phase-47.md` §CLAUDE.build.md "Pre-story schema gate" section for
  the mechanical implementation — the gate that checks for this before each story build.

## Three documented exceptions (cite exactly)

These three exception categories must appear verbatim in the pattern doc, because they
are the negotiated boundaries of the rule:

1. **Append-only audit/event log tables** (e.g., `assistant_events`) — observable via
   logs or a future log viewer. No human-editable fields.
2. **Pure junction tables** whose both parent tables already have full management UIs.
3. **Cron-output cache tables** that are regenerated on a schedule; no human-editable
   fields exist.

In all three cases: the exception must be explicitly noted in the spec. Silently omitting
the UI story without an acknowledged exception is not acceptable.

## Required catalog template sections

Fetch the template: `gh api repos/cloudnirvana/open-patterns/contents/PATTERN-TEMPLATE.md --jq '.content' | base64 -d`

Key sections:

**Pattern in 60 Seconds:** Problem = phases ship schema changes that no human can inspect
without a DB console. Insight = schema changes are features; a feature is incomplete until
it has an operator surface. Key structure = decision tree (new table → UI story in this
phase? / documented exception? / BLOCK). What broke = the "UI later" decay pattern.

**Classification:** Category: Production Readiness. Difficulty: Intermediate.
Adjacent: `system-hygiene-for-agentic-systems` (both gate production-readiness — this
pattern is the schema parity specialization).

**Motivation:** Concrete scenario: an AI agent introduces a new `recommendations` table
to persist cross-session suggestions. The phase ships. Three months later, operations
asks "how many recommendations have been generated this week?" The answer requires a DB
console query — there is no admin view, no API endpoint, no dashboard widget. The
oncall developer writes a one-off SQL query at 2am. With the pattern: the recommendations
table would have required a management view story before the phase could be checkpointed.

**Applicability — Use when:**
- A phase introduces any new persistent database table, collection, or index
- The system will have ongoing production data that operators need to inspect or manage
- You want to enforce UI completeness before phase checkpoint, not after

**Applicability — Do NOT use when:**
- The new schema object qualifies for one of the three documented exceptions (cite them)
- The project has no UI or operator surface at all (pure API/CLI — then the equivalent
  gate is "does the CLI expose management commands?")

**Structure:** Mermaid flowchart:
`Phase story introduces new table` →
`Scan remaining stories in phase for management surface` →
  Found: `Proceed normally` →
  Not found: `Check story spec for documented exception` →
    Exception documented: `Proceed normally` →
    No exception: `PRE-STORY BLOCK: add UI story or document exception`

**Participants:** Phase spec / Pre-story schema gate (orchestrator check) / Management
surface story / Exception acknowledgment in spec / Checkpoint gate (verifies no
undocumented schema-without-UI before tagging).

**How It Works:**
(1) Before building any story, orchestrator reads the story spec: does it introduce a
    new persistent schema object?
(2) If no: skip gate, proceed to build.
(3) If yes: scan remaining stories in phase for a management surface (route, page,
    CLI command, component where humans can read/create/update/delete without a DB console).
(4) If management surface story exists: proceed.
(5) If no management surface: check story spec for explicit exception (one of three).
(6) If exception documented: proceed (note in checkpoint report).
(7) If no management surface and no exception: BLOCK. Report. Require operator to add a
    management UI story or document an exception before building.

**Consequences — Benefits:** Every schema change ships with an operator surface. "We'll
do it later" is prevented at the gate. Exception acknowledgments are audit-trailed in
the spec. Phase completeness is verifiable without reading every migration.

**Consequences — Liabilities:** Adds overhead for phases with new schema (one extra check
per story). May feel onerous for simple lookup/config tables. Exception creep: if exceptions
are granted too liberally, the gate loses meaning.

**Consequences — What Broke in Practice:** "UI later" decay + exception-without-acknowledgment
(described above).

**Security Implications:** The gate is a process check, not a security control. No sensitive
data involved. Failure mode: gate bypassed via exception abuse. Mitigation: exceptions require
explicit justification in the spec — a reviewer can audit the reasoning.

**Known Uses:** flex project — enforced since Phase 40 via Pre-story schema gate in
`CLAUDE.build.md`. Global policy in `~/.claude/CLAUDE.md` "Conceptual rebuild completeness"
section.

**Related Patterns:**
- `system-hygiene-for-agentic-systems`: both gate production-readiness; this pattern is
  the schema specialization
- `phase-spec-pause-resume` (NP-2): the checkpoint gate (step 5 in that pattern) also
  checks for this pattern's compliance before tagging
- `builder-reviewer-sub-agent-loop` (NP-1): the orchestrator runs this gate before
  spawning the builder — it is a pre-build check, not a review-time check

**Metadata — Contributor:** David Hague, flex project (david@halfhorse.com)
**Metadata — License:** CC BY 4.0

## Output

Create `docs/patterns/production-readiness/conceptual-rebuild-completeness.md`
with the completed pattern doc. Create the directory if needed.
Do not modify any other file.

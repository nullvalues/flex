---
id: PATTERNS-003
phase: '48'
rail: PATTERNS
story_class: methodology
status: complete
primary_files:
  - docs/patterns/operations-orchestration/cer-backlog-living-phases.md
touches: []
---

# PATTERNS-003 — Draft "CER Backlog + Living Backlog Phases" pattern doc (NP-3)

See phase spec: `docs/phases/phase-48.md` § NP-3.

## Acceptance criterion

`docs/patterns/operations-orchestration/cer-backlog-living-phases.md` exists and follows
the cloudnirvana/open-patterns catalog template verbatim. All mandatory sections filled in
with real content. "What Broke in Practice" and "Security Implications" filled in. No
placeholder text. No flex jargon without definition.

## Pattern identity

**Name:** CER Backlog + Living Backlog Phases
**Category:** Operations & Orchestration (or Production Readiness — prefer Ops & Orchestration
to stay adjacent to `eod-reconciliation`)
**One-line intent:** A quadrant triage log (Do Now / Do Later / Do Much Later / Do Never)
where every finding from any source files into one of four buckets and is never deleted —
resolved findings stay with a resolution note — so teams stop re-discovering the same
issues quarterly.
**Also Known As:** Quadrant Finding Log, Living Engineering Backlog, CER (Cold-Eyes Review)
Backlog

**CER definition (required in-doc):** "CER" stands for Cold-Eyes Review — a structured
adversarial review session where a reviewer reads the project without prior context, as
if seeing it for the first time. Findings from CERs, security audits, operator
observations, and intent reviews all file into the same backlog.

## Real data to cite

The flex CER backlog at `docs/cer/backlog.md` contains 28+ real entries from Phases 12–47
spanning security audits, intent reviews, and operator observations. Read the full backlog
to find concrete examples for the pattern doc.

Specific incidents to cite:
- **CER-027 (Phase 47):** Surfaced an enforcement gap — context budget was LLM-attention-based.
  Filed as "Do Now." Resolved in Phase 47 INFRA-127/128/129. The backlog entry persists
  with a resolution note. This is the canonical "Do Now → resolved with audit trail" example.
- **CER-009 → CER-020 (Phases 17 and 28):** CER-009 partially resolved; CER-020 was a
  direct follow-on finding in the same code area (hooks pipe path validation). The backlog
  is what connected these two findings across 11 phases. Without it, CER-020 would have
  been re-discovered from scratch.
- **Backlog grooming policy** (from global `CLAUDE.md`): "Whenever a cold-eyes review
  generates a list of Do Now fixes, also read the project's backlog phases and identify
  any items whose forcing function has arrived." Quote this policy verbatim in the pattern doc.
  Fetch it: `cat /home/nullvalues/.claude/CLAUDE.md` § Living backlog phases.

## Required catalog template sections

Fetch the template: `gh api repos/cloudnirvana/open-patterns/contents/PATTERN-TEMPLATE.md --jq '.content' | base64 -d`

Key sections:

**Pattern in 60 Seconds:** Problem = findings not actionable right now get dropped silently;
teams re-discover the same issues quarterly. Insight = a quadrant log with a no-delete
policy means findings survive the moment and can be revisited when their forcing function
arrives. Key structure = four-quadrant table (Do Now / Do Later / Do Much Later / Do Never)
with the "never delete, always resolve" rule. What broke = team re-discovered CER-009's
cousin issue as CER-020 eleven phases later because the original entry was resolved without
noting the adjacent gap.

**Classification:** Category: Operations & Orchestration. Difficulty: Intermediate.

**Motivation:** Concrete scenario — a security auditor finds five issues. Three are
actionable now. Two are real but low-priority. Without a living backlog: the two
low-priority findings go into a Slack message, which gets archived. Six months later a
new audit re-discovers them. With the pattern: all five go into the backlog, the two
low-priority ones are triaged to "Do Later," and at every subsequent review the
orchestrator checks whether their forcing function has arrived.

**Applicability — Use when:**
- Projects span multiple phases or months
- Security audits or cold-eyes reviews generate more findings than can be acted on now
- You want a history of every finding including resolved ones
- You need to explain to a future reviewer why a known issue wasn't fixed

**Applicability — Do NOT use when:**
- Single-session throwaway projects
- Finding count is small enough to track in the phase doc itself (fewer than ~5 total)

**Structure:** Mermaid graph TD showing:
Finding arrives (any source) → triage to quadrant → Do Now (immediate) / Do Later
(important, not urgent) / Do Much Later (nice to have) / Do Never (rejected with reason).
Also show: cold-eyes review event → read backlog → identify "forcing function arrived"
items → surface for promotion.

**Participants:** CER Backlog file / Orchestrator / Security auditor / Intent reviewer /
Operator / Quadrant triage rule / Resolution note.

**How It Works:**
(1) Every finding from any review session gets a unique ID (CER-NNN) and files into
    one of four quadrants.
(2) Finding never deleted — resolution note is appended in-place when resolved.
(3) "Do Now" findings block the next phase checkpoint if unresolved.
(4) At every cold-eyes review: read the backlog, identify items whose forcing function
    has arrived (related to current diff, now low-effort, etc.), surface for operator
    decision. Never pull forward automatically — always ask.
(5) "Do Never" entries record the rejection reason so future reviewers don't re-raise
    the same point.

**Consequences — Benefits:** No finding is ever lost. Re-discovery is eliminated. The
backlog is auditable history. Checkpoint gates can reference it. Future reviewers see
what was considered and why.

**Consequences — Liabilities:** Backlog grows indefinitely. Requires discipline to triage
rather than file everything as "Do Now." May feel bureaucratic for small projects.

**Consequences — What Broke in Practice:** CER-009/CER-020 re-discovery pattern (cited above).

**Security Implications:** Backlog is internal project record. No secrets. Failure mode:
backlog grows stale and nobody reads it. Mitigation: "at every cold-eyes review, read
the backlog" policy makes reading automatic, not voluntary.

**Known Uses:** flex project — 28+ CER entries across Phases 12–47. Quadrant structure
at `docs/cer/backlog.md`.

**Related Patterns:**
- `eod-reconciliation`: both reconcile against evidence; CER backlog reconciles against
  code findings, eod-reconciliation reconciles against operational events
- `escalation-chain-with-sla`: both surface stalls; CER backlog's "Do Now" quadrant is
  an implicit escalation mechanism
- `phase-spec-pause-resume` (NP-2): the checkpoint gate checks for open "Do Now" entries
  before tagging — the two patterns compose

**Metadata — Contributor:** David Hague, flex project (david@halfhorse.com)
**Metadata — License:** CC BY 4.0

## Output

Create `docs/patterns/operations-orchestration/cer-backlog-living-phases.md`
with the completed pattern doc. Create the directory if needed.
Do not modify any other file.

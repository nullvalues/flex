# flex — Phase 48: Open-patterns publication initiative

← [Phase 47: Pair-mode methodology consolidation](phase-47.md)

**Status:** complete — all 7 stories shipped 2026-06-01; PR #4 open at
[cloudnirvana/open-patterns](https://github.com/cloudnirvana/open-patterns/pull/4);
NP-6 held pending open PR #3 resolution. Tag: `cp48-open-patterns-publication`.

**Parent phase:** Phase 47 (no deferred stories from 47 land here — this is net-new
scope surfaced during the 2026-05-29 review of
[cloudnirvana/open-patterns](https://github.com/cloudnirvana/open-patterns)).

## Goal

Contribute flex's novel methodology patterns to the public open-patterns catalog
(CC-BY 4.0). The catalog has 22 published + 1 in-progress patterns spanning
Trust & Governance, Agentic Architecture, Ops & Orchestration, RAG & Knowledge,
Production Readiness, Data Quality, Security & Compliance, and Cost & Operations.

Several flex methodology pieces have no catalog twin and would be load-bearing
additions. This phase captures those, drafts pattern docs against the catalog's
template, and submits via the catalog's `CONTRIBUTING.md` flow.

**Why this phase exists at all:** the patterns are real and battle-tested; the
catalog explicitly invites practitioner contributions; the cost of publishing
is mostly write-up (no code). Doing this *after* Phase 47 also means CER-027
enforcement is shipped, which is itself a concrete instantiation of one of the
patterns we'd be publishing — better story for the contribution.

## Catalog template reference

Pattern docs in the catalog follow a consistent structure (verified against
`patterns/agentic-architecture/files-over-databases.md` and
`patterns/agentic-architecture/context-lifecycle-management.md`):

- One-line intent (blockquote)
- **Pattern in 60 Seconds** — problem, insight, table, "What broke when we got
  this wrong"
- Classification table (Category, Difficulty, Also Known As, Related Patterns)
- Motivation / Problem in Detail
- Applicability (Use when / Do NOT use when)
- Structure (often with Mermaid diagrams)
- Participants table
- How It Works (numbered, with code/config examples)
- Consequences (Benefits / Liabilities / What broke / What survived)
- Implementation Notes (Variations, Common Pitfalls, Migration Path)
- Security Implications (Attack Surface, Data Sensitivity, Failure Modes, Mitigations)
- Known Uses
- Related Patterns
- Metadata + Revision History

All six flex pattern drafts must adopt this template.

## Novel patterns inventory

Each is a candidate for one published pattern in the catalog. Listed with the
catalog category that would receive it.

### NP-1: Builder/Reviewer Sub-Agent Loop
**Category:** Agentic Architecture (or new sub-area: Spec-Driven Agent Loops)

Closed-loop spec→build→review→re-spec where the spec is the *only* source of
acceptance criteria. Builder and reviewer are separate sub-agents reading from
the same phase doc + story file; reviewer's only authority is the spec, not
opinion. Loop exits when reviewer signs off the BUILD GATE.

What breaks without it: agents drift to taste-based code review, scope creep,
or silent acceptance of half-finished work.

Catalog adjacencies: `checkpoint-gated-autonomy` (this pattern's loop *is* the
gate), `hub-and-spoke-orchestration` (orchestrator routes between builder and
reviewer). Distinct because catalog has no closed-loop QA mechanism.

### NP-2: Phase Spec with Formal Pause/Resume
**Category:** Operations & Orchestration

Phase docs as living specs with an explicit story state machine:
`planned → in_progress → complete | deferred`. Forks across phases use a
`## Deferred stories` section + `**Parent phase:**` back-pointer, never silent
abandonment. Checkpoint gate refuses to tag a phase with silently-abandoned
`planned` stories.

What breaks without it: multi-phase initiatives lose continuity across forks;
unbuilt stories disappear from the manifest; reviewer can't tell "was this
done?" from "was this dropped?"

Catalog adjacencies: `runbook-driven-agent-cadence` (both separate spec from
execution), `checkpoint-gated-autonomy` (this is the *spec* side of the gate).
Distinct because catalog has no multi-phase state machine.

### NP-3: CER Backlog + Living Backlog Phases
**Category:** Production Readiness (or Ops & Orchestration)

Continuous Engineering Review backlog as a quadrant log (Do Now / Do Later /
Do Much Later / Do Never). Findings from any source — security audit, intent
review, operator observation, cold-eyes review — file into one of the four
quadrants and never get deleted (resolved findings stay with a resolution note).
"Backlog grooming on every cold-eyes review" pulls forward items whose forcing
function has arrived.

What breaks without it: findings get dropped silently when not actionable
*right now*; teams re-discover the same issues quarterly; the spec/build/review
loop has no place to park things it shouldn't act on yet.

Catalog adjacencies: `eod-reconciliation` (both reconcile against evidence),
`escalation-chain-with-sla` (both surface stalls). Distinct because catalog has
no living-backlog discipline.

### NP-4: Per-Phase Effort.db with Seeded Prior
**Category:** Cost & Operations

Per-phase median token-cost estimation in SQLite (`effort.db`) for prospective
budgeting, with a shipped cross-project seed file (`effort_baseline.json`,
~688 attempts across 7 projects) as the cold-start prior. Switches from prior
to per-phase median once ≥N attempts exist. Used by the context-budget hook
to decide when "next step probably won't fit" before the step starts.

What breaks without it: budget decisions use stale or arbitrary token
estimates; new phases have no baseline; cross-project learning never compounds.

Catalog adjacencies: `context-cost-control` (this is the *estimation* primitive
that cost-control patterns can build on), `context-lifecycle-management`
(decides when checkpointing should happen). Distinct because catalog patterns
assume static thresholds; this provides dynamic, learned ones.

### NP-5: Conceptual Rebuild Completeness
**Category:** Production Readiness

Rule: every new database table introduced by a phase must answer "where does
a human manage this data?" *before* the phase is checkpointed. If no existing
route covers it, a management UI story lands in the same phase spec — not the
backlog. Three documented exceptions (append-only audit logs, junction tables
where both parents already have CRUD, cron-output cache tables), each requiring
explicit spec-level acknowledgment.

What breaks without it: phases ship with new schema and no operator surface;
data accumulates in tables no human can inspect without a DB console; "we'll
build the UI later" becomes never.

Catalog adjacencies: `system-hygiene-for-agentic-systems` (both gate
production-readiness). Distinct because catalog has no schema-to-UI parity rule.

### NP-6 (candidate, possibly fold into NP-4 or own pattern): Source of Truth over Recall
**Category:** Agentic Architecture or Data Quality

Sub-pattern observed inline in catalog's `context-lifecycle-management.md`:
"Recall tells you *where* to look. The file tells you *what's true*." Flex
embodies this rigorously — `state.json`, `effort.db`, phase docs, story files
are all canonical; agents must read them rather than infer from context. The
catalog itself flags this as worth standalone treatment (see CLM doc, line
266 area). Decision deferred to phase build time: contribute as its own
pattern, fold into NP-4, or skip (catalog author may publish it).

## Stories

| ID | Title | Status | Notes |
|----|-------|--------|-------|
| PATTERNS-001 | Draft Builder/Reviewer Sub-Agent Loop pattern doc | complete | NP-1; uses catalog template; include the BUILD GATE failure mode CER-028 surfaced as a "what broke" case |
| PATTERNS-002 | Draft Phase Spec with Formal Pause/Resume pattern doc | complete | NP-2; cite flex's global CLAUDE.md "Phase continuity" section as the canonical rule statement |
| PATTERNS-003 | Draft CER Backlog + Living Backlog Phases pattern doc | complete | NP-3; reference real CER entries 001-028 as the production data |
| PATTERNS-004 | Draft Per-Phase Effort.db with Seeded Prior pattern doc | complete | NP-4; depends on Phase 47 INFRA-127 shipping (the seed file is built there) |
| PATTERNS-005 | Draft Conceptual Rebuild Completeness pattern doc | complete | NP-5; cite the global CLAUDE.md "Conceptual rebuild completeness" section |
| PATTERNS-006 | Decide on NP-6 ("Source of Truth over Recall") — own pattern, fold, or skip | complete | Coin-flip at build time; check whether catalog has published it by then — Decision: A — catalog has no equivalent pattern; CLM doc explicitly flags this sub-pattern as worth standalone treatment (line 266); flex has 3 distinct production incidents with "what broke" stories not covered by NP-1 or NP-4 |
| PATTERNS-007 | Submission package: PR against cloudnirvana/open-patterns | complete | Follow catalog's `CONTRIBUTING.md`; update `patterns.yaml`; assign IDs |

**Dependency:** PATTERNS-004 depends on Phase 47 INFRA-127 being checkpointed
(the seed file `effort_baseline.json` and the dynamic-median behavior are the
load-bearing implementation that the pattern doc references).

**Story sequencing:** PATTERNS-001..003, 005 in any order; PATTERNS-004 after
Phase 47 ships; PATTERNS-006 before PATTERNS-007; PATTERNS-007 last.

## Working principles

1. **Catalog template fidelity.** Each pattern doc must adopt the catalog's
   section structure verbatim. Differences become noise in the contribution PR.
2. **"What broke" is mandatory.** Catalog patterns lead with production failure
   stories. Each flex pattern draft must cite a real CER entry, a real phase
   incident, or a real operator observation. No theoretical patterns.
3. **No flex-internal jargon without definition.** Terms like "rail,"
   "pairmode," "story," "CER" need short inline definitions on first use.
4. **Cite the catalog's adjacent patterns.** Every flex pattern's "Related
   Patterns" section names which catalog patterns it composes with or
   distinguishes from. This is how readers of the catalog will navigate.
5. **CC-BY 4.0 by default.** Match the catalog's license. Attribute to the
   project (flex) and the operator who shipped the work.
6. **Do not auto-pull related backlog items into this phase.** Per global policy,
   surface adjacent backlog items at build time and let the operator decide.

## Open questions (resolve at build time, not now)

- **Which pattern to submit first?** → Resolved: bundled PR (#4) with all 5 patterns.
- **Do we need a flex-side "Cloud Nirvana attribution" sign-off?** → Resolved: CC BY 4.0,
  attributed to David Hague / flex project (david@halfhorse.com). No separate sign-off required.
- **Should NP-1 (Builder/Reviewer Loop) propose a new category?** → Resolved: Agentic
  Architecture (no new category proposed — consistent with catalog convention).
- **Sub-pattern NP-6 disposition.** → Resolved: see PATTERNS-006 (Decision A) and
  `## Submission` section for hold rationale (pending open PR #3 resolution).

## Follow-on scope (not in this phase)

- Patterns flex could *adopt* from the catalog (read but not build): inspect
  `agentic-identity-lifecycle` (per-capability trust + kill switches),
  `memory-vs-persistence-boundary` (graduation rules), `eod-reconciliation`
  (end-of-phase reconciliation against evidence). These get their own CER
  entries at adoption time, not phase-48 stories.
- Hub-and-spoke variant: catalog's pattern assumes many workspaces with a hub
  reading across; flex runs a hub-and-spoke *within one project workspace*.
  This is a published-pattern variant worth a paragraph in the contribution PR.

## Resume marker

When Phase 47 is checkpointed and the operator is ready to pick this up:
1. Re-read both pattern docs (catalog has likely added more by then).
2. Re-recon each NP against the current catalog — patterns may have been
   published in the interim that subsume some NPs.
3. Spec PATTERNS-001 first (lowest dependency, cleanest "what broke" story).
4. Build stories in the sequence above.

Tag (on ship): `cp48-open-patterns-publication`

## Submission

**PR:** https://github.com/cloudnirvana/open-patterns/pull/4 — "Add 5 flex methodology patterns for spec-driven agentic development"
**Submitted:** 2026-06-01
**Patterns submitted:** NP-1 (builder-reviewer-sub-agent-loop), NP-2 (phase-spec-pause-resume), NP-3 (cer-backlog-living-phases), NP-4 (per-phase-effort-seeded-prior), NP-5 (conceptual-rebuild-completeness)
**Held:** NP-6 (source-of-truth-over-recall) — pending resolution of PR #3 in cloudnirvana/open-patterns ("Canonical Source Over Recall" by nsmedia-io, RAG/Knowledge domain). Submit NP-6 as a follow-on PR after PR #3 merges or closes.

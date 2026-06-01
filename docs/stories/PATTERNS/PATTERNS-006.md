---
id: PATTERNS-006
phase: '48'
rail: PATTERNS
story_class: methodology
status: complete
primary_files:
  - docs/patterns/agentic-architecture/source-of-truth-over-recall.md
touches:
  - docs/phases/phase-48.md
  - docs/patterns/agentic-architecture/source-of-truth-over-recall.md
---

# PATTERNS-006 — Decide on NP-6 ("Source of Truth over Recall") disposition

See phase spec: `docs/phases/phase-48.md` § NP-6.

## Acceptance criterion

A decision has been made for NP-6: one of (A) own pattern, (B) fold into NP-4, (C) skip.
The decision is recorded in `docs/phases/phase-48.md` PATTERNS-006 row (status → complete)
with a one-line rationale appended to the Notes column.

If decision is (A): `docs/patterns/agentic-architecture/source-of-truth-over-recall.md`
exists and follows the catalog template verbatim, all mandatory sections filled in.
Add the file to primary_files in this story frontmatter before building.

If decision is (B) or (C): no new pattern file is created. The decision note in the
phase doc is the only output. `docs/patterns/agentic-architecture/` is not created unless
PATTERNS-001 already created it.

## Decision criteria

Check the catalog at build time:

```bash
gh repo view cloudnirvana/open-patterns 2>&1 | head -5
gh api repos/cloudnirvana/open-patterns/git/trees/main?recursive=1 \
  --jq '.tree[] | select(.type=="blob") | .path' | grep patterns/
```

Then decide:

**Choose (A) own pattern** if:
- The catalog has NOT published a "source of truth over recall" or equivalent pattern
  since Phase 48 was scaffolded (2026-05-29)
- The pattern can be written with a "what broke" story that is specific to flex/agentic
  systems (not just a restatement of general software hygiene)
- The catalog's `context-lifecycle-management.md` still references this as worth
  standalone treatment (re-check at build time)

**Choose (B) fold into NP-4** if:
- The sub-pattern's main expression is already covered well by the effort.db seeded
  prior pattern (NP-4), and treating it separately would be redundant
- The contribution story is weaker as a standalone (less "what broke" material)

**Choose (C) skip** if:
- The catalog has already published this pattern (or a near-equivalent)
- The pattern cannot be written with a real "what broke" story that isn't also
  covered by NP-1/NP-4 already

## Pattern identity (if choosing A)

**Name:** Source of Truth over Recall
**Category:** Agentic Architecture (or Data Quality)
**One-line intent:** Agents must read canonical source files rather than inferring from
context — recall tells you where to look; the file tells you what's true — preventing
the class of errors where agents act on stale or confabulated state.
**Also Known As:** Canonical Source Discipline, File-Authoritative Recall, Anti-Hallucination
Source Anchor

**Real incidents to cite (if choosing A):**
- `context-lifecycle-management.md` in the catalog (line ~266) references this sub-pattern
  explicitly as worth standalone treatment — re-read that section at build time via:
  `gh api repos/cloudnirvana/open-patterns/contents/patterns/agentic-architecture/context-lifecycle-management.md --jq '.content' | base64 -d`
- Operator observations from flex build sessions: agents reporting "the story is complete"
  by recalling a prior commit message rather than reading `git log` or the story file
- Agents citing `docs/architecture.md` from memory with stale line numbers or removed
  sections, when a direct `Read` of the file would have shown the current state

## Catalog adjacency check (required before deciding)

Read the current `context-lifecycle-management.md` from the catalog. If the file has been
updated to include a "source of truth over recall" section since 2026-05-29, that shifts
the decision toward (C) skip or (B) fold.

## Output

Primary output: the decision note in `docs/phases/phase-48.md` PATTERNS-006 row.
Secondary output (only if A): the pattern doc at
`docs/patterns/agentic-architecture/source-of-truth-over-recall.md`.

The story is complete when the decision is recorded, regardless of which path is chosen.

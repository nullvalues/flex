---
id: PATTERNS-007
phase: '48'
rail: PATTERNS
story_class: methodology
status: planned
primary_files: []
touches:
  - docs/patterns/agentic-architecture/builder-reviewer-sub-agent-loop.md
  - docs/patterns/agentic-architecture/source-of-truth-over-recall.md
  - docs/patterns/operations-orchestration/phase-spec-pause-resume.md
  - docs/patterns/operations-orchestration/cer-backlog-living-phases.md
  - docs/patterns/cost-operations/per-phase-effort-seeded-prior.md
  - docs/patterns/production-readiness/conceptual-rebuild-completeness.md
  - docs/patterns/production-readiness/conceptual-rebuild-completeness.md
---

# PATTERNS-007 — Submission package: PR against cloudnirvana/open-patterns

See phase spec: `docs/phases/phase-48.md` § PATTERNS-007.

**Prerequisites:** PATTERNS-001 through PATTERNS-006 must be complete before building
this story. All draft pattern files in `docs/patterns/` must exist. The PATTERNS-006
decision must be recorded (add the NP-6 file to the touches list above if it was created).

## Acceptance criterion

A pull request exists against the `cloudnirvana/open-patterns` repository with all
draft pattern docs from `docs/patterns/` organized into the catalog's directory structure.
The PR follows the catalog's `CONTRIBUTING.md` submission format. The PR URL is reported
to the orchestrator.

## Build instructions

### Step 1 — Read CONTRIBUTING.md and PR conventions

```bash
gh api repos/cloudnirvana/open-patterns/contents/CONTRIBUTING.md --jq '.content' | base64 -d
```

Also check recent merged PRs to understand whether the maintainers prefer one PR per
pattern or a bundled PR:

```bash
gh pr list --repo cloudnirvana/open-patterns --state merged --limit 10
```

If recent PRs are per-pattern (each PR adds one pattern): open one PR per pattern doc.
If recent PRs are bundled: open one PR with all patterns.

The orchestrator should resolve this before building — if ambiguous, prefer bundled
(one PR) for the initial submission and let the maintainer request splits.

### Step 2 — Fork and clone the repo

```bash
gh repo fork cloudnirvana/open-patterns --clone --remote
cd open-patterns
git checkout -b flex-methodology-patterns
```

### Step 3 — Copy pattern files to correct catalog directories

Map each draft file to its catalog directory:

| Draft file (flex/docs/patterns/) | Target (open-patterns/patterns/) |
|-----------------------------------|----------------------------------|
| `agentic-architecture/builder-reviewer-sub-agent-loop.md` | `agentic-architecture/builder-reviewer-sub-agent-loop.md` |
| `operations-orchestration/phase-spec-pause-resume.md` | `operations-orchestration/phase-spec-pause-resume.md` |
| `operations-orchestration/cer-backlog-living-phases.md` | `operations-orchestration/cer-backlog-living-phases.md` |
| `cost-operations/per-phase-effort-seeded-prior.md` | `cost-operations/per-phase-effort-seeded-prior.md` |
| `production-readiness/conceptual-rebuild-completeness.md` | `production-readiness/conceptual-rebuild-completeness.md` |
| `agentic-architecture/source-of-truth-over-recall.md` | `agentic-architecture/source-of-truth-over-recall.md` (if PATTERNS-006 chose A) |

Copy from the flex project root, not from a clone. Example:
```bash
cp /mnt/work/flex/docs/patterns/agentic-architecture/builder-reviewer-sub-agent-loop.md \
   patterns/agentic-architecture/
```

### Step 4 — Update patterns.yaml

Check if the catalog has a `patterns.yaml` index:
```bash
gh api repos/cloudnirvana/open-patterns/contents/patterns.yaml --jq '.content' | base64 -d | head -20 2>/dev/null || echo "No patterns.yaml found"
```

If `patterns.yaml` exists: add entries for each new pattern following the existing format.
If it does not exist: skip this step (the catalog may not maintain a manual index).

### Step 5 — Commit and open PR

```bash
git add patterns/
git commit -m "Add flex methodology patterns: builder-reviewer loop, phase spec, CER backlog, effort prior, rebuild completeness"
```

Open the PR with a description that follows the catalog's conventions:
- Brief description of the pattern set and where it was tested
- Link to the flex project (or note it is an internal project)
- Confirm all patterns meet the quality bar (real implementations, "What Broke" filled,
  Security Implications filled, vendor-neutral)

```bash
gh pr create \
  --repo cloudnirvana/open-patterns \
  --title "Add 5 flex methodology patterns for agentic software development" \
  --body "$(cat <<'EOF'
## Summary

Five battle-tested methodology patterns from the flex project — a Claude Code plugin for
structured agentic software development. These patterns emerged from ~47 build phases
across 7 downstream projects and are documented with real failure modes (CER backlog entries),
not theoretical scenarios.

**Patterns submitted:**
- **Builder/Reviewer Sub-Agent Loop** (Agentic Architecture) — closed spec→build→review loop
  where reviewer authority is limited to the spec, eliminating taste-based drift
- **Phase Spec with Formal Pause/Resume** (Operations & Orchestration) — story state machine
  (planned/in_progress/complete/deferred) enabling continuity across context clears and forks
- **CER Backlog + Living Backlog Phases** (Operations & Orchestration) — quadrant triage log
  where findings are never deleted, only resolved — eliminating quarterly re-discovery
- **Per-Phase Effort.db with Seeded Prior** (Cost & Operations) — cross-project token-cost
  seed file that bootstraps per-phase estimation, solving the new-project cold-start problem
- **Conceptual Rebuild Completeness** (Production Readiness) — gate requiring every new
  database table to have an operator surface before phase checkpoint

**Quality bar:**
- All patterns have "What Broke in Practice" filled with real CER entries or operator observations
- All patterns have "Security Implications" filled
- All patterns are vendor-neutral (reference Claude/SQLite as examples, not endorsements)
- All patterns have been in production use across 7 projects

**Attribution:** David Hague, flex project — CC BY 4.0
EOF
)"
```

### Step 6 — Report PR URL

Output the PR URL from `gh pr create` output and report it to the orchestrator.

## Notes

- Do not push to any branch in the main flex repository — all git operations for this
  story are against the forked cloudnirvana/open-patterns repo.
- If the fork already exists (from a previous attempt): `gh repo fork` will reuse it.
  Just create a fresh branch.
- If the maintainer requests splits (one PR per pattern): open separate PRs in a follow-on
  session. The draft files in `docs/patterns/` remain the source of truth.
- The `patterns.yaml` update (Step 4) is best-effort — if the catalog does not maintain one
  or the format is unclear, skip it and note in the PR description.

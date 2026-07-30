---
id: RELEASE-071
rail: RELEASE
title: Campaign close: full-fleet DP8 gate, supersede RELEASE-043..057, clean stale seeds, mark phase-97 complete
status: complete
phase: "106"
auth_gated: false
schema_introduces: false
touches:
  - docs/stories/RELEASE/RELEASE-071.md
  - docs/phases/phase-106.md
  - docs/phases/phase-97.md
  - docs/phases/index.md
---

<!-- SPEC-WRITER NOTE (frontmatter): `touches:` is block-style per CER-115.
     This story's write targets span flex (phase-97.md, index.md, this file,
     phase-106.md) plus six external repos for seed-doc removal — see
     § Cross-repo scope boundaries. Same orchestrator-level execution model
     as RELEASE-068/069/070: no story worktree, no builder subagent. -->

## Context

Campaign close for phase 106. Three real pieces of work, surfaced by a
fresh fleet-wide `fleet_discovery.py --no-snapshot` sweep and a stale-seed
scan across the fleet (2026-07-29) — this is not a pure status-flip story.

**1. DP8 denominator changed since phase 106's Goal was written.** The
Goal states "16/16 projects at pairmode 0.3.0." Since then, RELEASE-069
decommissioned base56 from pairmode entirely (by explicit operator
directive — "easier to re-seed later than migrate a fully-developed
product") — base56 no longer registers as a pairmode candidate at all
(`fleet_discovery` silently omits it once `.companion/` is gone). The
fleet denominator is now **15 projects**, not 16. Fresh sweep result:

| binding | count | detail |
|---|---|---|
| both (clean, 0.3.0) | 14 | aab, asp, caddy, coherra, forqsite, forqsite.help, halfhorse, lumin, meander, pokus, radar, rockue, stackabid, ud |
| version only | 1 | cora — `signal1_absent_reason: "foreign-checkout"`, hooks resolve to `/mnt/work/flex` (dev checkout) not the release channel; recorded as a RELEASE-070 finding, INFRA-319 candidate, not fixed here |

DP8 verdict for this campaign: **14/15 clean, 1/15 partial (cora, known
finding, not blocking), 1 project out of scope by design (base56,
decommissioned)** — not a literal "16/16," and the Goal language is stale
relative to the campaign's own later decisions (RELEASE-069). This story
does not rewrite phase 106's Goal text (historical record); it records the
true final disposition here and in the phase-106 stories-table row.

**2. Stale seed docs.** Phase 97's original resolution (before phase 106
existed) was to seed each fleet project with a proposed-phase file
(`docs/phases/phase-proposed-pairmode-030-migration-*.md`) so migration
would resume in *that project's own session* later. Phase 106 superseded
that plan by driving the migrations centrally instead. A 2026-07-29 scan
(`ls docs/phases/phase-proposed-pairmode-030-migration*.md` + `git
ls-files` per project) found six already-migrated projects still carrying
this now-moot, git-tracked seed doc:

| Project | Path |
|---|---|
| forqsite.help | `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md` |
| halfhorse | `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md` |
| lumin | `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md` |
| meander | `docs/phases/phase-proposed-pairmode-030-migration-20260722.md` (no `-001` suffix — meander's is named slightly differently) |
| pokus | `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md` |
| rockue | `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md` |

base56's copy of this file was already removed by RELEASE-069. The
remaining nine fleet projects (aab, asp, caddy, coherra, cora, forqsite,
radar, stackabid, ud) never had this file or don't currently carry it —
verified absent, no action needed there.

**3. Supersede RELEASE-043..057 and close phase-97.** Phase 97's Stories
table currently lists RELEASE-043 through RELEASE-057 (15 per-project
fleet-migration stubs) as `deferred`, and phase-97's own row in
`docs/phases/index.md` reads `deferred` ("paused 2026-07-24, phase-99
sequenced first... resumes after cp-99"). Phase 106 is the actual
resolution of that deferral — RELEASE-063 through RELEASE-070 (this
campaign's real stories) did the work RELEASE-043..057 stubbed out,
project-by-project, under a cleaner numbering scheme. RELEASE-058 (the
original DP8 pre-fold gate) was already separately waived in phase-97
itself (`## DP8 gate override`, 2026-07-23, operator override, verdict
BLOCK 8/16 at that time) — unrelated to and not reopened by this story.

**Operator decision confirmed (2026-07-29):** proceed with all six seed-doc
removals (git rm + commit + push, one commit per repo).

## Cross-repo scope boundaries

**Writable — inside `/mnt/work/flex`:**
- `docs/stories/RELEASE/RELEASE-071.md` — `## Evidence` section only.
- `docs/phases/phase-106.md` — RELEASE-071's status row.
- `docs/phases/phase-97.md` — RELEASE-043..057 status cells (`deferred` →
  `superseded`), with a one-line pointer to the phase-106 story that
  actually closed each; a closing note referencing this story.
- `docs/phases/index.md` — phase-97's row, `deferred` → `complete`.

**Writable — inside each of six external repos** (forqsite.help,
halfhorse, lumin, meander, pokus, rockue), **only**:
- `git rm` the one stale seed-doc path listed above, one commit per repo,
  subject not naming a RELEASE-0NN ID, pushed to `origin/main`.

**Read-only — never modified:**
- All nine other fleet projects (aab, asp, caddy, coherra, cora, forqsite,
  radar, stackabid, ud) and base56 — no write of any kind.
- Any file in the six seed-removal repos other than the one named seed doc.
- `/mnt/work/flex-harness` (release channel) — read-only, used only for
  `fleet_discovery.py --no-snapshot` invocations.
- Phase-97's own historical narrative (Goal, Deferred-stories rationale,
  DP8-override section) — this story adds a closing pointer, does not
  rewrite phase-97's history.

**Forbidden outright:**
- Building or reopening RELEASE-058 (DP8 gate tooling) — remains waived,
  out of scope.
- Touching cora's hook-path binding (INFRA-319 territory, phase 114) —
  record only.
- Any product-code change in any of the fleet projects.

## Requires

- RELEASE-063 through RELEASE-070 all `complete` in phase-106.md (verify
  before proceeding).
- Each of the six seed-removal repos is a clean git tree with no in-flight
  build before its commit (`git status --porcelain` empty, no
  `.pairmode-worktrees/`).

## Ensures

- Fresh `fleet_discovery.py --no-snapshot` sweep across all 15 current
  fleet candidates recorded in Evidence, with the 14/15-clean, 1/15-partial
  (cora) breakdown and base56's absence explained.
- All six seed-removal repos: the named seed doc no longer exists on disk
  or in `git ls-files`; each repo has exactly one new commit for this
  removal, pushed; `git status --porcelain` clean after.
- The nine non-seed fleet projects and base56: zero file changes (spot
  checked, not modified).
- `docs/phases/phase-97.md`: RELEASE-043..057 status cells changed from
  `deferred` to `superseded`, each with a one-line pointer to the
  phase-106 story (RELEASE-063..070) that actually resolved that project
  (or, for any of the 15 with no direct phase-106 counterpart, a note
  explaining its disposition — verify the RELEASE-043..057 → project
  mapping against phase-106's actual six built/verified stories plus the
  five that completed before this closeout, e.g. RELEASE-063..067, and
  record exactly which of the 15 remain unaccounted for, if any, rather
  than assuming full 1:1 coverage).
- `docs/phases/index.md`: phase-97's row status changes from `deferred` to
  `complete`.
- `docs/phases/phase-106.md`: RELEASE-071's row changes from `draft` to
  `complete`.
- `## Evidence` section appended to this story file recording every
  command, its real output, and the final RELEASE-043..057 disposition
  table.
- `git -C /mnt/work/flex status --porcelain` after this story shows only
  this story file plus the three phase-doc edits.

## Instructions

1. Verify RELEASE-063..070 all `complete` in `docs/phases/phase-106.md`.
2. Run a fresh `fleet_discovery.py --no-snapshot` sweep across all 15
   current fleet candidates (aab, asp, caddy, coherra, cora, forqsite,
   forqsite.help, halfhorse, lumin, meander, pokus, radar, rockue,
   stackabid, ud); confirm base56 no longer registers. Record the
   binding/version breakdown.
3. For each of the six seed-removal repos: confirm clean tree, `git rm`
   the named seed doc, commit (subject not naming a RELEASE-0NN ID),
   push. Verify `git status --porcelain` clean after.
4. Spot-check the nine non-seed fleet projects and base56 are untouched
   (`git status --porcelain` clean, no unexpected diff).
5. Build the RELEASE-043..057 → phase-106-story disposition table:
   for each of the 15 stub stories, name which phase-106 story (or which
   other mechanism, e.g. RELEASE-069's decommission for base56, RELEASE-070's
   hand-migration record for any overlap) actually resolved it, or record
   it as still genuinely open if none did. Do not assume coverage — verify
   against phase-106.md's actual Stories table.
6. Edit `docs/phases/phase-97.md`'s Stories table: flip each of
   RELEASE-043..057 from `deferred` to `superseded`, with the pointer from
   step 5. Add a short closing note (not a full history rewrite) referencing
   RELEASE-071/phase-106 as the actual resolution.
7. Edit `docs/phases/index.md`: phase-97's row, `deferred` → `complete`.
8. Write `## Evidence` in this story file (append, don't touch anything
   above it) with every command and its real output, the fleet-sweep
   breakdown, the six-repo removal confirmations, and the disposition
   table from step 5. Set this file's frontmatter `status:` to `complete`.
9. Edit `docs/phases/phase-106.md`'s RELEASE-071 row to `complete`.
10. Commit all flex-side changes (this story file, phase-106.md,
    phase-97.md, index.md) in flex with a `spec(RELEASE-071): ...`
    prefixed subject, per this project's commit-prefix convention, and
    push (`origin main --tags`).

## Tests

No flex-side unit test — acceptance is the recorded verification commands
in `## Evidence` (fresh fleet sweep output, six-repo git log/status
before/after, the RELEASE-043..057 disposition table, phase-97/index.md
diffs).

## Out of scope

- RELEASE-058 (DP8 gate tooling) — remains waived per phase-97's own
  2026-07-23 override; not reopened.
- Fixing cora's foreign-checkout hook binding — INFRA-319/phase 114
  territory, record only.
- Any change to the nine non-seed fleet projects or base56.
- Re-litigating or rewriting phase-97's historical narrative sections
  (Goal, Deferred stories rationale, DP8 gate override) — only the
  Stories-table status cells and a short closing pointer are added.

## Evidence

**Execution model:** orchestrator-level with operator present, per this story's own execution model.

### Step 1 — Precondition check
RELEASE-063 through RELEASE-070 all confirmed `complete` in `docs/phases/phase-106.md`'s Stories table before proceeding.

### Step 2 — Fresh fleet-wide sweep
`fleet_discovery.py --no-snapshot` run against all 15 current fleet candidates (aab, asp, caddy, coherra, cora, forqsite, forqsite.help, halfhorse, lumin, meander, pokus, radar, rockue, stackabid, ud) plus base56:

```
scanned candidates that registered: 15
  aab -> both 0.3.0
  asp -> both 0.3.0
  caddy -> both 0.3.0
  coherra -> both 0.3.0
  cora -> version 0.3.0 (foreign-checkout — hooks resolve to /mnt/work/flex dev checkout, not the release channel)
  forqsite -> both 0.3.0
  forqsite.help -> both 0.3.0
  halfhorse -> both 0.3.0
  lumin -> both 0.3.0
  meander -> both 0.3.0
  pokus -> both 0.3.0
  radar -> both 0.3.0
  rockue -> both 0.3.0
  stackabid -> both 0.3.0
  ud -> both 0.3.0
base56 registered: False (confirmed absent — decommissioned by RELEASE-069, no .companion/ surface left to detect)
```

**DP8 verdict:** 14/15 clean (binding: both, 0.3.0), 1/15 partial (cora, binding: version only — recorded as a RELEASE-070 finding, INFRA-319 candidate, not fixed here), 1 project out of scope by design (base56, decommissioned). Phase 106's Goal text ("16/16 projects") is stale relative to the campaign's own later RELEASE-069 decision; this Evidence section is the corrected final disposition, and the Goal text is left as historical record, not rewritten.

### Step 3 — Six stale-seed removals
Each repo confirmed clean (only untracked `.companion/` noise, unrelated to this story) before its commit. All six `git rm` + commit + push completed successfully:

| Repo | Seed path removed | Commit | Push |
|---|---|---|---|
| forqsite.help | docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md | a86636d | 192410a..a86636d |
| halfhorse | docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md | 48eb8cc | 6599650..48eb8cc |
| lumin | docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md | bf97be9 | 433593d..bf97be9 |
| meander | docs/phases/phase-proposed-pairmode-030-migration-20260722.md | e9c8878 | 97e0a1d..e9c8878 |
| pokus | docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md | 95d9466 | 7443b35..95d9466 |
| rockue | docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md | 292a69f | 1b513c6..292a69f |

Commit subjects: `docs: remove stale pairmode-0.3.0-migration seed (superseded by phase-106 central migration)` — none name a RELEASE-0NN ID, per CER-116. `git status --porcelain` clean (modulo pre-existing untracked `.companion/` noise) in all six after.

### Step 4 — Spot-check: nine non-seed projects + base56 untouched
`git status --porcelain` checked in aab, asp, caddy, coherra, cora, forqsite, radar, stackabid, ud, base56. All dirt found (aab's CLAUDE.md/CLAUDE.build.md drift, missing agent shells, caddy's settings.json/permissions-json drift, cora's Docker/worktree files, radar's stray screenshot) was **pre-existing, unrelated to this story** — none caused by any command run in this story (only read-only `fleet_discovery.py --no-snapshot` calls touched these nine plus base56; no write of any kind). Not fixed here — out of scope for RELEASE-071, which only touches the six seed-removal repos.

### Step 5 — RELEASE-043..057 disposition table

| Story | Project | Resolution |
|---|---|---|
| RELEASE-043 | aab | superseded — own hand-migrated session (commit d40c44b) |
| RELEASE-044 | asp | superseded — own hand-migrated session (PM057-main) |
| RELEASE-045 | base56 | superseded — phase-106 RELEASE-069 (decommissioned, not migrated) |
| RELEASE-046 | caddy | superseded — phase-106 RELEASE-065 |
| RELEASE-047 | coherra | superseded — own hand-migrated session (story-INFRA-045) |
| RELEASE-048 | forqsite | superseded — own hand-migrated session (story-INFRA-020) |
| RELEASE-049 | forqsite.help | superseded — phase-106 RELEASE-066 |
| RELEASE-050 | halfhorse | superseded — phase-106 RELEASE-067 |
| RELEASE-051 | lumin | superseded — phase-106 RELEASE-064 |
| RELEASE-052 | meander | superseded — phase-106 RELEASE-063 (campaign canary) |
| RELEASE-053 | pokus | superseded — phase-106 RELEASE-068 (canon-only, proof-deferred) |
| RELEASE-054 | radar | superseded — own hand-migrated session (story-MU-128) |
| RELEASE-055 | rockue | superseded — own hand-migrated session (RK011-ante1) |
| RELEASE-056 | stackabid | superseded — own hand-migrated session (story-INFRA-014) |
| RELEASE-057 | ud | superseded — own hand-migrated session (INFRA-210/211) |

All 15 accounted for: 7 resolved directly by phase-106's driven campaign (RELEASE-063..069), 8 resolved independently by each project's own session, verified by git log inspection in each repo (`git log --oneline --all | grep -i "0.3.0|pairmode"`), not merely asserted. cora (RELEASE-070) was not part of the original RELEASE-043..057 list — it was added to the fleet later and is recorded separately, already complete.

### Step 6-7 — phase-97.md and index.md updated
`docs/phases/phase-97.md`'s Stories table: all 15 RELEASE-043..057 rows changed from `deferred` to `superseded`, each with the disposition pointer above. A `## Closed (2026-07-29, RELEASE-071)` section added, referencing this story and phase-106 — phase-97's original historical narrative (Goal, Deferred-stories rationale, DP8 override section) left untouched. `docs/phases/index.md`'s phase-97 row changed from `deferred` to `complete`.

### Outcome
Phase 106's campaign is functionally closed: DP8 status is 14/15 clean + 1 known partial (cora) + 1 out-of-scope-by-design (base56), all six stale seeds removed, all 15 of phase-97's original deferred stubs formally superseded with verified dispositions, phase-97 marked complete in the index. RELEASE-058 (DP8 gate tooling) remains waived, untouched, per its own 2026-07-23 operator override.

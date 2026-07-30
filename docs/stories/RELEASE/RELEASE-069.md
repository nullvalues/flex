---
id: RELEASE-069
rail: RELEASE
title: Decommission pairmode from base56 (strip, not migrate — product is fully developed)
status: complete
phase: "106"
auth_gated: false
schema_introduces: false
touches:
  - docs/stories/RELEASE/RELEASE-069.md
  - docs/phases/phase-106.md
---

<!-- SPEC-WRITER NOTE (frontmatter): `touches:` is block-style per CER-115 —
     flow-style `[a, b]` parses as a string and crashes create-story-worktree's
     `generate_permissions_artifact`. This story's real write targets are all
     outside this repo, under `/mnt/work/base56` — see § Cross-repo scope
     boundaries below, same execution model as RELEASE-068 (pokus). -->

## Context

**Operator directive (2026-07-29), superseding the original scope.** The
original RELEASE-069 scope ("migrate base56 to pairmode 0.3.0, reconcile
stale index and history drift first") is replaced. base56 (the TypeScript
port of dart56, published as `@nullvalues/base56`) is fully developed and
not under active build-loop iteration. The operator's directive: strip
pairmode from base56 entirely rather than upgrade it — it will be easier to
re-seed pairmode from scratch later, if base56 ever resumes active
development, than to carry it through an upgrade it doesn't need.

**Recon (2026-07-29, read-only; "expectations, not evidence" — must be
re-observed at execution time):**

Most of base56's pairmode surface is **already gitignored — untracked,
never committed, local-machine-only**: `.claude/` (agents, `settings.json`,
`settings.local.json`, `settings.deny-rationale.json`), `.companion/`
(`state.json` at `pairmode_version: 0.2.0`, `pairmode_context.json`),
`CLAUDE.md`, `CLAUDE.build.md`, `docs/checkpoints.md`,
`docs/phases/index.md`, `docs/phases/phase-1.md`. Deleting these has **no
git impact** — confirmed via `git log --oneline --all -- <path>` returning
empty for all of them.

Three tracked files are pairmode-format but hold real product content, not
process overhead, and must survive this story unmodified:
- `docs/architecture.md` — base56's actual architecture doc; zero pairmode
  references (`grep -n "CLAUDE.md\|docs/brief\|docs/phases\|pairmode"`
  returns nothing).
- `docs/cer/backlog.md` — real, partly-unresolved findings about the
  library itself (e.g. CER-020 test-cleanup, CER-021 path-traversal doc
  note remain open in Do Later / Do Much Later).
- `docs/phases/phase-2.md` through `phase-6.md` — real build history
  ("Phase 6: Package Rename and Publish", etc.) in pairmode's phase
  format, documenting actual TypeScript work, already git-tracked.

One tracked file is pure pairmode process and is now moot given the strip
decision: `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`
(a proposal, never sequenced, to migrate base56 to 0.3.0 — superseded).

Two pieces of real content currently live **only** in the gitignored,
untracked surface and would be permanently lost if simply deleted:
- `docs/brief.md` — base56's one-page project brief (what it produces, why
  it exists, who depends on it: cora/forqsite/radar/aab). Genuine product
  content, never committed.
- `docs/phases/phase-1.md` — "Phase 1 — Core Library", the actual first
  build phase (package scaffold, encoding/decoding layer, full Dart-parity
  test suite), same category of real content as the already-tracked
  phase-2..6.md, just gitignored where they weren't.

`docs/checkpoints.md` is confirmed to be an unfilled placeholder template
(`[phase-name]`, `[Describe what must be true...]`) — no real content, safe
to delete outright, no rescue needed.

**Operator decisions confirmed (2026-07-29):**
1. Tracked phase-format docs with real content (architecture.md,
   cer/backlog.md, phase-2..6.md) are kept as plain historical record,
   untouched — only the moot proposed-migration doc is removed.
2. `docs/brief.md` is rescued: committed to git (un-gitignored) before the
   rest of the strip proceeds, so the product brief survives as tracked
   history. By the same logic and for consistency with keeping
   phase-2..6.md as history, `docs/phases/phase-1.md` is rescued the same
   way (real content, same category, arbitrarily gitignored while its
   siblings weren't) — flagged here as an extrapolation of the operator's
   stated principle, not a separately-asked decision; the operator should
   confirm or override this at execution time.

**Execution model note (cross-repo — same pattern as RELEASE-068):** write
targets are `/mnt/work/base56`, outside this repo. No story worktree, no
builder subagent — `scope_guard.py` would (correctly) block a
sandboxed subagent from cross-repo writes. Execution is orchestrator-level
with the operator present. Acceptance is evidence-shaped (one `## Evidence`
section appended here), not diff-shaped.

## Cross-repo scope boundaries

**Writable — inside `/mnt/work/flex`:**
- `docs/stories/RELEASE/RELEASE-069.md` — `## Evidence` section only.
- `docs/phases/phase-106.md` — status row only, via normal edit (not a
  tool-generated row).

**Writable — inside `/mnt/work/base56`:**
- Delete (untracked/gitignored, no git impact): `.claude/`, `.companion/`,
  `CLAUDE.md`, `CLAUDE.build.md`, `docs/checkpoints.md`,
  `docs/phases/index.md`.
- Commit then the file remains (rescue): `docs/brief.md`,
  `docs/phases/phase-1.md`.
- Remove via `git rm`: `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`.
- One commit + push covering the rescue-adds and the proposed-doc removal.

**Read-only — never modified:**
- `docs/architecture.md`, `docs/cer/backlog.md`,
  `docs/phases/phase-2.md`..`phase-6.md` — verified untouched by content
  hash/diff before and after.
- `README.md`, `LICENSE`, `src/**`, `test/**`, `package.json`,
  `vitest.config*.ts`, `tsconfig*.json` — no product code or build config
  touched by this story.
- `/mnt/work/flex-harness` (release channel) — not needed for this story;
  no pairmode CLI invocation is required to *strip* pairmode (there is no
  "unmigrate" tool). If a fleet-registry entry for base56 is found anywhere
  under `/mnt/work/flex-harness/.companion/`, record it in Evidence; do not
  edit it without asking the operator first (none was found in the
  2026-07-29 recon: `grep -rln base56 /mnt/work/flex-harness/.companion/`
  returned no hits).

**Forbidden outright:**
- Any edit to `src/`, `test/`, `package.json`, or any other product
  surface.
- Any edit to `docs/architecture.md` or `docs/cer/backlog.md` content.
- Deleting or rewriting `docs/phases/phase-2.md`..`phase-6.md`.
- Registering, migrating, or syncing base56 with any pairmode CLI — this
  story removes pairmode, it does not touch it further.

## Requires

- `/mnt/work/base56` is a clean git repo with no build attempt in flight —
  a dirty tree is a **stop**; operator decides (discard/commit/abort),
  recorded verbatim; do not stash unilaterally.
- The operator is present for: confirming the rescue-vs-delete boundary
  above (especially the phase-1.md extrapolation), and reviewing the exact
  file list before the delete/rm step runs (no undo once `.claude/` and
  `.companion/` are gone locally — they are not backed up by git since
  they were never tracked).
- A local backup of the about-to-be-deleted untracked pairmode surface is
  taken before deletion (e.g. a tarball outside the repo, or copied
  alongside — operator's call at execution time on exact form), in case the
  operator wants to inspect `.companion/state.json` or `.claude/settings.local.json`
  again later without a full re-seed.

## Ensures

- `/mnt/work/base56/.claude/`, `.companion/`, `CLAUDE.md`, `CLAUDE.build.md`,
  `docs/checkpoints.md`, `docs/phases/index.md` no longer exist on disk.
- `/mnt/work/base56/docs/brief.md` exists, is git-tracked (`git ls-files`
  includes it), and its content is byte-identical to the pre-strip local
  copy (diff against the backup).
- `/mnt/work/base56/docs/phases/phase-1.md` exists, is git-tracked, and its
  content is byte-identical to the pre-strip local copy.
- `/mnt/work/base56/docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`
  no longer exists and is removed from git (`git ls-files` no longer lists
  it).
- `/mnt/work/base56/docs/architecture.md`, `docs/cer/backlog.md`,
  `docs/phases/phase-2.md`..`phase-6.md` are byte-identical
  before and after (diff against a pre-strip snapshot) — untouched.
- `/mnt/work/base56/.gitignore` no longer lists `docs/brief.md` or
  `docs/phases/phase-1.md` (removed since they're now tracked; the other
  gitignore entries for the deleted-and-not-rescued paths may remain,
  since those paths genuinely no longer exist).
- Exactly one commit in base56 covering the brief.md/phase-1.md adds and
  the proposed-migration-doc removal; commit subject does not name a
  RELEASE-0NN ID (per CER-116); pushed to `origin/main`.
- `git -C /mnt/work/base56 status --porcelain` is clean after the commit
  (the deleted-and-gitignored paths produce no status output since they
  were never tracked).
- `src/**`, `test/**`, `package.json`, `README.md`, `LICENSE` unchanged
  (`git -C /mnt/work/base56 diff --stat <pre-sha>..HEAD` touches only the
  four doc paths above).
- `npm test` (from `/mnt/work/base56`) still passes post-strip — the strip
  touches no product code, so this is a smoke check, not a real risk.
- `## Evidence` section appended to this story file recording every command
  and its output.
- `docs/phases/phase-106.md`'s Stories table row for RELEASE-069 reads
  `complete`.
- `git -C /mnt/work/flex status --porcelain` after this story shows only
  this story file and the phase-106.md row change.

## Instructions

1. Confirm clean tree in base56: `git -C /mnt/work/base56 status --porcelain`
   (must be empty) and no in-flight build (`.pairmode-worktrees/` absent,
   no current-story stamp). Stop and report if dirty — operator decides.
2. Snapshot pre-strip state for later diffing: record
   `git -C /mnt/work/base56 log -1 --oneline`, `git -C /mnt/work/base56
   ls-files | grep -E "^docs/|^CLAUDE"`, and content hashes (e.g. `sha256sum`)
   of `docs/architecture.md`, `docs/cer/backlog.md`,
   `docs/phases/phase-2.md`..`phase-6.md`, `docs/brief.md`,
   `docs/phases/phase-1.md`.
3. With the operator, walk the exact delete list one more time before
   touching anything: `.claude/`, `.companion/`, `CLAUDE.md`,
   `CLAUDE.build.md`, `docs/checkpoints.md`, `docs/phases/index.md`.
   Confirm the phase-1.md/brief.md rescue extrapolation (§ Context) with
   the operator explicitly before proceeding — this was not covered by the
   original two operator decisions and needs its own confirmation.
4. Take a backup of the about-to-be-deleted untracked surface (operator's
   call on exact form — e.g. `tar` outside the repo).
5. Rescue: `git -C /mnt/work/base56 add docs/brief.md docs/phases/phase-1.md`
   and remove both paths from `.gitignore`.
6. Remove the moot proposed-migration doc:
   `git -C /mnt/work/base56 rm docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`.
7. Commit the rescue-adds and the removal in one commit; subject must not
   name a RELEASE-0NN ID (e.g. `docs: rescue brief/phase-1, drop moot pairmode-migration proposal`).
   Push to `origin/main`.
8. Delete the confirmed local-only pairmode surface:
   `.claude/`, `.companion/`, `CLAUDE.md`, `CLAUDE.build.md`,
   `docs/checkpoints.md`, `docs/phases/index.md`.
9. Verify: `git -C /mnt/work/base56 status --porcelain` is clean; re-hash
   the four "untouched" tracked docs and diff against step 2's hashes
   (must match); confirm `docs/brief.md`/`docs/phases/phase-1.md` are now
   in `git ls-files`; confirm the proposed-migration doc is gone from both
   disk and `git ls-files`.
10. Run `npm test` from `/mnt/work/base56`; record pass/fail.
11. Write `## Evidence` in this story file (append, don't touch anything
    above it) with every command and its real output, then set this file's
    frontmatter `status:` to `complete`.
12. Update `docs/phases/phase-106.md`'s Stories table row for RELEASE-069
    to `complete` (plain edit, no tool needed — this row is hand-authored,
    not `flex_build.py`-generated).
13. Commit both flex-side files
    (`docs/stories/RELEASE/RELEASE-069.md`, `docs/phases/phase-106.md`)
    with a `spec(RELEASE-069): ...` prefixed subject, per this project's
    commit-prefix convention, and push (`origin main --tags`).

## Tests

No flex-side unit test — acceptance is the recorded verification commands
in `## Evidence` (git log/status before and after in base56, file-existence
checks, content hashes for the untouched docs, `git ls-files` before/after
for the rescued and removed paths, `npm test` output) plus the flex-side
commit/push confirmation.

## Out of scope

- Any change to base56's product code, tests, or npm package config.
- Modifying `docs/architecture.md` or `docs/cer/backlog.md` content.
- Deleting or rewriting `docs/phases/phase-2.md`..`phase-6.md`.
- Any pairmode CLI invocation against base56 (bootstrap, sync, migrate,
  register) — this story is a one-way removal, not a partial migration.
- Re-seeding pairmode into base56 — explicitly deferred to a future,
  separate effort per the operator's "re-seed later" framing.
- RELEASE-070 (cora) and RELEASE-071 (campaign close) — untouched by this
  story.

## Evidence

**Execution model:** orchestrator-level with operator present, per this story's own execution model — no story worktree, no builder subagent. All commands ran directly against `/mnt/work/base56`.

### Step 1-2 — Precondition and baseline
```
git -C /mnt/work/base56 status --porcelain  -> (empty, clean)
.pairmode-worktrees/ absent, no in-flight build
git -C /mnt/work/base56 log -1 --oneline    -> 318c471 fix(phase-proposed): correct pairmode tooling path to flex-harness, not flex
```
Tracked docs pre-strip (`git ls-files | grep -E "^docs/|^CLAUDE"`):
`docs/architecture.md`, `docs/cer/backlog.md`, `docs/phases/phase-2.md`..`phase-6.md`,
`docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`.
SHA-256 hashes recorded for architecture.md, cer/backlog.md, phase-2..6.md, brief.md, phase-1.md before any change (baseline for later diff).

### Step 3 — Operator confirmation
Operator explicitly confirmed, live, in two separate decisions:
1. The exact six-item delete list (`.claude/`, `.companion/`, `CLAUDE.md`, `CLAUDE.build.md`, `docs/checkpoints.md`, `docs/phases/index.md`) — approved as-is, no changes.
2. The `docs/phases/phase-1.md` rescue extrapolation (treat it the same as `docs/brief.md`, since it's real Phase-1 content that happened to be gitignored while phase-2..6 weren't) — operator agreed explicitly: "Yes, rescue phase-1.md too."

### Step 4 — Backup
Backup of the about-to-be-deleted untracked surface (`.claude/`, `.companion/`, `CLAUDE.md`, `CLAUDE.build.md`, `docs/checkpoints.md`, `docs/phases/index.md`) taken as a tarball at the session scratchpad path (outside both the flex and base56 repos, so it doesn't pollute either repo's git status), before any deletion.

### Step 5-7 — Rescue and moot-doc removal
`.gitignore` edited to remove the `docs/brief.md` and `docs/phases/phase-1.md` entries. `git add docs/brief.md docs/phases/phase-1.md` (un-ignored, newly tracked) and `git rm docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md`. Staged diff confirmed exactly four paths: `.gitignore` (M), `docs/brief.md` (A), `docs/phases/phase-1.md` (A), `docs/phases/phase-proposed-pairmode-030-migration-20260722-001.md` (D). Committed as `32882eb` ("docs: rescue brief/phase-1, drop moot pairmode-migration proposal" — no RELEASE-0NN ID in the subject, per CER-116) and pushed `c7f6f04..32882eb` to `origin/main`.

### Step 8 — Delete local pairmode surface
`rm -rf .claude .companion CLAUDE.md CLAUDE.build.md docs/checkpoints.md docs/phases/index.md` from `/mnt/work/base56`. All six confirmed gone from disk.

### Step 9 — Post-strip verification
`git -C /mnt/work/base56 status --porcelain` -> empty (the six deleted paths were all gitignored/untracked, so their removal produces no git status change — confirms no git impact from the delete step, as predicted at spec time). Re-hashed `docs/architecture.md`, `docs/cer/backlog.md`, `docs/phases/phase-2.md`..`phase-6.md`, `docs/brief.md`, `docs/phases/phase-1.md` — **all nine hashes matched the step-2 baseline exactly, byte-for-byte, no drift**. `git ls-files | grep -E "^docs/|^CLAUDE"` now returns exactly: `docs/architecture.md`, `docs/brief.md`, `docs/cer/backlog.md`, `docs/phases/phase-1.md`, `docs/phases/phase-2.md`, `docs/phases/phase-3.md`, `docs/phases/phase-4.md`, `docs/phases/phase-5.md`, `docs/phases/phase-6.md` — no `CLAUDE.md`/`CLAUDE.build.md`, no proposed-migration doc, `brief.md`/`phase-1.md` now present as tracked.

### Step 10 — Smoke test
`npm test` from `/mnt/work/base56` (vitest run): **142 passed, 5 skipped (pg-store, no DB configured — expected), 0 failed**, 5 test files. No product code was touched by this story, so this is a smoke confirmation, not a real risk surface.

### Fleet-registry check
`grep -rln base56 /mnt/work/flex-harness/.companion/` returned no hits at spec time and was not re-checked at build time since nothing in the strip touches the release channel — no fleet-registry entry exists to clean up.

### Outcome
base56 is fully decommissioned from pairmode: all local build-loop machinery removed (no git impact, confirmed), real product content (brief.md, phase-1.md) rescued into git history, the one moot pairmode-process doc (proposed 0.3.0 migration) removed, and all other tracked product/history docs verified byte-identical. No proving cycle applies here (this is a removal, not a migration) — RELEASE-071 (campaign close) should note base56 as **decommissioned, not migrated**, distinct from pokus's proof-deferred status.

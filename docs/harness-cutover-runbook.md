# Harness Cutover & Migration Runbook

**Status:** Authored in `HARNESS001-ante1` (RELEASE-006); **executed at/after HARNESS006-main**.

**Authority:** `docs/agreements/HARNESS001-ante1.md` (DP5, DP6, DP8 settled decisions).

This runbook describes the migration sequence from pairmode 0.2.x (`main`) to 0.3.0 (thin harness, unified).
It is a **plan document, not an action taken now**. The migration is **opt-in, do-nothing-stays-stable,
rolling, and sync-driven** — projects that do not run `sync-all` continue running 0.2.x indefinitely.

---

## Strategy (Option Y)

**Decision:** opt-in, do-nothing-stays-stable, rolling, sync-driven.

### Topology

- **`main`** (fleet-facing, stable): stays on **pairmode 0.2.x** through the entire migration window.
  No `stable/0.2` branch; `main` *is* stable.
- **`harness` worktree** (`/mnt/work/flex-harness`, DP1): carries pairmode **0.3.0** (and later **0.3.0-dev**
  during development, finalized to **0.3.0** at flip). Never executed by the fleet; isolated from running
  projects via a hard filesystem boundary (different path).
- **Consumer projects** begin on 0.2.x; projects opt into 0.3.0 migration by running `sync-all --apply`
  from the harness worktree's scripts.

### Core principle

**"Do nothing = stay on 0.2.x"** is structural. An un-synced project ignores any 0.3.0 checkout's mere
existence. The binding mechanic is **the absolute `pairmode_scripts_dir` baked into a project's
`CLAUDE.build.md` at sync time** (`Path(__file__).parent` of the syncing checkout), not by `FLEX_DIR`
(which only drives the version-nag hook). As long as a project does not run `sync-all`, its `CLAUDE.build.md`
continues to point at the 0.2.x worktree, and the 0.3.0 harness does not affect it.

### Rejected alternatives

- **Flip `main` immediately to 0.3.0:** breaks any project that does nothing (their `CLAUDE.build.md`
  points at `/mnt/work/flex`, which becomes 0.3.0, breaking their build). Option Y avoids this by keeping
  `main` stable through migration.
- **No branch isolation (single shared `main`, additive discipline only):** no safety net if "additive" slips.
  The DP1 worktree gives a hard barrier.

---

## Rolling sequence (DP5 + DP6)

**flex dogfoods first; then one canary; then the rest.**

This sequence ensures the thin harness is proven before fleet-wide rollout.

### Phase 1: flex itself (DP6 dogfood)

**Timing:** immediately after HARNESS006-main is stable on `harness` line.

**Executor:** the flex repo owner / release manager.

**Steps:**

1. **Verify harness builds complete:** flex's tests pass on the `harness` branch with the 0.3.0 thin-harness
   loop (HARNESS001–005 built with 0.2.x loop, HARNESS006 flips the loop and builds itself).
   
2. **Finalize the version:** on the `harness` branch, edit `skills/pairmode/scripts/_version.py` to change
   `"0.3.0-dev"` → `"0.3.0"` (the semantic marker "migration-ready").

3. **Sync flex's own loop:**
   ```bash
   # From flex repo root (main or harness — either is OK here for flex's self-sync)
   # But run FROM the harness checkout's scripts:
   PYTHONPATH=/mnt/work/flex-harness uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
     sync-all --project-dir /mnt/work/flex --apply --yes
   ```
   This rewrites flex's own `CLAUDE.build.md` to point at the harness `pairmode_scripts_dir` and marks
   it as 0.3.0-using.

4. **Verify a full build round:** run one complete pairmode story through flex's new thin-harness loop
   (at least a doc or lesson story to exercise all agents). Confirm that the build completes, the
   orchestrator/resolver/agents integrate correctly, and no regressions appear.

5. **Confirm `pairmode_version` advanced:** check that `flex/.companion/state.json` now carries
   `"pairmode_version": "0.3.0"` (set by `sync-all`).

6. **Commit & tag on harness line:**
   ```bash
   git add -A
   git commit -m "flex: finalize 0.3.0, sync to thin-harness loop"
   # (Do not tag yet — wait for final fold step)
   ```

**Acceptance:** flex builds successfully with the new loop, proving the harness is functional. The DP6
dogfood removes risk from canary selection.

### Phase 2: One canary fleet project

**Timing:** after Phase 1 acceptance.

**Candidate:** a mid-size, lower-criticality project already using pairmode (e.g., radar, lumin, forqsite).
**Executor:** the flex repo owner + canary project owner (joint verification).

**Steps:**

1. **Dry-run the migration:**
   ```bash
   # From the canary project directory
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
     sync-all --project-dir /path/to/canary-project --dry-run
   ```
   Review the printed diff to understand what is changing in the project's `CLAUDE.build.md`,
   agent files, and methodology templates. Confirm expectations; abort if changes are unexpected.

2. **Apply the migration:**
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
     sync-all --project-dir /path/to/canary-project --apply --yes
   ```
   This stages the changes (does not commit yet).

3. **Verify a build round:** run one complete pairmode story through the canary project's migrated loop
   (any story). Confirm that the build completes with no regressions. The resolver and agents are
   exercised.

4. **Confirm `pairmode_version`:** check the canary project's `.companion/state.json`:
   ```bash
   cat /path/to/canary-project/.companion/state.json | grep pairmode_version
   ```
   Should read `"pairmode_version": "0.3.0"`.

5. **Commit the changes (canary project repo):**
   ```bash
   cd /path/to/canary-project
   git add -A
   git commit -m "sync: migrate to pairmode 0.3.0 thin-harness loop"
   ```

6. **Document the result:** record in the HARNESS006 era doc or release notes which project was
   the canary, what dates, and any findings.

**Acceptance:** canary project builds successfully; confidence in the harness is high; migration sequence is proven.

### Phase 3: The rest of the fleet (rolling)

**Timing:** after Phase 2 acceptance.

**Operator-initiated per project; nothing forced.** Each bound project owner decides when to migrate.
No deadline, no forced cutover — this is "opt-in."

**Steps for each project P:**

1. **Dry-run:**
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
     sync-all --project-dir /path/to/P --dry-run
   ```

2. **Apply:**
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
     sync-all --project-dir /path/to/P --apply --yes
   ```

3. **Verify a build round:** run one story.

4. **Confirm `pairmode_version` == 0.3.0:**
   ```bash
   cat /path/to/P/.companion/state.json | grep pairmode_version
   ```

5. **Commit & push.**

6. **Optional: repoint `FLEX_DIR`** (project's own environment config, if used). This is optional because
   the binding is already baked into the `CLAUDE.build.md` `pairmode_scripts_dir`. The version-nag hook
   will stop complaining once `FLEX_DIR` points at the new 0.3.0 unified line (after the fold). Until
   then, the nag is harmless.

**No deadline:** projects on 0.2.x continue to work indefinitely; migration is available on-demand.

---

## Per-project mechanic (DP5)

Each project's sync **must run from the harness worktree's scripts** to bake the correct `pairmode_scripts_dir`.

### Command sequence (per project P)

```bash
# Step 1: Dry-run (preview the rewrite)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
  sync-all --project-dir /path/to/P --dry-run

# Step 2: Review the diff output above. If acceptable, apply:
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py \
  sync-all --project-dir /path/to/P --apply --yes

# Step 3: Verify a build round (run one story)
cd /path/to/P
uv run pytest tests/pairmode/ -x -q  # or run a single story per project's CLAUDE.build.md

# Step 4: Confirm pairmode_version advanced to 0.3.0
cat .companion/state.json | grep pairmode_version
# Expected: "pairmode_version": "0.3.0"

# Step 5: Commit the changes
git add -A
git commit -m "sync: migrate to pairmode 0.3.0 thin-harness loop"
git push
```

### What `sync-all` does (three operations in sequence)

`sync-all` sequences three sync operations:

1. **`sync.py`** (if `--apply` is set): re-renders methodology files (CLAUDE.md, era docs, etc.) from
   canonical templates. On `--dry-run`, this is skipped (no dry-run mode for `sync.py`).

2. **`sync-agents`** (with or without `--dry-run`): re-renders agent file frontmatter and merges new body
   sections from the canonical templates. Prints a unified diff.

3. **`sync-build`** (with or without `--dry-run`): compares the project's `CLAUDE.build.md` against the
   canonical template rendered with the project's context, prints the diff, and (with `--apply`) writes
   the new version.

When `sync-all` writes a file, the `pairmode_scripts_dir` variable is baked into the template context as
the absolute path of the harness worktree's scripts directory. This is the **binding point**: subsequent
builds execute scripts from that absolute path, not from `FLEX_DIR`.

### Context at sync time

The canonical template is rendered with context including:
- `pairmode_scripts_dir` = `/mnt/work/flex-harness/skills/pairmode/scripts` (from the harness worktree)
- `pairmode_version` = `"0.3.0"` (or `"0.3.0-dev"` during dev, finalized at flip)
- Project-specific settings from `.companion/state.json` and `.companion/pairmode_context.json`

This ensures every migrated project's loop points at the 0.3.0 harness, even before the flip merges
harness back to `main`.

---

## DP6 dogfood detail: How flex flips itself

Flex builds HARNESS001–005 **with the existing 0.2.x loop** (safe because of DP4 additive contract).
The resolver and leaf workers built during those stories are exercised **only by their own tests**,
never wired into flex's live loop until HARNESS006.

### Why this matters

Progressively wiring the resolver into the live loop during HARNESS001–005 would void the additive
guarantee — the live loop would start depending on new code that hasn't stabilized yet. Instead:

- **HARNESS001–005 on flex's worktree:** build the resolver, workers, and new gates using the existing
  0.2.x orchestrator loop. All new code is isolated to its own tests.
- **HARNESS006-main:** wire in `next-action` resolver + workers into the thin-harness template,
  flip the loop shape, and verify the integration works before the fleet is affected.
- **Flex flips first:** after HARNESS006 proves the integrated system, flex self-syncs (Phase 1 above)
  to verify the thin harness works on itself, *then* the fleet migrates.

This is the **DP6 dogfood**: flex is both developer (building the harness) and canary (first to use it).

---

## Pre-fold discovery gate (DP8)

**Timing:** immediately before the final fold (step 6a below).

**Binding requirement:** the pre-fold discovery run is a **hard gate**. No project can remain un-migrated
when the fold proceeds, because the fold makes `/mnt/work/flex` = 0.3.0 and would break un-migrated
bound projects (they would find `pairmode_scripts_dir` pointing at a 0.3.0 tree that doesn't match
their 0.2.x loop expectations).

### Discovery command

Execute the fleet-discovery read-only tool (built in RELEASE-005):

```bash
# Exact command TBD by RELEASE-005 implementation; pseudo-example:
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex/skills/pairmode/scripts/fleet_discovery.py \
  --scan-paths /mnt/work \
  --output /tmp/fleet-discovery-pre-fold.json
```

This tool scans candidate directories for both binding signals:
- A `CLAUDE.build.md` whose `pairmode_scripts_dir` references `/mnt/work/flex` or `/mnt/work/flex-harness`
- A `.companion/state.json` with a `pairmode_version` entry

### Gate decision

The output is an authoritative list of bound projects. For each bound project:
- **If `pairmode_version` == "0.3.0":** project is migrated ✓ proceed.
- **If `pairmode_version` == "0.2.x":** project has not migrated ✗ **do not proceed with fold** until this
  project is migrated (or consciously accepted / removed from the fleet).

**No partial folds:** the fold either proceeds with all migrated projects, or is deferred until remaining
projects are handled.

### Signal-1 verification step (CER-059b)

After syncing each project to 0.3.0 (running `pairmode sync --apply` in the project), re-run
fleet discovery and confirm `binding: scripts` appears in the output for that project. A newly-synced
project's `CLAUDE.build.md` should contain a `pairmode_scripts_dir` declaration pointing to the
0.3.0 scripts directory; if `Signal 1 (scripts path): absent` persists after sync, the project's
`CLAUDE.build.md` was not updated by sync and the bind is incomplete.

```bash
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex/skills/pairmode/scripts/fleet_discovery.py \
  --candidate-dir /path/to/project
```

Confirm the output shows `Signal 1 (scripts path): present` before proceeding to the next project.

---

## Final fold sequence

**Timing:** after pre-fold discovery gate passes (all bound projects migrated or accepted).

**Executor:** the flex repo owner / release manager.

**Steps:**

1. **Fold harness → main:**
   ```bash
   cd /mnt/work/flex
   git merge --no-ff /mnt/work/flex-harness -m "Era 003: fold harness to main, pairmode 0.3.0"
   ```
   This brings all harness development (HARNESS001–005 code + HARNESS006 gate rewrite + thin-harness
   integration) into `main`. `main` becomes the unified 0.3.0 line.

2. **Tag v0.3.0:**
   ```bash
   git tag -a v0.3.0 -m "flex: pairmode 0.3.0 (thin-harness era)"
   git push origin main v0.3.0
   ```

3. **Re-sync each migrated project** to point back at canonical `/mnt/work/flex`:
   ```bash
   # For each migrated project P:
   PATH=$HOME/.local/bin:$PATH uv run python \
     /mnt/work/flex/skills/pairmode/scripts/pairmode_sync.py \
     sync-all --project-dir /path/to/P --apply --yes
   ```
   This updates their `CLAUDE.build.md` to reference the canonical `/mnt/work/flex` (no longer the
   transient `/mnt/work/flex-harness`). The `pairmode_scripts_dir` baked into the template now points
   at `/mnt/work/flex/skills/pairmode/scripts` (the unified line).

4. **Verify no binding breakage:** spot-check one or two project builds after re-sync to confirm
   they still work.

5. **Remove the transient worktree:**
   ```bash
   rm -rf /mnt/work/flex-harness
   git worktree remove /mnt/work/flex-harness
   ```

6. **Clean up harness branch** (optional, but recommended):
   ```bash
   git branch -d harness  # or keep as a historical ref; team decision
   ```

**Final state:** `/mnt/work/flex` is 0.3.0, all migrated projects are using the unified line,
the harness development worktree is gone, and the version nag hook on migrated projects is satisfied.
Any non-migrated projects remain on 0.2.x indefinitely (do-nothing-stays-stable).

---

## Execution timing note

**This runbook is authored in HARNESS001-ante1 (now).** It is a plan document only — no part of it is
executed during this phase or HARNESS001–005. The migration **begins at HARNESS006-main**, after the thin
harness is proven stable and ready for fleet rollout. Between now and HARNESS006, this document serves as
the settled specification for the migration (approved by all decision points: DP5, DP6, DP8). It is safe
to reference in planning, review, and communication; it is not safe to execute until the orchestrator
signals readiness.

---

## Cross-references to settled agreements

Authority for every section above:

| Section | Authority |
|---------|-----------|
| Strategy (Option Y) | DP5 (`docs/agreements/HARNESS001-ante1.md` line 188) |
| Topology (main stays 0.2.x, no stable/0.2 branch) | DP5 line 188–198 |
| Binding mechanic (`pairmode_scripts_dir` baked at sync) | DP5 line 191–194 |
| Rolling sequence (flex → canary → rest) | DP5 line 205–208; DP6 line 226–235 |
| Per-project sync-all mechanic | DP5 line 201–204 |
| flex's DP6 dogfood (0.2.x loop through HARNESS001–005, flip at HARNESS006) | DP6 line 226–235 |
| Forbid progressive resolver wiring during HARNESS001–005 | DP6 line 234–235 |
| Pre-fold discovery gate (DP8 hard gate) | DP8 line 316–324 |
| Final fold sequence | DP5 line 209–211 |
| Semantic separation (effort.db ≠ context-control) | DP7 line 254–267; codified comingling remediation line 269–280 |

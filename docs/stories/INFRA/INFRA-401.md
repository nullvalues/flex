---
id: INFRA-401
rail: INFRA
title: Fix scrub_fleet_names crash, incomplete anonymization coverage, and unwired gate (CER-194)
status: draft
phase: "131"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_map.py
  - skills/pairmode/scripts/fleet_discovery.py
  - skills/pairmode/scripts/scrub_fleet_names.py
touches:
  - tests/pairmode/test_fleet_discovery.py
  - tests/pairmode/test_scrub_fleet_names.py
  - tests/pairmode/test_bootstrap.py
  - skills/pairmode/scripts/bootstrap.py
  - docs/architecture.md
narrative_roles: []
---

## Context

The Phase 125 checkpoint's second security-auditor pass (CER-194) found that
INFRA-400's fleet de-identification mechanism, while present, is partly broken and
partly unwired. `fleet_map.py`'s `sibling_repo_dirs()` raises `PermissionError` from
its `.git` probe on any unreadable candidate directory — contradicting its own
"never raises" docstring and aborting `scrub_fleet_names.py --verify` entirely
before it scans anything. `fleet_discovery.py` anonymizes only each result's `path`
key, so two further path-shaped fields still reach the tracked snapshot verbatim,
and the CLI still echoes raw absolute paths to stdout. And the `install-hook`
pre-commit gate is documented but invoked by nothing, so the regression gate CER-188
asked for protects nothing today. This story fixes all three at code level; every
test fixture uses synthetic names only.

## Requires

INFRA-400 complete (`fleet_map.py`, the `_anonymize_results_for_snapshot` path, and
the `install-hook` subcommand all exist on `main`).

## Ensures

1. `fleet_map.sibling_repo_dirs()` returns the readable repo directories and omits an
   unreadable candidate directory instead of raising, so `scrub_fleet_names.py
   --verify` completes and reports on a fleet root containing one; forbidden proxy:
   catching the error at the `verify()`/`_reconcile_fleet_root()` caller while
   `sibling_repo_dirs()` itself still propagates.
2. A `signal1_value` or `signal1_absent_detail` string containing a fleet-root repo
   path is replaced by that repo's label (or by the same `<unmapped-repo-N>`
   placeholder used for `path`) in both the composed snapshot text and every CLI
   output path (`--json` included) — no fixture repo name appears in either output;
   forbidden proxy: anonymizing only at snapshot-composition time while the CLI print
   path still emits the raw string.
3. `bootstrap.py` installs the `scrub_fleet_names.py` pre-commit hook as part of its
   normal run, and reports a distinct, visible status line for each of: installed,
   already installed (byte-identical, not rewritten), target is not a git repository,
   target's `.git` is a worktree pointer file, and a pre-existing foreign
   `pre-commit` hook (left unmodified in that case); forbidden proxy: a silent
   `return` on any of those branches.

## Instructions

1. **fleet_map.py.** In `sibling_repo_dirs()`, wrap the per-candidate `p.is_dir()` /
   `(p / ".git").exists()` probe so a `PermissionError` (and any other `OSError`)
   on one candidate skips that candidate rather than propagating; also guard the
   `fleet_root.iterdir()` call itself, returning `[]` on `OSError` — the docstring's
   "never raises" contract is the acceptance criterion.
2. **fleet_discovery.py.** Generalize `_anonymize_results_for_snapshot` (rename to
   `_anonymize_results_for_output`) so it also maps `signal1_value` and
   `signal1_absent_detail`. These are free-text absolute paths, not bare repo paths:
   substitute *within* the string every occurrence of a fleet-root child path,
   resolving each through the same `_resolve` used for `path` (mapped label, or the
   per-call `<unmapped-repo-N>` placeholder), so both mapped and unmapped repos are
   covered. Apply the function at the CLI output boundary as well as before snapshot
   composition, covering the human-readable `click.echo` block and the `--json` dump.
   Leave the in-memory results real for programmatic callers — anonymize at the
   output boundary, not at collection.
3. **Gate wiring (bootstrap.py + scrub_fleet_names.py).** Chosen mechanism:
   `bootstrap.py` invokes `install_hook` on the project being bootstrapped, as a new
   sub-step alongside the existing hook-registration step (~line 1913, honouring
   `dry_run` the same way). Rationale: bootstrap is this project's only existing
   "apply pairmode's machinery to a checkout" touchpoint, it already owns hook
   registration, and it runs once per checkout — which is exactly the lifecycle
   `install_hook`'s docstring assumes but never got. A checkpoint-step check was
   rejected because it would verify the gate only on the one repo doing the
   checkpoint, and only after the commits it was meant to block. This is safe for
   consuming projects: `verify()` returns 0 immediately when no
   `.pairmode-fleet.local.json` exists.
   Change `install_hook` to return a status plus the path (e.g.
   `("installed" | "already-installed" | "not-a-git-repo" | "worktree" |
   "foreign-hook", Path | None)`) instead of assuming success:
   - `.git` missing → `not-a-git-repo`, do not create it.
   - `.git` is a file (worktree/submodule pointer) → `worktree`; the hook belongs to
     the main checkout, so do not write.
   - `.git/hooks/pre-commit` exists with content byte-identical to the rendered
     template → `already-installed`, no write.
   - exists with any other content → `foreign-hook`, leave the file untouched.
   The `install-hook` CLI prints the status and exits 0 for
   installed/already-installed, 1 otherwise (an explicit request that could not be
   fulfilled is a failure); `bootstrap.py` prints the status line and never fails the
   bootstrap on a skip.
   Update `install_hook`'s docstring (it currently says "Never invoked
   automatically") and add a short note to `docs/architecture.md` where pairmode's
   other hook registration is described, stating that the scrub pre-commit gate is
   installed by `bootstrap.py` and can be re-applied with `install-hook`.
4. **Tests** (synthetic fixtures only — never read `.pairmode-fleet.local.json` or
   `docs/fleet-snapshot.md`, and never write a real repo name into a fixture):
   - `test_scrub_fleet_names.py`: build a `tmp_path` fleet root with one readable
     fixture repo (`repo-alpha/.git`) and one directory chmod'd to `0o000`; assert
     `sibling_repo_dirs()` returns the readable one without raising, and that
     `verify()` runs to completion against that root. Guard with
     `pytest.skip` when `os.geteuid() == 0` (root bypasses mode bits), or use a
     monkeypatched `Path.exists` raising `PermissionError` instead.
   - `test_fleet_discovery.py`: a fixture fleet map (`{"Repo-Z":
     "/fake/fleet/repo-zeta"}`) plus a result whose `signal1_absent_detail` is a path
     read from a synthetic third-party `CLAUDE.build.md` containing
     `/fake/fleet/repo-zeta/skills/pairmode/scripts`; assert `repo-zeta` appears in
     neither the composed snapshot text nor the CLI stdout (both modes), and that
     `Repo-Z` does. Add an unmapped-sibling case asserting the
     `<unmapped-repo-N>` placeholder.
   - `test_bootstrap.py`: assert bootstrap writes an executable `.git/hooks/pre-commit`
     in a fixture git repo; assert the four skip/idempotent branches each produce
     their status without modifying the target file.
5. Manual verification for this checkout (flex dogfoods the gate): run
   `uv run python skills/pairmode/scripts/scrub_fleet_names.py install-hook .` from
   the main checkout and confirm it reports `installed` (or `already-installed`) and
   that `test -x .git/hooks/pre-commit` succeeds. Do not add a test asserting this
   repo's own hook file exists — builder worktrees and fresh clones would fail it
   spuriously.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_scrub_fleet_names.py \
  tests/pairmode/test_fleet_discovery.py tests/pairmode/test_bootstrap.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green, including the new permission-skip, anonymization-coverage,
and hook-wiring cases. Also confirm by inspection that no fixture in the diff
contains a real sibling-repo name.

## Out of scope

- Reconciling the live local `.pairmode-fleet.local.json` against the real on-disk
  sibling set, and scrubbing any real names that reconciliation surfaces in tracked
  files — the operator handles this directly, outside this story, precisely because
  it requires touching real private data this story's fixtures must never see.
- CER-192 (git-history remediation of pre-scrub commits) — deferred pending explicit
  operator direction.
- CER-189 / CER-190 / CER-191 (the three LOW findings from the first checkpoint
  pass) — separately tracked, not fixed here.
- `docs/fleet-snapshot.md` itself: named in `## Instructions` only as a file the
  builder must never read or write (spec-preflight reports it as a declared-scope
  gap; that is intentional and must stay out of `touches`).
- Broadening anonymization to fields that are not path-shaped (e.g. `signal2_value`,
  a version string) or to any output surface other than the snapshot file and this
  CLI.

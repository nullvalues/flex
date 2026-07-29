---
id: INFRA-295
rail: INFRA
title: "fleet_discovery snapshot targeting: default snapshot must not write into the scripts checkout"
status: complete
phase: "112"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_discovery.py
touches:
  - tests/pairmode/test_fleet_discovery.py
  - docs/architecture.md
  - docs/harness-cutover-runbook.md
  - docs/stories/INFRA/INFRA-295.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 112 defect 3. During the caddy migration (RELEASE-065), a native caddy
session ran `fleet_discovery.py` from the channel checkout without
`--no-snapshot`. The `--snapshot` default is resolved as
`_FLEX_ROOT / "docs" / "fleet-snapshot.md"` — `_FLEX_ROOT` being derived from
`Path(__file__)`, i.e. *the checkout the script lives in*, not the project the
operator is working in — so the run wrote `docs/fleet-snapshot.md` into
`/mnt/work/flex-harness`. That is a migration-story E11 violation (the scripts
checkout is a read-only release channel); it was caught and reverted by hand.

The tool's own contract says it is READ-ONLY, and the one write it permits
itself was justified in the architecture doc as "the snapshot under
`docs/fleet-snapshot.md` in THIS repo, which is not a scanned project". That
justification was written when THIS repo *was* the repo the operator was
working in. Post-fold, with `/mnt/work/flex-harness` as a permanent release
channel consumed by fleet projects, the derivation is wrong: the default now
resolves to a checkout that nobody invoking the tool intends to modify.

This story makes the default snapshot destination refuse to write into the
scripts checkout when the scripts checkout is not the repo the tool was invoked
from. It deliberately inverts a guarantee that two existing tests encode
("snapshot goes to the flex repo"), so those tests are rewritten rather than
extended, and the three doc surfaces that state the old rule are corrected in
the same story.

**Backlog pull, CER-059(a) (operator-approved at the phase-112 scaffold
review).** CER-059(a) itself — the Signal-2-only / zero-Signal-1 diagnosis — was
already **resolved in Phase 105 (INFRA-270)**: absence is now classified into
four reason codes and the zero-hit result was confirmed correct for a 0.2.x
fleet. The residual slice that belongs here, because it lives in the same
files, is the CER-059(b) runbook artefact: the Signal-1 verification command in
`docs/harness-cutover-runbook.md` (§ "Signal-1 verification step (CER-059b)")
is documented to be run *per project during migration* and omits
`--no-snapshot`, so following the runbook literally is exactly what produced
this defect. That command is corrected here. The rest of the CER-059 surface
(re-running fleet discovery to regenerate `docs/fleet-snapshot.md` with the new
reason codes across the whole fleet) is **deferred** — it is a fleet-operations
run, not a code change, and belongs with the RELEASE-066..070 campaign.

Recon already performed for the builder (do not redo it):

- Default resolution is one line: `fleet_discovery.py:555`
  (`dest = Path(snapshot_path) if snapshot_path else _FLEX_ROOT / "docs" / "fleet-snapshot.md"`),
  inside the `if not no_snapshot:` block at `:554`. `_write_snapshot`
  (`:381`) is the only writer and is called from exactly this one site.
- `_FLEX_ROOT` (`:49`) and `_THIS_SCRIPTS_DIR` (`:52`) are module-level and are
  already monkeypatched wholesale by the existing `patch_scripts_dir` fixture
  (`test_fleet_discovery.py:114-117`), so a new predicate that reads them is
  testable without new fixture machinery.
- The two tests that encode the old guarantee are
  `TestSnapshot::test_snapshot_written_to_flex_repo` (~:252) and
  `TestSnapshot::test_snapshot_does_not_write_to_scanned_project` (~:277).
- Doc surfaces stating the old default: module docstring options block
  (`fleet_discovery.py:18`), `--snapshot` help string (`:473`),
  `_write_snapshot` docstring (`:384`), `docs/architecture.md` § Fleet
  discovery "**Read-only contract:**" paragraph (~:3343) and the CLI options
  block (~:3374). (The phase dossier's `architecture.md:3291,:3322` line
  numbers are stale — locate by the quoted text, not by line number.)
- Existing CLI tests already use `click.testing.CliRunner` (e.g. `:396`,
  `:577`), so the new CLI-level tests follow that idiom.

## Requires

- No dependency on INFRA-293 or INFRA-294; this story touches a disjoint file
  set and may be built in any order within phase 112.
- `skills/pairmode/scripts/fleet_discovery.py` at HEAD still resolves the
  default snapshot destination from `_FLEX_ROOT` at `:555` (if a prior story
  has already changed this line, stop and report).
- Working tree clean at HEAD on `main`.

## Ensures

1. `fleet_discovery.py` defines a named, pure predicate — no I/O beyond path
   resolution — that answers "is the scripts checkout also the repo this
   invocation came from?". It takes the invoking directory and the flex root as
   explicit arguments (both defaulting to `Path.cwd()` and `_FLEX_ROOT`
   respectively) and returns `True` iff the resolved invoking directory is
   `flex_root` or is nested under it. Its docstring names the rule it protects:
   the scripts checkout is a read-only release channel.
2. `fleet_discovery.py` defines a default-destination resolver that returns
   `flex_root / "docs" / "fleet-snapshot.md"` when the predicate in Ensures 1
   is `True`, and `None` when it is `False`. It performs no writes.
3. With `--snapshot` omitted, `--no-snapshot` omitted, and the invoking
   directory *outside* the flex root, the CLI writes no snapshot file
   anywhere: no file named `fleet-snapshot.md` is created under either the
   flex root or the invoking directory. Asserted by a `CliRunner` test that
   monkeypatches `_FLEX_ROOT`/`_THIS_SCRIPTS_DIR` to a fixture checkout and
   `Path.cwd` (or chdir) to a directory outside it.
4. In that refusal case the CLI exits `0` and emits a warning naming both
   remedies — the string contains `--snapshot` and `--no-snapshot` — and names
   the path it declined to write. The refusal notice is emitted on stderr, so
   `--json` stdout remains valid parseable JSON in the refusal case (asserted
   by a test that `json.loads` the `--json` stdout with `mix_stderr=False`).
5. With `--snapshot` omitted and the invoking directory *inside* the flex root,
   the CLI still writes `<flex_root>/docs/fleet-snapshot.md` — flex's own
   in-repo use is unchanged.
6. An explicit `--snapshot PATH` is honoured unchanged in both cases, including
   a path that resolves inside the flex root from a foreign invoking directory:
   explicitness is the escape hatch, and there is exactly one guard site (the
   default-resolution path). `_write_snapshot` itself grows no refusal branch —
   no second, independent copy of the rule.
7. `--no-snapshot` behaviour is unchanged: no snapshot written, no refusal
   warning emitted.
8. `tests/pairmode/test_fleet_discovery.py::TestSnapshot::test_snapshot_written_to_flex_repo`
   is **rewritten** (not extended) so it no longer asserts "the default target
   is the flex repo": it asserts only that `_write_snapshot` writes the
   requested destination and that the content carries the header and gate
   notice. `test_snapshot_does_not_write_to_scanned_project` survives with its
   assertion intact but its docstring corrected to state the guarantee it
   actually still holds (no scanned project is ever written), not the retired
   default-target claim. `grep -n "Snapshot goes to flex repo"
   tests/pairmode/test_fleet_discovery.py` returns nothing.
9. A new test class covering Ensures 3–7 exists in
   `tests/pairmode/test_fleet_discovery.py` with at least five tests: refusal
   (no file written), refusal exit code + message content, refusal under
   `--json` (stdout still parses), in-repo default still writes, explicit
   `--snapshot` honoured from a foreign cwd.
10. Doc surfaces state the new rule, and no surface still states the old one:
    - `fleet_discovery.py` module docstring options block describes the
      `--snapshot` default as "the invoking flex checkout's
      `docs/fleet-snapshot.md`; refused when the scripts checkout is not the
      invoking repo".
    - The `--snapshot` Click `help=` string carries the same qualification.
    - `_write_snapshot`'s docstring no longer asserts "snapshot_path is under
      `_FLEX_ROOT`" as a fact; it states that the caller owns destination
      policy and that this function writes wherever it is told.
    - `docs/architecture.md` § Fleet discovery "**Read-only contract:**"
      paragraph records the new rule *with its rationale* (the scripts checkout
      is a permanent read-only release channel post-fold), and its CLI options
      block matches the corrected `--snapshot` help text.
    - `grep -rn "docs/fleet-snapshot.md" docs/architecture.md
      skills/pairmode/scripts/fleet_discovery.py` shows no remaining
      unqualified claim that the default writes into THIS repo.
11. `docs/harness-cutover-runbook.md` § "Signal-1 verification step (CER-059b)"
    bash block passes `--no-snapshot` (CER-059(a) pull), and the surrounding
    prose says why (the command is run from the project being migrated, not
    from the flex checkout).
12. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` completes
    with no failures other than the known pre-existing
    `test_observability_ui.py::test_ui_build_emits_dist_index_html`
    worktree-only failure (acceptable only if it also reproduces on clean
    HEAD).

## Instructions

1. **Decide nothing at build time — the rule is fixed here.** The default
   snapshot destination is *refuse-by-default when the scripts checkout is not
   the invoking repo*. Do **not** implement the alternative the phase doc lists
   ("target the invoking project"): silently creating `docs/fleet-snapshot.md`
   inside an arbitrary consumer repo trades one surprise write for another, and
   the fleet campaign runs this tool inside repos whose diffs are under review.
   Refusal is loud, reversible, and leaves the operator one flag away from
   either outcome.

2. In `skills/pairmode/scripts/fleet_discovery.py`, add the two helpers next to
   the existing path-resolution block (after `_THIS_SCRIPTS_DIR`, or in the
   snapshot-writer section above `_write_snapshot` — either is fine; keep them
   adjacent to each other):

   - the predicate from Ensures 1. Implement the containment check with
     `Path.resolve()` plus `is_relative_to` (Python 3.11+ is the project
     floor, per CLAUDE.md), not string prefix matching.
   - the default-destination resolver from Ensures 2, returning `Path | None`.

   Both take `invoking_dir` and `flex_root` as arguments with defaults so tests
   can call them directly *and* so the CLI path is exercised through the same
   code.

3. Replace the default-resolution line at `:555` so the `if not no_snapshot:`
   block reads: explicit `--snapshot` → `Path(snapshot_path)`; otherwise call
   the resolver. If the resolver returns `None`, do not call `_write_snapshot`;
   emit the refusal notice (Ensures 4) via `click.echo(..., err=True)` and fall
   through — the command must still exit 0, because discovery itself succeeded
   and the runbook/gate steps that call it must not start failing.

4. Do **not** add a guard inside `_write_snapshot`. One rule, one site. A
   second check there would be a duplicate writer of the same policy (the
   CP-112 cold-eyes "duplicate state" item) and would break the explicit
   `--snapshot` escape hatch.

5. Rewrite the two `TestSnapshot` tests per Ensures 8. These are unit tests of
   `_write_snapshot` and should stay that way — the destination *policy* is now
   CLI-level and belongs in the new class, not smuggled back into
   `TestSnapshot`.

6. Add the new test class (Ensures 9) using the existing `fleet` +
   `patch_scripts_dir` fixtures and `click.testing.CliRunner`, matching the
   idiom at `test_fleet_discovery.py:396` and `:577`. Simulate a foreign
   invoking directory with `monkeypatch.chdir(tmp_path / "elsewhere")` (a
   directory that is not under `fake_flex_root`) rather than patching
   `Path.cwd` globally. Pass `--candidate-dir` explicitly and keep
   `--no-snapshot` off for the refusal cases. For the `--json` refusal test,
   construct the runner with `mix_stderr=False` so stdout can be parsed
   independently of the warning.

7. Update the doc surfaces in the same commit (Ensures 10–11). The
   architecture-doc edit must carry the *reason*, not just the new rule — this
   is the project's "rationale-bearing decisions over bare rules" conviction,
   and the previous paragraph is a live example of what happens when a
   rationale ("which is not a scanned project") outlives the topology that made
   it true.

8. Ideology note (Step 4a, resolved inline): `docs/ideology.md` § Accepted
   constraints "Sidebar owns all state writes" is not engaged — the snapshot is
   a doc artefact, not `.companion/` state — and no conviction is contradicted.
   The alignment adjustment made was in step 7: the architecture-doc change is
   specified to record rationale alongside the rule rather than only the rule,
   to preserve the "rationale-bearing decisions" conviction. `docs/ideology.md`
   § Prototype fingerprints marks nothing here as "No"/"Conditional".

9. Do not run `fleet_discovery.py` against the real fleet from inside this
   build, and do not modify `/mnt/work/flex-harness` — that checkout is the
   read-only channel this story exists to protect. All verification is via the
   test suite against fixture checkouts.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_fleet_discovery.py -q
```

Then the full suite, without `-x` so the known pre-existing failure does not
mask a real one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:** the targeted run is fully green, including the rewritten
`TestSnapshot` tests and the new default-target class; the full run reports no
failures except `test_observability_ui.py::test_ui_build_emits_dist_index_html`
if and only if that failure also reproduces on clean HEAD.

## Out of scope

- **Regenerating `docs/fleet-snapshot.md`.** The committed snapshot is a dated
  artefact of a past run; refreshing it (with or without the INFRA-270 reason
  codes) is a fleet-operations run belonging to the RELEASE-066..070 campaign,
  not to this code change. This is the deferred remainder of the CER-059(a)
  pull.
- **Any change to Signal-1/Signal-2 detection, `signal1_absence_reason`, the
  duplicate-hooks signal, or the candidate-set logic.** This story touches only
  destination policy for the snapshot write.
- **Snapshot content or format.** No new columns, no new sections.
- **Generalising the "read-only channel" predicate into a shared module** for
  other scripts (e.g. `pairmode_sync.py`, `flex_build.py`) to import. If a
  second consumer appears, promote it then; one caller does not justify a
  shared surface, and `hook_view.py`-style extraction is a separate decision.
- **The hardcoded `/mnt/work/flex/skills/...` path in the runbook's Signal-1
  command.** Only `--no-snapshot` is added here; whether the runbook should
  point at the channel checkout is a runbook-accuracy question for the
  campaign.
- **INFRA-293's parser/sync work and INFRA-294's CER-guard fix.** Disjoint
  files, same phase.

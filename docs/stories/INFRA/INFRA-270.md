---
id: INFRA-270
rail: INFRA
title: Audit registered_projects writers and fix Signal-1 false negatives (CER-058, CER-059)
status: draft
phase: "105"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_register.py
  - skills/pairmode/scripts/fleet_discovery.py
touches:
  - skills/pairmode/scripts/pairmode_sync.py
  - tests/pairmode/test_register.py
  - tests/pairmode/test_fleet_discovery.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-270.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 105 de-risks the fleet campaign before Phase 106 drives migration from flex.
Two of the phase's five stories harden the *inputs* the campaign reads. This one owns
both halves of "does flex know what its fleet actually is": the **registration list**
(CER-058) and the **binding signal** (CER-059).

**CER-058 — unexplained `registered_projects` writes.** A brand-new project
(`meander`, bootstrapped 2026-06-26, still in inception) appeared in flex's
`.companion/state.json` `registered_projects` without the operator ever running
`pairmode_sync.py register`. The CER asks for an audit: *enumerate every writer of
`registered_projects` and confirm none bypasses the intended registration entry
point; if a bootstrap path writes it directly, either route it through `register` or
document the provenance.*

Recon done at spec time: `pairmode_register.py:154` (`register`) and
`pairmode_register.py:192` (`unregister`) are the **only** in-repo assignments to the
key. `pairmode_register.py:153` already carries the marker comment
`# intentional direct write: this IS the canonical register entry point (CER-058)`.
Every other reference is a read — `fleet_discovery._read_registered_projects:64-75`,
`pairmode_status.py:188`, `lesson_review.py:399`. `bootstrap.py` never writes the key;
it only *prints* the register command as operator guidance (`bootstrap.py:670`).

So the audit's conclusion is already visible: **no in-repo bypass path exists**, and
the `meander` entry was written out of band — a manual or agent-session edit of
`state.json`. That conclusion is worth nothing as a spec-time observation, because
nothing prevents the next such write and nothing records that the audit was ever run.
This story converts the finding into two durable artifacts: a **single-writer
regression test** that fails if any new module assigns the key, and a **provenance
sidecar** so an entry that arrived out of band is visibly distinguishable from one
that came through `register`. The four entries live today
(`/mnt/work/coherra`, `/mnt/work/meander`, `/mnt/work/caddy`,
`/mnt/work/forqsite.help`) predate provenance and must audit as `unknown` rather than
being retroactively invented.

**CER-059 — Signal-1 zero-hit.** `docs/fleet-snapshot.md` showed all discovered
projects bound via Signal 2 (`pairmode_version`) only, with **zero Signal 1
(`pairmode_scripts_dir`) hits**, on a fleet expected to be scripts-bound to this
checkout. Item (a) demanded a diagnosis before the pre-fold discovery gate runs,
because that gate reads Signal-1 binding to size the fold's blast radius and a false
negative under-reports it.

The diagnosis has since been written into `_check_signal1`'s docstring
(`fleet_discovery.py:108-115`): `_SCRIPTS_DIR_PATTERN` matches only the explicit
`pairmode_scripts_dir = <path>` key-value form, which `pairmode_sync.py sync-all
--apply` writes at 0.3.0 migration; 0.2.x projects embed the path only inside inline
shell commands. Zero hits across a 0.2.x fleet is therefore the *correct* result.

That closes the "is it a bug?" question but leaves the CER's actual concern open. The
tool still reports a bare `absent`, which is indistinguishable across three very
different situations: a project with no `CLAUDE.build.md` at all (not bound, no blast
radius), a 0.2.x project whose build loop calls **this checkout's** scripts inline
(bound, breaks at the fold, and today invisible if it has no `pairmode_version`), and
a project carrying a `pairmode_scripts_dir` declaration that resolves under a
**different** flex checkout (bound elsewhere — a genuine mis-binding). The gate cannot
size blast radius from a single boolean. This story makes Signal-1 absence
*diagnosable*: a reason code per project, surfaced in the CLI, the JSON, and the
snapshot.

Items (b) and (c) of CER-059 are already satisfied and are **assertions here, not
work**: `docs/harness-cutover-runbook.md` carries a `### Signal-1 verification step
(CER-059b)` section, and `docs/stories/RELEASE/RELEASE-002.md` is `status: complete`.
This story verifies both and retires the CER row rather than re-doing them.

**Ordering.** INFRA-269 lands first — both stories edit `fleet_discovery.py`
(INFRA-269 owns `_check_duplicate_hooks` and the snapshot's duplicate-hooks section;
this story owns `_check_signal1`'s neighbourhood and the per-project signal lines).
Build on top of INFRA-269's diff; never revert it.

## Requires

- **INFRA-269 is complete and merged**, and this story's worktree is cut from a `HEAD`
  that contains it. Verify before building:
  `git log --oneline -1 --grep 'INFRA-269'` returns a commit reachable from `HEAD`.
- `skills/pairmode/scripts/fleet_discovery.py` exposes the module-level path anchors
  `_SCRIPTS_DIR`, `_PAIRMODE_DIR`, `_SKILLS_DIR`, `_FLEX_ROOT`, `_THIS_SCRIPTS_DIR`,
  the `_SCRIPTS_DIR_PATTERN` regex, `_DOCUMENTED_CANDIDATES`,
  `_read_registered_projects()`, `_default_candidates()`, `_check_signal1(project_dir)
  -> tuple[bool, str | None]`, `_check_signal2(project_dir)`, `_check_duplicate_hooks(
  project_dir)` (INFRA-269), `discover(candidate_dirs) -> list[dict]`,
  `_write_snapshot(results, snapshot_path)`, and the `cli` click command.
- `skills/pairmode/scripts/pairmode_register.py` exposes `_DEFAULT_COMPANION_DIR`,
  `_depth_guard(path)`, `_read_state(companion_dir)`,
  `_write_state_atomic(companion_dir, state)`, and the three click commands
  `register`, `unregister`, `list_projects`.
- `skills/pairmode/scripts/pairmode_sync.py:1184-1190` imports those three commands
  from `pairmode_register` and attaches them to `pairmode_cli` via `add_command`.
- `docs/harness-cutover-runbook.md` contains a heading
  `### Signal-1 verification step (CER-059b)` and greps for the literal strings
  `Signal 1 (scripts path): present` / `Signal 1 (scripts path): absent`.
- `docs/stories/RELEASE/RELEASE-002.md` frontmatter reads `status: complete`.
- `docs/cer/backlog.md` contains a `CER-058` row and a `CER-059` row, neither
  carrying a `RESOLVED` note.
- `docs/architecture.md` documents `pairmode_register.py` (§ around line 1555), the
  `state.json` `registered_projects` key (§ around line 2023), and fleet discovery
  including the read-only constraint and the drift-opt-in rule (§ around lines
  2981-3013).

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a command.

### A — `registered_projects` has exactly one writer, provably

**A1. The single-writer rule is a test, not a comment.**
`tests/pairmode/test_register.py` gains `test_registered_projects_has_a_single_writer`,
which walks every `*.py` file under `skills/` and `hooks/` (excluding `tests/` and
`__pycache__`), and asserts that the set of files containing an **assignment** to the
key — matched by the regex `r'''\[\s*["']registered_projects["']\s*\]\s*='''` or
`r'''["']registered_projects["']\s*:\s*'''` in a dict literal being written to state —
is exactly `{skills/pairmode/scripts/pairmode_register.py}`. The failure message names
the offending file and states that a new writer must either route through
`pairmode_register.register` or be added to the allow-list *with a recorded reason*.
Read-only references (`state.get("registered_projects"...)`) must not trip it — a test
asserts the matcher does not flag `fleet_discovery.py`, `pairmode_status.py`, or
`lesson_review.py`.

**A2. The allow-list is a named module constant, not a literal in the test body.**
`pairmode_register.REGISTERED_PROJECTS_WRITERS` is a `frozenset` whose single member is
the string `"skills/pairmode/scripts/pairmode_register.py"`, documented as the CER-058
single-writer invariant. A1's test reads it. (`spec-preflight` will report
`REGISTERED_PROJECTS_WRITERS`, `REGISTERED_PROJECTS_PROVENANCE_KEY`, `audit_projects`,
`_provenance_for`, `PROVENANCE_UNKNOWN`, `signal1_absence_reason`,
`SIGNAL1_ABSENT_*` and `_INLINE_BINDING_SENTINELS` as undefined — intentional; this
story creates all of them.)

**A3. Registration records provenance in a sidecar key.**
`pairmode_register.REGISTERED_PROJECTS_PROVENANCE_KEY == "registered_projects_provenance"`.
`register` writes `state["registered_projects_provenance"][<resolved path str>] =
{"source": <str>, "registered_at": <iso8601 utc>}` inside the same
`_write_state_atomic` call it already performs — **no second write**. `source` comes
from a new `--source` option defaulting to `"cli"`. `unregister` deletes the matching
provenance entry in its existing write. Neither command errors when the sidecar key is
missing or is not a dict; both treat it as `{}`.

**A4. `registered_projects` keeps its shape.** The sidecar is additive: after
`register`, `state["registered_projects"]` is still a flat `list[str]` of absolute
paths in insertion order, and `fleet_discovery._read_registered_projects()`,
`pairmode_status.py:188`, and `lesson_review.py:399` are **unmodified** —
`git diff --stat` shows no change to `pairmode_status.py` or `lesson_review.py`. A test
writes a pre-INFRA-270 state (list present, no sidecar), runs `register` for a new
path, and asserts the four pre-existing entries survive verbatim.

**A5. Pre-existing entries audit as `unknown`, and are not invented.**
`pairmode_register.PROVENANCE_UNKNOWN == "unknown"`. `_provenance_for(state, path)`
returns the recorded entry, or `{"source": PROVENANCE_UNKNOWN, "registered_at": None}`
when the path has no sidecar record. No code path back-fills a fabricated
`registered_at` for a historical entry.

**A6. An `audit` subcommand reports the finding.** A new click command
`audit_projects` (command name `audit-projects`) in `pairmode_register.py` prints one
line per registered path in list order — `<path> — source: <source> — registered_at:
<iso|->` — followed by a summary line
`N registered, M with recorded provenance, K unknown (pre-INFRA-270)`. It also flags,
on its own line prefixed `WARN:`, any registered path that does not exist on disk or
lacks a `.companion/` directory. It is **read-only**: it never writes `state.json`
(a test asserts the file's bytes are unchanged across the call). It accepts the same
hidden `--companion-dir` override as the other three commands, and supports `--json`
emitting `{"registered": [...], "unknown_count": int}`.

**A7. The command is reachable from the documented CLI.**
`pairmode_sync.py` imports `audit_projects` alongside `register`/`unregister`/
`list_projects` at `pairmode_sync.py:1185` and attaches it with `pairmode_cli.add_command(
audit_projects)`. `PATH=$HOME/.local/bin:$PATH uv run python
skills/pairmode/scripts/pairmode_sync.py audit-projects --help` exits 0.

**A8. The audit's conclusion is recorded where it survives.** `docs/architecture.md`'s
`pairmode_register.py` section states, in at most one short paragraph: that
`registered_projects` has exactly one writer by invariant, that the invariant is
enforced by `test_registered_projects_has_a_single_writer` against
`REGISTERED_PROJECTS_WRITERS`, that entries predating this story carry
`source: unknown` because their provenance is genuinely unrecoverable, and that an
out-of-band edit of `state.json` remains possible — the invariant covers *code paths*,
not the filesystem. It must not claim `meander` was traced to a specific writer; the
audit found no in-repo bypass, and asserting more than that would be a fabrication.

### B — Signal-1 absence is diagnosable

**B1. `_check_signal1`'s contract is unchanged.** It still returns
`tuple[bool, str | None]` with today's semantics, and every existing test in
`tests/pairmode/test_fleet_discovery.py::TestSignal1` passes **by its original name**.
The diagnosis is delivered by a *new, separate* pure function so the additive contract
holds (era doc § Compatibility strategy, DP4).

**B2. Four reason codes exist as named constants.** In `fleet_discovery.py`:
`SIGNAL1_ABSENT_NO_BUILD_MD == "no-build-md"`,
`SIGNAL1_ABSENT_NO_DECLARATION == "no-declaration"`,
`SIGNAL1_ABSENT_INLINE_ONLY == "inline-only"`,
`SIGNAL1_ABSENT_FOREIGN_CHECKOUT == "foreign-checkout"`.

**B3. `signal1_absence_reason(project_dir)` classifies, purely.** It returns
`tuple[str | None, str | None]` — `(reason_code, detail_or_none)` — and:
- returns `(None, None)` when `_check_signal1` matched (there is no absence to explain);
- returns `(SIGNAL1_ABSENT_NO_BUILD_MD, None)` when `CLAUDE.build.md` is missing or unreadable;
- returns `(SIGNAL1_ABSENT_FOREIGN_CHECKOUT, <the raw declared value>)` when at least one
  `_SCRIPTS_DIR_PATTERN` match exists but none resolves under `_THIS_SCRIPTS_DIR` or `_FLEX_ROOT`;
- returns `(SIGNAL1_ABSENT_INLINE_ONLY, <the matched sentinel>)` when there is **no**
  key-value declaration but the file text contains `str(_THIS_SCRIPTS_DIR)` or
  `str(_FLEX_ROOT)` — the two members of `_INLINE_BINDING_SENTINELS`, checked longest-first
  so the more specific scripts path is reported when both match;
- returns `(SIGNAL1_ABSENT_NO_DECLARATION, None)` otherwise.

It performs **no writes** and never raises: any `OSError` or decode failure yields
`(SIGNAL1_ABSENT_NO_BUILD_MD, None)`. It is checked in that order — foreign-checkout
outranks inline-only, because an explicit declaration is stronger evidence of intent
than a path appearing in a shell line.

**B4. `discover()` carries the reason.** Every result dict gains
`"signal1_absent_reason": str | None` and `"signal1_absent_detail": str | None`. For a
project where Signal 1 matched, both are `None`. Every existing key
(`path`, `signal1`, `signal1_value`, `signal2`, `signal2_value`, `binding`,
`duplicate_hooks`) keeps its current name and semantics.

**B5. Inline-bound and foreign-bound projects are no longer invisible.** `discover()`'s
"skip when neither signal fired" rule is relaxed for exactly the two at-risk reasons: a
project with `signal1 == False`, `signal2 == False`, and a reason of
`SIGNAL1_ABSENT_INLINE_ONLY` or `SIGNAL1_ABSENT_FOREIGN_CHECKOUT` **is** included in
results, with `binding` set to `"inline"` or `"foreign"` respectively. A project whose
reason is `no-build-md` or `no-declaration` and which fired no signal is still skipped,
exactly as today. Tests assert both directions, and assert that `binding` for the
pre-existing cases is still exactly `"scripts"` / `"version"` / `"both"` — the four new
projects-with-no-signal-2 cases must not perturb any existing classification.

This relaxation is the substance of CER-059(a): the pre-fold gate reads this output to
size blast radius, and a 0.2.x project that calls this checkout's scripts inline breaks
at the fold whether or not it has a `pairmode_version`.

**B6. The CLI surfaces the reason without breaking the runbook's greps.** For a result
with `signal1 == False`, the human output prints
`    signal1 (scripts path): absent — <reason>` and, when `signal1_absent_detail` is
set, ` (<detail>)`. The `--json` output includes both new keys.
`docs/harness-cutover-runbook.md`'s literals `Signal 1 (scripts path): present` and
`Signal 1 (scripts path): absent` continue to appear verbatim in the **snapshot** (B7),
and the runbook is **not edited** — `git diff --stat docs/harness-cutover-runbook.md`
shows no change.

**B7. The snapshot renders the reason as a suffix, not a replacement.**
`_write_snapshot` emits, for an absent Signal 1,
`- **Signal 1 (scripts path):** absent — <reason>` (plus ` — \`<detail>\`` when set), so
the substring `Signal 1 (scripts path):** absent` still matches. The `present` line is
unchanged. A test asserts a generated snapshot contains both the literal
`Signal 1 (scripts path):** absent` and the reason code text.

**B8. Read-only discipline holds.** `signal1_absence_reason`, `discover`, and the
extended snapshot writer write nothing to any scanned project. The existing
`TestReadOnly` tests pass unchanged, and a new test asserts `signal1_absence_reason`
does not create or modify any file in a fixture project directory
(`docs/architecture.md` § fleet discovery, read-only constraint).

**B9. The tool still never writes `registered_projects`.** The drift-opt-in rule
(`docs/architecture.md`: *"the discovery tool never writes to `registered_projects`"*)
survives: `grep -n 'registered_projects' skills/pairmode/scripts/fleet_discovery.py`
shows only reads.

### C — CER-059 items (b) and (c) are verified, not rebuilt

**C1. The runbook's Signal-1 verification step exists.**
`grep -c 'Signal-1 verification step (CER-059b)' docs/harness-cutover-runbook.md`
prints `1`. No edit is made to the runbook.

**C2. RELEASE-002 is reconciled.** `grep -n '^status:' docs/stories/RELEASE/RELEASE-002.md`
prints `status: complete`. No edit is made to that story file.

### D — documentation and CER rows

**D1. Architecture is updated in two places, briefly.**
`docs/architecture.md`'s fleet-discovery section gains at most two short paragraphs
naming the four reason codes, stating why `no-declaration` is the *correct* result for a
0.2.x project rather than a bug (CER-059a), and stating why `inline` and `foreign`
bindings are now reported despite firing neither signal (blast-radius accuracy at the
pre-fold gate). The `pairmode_register.py` section gains A8's paragraph. No new
`##`-level heading is added, and the documented `state.json` key list (§ ~line 2023)
gains a one-line entry for `registered_projects_provenance` marked **optional**.

**D2. Both CER rows carry a RESOLVED note.** `docs/cer/backlog.md`'s `CER-058` and
`CER-059` rows each gain a bolded `**RESOLVED Phase 105 — INFRA-270 …**` note appended
to the Finding cell, and each row's `Phase` cell reads `105`. Neither row is deleted or
moved between quadrants. CER-058's note must state the audit's *actual* finding — no
in-repo writer bypasses `register`; the `meander` entry has no recoverable provenance
and audits as `unknown`; the invariant is now test-enforced but covers code paths only.
CER-059's note must name (a) as diagnosed-and-instrumented, and (b)/(c) as verified
pre-existing.

**D3. `schema_introduces` stays `false`.** `registered_projects_provenance` is a new key
inside the existing `.companion/state.json`, not a new persistent schema object — no row
is owed in `docs/phases/phase-105.md` § Schema delivery. The management surface is the
`audit-projects` / `list-projects` / `register` / `unregister` CLI, which already exists.

**D4. No migration step, and no legacy breakage.** A `state.json` with
`registered_projects` and no `registered_projects_provenance` is read correctly by every
changed reader and is upgraded on its next successful `register`/`unregister`. A test
loads a pre-INFRA-270 fixture and asserts `audit-projects`, `list-projects`, and
`discover()` all behave. No entry in `pairmode_migrate.py` is added.

## Instructions

You are the builder. Work only in this repository, inside your story worktree. Build A
then B; they are independent, and A is smaller. Run the suite after each.

**0. Rebase check.** Confirm INFRA-269 is in your `HEAD` (§ Requires). Read the current
bodies of `_check_signal1`, `_check_duplicate_hooks`, `discover`, `_write_snapshot` and
the `cli` command **as they exist after INFRA-269** — every line number in this spec is
an anchor, not a coordinate. Layer on top of INFRA-269's changes; never revert them to
make an assertion here easier to satisfy. If a genuine conflict exists, stop and report
`FAIL-CAUSE`.

**1. (A) Extend `pairmode_register.py`.** Add `REGISTERED_PROJECTS_WRITERS`,
`REGISTERED_PROJECTS_PROVENANCE_KEY`, `PROVENANCE_UNKNOWN`, `_provenance_for`, and the
`audit_projects` command. Thread `--source` into `register`.

The provenance write must ride **inside** the existing `_write_state_atomic` call, not
beside it: `register` currently does one read, one mutate, one atomic write, and that
shape is what makes it safe under the concurrent-session conditions INFRA-285 hardened
for. Adding a second write would reintroduce exactly the read-modify-write window that
story closed. Comment the line with that reason.

Keep the sidecar tolerant in both directions: a missing key, a `None`, a list, or a
string where a dict is expected must all degrade to `{}` rather than raise. `register`
is an operator command whose failure mode is a confused operator, and `unregister` must
stay usable to clean up exactly the kind of hand-edited state that produced CER-058.

**2. (A) Write the single-writer test.** In `tests/pairmode/test_register.py`, resolve
the repo root from `__file__` (do not hardcode `/mnt/work/flex` — `_FLEX_ROOT`-style
relative anchoring is the established convention, see `fleet_discovery.py:38-45`), walk
`skills/` and `hooks/`, and compare against `REGISTERED_PROJECTS_WRITERS`.

Make the failure message do the teaching. This test exists because the *policy* —
"registration goes through `register`" — was previously only a convention plus a comment
at `pairmode_register.py:153`, and a convention is what CER-058 already got violated
against. A future builder who trips this test must be told from the assertion message
what the invariant protects (fleet-discovery accuracy at the pre-fold gate) and what the
two legitimate resolutions are.

**3. (A) Wire the CLI and document.** Add `audit_projects` to `pairmode_sync.py:1185`'s
import and `add_command` block. Write A8's architecture paragraph. Be precise about what
the audit found: *no in-repo bypass path exists*. Do not write that `meander` was traced
to bootstrap or to any named path — it was not, and the honest finding is that
provenance is unrecoverable. Overclaiming here is worse than the gap, because the next
operator reads this paragraph instead of re-running the audit.

**4. (B) Add the reason classifier to `fleet_discovery.py`.** Define the four
`SIGNAL1_ABSENT_*` constants and `_INLINE_BINDING_SENTINELS = (str(_THIS_SCRIPTS_DIR),
str(_FLEX_ROOT))` next to `_SCRIPTS_DIR_PATTERN`, then write `signal1_absence_reason` as
a new module-level pure function immediately after `_check_signal1`.

Do **not** widen `_check_signal1`'s return tuple. Three existing tests unpack it as a
2-tuple, `discover()` unpacks it as a 2-tuple, and the era's additive-until-flip contract
(era doc § Compatibility strategy, DP4) says existing signatures stay
backward-compatible through the migration window. A separate function costs one extra
`CLAUDE.build.md` read per project in `discover()`; that is acceptable for a tool that
runs at operator cadence over ~16 candidates. If you want to avoid the double read,
factor a private `_read_build_md(project_dir) -> str | None` used by both — but the
public shape of `_check_signal1` does not change either way.

Move the CER-059a diagnosis out of `_check_signal1`'s docstring and into
`signal1_absence_reason`'s, expanded: the docstring must explain what each of the four
codes *means for the fold*, not just what it detects. `no-declaration` means "0.2.x
shape, will bind after `sync-all --apply`"; `inline-only` means "bound to this checkout
today and breaks at the fold"; `foreign-checkout` means "bound to a different flex
checkout — investigate before assuming it is ours"; `no-build-md` means "not a pairmode
project". Leave a one-line pointer in `_check_signal1`'s docstring rather than deleting
the reference entirely.

**5. (B) Thread it through `discover`, the CLI, and the snapshot.** Add the two keys to
the result dict (B4), relax the skip rule for the two at-risk reasons (B5), and extend
the human output (B6) and `_write_snapshot` (B7).

The snapshot format is load-bearing on a document you are not allowed to edit:
`docs/harness-cutover-runbook.md` instructs the operator to look for
`Signal 1 (scripts path): absent` / `present`. Append the reason **after** the existing
text; never rewrite the line's prefix. Verify by grepping the generated snapshot, not by
inspection.

**6. (C) Verify, do not rebuild.** Run C1 and C2's greps. If either fails, stop and
report `FAIL-CAUSE` — a missing runbook section or a non-`complete` RELEASE-002 means
the phase's assumptions moved, and inventing the fix here would put it in the wrong
story.

**7. Tests.** Extend `tests/pairmode/test_register.py` (A1–A6, D4) and
`tests/pairmode/test_fleet_discovery.py` (B2–B9, D4). Follow each file's existing
fixture style — `test_fleet_discovery.py` is class-organised (`TestSignal1`,
`TestSignal2`, `TestDiscover`, `TestReadOnly`, `TestSnapshot`,
`TestCheckDuplicateHooks`); add a `TestSignal1AbsenceReason` class and extend the
existing classes rather than adding loose functions. Delete no test, and rename no
existing test.

For B5 you need a fixture project whose `CLAUDE.build.md` contains this checkout's real
scripts path inline. Build the path from `fleet_discovery._THIS_SCRIPTS_DIR` at test
time — do not hardcode it, or the test breaks in every worktree, which is precisely
where this suite runs.

**8. Docs and CER rows.** Write D1's paragraphs and D2's two RESOLVED notes.

**9. Ideology note (Step 4a — resolved inline, no conflict).** Three entries shaped this
spec. *"We prefer codifying policy over implicit convention"* is why A1 exists at all:
the CER-058 single-writer rule was already a comment and already got violated, so this
story converts it to an executable check. *"Sidebar owns all state writes"* (no override
permitted) is satisfied without tension — `pairmode_register.py` is a skill script, one
of the two sanctioned writer classes, and this story **narrows** the writer set rather
than widening it; no hook and no new module gains write access. *"Rationale-bearing
decisions over bare rules"* is why step 4 requires the four reason codes to carry their
fold-consequence in the docstring rather than being bare enum strings, and why A8 and
D2 forbid overclaiming the audit's finding — a recorded conclusion stronger than the
evidence is the failure mode this conviction exists to prevent.

## Tests

Run from the story worktree root. After each item:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_register.py \
  tests/pairmode/test_fleet_discovery.py \
  -q 2>&1 | tail -30
```

Then the adjacent surface, to catch collateral damage from the `discover()` result-shape
change and the `pairmode_sync` command wiring:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_pairmode_sync.py \
  tests/pairmode/test_pairmode_status.py \
  tests/pairmode/test_lesson_review.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
# A — single writer, wired CLI
grep -rn '\["registered_projects"\]\s*=' skills/ hooks/ --include=*.py   # only pairmode_register.py
grep -n 'audit_projects' skills/pairmode/scripts/pairmode_sync.py        # import + add_command
PATH=$HOME/.local/bin:$PATH uv run python \
  skills/pairmode/scripts/pairmode_sync.py audit-projects --help         # exits 0

# B — reasons exist, discovery still read-only w.r.t. registration
grep -n 'SIGNAL1_ABSENT_' skills/pairmode/scripts/fleet_discovery.py     # four constants
grep -n 'registered_projects' skills/pairmode/scripts/fleet_discovery.py # reads only

# C — verify-only items
grep -c 'Signal-1 verification step (CER-059b)' docs/harness-cutover-runbook.md   # 1
grep -n '^status:' docs/stories/RELEASE/RELEASE-002.md                            # complete
git diff --stat docs/harness-cutover-runbook.md docs/stories/RELEASE/RELEASE-002.md  # empty

# D — CER rows retired
grep 'CER-058' docs/cer/backlog.md | grep -c 'RESOLVED Phase 105'        # 1
grep 'CER-059' docs/cer/backlog.md | grep -c 'RESOLVED Phase 105'        # 1

# untouched readers
git diff --stat skills/pairmode/scripts/pairmode_status.py \
                skills/pairmode/scripts/lesson_review.py                 # empty
```

Acceptance:

- every new test from A1–A6, B2–B9, D4 passes;
- every pre-existing test in `test_register.py` and `test_fleet_discovery.py` passes
  **by its original name** — especially `TestSignal1`'s three tests and `TestDiscover`'s
  six, whose subjects this story extends rather than replaces;
- the full suite is green. If a failure appears, verify it reproduces on clean `HEAD`
  before attributing it elsewhere, and say so explicitly in the build result.

## Out of scope

- **Un-registering `meander`, or any live fleet-state edit.** This story builds the audit
  and reports the finding; deciding whether a registered project belongs in the list is an
  operator call, and `.companion/state.json` is runtime state, not a build artifact. The
  builder must not modify flex's own `registered_projects`.
- **Enforcing registration provenance.** `register --source` records what the caller
  claims; nothing validates it, and nothing blocks an unattributed entry. A trust model
  for registration provenance is not warranted for an operator-run CLI and would be its
  own story.
- **Preventing out-of-band `state.json` edits.** The single-writer invariant covers
  in-repo code paths. A hook, watcher, or file-integrity check over `.companion/state.json`
  is forbidden here by *"hooks are thin relays only"* (`docs/ideology.md` § Accepted
  constraints, **no override permitted**) and is not attempted.
- **Editing `docs/harness-cutover-runbook.md` or `docs/stories/RELEASE/RELEASE-002.md`.**
  CER-059(b) and (c) are already satisfied; this story asserts them (C1, C2). Touching
  either file would collide with the runbook's ownership by the RELEASE rail.
- **Regenerating `docs/fleet-snapshot.md`.** The snapshot is the output of a live fleet
  scan, not a checked-in artifact this story maintains. The authoritative regeneration is
  the pre-fold discovery gate run (DP8), which happens in Phase 106.
- **Anything INFRA-269 owns.** `_check_duplicate_hooks`, the bootstrap registrars'
  dedupe, and the snapshot's duplicate-hooks section. Build on that diff; do not alter it.
- **Changing `_check_signal1`'s matching regex or its return shape.** The zero-hit result
  is correct for a 0.2.x fleet (CER-059a); widening `_SCRIPTS_DIR_PATTERN` to match inline
  command forms would turn a true negative into a true positive with the wrong semantics —
  `binding: scripts` is meant to signal a *0.3.0 declaration*, which is what the pre-fold
  gate tests for.
- **Teaching the observability SPA to render provenance or Signal-1 reasons.** OBS-rail
  work (era doc § Phase G scope); it would widen this story into a cross-language change.

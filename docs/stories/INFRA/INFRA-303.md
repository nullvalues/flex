---
id: INFRA-303
rail: INFRA
title: "Migration tooling: rules 9/10 name parity; expected_step_tokens opt-out and honest CER-111 disposition"
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_migrate.py
touches:
  - tests/pairmode/test_pairmode_migrate.py
  - docs/cer/backlog.md
  - docs/architecture.md
  - docs/stories/INFRA/INFRA-303.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This story closes the two migration-tooling rows left in the Do Later backlog —
CER-108 (`docs/cer/backlog.md:56`) and CER-111 (`docs/cer/backlog.md:59`) — and
it is a campaign edge: the fleet migration campaign's next dispatch,
RELEASE-070 (Repo-G, 0.1.0 → 0.3.0), is the fleet project most likely to still
carry `anchor:`-prefixed skill names, because it is the oldest bootstrap on the
fleet. The fix must therefore be on the `/mnt/work/flex-harness` release
channel before RELEASE-070 runs, not merely on `main` (§ Ensures F).

**CER-108 — real, small, and asymmetric.** `MIGRATION_RULES` rule 8
(`pairmode_migrate.py:176-184`) carries two patterns: it rewrites the
`/anchor:seed` command reference *and* the SKILL.md frontmatter name via
`(r"\bname:\s*anchor:seed\b", "name: seed")`. Rules 9 and 10
(`:185-193`, `:194-202`) — the pairmode and companion SKILL.md rules — carry
only the command-reference pattern. A migrated anchor project therefore emerges
with `/flex:pairmode` in its prose but `name: anchor:pairmode` still in its
SKILL.md frontmatter. The asymmetry is pre-existing; INFRA-292 made it visible
by fixing rule 8. The correct target is the **bare** name (`name: pairmode`),
not `name: flex:pairmode` — Claude Code already applies the plugin namespace,
and a `flex:` prefix in frontmatter doubles it. That is the same conclusion
INFRA-292 reached for seed, and it is enforced in this repo by
`tests/pairmode/test_plugin_manifest.py::_EXPECTED_SKILL_NAMES`
(`:30-35`), which asserts bare names for all four skills.

**CER-111 — the backlog row's premise is wrong, and the annotation must say so.**
The row reads: *"`to-030` silently rewrote Repo-J's custom `expected_step_tokens`
53000 → 5000; canary run kept the custom value with a WARN — restore keep+WARN
(or prompt) for custom values."* Three separate claims in that sentence do not
survive contact with the code at `pairmode_migrate.py:952-971`:

1. **Nothing was removed, so nothing can be "restored".** The B6 block is a
   three-way branch and always has been: `est == ERA2_STAMP` → rewrite (`:956`);
   `est is not None and est != THIN_HARNESS_STEP_TOKENS` → keep with a `[WARN]`
   line (`:969-971`); otherwise → silent no-op. keep+WARN is live on `main`
   today and is pinned by an existing test
   (`test_pairmode_migrate.py::test_to030_keeps_custom_expected_step_tokens`,
   `:856`). The fix direction the row proposes is a no-op.
2. **The two observations are not a contradiction; they are the two arms of a
   clean A/B, and the discriminator is the value itself.**
   `ERA2_STAMP = 53000` (`:733`) is the Era 2 fleet-wide stamp. Repo-J's custom
   value was *exactly* 53000, so it took the rewrite arm. The canary's value was
   not 53000, so it took the keep+WARN arm. Both behaved exactly as written.
   A deliberately-chosen 53000 and the Era 2 stamp are **definitionally
   indistinguishable** in `state.json` — the file records a number, not its
   provenance. No code change can tell them apart.
3. **"Silently" is inaccurate.** The rewrite arm echoes
   `[apply] rewrote expected_step_tokens: 53000 → 5000` (`:963`). It was
   *unnoticed*, not silent. That distinction matters, because it moves the
   remedy from "add an echo" to "make the echo say something the operator can
   act on".

**Session-fresh field evidence confirming the 2×2.** Repo-F (RELEASE-067,
2026-07-29) held exactly `53000` and hit the rewrite arm; the operator reviewed
the echoed line and **accepted** the stamp rewrite. Repo-D, Repo-C and
Repo-B each held `53416` and hit the keep+WARN arm, value preserved. Four
projects, two values, two arms, zero deviations — the branch is correct and the
only genuine defect is that the rewrite arm gives an operator holding a
deliberate 53000 no way to say "no".

**Therefore the remedy is an escape hatch and an honest message, not a
behaviour restoration.** This story adds a `--keep-expected-step-tokens`
opt-out flag to `to-030` that suppresses B6 entirely, and rewrites the rewrite
arm's message to name the ambiguity and the flag. Recording provenance for the
value (a `state.json` key saying "this 53000 was chosen, not stamped") was
considered and **rejected**: it would add a permanent fleet-wide state key to
serve a one-time migration command, and it cannot help the projects already
migrated — the ones the row is about. That rejection is recorded in
§ Out of scope, not silently omitted.

The backlog annotation this story writes must state the corrected analysis
plainly, including that the row's premise was wrong. Annotating CER-111 as
"RESOLVED — keep+WARN restored" would put a false statement into the permanent
record and is explicitly forbidden by § Ensures C2.

## Requires

Re-verified against the working tree at spec time (2026-07-29,
`main` @ `1c4af83d`). A builder finding any of these anchors moved should
re-locate by symbol name, not by line number, and note the drift in its report.

- `MIGRATION_RULES` rule 8 (`skills/pairmode/scripts/pairmode_migrate.py:176-184`)
  has patterns `(r"\bname:\s*anchor:seed\b", "name: seed")` and
  `(r"/anchor:seed\b", "/flex:seed")`.
- Rule 9 (`:185-193`, `description="skills/pairmode/SKILL.md — regex substitution"`)
  has exactly one pattern: `(r"/anchor:pairmode\b", "/flex:pairmode")`.
- Rule 10 (`:194-202`, `description="skills/companion/SKILL.md — regex substitution"`)
  has exactly one pattern: `(r"/anchor:companion\b", "/flex:companion")`.
- `MIGRATION_RULES` has 14 entries with sequential ids 1..14, pinned by
  `test_pairmode_migrate.py::test_migration_rules_has_14_entries` (`:737`) and
  `::test_migration_rules_ids_are_sequential_1_to_14` (`:740`).
- `THIN_HARNESS_STEP_TOKENS = 5000` (`:732`); `ERA2_STAMP = 53000` (`:733`).
- `cmd_to_030` (`:907-918`) declares exactly two options: `--project-dir`
  (required) and `--apply` (flag, default `False`).
- The B6 block sits at `:952-971`, between the B5 state-seed block
  (`:930-950`) and the B4 `pipe_path` block (`:973+`).
- The test module is `tests/pairmode/test_pairmode_migrate.py` (confirmed —
  there is no `test_migrate.py`). Its helpers: `_build_anchor_project` (`:34`),
  `_run_migrate_no_subprocess`, `_build_030_project` (`:794`), `_invoke_030`
  (`:808`, builds `args = ["to-030", "--project-dir", str(project_dir)]` and
  appends `--apply`).
- The migrate fixture's SKILL.md files carry **no frontmatter today**:
  `skills/pairmode/SKILL.md` is written at `:126` as
  `"Use /anchor:pairmode to bootstrap a project.\n"`; `skills/companion/SKILL.md`
  at `:95` as `"# Companion skill\nUse /anchor:companion to start.\n"`. The
  second (idempotency) fixture writes the same two files at `:497` and `:505`.
  Both fixtures must gain `name:` frontmatter for the new rules to have anything
  to rewrite.
- `test_plugin_manifest.py:30-35` maps all four `skills/*/SKILL.md` paths to
  **bare** names.
- Baseline: `main`'s suite is green — 4116 passed, 211 skipped. The
  `test_observability_ui` failure is **worktree-only** (CER-090: the vendored
  `node_modules` payload is incomplete in a fresh worktree). If it appears, fix
  it by `rsync`-ing the payload from the main checkout — **never** by running
  `pnpm install`.

No sibling story in Phase 114 is a prerequisite. INFRA-303 touches
`pairmode_migrate.py`, which no other Phase 114 story edits; the only shared
file is `docs/cer/backlog.md` (INFRA-304 and INFRA-305 also annotate rows) —
edit only the CER-108 and CER-111 rows.

## Ensures

### A — CER-108: rules 9 and 10 reach frontmatter parity with rule 8

**A1.** Rule 9's `patterns` list gains `(r"\bname:\s*anchor:pairmode\b", "name: pairmode")`,
mirroring rule 8's shape exactly (same `\b` anchoring, same `\s*`, same bare
replacement). Rule 10's `patterns` list gains
`(r"\bname:\s*anchor:companion\b", "name: companion")`.

**A2.** The replacement is **bare**, not `flex:`-prefixed. After the change,
`grep -n 'name: flex:' skills/pairmode/scripts/pairmode_migrate.py` returns no
match, and each new pattern's replacement string contains no `flex:`.

**A3.** No new `MigrationRule` is added and no rule id changes:
`test_migration_rules_has_14_entries` and
`test_migration_rules_ids_are_sequential_1_to_14` still pass unmodified.

**A4.** The existing command-reference patterns on rules 9 and 10 are unchanged
and still ordered first in each `patterns` list, so `/anchor:pairmode` →
`/flex:pairmode` and `/anchor:companion` → `/flex:companion` continue to apply.

**A5.** Both migrate fixtures in `tests/pairmode/test_pairmode_migrate.py` are
extended so `skills/pairmode/SKILL.md` and `skills/companion/SKILL.md` carry
YAML frontmatter containing `name: anchor:pairmode` / `name: anchor:companion`
respectively, in **block style**, alongside the existing `/anchor:` prose. Both
`_build_anchor_project` (`:34`) and the idempotency fixture (`:490-510`) are
updated, so the idempotency assertion covers the new patterns too.

**A6.** A test named for CER-108 asserts, after `--apply` against the fixture
project: `skills/pairmode/SKILL.md` contains `name: pairmode`, does **not**
contain `name: flex:pairmode`, and does **not** contain `anchor:pairmode`
anywhere; and the same three assertions for companion
(`name: companion` / not `name: flex:companion` / no `anchor:companion`). Its
docstring names CER-108 and INFRA-292's bare-name rationale.

**A7.** `test_migrate_idempotent` (`:532`) still passes with the extended
fixture — a second `--apply` produces no further changes to either SKILL.md.

### B — CER-111: `--keep-expected-step-tokens` opt-out and an ambiguity-naming message

**B1.** `cmd_to_030` gains a third Click option,
`--keep-expected-step-tokens`, declared `is_flag=True, default=False`, with
help text naming what it suppresses (the B6 `expected_step_tokens` step) and
why an operator would want it (a deliberately-chosen value that happens to
equal the Era 2 stamp). The option is additive: `--project-dir` and `--apply`
keep their current names, types and defaults.

**B2.** When the flag is passed, the B6 block is suppressed **entirely** —
neither the rewrite arm nor the WARN arm runs, and `state["expected_step_tokens"]`
is never assigned. B6 instead emits exactly one informational line naming the
observed value and the flag, e.g.
`[keep] expected_step_tokens=53000 — left unchanged (--keep-expected-step-tokens)`.
No `[apply]`/`[would]` rewrite line and no `[WARN]` line is emitted for B6 in
this mode.

**B3.** Suppression is scoped to B6 only. With the flag passed, every other
`to-030` step (B5 state seed, B4 `pipe_path` removal, `[agent-cleanup]`,
`effort_tracking` backfill, version bump) behaves byte-identically to a run
without the flag. A test pins at least one other step still firing under the
flag.

**B4.** The rewrite arm's message (both `[apply]` and `[would]` forms) is
rewritten to name **the ambiguity** and **the escape hatch**. It must state
that `53000` is the Era 2 fleet-wide stamp and is indistinguishable from a
deliberately-chosen `53000`, and it must name `--keep-expected-step-tokens` as
the way to keep the value. Both strings are asserted by test to contain the
literal substring `--keep-expected-step-tokens`.

**B5.** Default behaviour without the flag is **unchanged** in every arm. The
three-way branch keeps the same conditions and the same value assignments:
`53000` → rewrite to `5000`; any other non-`None`, non-`5000` value → keep and
`[WARN]`; `5000` or absent → silent no-op. `ERA2_STAMP` and
`THIN_HARNESS_STEP_TOKENS` keep their current values.

**B6.** The dry-run/apply split is preserved under the flag: a dry run with the
flag writes nothing (`state.json` bytes identical before and after), and an
`--apply` run with the flag also leaves `expected_step_tokens` at its input
value.

**B7.** The B6 block gains a comment (above the branch) recording, in two or
three lines: that `53000` is definitionally ambiguous with a deliberate custom
value; that keep+WARN was never removed; and that
`--keep-expected-step-tokens` is the operator's only way to override the
rewrite arm. The comment names CER-111 and INFRA-303.

### C — CER backlog: honest disposition, not a false restoration

**C1.** The CER-108 row (`docs/cer/backlog.md:56`) is annotated
`**RESOLVED INFRA-303 (Phase 114)**` with a one-sentence statement of what
landed: rules 9 and 10 gained bare `name:` rewrites mirroring rule 8.

**C2.** The CER-111 row (`docs/cer/backlog.md:59`) is annotated with the
**corrected analysis**, and the annotation must **not** claim keep+WARN was
restored. It must state, in the row itself:
(a) keep+WARN was never removed — the three-way branch at
`pairmode_migrate.py:956/:969` was live the whole time and pinned by
`test_to030_keeps_custom_expected_step_tokens`;
(b) Repo-J's value was exactly `ERA2_STAMP` (53000), which is definitionally
indistinguishable from a deliberate custom 53000, so the two observations are
the two arms of a correct branch, not a contradiction;
(c) "silently" was inaccurate — the rewrite arm always echoed;
(d) the delivered remedy is the `--keep-expected-step-tokens` opt-out plus an
ambiguity-naming message (INFRA-303), and provenance recording was considered
and rejected.
The annotation is labelled so a reader can tell the row's original premise was
wrong — e.g. `**CORRECTED / RESOLVED INFRA-303 (Phase 114):** the row's premise
was incorrect — …`.

**C3.** No other backlog row is edited by this story, and no row is deleted.
`git diff docs/cer/backlog.md` touches exactly two rows.

### D — documentation

**D1.** `docs/architecture.md` records the `to-030` `expected_step_tokens`
contract in the section that already owns `expected_step_tokens`
(the live-derivation subsection around `:511-587`): the `53000` Era 2 stamp,
its definitional ambiguity with a deliberate custom value, the three-way B6
branch, and the `--keep-expected-step-tokens` opt-out. Three to six sentences;
no restatement of the whole migration rule table.

**D2.** The architecture note does not claim `to-030` can distinguish a stamped
53000 from a chosen 53000. It states the opposite.

**D3.** No new architectural decision is introduced beyond the opt-out flag, so
no ADR-style entry is required; `schema_introduces` stays `false` and Phase
114's § Schema delivery table owes this story no row.

### E — tests and suite

**E1.** The four-way `expected_step_tokens` matrix is pinned by tests, one case
each:

| input `expected_step_tokens` | flag | expected |
|---|---|---|
| `53000` (`ERA2_STAMP`) | absent | rewritten to `5000`; output contains the ambiguity message and `--keep-expected-step-tokens` |
| `53000` | `--keep-expected-step-tokens` | unchanged; `[keep]` line; no `rewrote`/`[WARN]` in output |
| `53416` | absent | unchanged; `[WARN]` present |
| `5000` (`THIN_HARNESS_STEP_TOKENS`) | absent | unchanged; no `rewrote`, no `[WARN]`, no `[keep]` in output |

The `53416` case uses that literal value, not the existing test's `25000` —
it is the value four live fleet projects actually held, and the test docstring
says so.

**E2.** `_invoke_030` gains a `keep_expected_step_tokens: bool = False`
keyword that appends the flag; no existing call site changes meaning.

**E3.** The existing to-030 tests (`:828`, `:843`, `:856`, `:952` and the rest
of the block) still pass. `test_to030_keeps_custom_expected_step_tokens` is
**not** deleted — it is the proof that keep+WARN was never removed, which is
the evidence C2's annotation rests on. It may gain a docstring line pointing at
CER-111.

**E4.** The rule-9/10 tests from A6 and the matrix tests from E1 all pass:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_migrate.py -q
```

**E5.** The full suite is green, run **once without `-x`** so a pre-existing
failure cannot mask a new one. Baseline to match: 4116 passed / 211 skipped,
plus whatever this story adds. A `test_observability_ui` failure inside the
story worktree is the known CER-090 payload gap — resolve it by `rsync`-ing the
vendored payload from the main checkout, never by `pnpm install`, and record in
the build report that it does **not** reproduce on a clean `main` checkout.

### F — release-channel promotion before RELEASE-070

The fleet migration campaign runs its CLIs from `/mnt/work/flex-harness`, not
from this repo. A fix merged to `main` is invisible to the campaign until the
channel is fast-forwarded. This story is a campaign edge (closeout plan § C.2
item 3), so it carries a channel-promotion criterion in the INFRA-293 F3/F4
shape: a build-time half the reviewer verifies, and an operator-run half that
gates the campaign dispatch.

**F1 (build-time, reviewer-verifiable).** The rule-9/10 test from A6 is written
as a *migration-shaped* regression: it runs the real `migrate-from-anchor`
apply path against a fixture whose SKILL.md files carry `anchor:`-prefixed
frontmatter names, not a unit test over the `patterns` tuples. A reviewer can
read the test and see the end-to-end rewrite.

**F2 (operator-run, pre-RELEASE-070).** After this story merges to `main`, the
change is fast-forwarded to `/mnt/work/flex-harness` **before RELEASE-070
(Repo-G) is dispatched**, and the promotion is verified by reading the channel
copy:

```bash
grep -n 'name:\s*anchor:pairmode\|name:\s*anchor:companion\|keep-expected-step-tokens' \
  /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_migrate.py
```

Three matches (the two new rewrite patterns and the new option) confirm
promotion. RELEASE-070 is not dispatched until this returns them.

**F3.** The verification and its date are recorded in the phase doc's CP-114
cold-eyes checklist (orchestrator-filled, per project convention). **Phase 114
cannot be checkpointed with F2 unrun.** If RELEASE-070 is dispatched against an
unpromoted channel, Repo-G migrates with `anchor:` names still in frontmatter —
record that as a FAIL and a re-migration obligation, not as a skip.

**F4.** F2/F3 are **not** builder work. The builder's obligation ends at F1 and
E5; the builder must not attempt to write to `/mnt/work/flex-harness` (it is
outside the project root and `scope_guard` will deny it). The builder's report
states that F2 remains outstanding and is the operator's.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Do not write to `/mnt/work/flex-harness` or any path outside the project root.

Build in order **A → B → C → D**, running
`uv run pytest tests/pairmode/test_pairmode_migrate.py -q` after A and after B,
then the full suite (without `-x`) at the end.

**A — rules 9/10.** Edit `MIGRATION_RULES` in
`skills/pairmode/scripts/pairmode_migrate.py`. Add one pattern tuple to each of
rules 9 and 10, placed **after** the existing `/anchor:…` pattern so ordering
matches rule 8's convention (command reference first, frontmatter name second —
rule 8 happens to list name first; match rule 8's *shape*, and if you deviate
on ordering, say why in a comment; the patterns are independent so order does
not change the result). Copy rule 8's regex shape verbatim, substituting the
skill name. Do **not** add a rule; do **not** renumber.

Then extend both migrate fixtures in `tests/pairmode/test_pairmode_migrate.py`
so the two SKILL.md files carry frontmatter. Use **block-style YAML** in the
fixture content — a `---` delimited block with `name: anchor:pairmode` on its
own line — because a flow-style scalar is exactly the shape CER-115 shows the
frontmatter parser mishandles, and a fixture should not model a broken shape.
Write the new CER-108 test per A6.

**B — the opt-out.** Add the `--keep-expected-step-tokens` flag to `cmd_to_030`
and thread it into the function signature (Click passes it as
`keep_expected_step_tokens`). Restructure B6 as:

- if the flag is set → emit the single `[keep]` line and fall through past B6
  entirely (an early `if`/`else` around the existing branch, not a `return` —
  B4 and everything after it must still run, per B3);
- else → the existing three-way branch, with the rewrite arm's two messages
  rewritten per B4.

Keep the `[apply]`/`[would]` prefixes on the rewrite arm so existing
dry-run assertions keep working. Add the B7 comment. Extend `_invoke_030` per
E2 and write the four matrix tests per E1.

**C — backlog.** Annotate exactly the CER-108 and CER-111 rows in
`docs/cer/backlog.md`. For CER-111, write the correction honestly: the row's
premise was wrong, and the annotation says which parts and why. Do not write
"restored". Do not reword the original finding text — append the annotation to
the existing Finding cell, as sibling rows do.

**D — architecture.** Add the D1 note to `docs/architecture.md` in the
`expected_step_tokens` section.

**Ideology-alignment note (Step 4a, resolved inline).** `docs/ideology.md`
§ Accepted constraints — *"Never silently pass contradictions"* — reads on this
story directly: an override must be *explicitly acknowledged*, never a silent
bypass. The drafted design satisfies it in both directions: the flag is an
explicit, operator-typed acknowledgement (never a default, never inferred), and
the non-flag rewrite arm is made *louder* rather than quieter (B4 names the
ambiguity and the escape hatch). The rejected provenance-recording alternative
would have inferred the operator's intent from a stored key rather than
requiring the acknowledgement, which is why § Out of scope rejects it on
ideology grounds and not merely on cost. § Core convictions —
*"rationale-bearing decisions over bare rules"* — is why B7's comment and C2's
annotation both carry the *why*, not just the *what*.

## Tests

```bash
# Focused — the migration module
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_migrate.py -q

# Full suite — once, WITHOUT -x, so a pre-existing failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:**

- Focused run green, including the new CER-108 rewrite test and all four
  `expected_step_tokens` matrix cases.
- Full suite green against the `main` baseline of 4116 passed / 211 skipped
  (plus this story's new tests). No new failures.
- A `test_observability_ui` failure is worktree-only (CER-090). Fix by
  `rsync`-ing the vendored payload from the main checkout; never
  `pnpm install`. State in the build report that it does not reproduce on a
  clean `main` checkout.
- `test_plugin_manifest.py` still passes — this repo's own SKILL.md names are
  untouched by this story.

**New tests required** (names indicative):

- `test_migrate_rule_9_rewrites_pairmode_name_bare_not_flex_prefixed`
- `test_migrate_rule_10_rewrites_companion_name_bare_not_flex_prefixed`
  (or one test covering both, per A6)
- `test_to030_rewrite_message_names_ambiguity_and_opt_out`
- `test_to030_keep_flag_suppresses_era2_rewrite`
- `test_to030_keep_flag_does_not_suppress_other_steps` (B3)
- `test_to030_warns_and_keeps_53416` (the live fleet value, E1 row 3)
- `test_to030_silent_when_already_thin_harness_value` (E1 row 4)

## Out of scope

- **Provenance recording for `expected_step_tokens` — rejected, not deferred.**
  A `state.json` key recording whether a value was stamped or chosen would add
  a permanent fleet-wide state key in service of a one-time migration command,
  and it cannot help any project already migrated — which is the entire
  population CER-111 is about. It also infers operator intent from stored state
  rather than requiring the explicit acknowledgement `docs/ideology.md`
  § "Never silently pass contradictions" asks for. Do not add it.
- **Interactive prompting on the rewrite arm.** `to-030` is a non-interactive
  migration CLI run from campaign automation; a prompt would hang the campaign.
  The flag is the non-interactive equivalent. (Compare INFRA-301, which is
  removing an interactive prompt from `story_new.py` for the same reason.)
- **Changing `ERA2_STAMP` or `THIN_HARNESS_STEP_TOKENS`.** Both keep their
  current values (`53000`, `5000`).
- **Retroactively repairing Repo-F's rewritten value.** The operator
  reviewed the echoed line at RELEASE-067 and accepted the stamp rewrite. That
  is a settled field decision, not a defect to undo.
- **Rule 8 and the seed skill.** Already correct (INFRA-292); this story only
  brings 9 and 10 to parity.
- **The other twelve migration rules**, the gate scan, the backup-suffix
  mechanism, and `migrate-from-anchor`'s CLI surface.
- **CER-109's `_EXPECTED_SKILL_NAMES` glob** — that is INFRA-308 (Phase 115).
  This story reads that constant as a rationale for bare names; it does not
  edit it.
- **Fast-forwarding `/mnt/work/flex-harness`.** Operator-run (§ Ensures F2);
  the builder must not write outside the project root.

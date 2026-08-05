---
id: INFRA-293
rail: INFRA
title: "Worker result-grammar reconciliation: parser tolerance for legacy plain-text verdicts + sync-agents replaces stale return-format sections (E6b, CER-101 downstream)"
status: complete
phase: "112"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/pairmode_sync.py
touches:
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_sync_agents.py
  - tests/pairmode/test_pairmode_sync.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-293.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This story unblocks the fleet migration campaign (RELEASE-066..070), which
re-blocked at RELEASE-065 evidence point E6b. Repo-C — the first fully migrated
0.3.0 consumer — ran a real proving cycle (PAIRMODE-002) and produced two
`effort.db` attempt rows (33 and 34) that can never leave the pending state.
The spawns completed, the transcripts are readable, the usage is parseable, and
`_contained_spawn_output` admits the output files (INFRA-287 verified all of
that). What fails is the last step: the workers returned the **0.2-era
plain-text result grammar** — `BUILD-RESULT: DONE`, `REVIEW-RESULT: PASS` — and
`parse_worker_outcome` (`subagent_transcript.py:311`) reads only the WORKER-004
JSON grammar. It returns `outcome=None`, and the CER-091 defect-2 branch at
`subagent_transcript.py:1768` then does the right thing and refuses to commit a
partial row. Correct behaviour, wrong input.

The reason the workers emitted the old grammar is a sync defect, not worker
error. `pairmode_sync.py sync-agents` re-renders agent frontmatter and
**additively** appends template body sections whose normalized concept key is
absent from the target (`_merge_body_sections`, `pairmode_sync.py:321`). The
0.2-era agent body carries its return contract under the heading
`## Final output to orchestrator`; the 0.3 template's is `## Return`
(`skills/pairmode/templates/agents/builder.md.j2:43`,
`reviewer.md.j2:43`). Those are different concept keys, so sync appends
`## Return` at the **end** of the file and leaves the stale block — containing
the literal `BUILD-RESULT: DONE` example at Repo-C's
`.claude/agents/builder.md:106` — sitting **earlier** in the file. A worker
reading top-down follows the first return contract it meets. The merge function
is structurally incapable of fixing this: it can add a heading, never replace
one the current template no longer uses. Without a removal/aliasing mechanic
the whole sync half of the fix is unreachable code.

Both halves are needed, and this story builds both — the same two-ended
treatment Phase 110 gave CER-104. The parser half makes every already-stranded
row on every 0.2-era fleet project (Repo-D, Repo-F, Repo-K, base56,
Repo-G at minimum) reconcilable retroactively. The sync half stops new consumers
from emitting the legacy grammar at all. Neither alone closes E6b.

**Time bound.** `RECONCILE_MAX_AGE_DAYS` is 14
(`subagent_transcript.py:156`, single-sourced from
`effort_db.PENDING_MAX_AGE_DAYS`). Repo-C's rows 33/34 were written 2026-07-28,
so they leave the sweep window permanently on **2026-08-11**. The fix must
reach the `/mnt/work/flex-harness` release channel and a sweep must run against
Repo-C before that date. § Ensures F carries this as a first-class, dated
acceptance obligation, not a nice-to-have.

**Backlog drained into this story** (operator-approved at the Phase 112
scaffold review):

- **CER-099** (`docs/cer/backlog.md:68`) — containment-guard parity gap. Half
  of it closed incidentally in INFRA-287: `classify_pending_reason` now routes
  through `is_reconcilable_spawn_output`
  (`subagent_transcript.py:1278`). The other half is still live and sits inside
  the exact function this story edits: `reconcile_pending_attempts`'s
  `include_quiescent` branch calls `path.stat()` and
  `_stream_spawn_output(path)` on the **raw** `attempts.output_file` value
  (`:1781`, `:1790`), and its skip-list at `:1775` omits the `uncontained`
  reason INFRA-287 introduced — so an uncontained row falls straight through to
  raw streaming. Fixed here (§ Ensures C).
- **CER-033** (`docs/cer/backlog.md:161`) — legacy verbose `BUILT:` /
  `REVIEW PASS` template blocks. Already marked RESOLVED for *flex's own*
  templates (the dogfood flip deleted them; verified: no `.j2` under
  `skills/pairmode/templates/agents/` and no file under `.claude/agents/`
  in this repo contains `Final output to orchestrator`). What was never
  addressed is the same debt in **consumer** trees, which is precisely what
  § Ensures B ports. Absorbed and annotated here (§ Ensures D).

**CER-111 is not pulled.** The operator declined an unconditional pull and
conditioned it on the sync-side fix being routed through `to-030`
agent-cleanup. This story routes it through `sync-agents` instead (§ Ensures B,
decision B0), so the condition is not met and `pairmode_migrate.py` is out of
scope entirely.

## Requires

- Phase 110 is complete. In particular INFRA-287 has landed:
  `is_reconcilable_spawn_output` exists in
  `skills/pairmode/scripts/subagent_transcript.py` and is consumed by both
  `read_completed_spawn` and `classify_pending_reason`, and `uncontained` is a
  first-class pending reason. Verify:
  `grep -c 'def is_reconcilable_spawn_output' skills/pairmode/scripts/subagent_transcript.py`
  returns `1`.
- `skills/pairmode/scripts/subagent_transcript.py` contains
  `parse_worker_outcome` (≈ `:311`), `RECOGNISED_REVIEW_VERDICTS` (≈ `:308`,
  the frozenset `{"PASS", "FAIL", "ALIGNED"}`), `_FAIL_CAUSE_LINE_RE`
  (≈ `:117`), and `reconcile_pending_attempts` with an `include_quiescent`
  parameter (≈ `:1553`).
- `skills/pairmode/scripts/worker_result.py`'s `_SCHEMAS[BUILD_RESULT]["enums"]["outcome"]`
  is exactly `{"PASS", "FAIL"}` (≈ `:44`). There is no `DONE` member. This is
  the constraint that forces the mapping decision in § Ensures A.
- `skills/pairmode/scripts/pairmode_sync.py` contains `_heading_concept_key`
  (≈ `:231`), `_target_concept_keys` (≈ `:287`), `_sections_to_add` (≈ `:305`),
  `_merge_body_sections` (≈ `:321`), and `_collect_changes` calling
  `_merge_body_sections` at ≈ `:615`.
- `skills/pairmode/templates/agents/builder.md.j2` and `reviewer.md.j2` both
  carry a `## Return` H2 section (≈ `:43` in each). No template in
  `skills/pairmode/templates/agents/` contains the string
  `Final output to orchestrator`. Verify:
  `grep -rl 'Final output to orchestrator' skills/pairmode/templates/` returns
  nothing.
- The test files named in `touches` all exist and are collected by pytest;
  `tests/pairmode/test_subagent_transcript.py` contains a
  `class TestParseWorkerOutcome` (≈ `:100`).
- No dependency on INFRA-294 or INFRA-295. All three Phase 112 stories touch
  disjoint files (`next_action.py` / `cer.py` there; `fleet_discovery.py`
  there) and may build in any order.

## Ensures

Every assertion is checkable from the diff, by running the command given, or by
running the named test. § Ensures F is the one deliberate exception and states
its own verification path.

### A — parser tolerance for the 0.2-era plain-text grammar

**A1. A legacy result-line pattern exists and is anchored.**
`skills/pairmode/scripts/subagent_transcript.py` defines a module-level
compiled regex (name the builder's choice; `_LEGACY_RESULT_LINE_RE` is the
suggested name) that matches a **whole line** of the form
`BUILD-RESULT: <VERDICT>` or `REVIEW-RESULT: <VERDICT>`, compiled with
`re.MULTILINE`, anchored with `^` at the start and `$` at the end (leading and
trailing whitespace tolerated, arbitrary trailing prose **not**). A line such
as `return BUILD-RESULT: DONE when you are finished` must **not** match.

**A2. The BUILD legacy verdict map is explicit and maps `DONE` to `PASS`.**
A module-level mapping (suggested `_LEGACY_BUILD_VERDICTS`) maps exactly
`{"DONE": "PASS", "PASS": "PASS", "FAIL": "FAIL"}`. A verdict token absent from
this mapping yields no outcome (the row stays pending) rather than being
written through unvalidated.

**A3. The `DONE` mapping carries its rationale in a comment.** A comment
immediately above the mapping states, in substance: the 0.2-era builder had no
plain-text FAIL form — a stuck builder emitted the prose `BUILDER STUCK — …`,
which produces no verdict line at all — so `DONE` is unambiguously the 0.2
success token and nothing is lost by normalizing it to the `worker_result.py`
BUILD enum's `PASS`. Rejecting `DONE` instead would leave Repo-C rows 33/34 (and
every equivalent fleet row) permanently unreconcilable, which is the defect
this story exists to close. The comment names `worker_result.py`'s
`{"PASS", "FAIL"}` enum as the reason `DONE` cannot simply be stored verbatim.

**A4. REVIEW legacy verdicts are enum-checked against the existing
frozenset.** A plain-text `REVIEW-RESULT: <V>` yields an outcome only when `V`
is a member of `RECOGNISED_REVIEW_VERDICTS` (`{"PASS", "FAIL", "ALIGNED"}`).
The frozenset is **reused**, not re-literalled — no second copy of the verdict
vocabulary is introduced anywhere in the diff (`grep -c '"ALIGNED"'` on
`subagent_transcript.py` does not increase).

**A5. JSON wins; legacy is a fallback only.** The legacy scan runs **only**
when the existing JSON scan left `outcome is None`. When a transcript contains
both a JSON `BUILD-RESULT` object and a plain-text `BUILD-RESULT:` line with a
conflicting verdict, the JSON verdict is returned. A dedicated test asserts
this precedence.

**A6. Last recognised legacy match wins,** mirroring the existing JSON loop's
overwrite semantics (`outcome = obj.get("outcome") or outcome`). A test with
two legacy lines asserts the second is returned.

**A7. `fail_cause` behaviour is unchanged.** The `FAIL-CAUSE:` line fallback
(`_FAIL_CAUSE_LINE_RE`, ≈ `:117`) still runs after outcome resolution and is
neither moved nor gated on which grammar produced the outcome. A legacy
`REVIEW-RESULT: FAIL` accompanied by a `FAIL-CAUSE:` line returns
`("FAIL", "<the cause text>")`.

**A8. The function's contract is otherwise untouched.**
`parse_worker_outcome` still returns `tuple[str | None, str | None]`, still
never raises for any input (including `None`, a non-string, a dict, and a list
of content blocks), and still returns `(None, None)` for prose with no
recognisable result. All six existing `TestParseWorkerOutcome` tests
(`tests/pairmode/test_subagent_transcript.py:100-155`) pass **unmodified**.

**A9. All four call sites keep working unchanged.** The diff edits
`parse_worker_outcome`'s body and adds module constants; it does not change the
call signature at `:1289`, `:1357`, `:1802`, or `:1981`. `grep -c
'parse_worker_outcome(' skills/pairmode/scripts/subagent_transcript.py` returns
the same count as at `HEAD` (5: one `def`, four calls).

**A10. The module stays import-light.** No new import is added to
`subagent_transcript.py` — in particular it must **not** import
`worker_result.py`. The existing comment above `RECOGNISED_REVIEW_VERDICTS`
(`:300-307`) explains why that module is deliberately not imported on the hook
path; the same reasoning binds the new mapping, and a comment says so.

### B — sync-agents replaces stale return-format sections (single owner)

**B0. `sync-agents` is the sole owner of the sync-side fix.**
`skills/pairmode/scripts/pairmode_migrate.py` is **not modified by this
story**. `git diff --name-only` contains no `pairmode_migrate.py` entry, and
`to-030`'s `[agent-cleanup]` step, `_AGENT_STEMS`, and `_ERA2_AGENT_HASHES`
are byte-identical to `HEAD`. Rationale, recorded in a comment beside the new
mechanic: `to-030` is a one-shot migration command whose agent-cleanup step
can only WARN (`_ERA2_AGENT_HASHES` is empty, so every file takes the
"manual porting required" path — the WARN that was twice adjudicated noise),
whereas `sync-agents` is idempotent, re-runnable on every consumer forever, and
already owns agent-file body content. Two writers for one fact is the
duplicate-state failure this phase's cold-eyes checklist asks about; there is
exactly one.

**B1. A legacy-heading alias map exists and is explicit.**
`pairmode_sync.py` defines a module-level mapping (suggested
`_LEGACY_HEADING_ALIASES: dict[str, str]`) from a **legacy normalized concept
key** to the **current template's normalized concept key**. It contains at
minimum `"final output to orchestrator" -> "return"`. Keys and values are
already-normalized (the output shape of `_heading_concept_key`), and a comment
says so. The map is a closed, enumerated allowlist — no pattern matching, no
heuristics.

**B2. A replacement pass exists and is position-preserving.** A new function
(suggested `_replace_aliased_sections(template_sections, target_body) -> str`)
walks the target body's sections; for any target section whose concept key is a
key of `_LEGACY_HEADING_ALIASES` **and** whose aliased value matches the
concept key of some section in `template_sections`, it replaces that target
section's heading **and** content in place with the template section's heading
and content. The replaced section stays at its original position in the file —
it is not deleted and re-appended at the end. This is the load-bearing
property: the stale block sits *earlier* than the appended `## Return`, which is
why workers followed it, so moving the canonical content to the end would not
fix anything.

**B3. `_merge_body_sections` calls the replacement pass before computing
additions.** The alias replacement runs first; `_sections_to_add` is then
computed against the **post-replacement** body. Consequence, asserted by test:
a target whose only return section is `## Final output to orchestrator` ends up
with exactly one return section — the template's `## Return`, at the legacy
section's original position — and **no** appended duplicate.
`new_content.count("## Return") == 1` and
`"Final output to orchestrator" not in new_content`.

**B4. Non-aliased project-specific sections are still never removed.** The
existing guarantee in `_merge_body_sections`'s docstring — "Sections in the
target that are absent from the template are preserved (project-specific
additions are never removed)" — holds for every heading **not** named in
`_LEGACY_HEADING_ALIASES`. The docstring is updated to state the aliasing
exception explicitly and to say why it exists (a return contract is a
machine-read data contract, not a project customisation; two competing return
contracts in one file is the E6b defect). A test writes a target with a
bespoke `## Project notes` section and asserts it survives a sync that also
performs an alias replacement.

**B5. The pass is a no-op on already-current bodies.** Syncing an agent file
that already carries `## Return` and has no legacy heading produces no change
from the alias pass. Re-running `sync-agents` twice on the same tree produces
no change on the second run (idempotence), asserted by a test that calls
`_collect_changes` on the output of the first merge and gets an empty change
list.

**B6. `_heading_concept_key`, `_target_concept_keys` and `_sections_to_add`
are not changed.** INFRA-202's normalization and duplicate-append guard keep
their current behaviour; the alias mechanic is layered on top of them, not
woven into them. Their existing tests in `tests/pairmode/test_pairmode_sync.py`
and `tests/pairmode/test_sync_agents.py` pass unmodified — with the one
exception named in B7.

**B7. The one legitimately-inverted existing assertion is rewritten, not
extended.** `tests/pairmode/test_pairmode_sync.py:408` currently asserts
`merged.split("## Final output to orchestrator")[1].strip() == "End here."` —
it encodes preservation of the exact heading this story replaces. Rewrite that
assertion to the new expected behaviour (the section is now the template's
`## Return`, at the same position), and add a comment naming INFRA-293 as the
reason the expectation changed. Do not delete the test and do not add a second
test alongside the stale one.
`tests/pairmode/test_sync_agents.py:489,514` use the legacy heading in
**both** the target and template fixtures of a duplicate-append test — with the
legacy heading present in the template, the alias's value key never matches, so
that test's behaviour is unchanged and it must pass untouched. Confirm this
rather than assuming it; if it does fail, fix the production code, not the
fixture.

### C — CER-099: containment parity in the quiescent-retirement path

**C1. `uncontained` is skipped by the quiescent branch.** The reason check in
`reconcile_pending_attempts` (≈ `:1775`,
`if reason in ("reconcilable", "in-flight", "file-missing", "no-output-file")`)
also skips `"uncontained"`. A comment names CER-099 and states why: an
uncontained path must never be opened, and INFRA-287 added this reason after
the skip-list was written.

**C2. The quiescent branch never touches a raw `output_file` path.** Neither
`path.stat()` (≈ `:1781`) nor `_stream_spawn_output(path)` (≈ `:1790`) is
called on the unvalidated `attempts.output_file` value. Both operate on a path
returned by `_contained_spawn_output(...)` (or by
`is_reconcilable_spawn_output`, which wraps it), with `tasks_root` and `home`
forwarded exactly as the `read_completed_spawn` call at `:1710` forwards them.
When containment returns `None`, the loop `continue`s.

**C3. A regression test proves the guard is armed.** A test in
`tests/pairmode/test_subagent_transcript.py` inserts a pending row whose
`output_file` points outside every containment root, runs
`reconcile_pending_attempts(..., include_quiescent=True)` with an aged row and
an aged file, and asserts the row is **not** updated and the file is not read.
Before this fix the same test would have streamed the file.

**C4. Nothing else in `reconcile_pending_attempts` changes semantics.** The
default (non-quiescent) sweep path, the refuse-partial branch, the
`bump:late-fail` / `skip:late-bump-blocked` logging (`:1745-1765`), the
newest+oldest row fetch, and `RECONCILE_MAX_AGE_DAYS` are untouched. Existing
sweep tests pass unmodified.

### D — CER backlog: CER-099 closed, CER-033 absorbed

**D1. CER-099's row records the resolution.** `docs/cer/backlog.md:68`'s
CER-099 row is extended (not replaced) with a bold `**RESOLVED Phase 112 —
INFRA-293.**` note stating: the `classify_pending_reason` half closed
incidentally in INFRA-287 when it adopted `is_reconcilable_spawn_output`; the
`include_quiescent` half — a raw `stat()`/`_stream_spawn_output` on
`attempts.output_file` plus a skip-list that predated the `uncontained` reason
— closed here (§ Ensures C).

**D2. CER-033's row records the consumer-side absorption.**
`docs/cer/backlog.md:161`'s CER-033 row — already marked RESOLVED for flex's
own templates — gains a sentence stating that the equivalent debt in
**consumer** 0.2-era agent bodies (`## Final output to orchestrator` carrying
`BUILD-RESULT: DONE` alongside the appended `## Return`) is what § Ensures B
ports via the `sync-agents` alias mechanic, and that this is the runtime defect
the LOW-severity flex-side cleanup did not cover.

**D3. No CER row is deleted, renumbered, or reordered,** and no new CER is
filed by this story except as § Out of scope directs.

### E — documentation

**E1. `docs/architecture.md`'s `parse_worker_outcome` narrative names the
legacy tolerance.** The passage at `:2815-2825` (which already explains the
CER-091 `ALIGNED` stranding and the `RECOGNISED_REVIEW_VERDICTS` mirror) gains
a statement that the parser additionally accepts the 0.2-era plain-text verdict
lines as a **fallback below** the JSON grammar, that `DONE` normalizes to
`PASS`, that the 0.2 builder had no plain-text FAIL form, and that this exists
so 0.2-era fleet rows remain reconcilable inside the 14-day window.

**E2. `docs/architecture.md`'s `sync-agents` section records the aliasing
exception.** The `_merge_body_sections` discussion at `:1571-1580` (INFRA-202's
duplication-risk note) gains the legacy-heading alias rule: additive-only is
still the default, with an enumerated alias allowlist as the single documented
exception, owned by `sync-agents` and **not** by `to-030`, with the
duplicate-writer reasoning from B0.

**E3. No other architecture section is edited.** The diff to
`docs/architecture.md` is confined to the two passages in E1/E2.

**E4. `schema_introduces` stays `false`.** No table, migration, or persistent
state object is introduced, so `docs/phases/phase-112.md` § Schema delivery
owes no row for this story.

**E5. The full suite is green** (`tests/pairmode/`), run once **without `-x`**
so a pre-existing failure cannot mask a new one.

### F — field acceptance: Repo-C rows 33/34 reconcile before 2026-08-11

This is the acceptance the whole story is for, and it cannot complete inside
the story worktree — it needs the fix on the `/mnt/work/flex-harness` release
channel and a live sweep against Repo-C's `effort.db`. It is therefore split
into a build-time half the reviewer verifies and an operator-run half that
gates the CP-112 checkpoint.

**F1 (build-time, reviewer-verifiable). A transcript-shaped regression test
pins the exact Repo-C failure.** `tests/pairmode/test_subagent_transcript.py`
contains a test that constructs a spawn-output entry whose final assistant
message text is the 0.2-era builder return — a line reading exactly
`BUILD-RESULT: DONE` — feeds it through the same path the sweep uses
(`read_completed_spawn`, or `parse_worker_outcome` on the flattened final
message, whichever the builder can drive from a fixture), and asserts the
resulting `outcome` is `"PASS"`. A sibling test does the same for
`REVIEW-RESULT: PASS` asserting `"PASS"`. The tests' docstrings name Repo-C rows
33/34 and PAIRMODE-002.

**F2 (build-time). The acceptance does NOT assert a "tokens present, outcome
NULL" row shape.** Repo-C rows 33/34 are fully NULL except `model` (set at
insert); tokens are parseable at sweep time but the refuse-partial branch skips
the whole row, so nothing partial is ever written. No test in this diff asserts
that a pending row has non-NULL tokens with a NULL outcome. `grep` the new
tests: no such assertion exists.

**F3 (operator-run, post-channel-release, deadline 2026-08-11).** After this
story merges to `main` and the change reaches `/mnt/work/flex-harness`, an
explicit sweep is run against Repo-C:

```bash
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/subagent_transcript.py \
  reconcile --project-dir <Repo-C-project-dir> --limit 200 --json
```

and rows 33 and 34 are confirmed to have non-NULL `outcome`. Both the
newest-first fetch (`--limit 200`) and the `RECONCILE_OLDEST_ROWS = 2`
oldest-first fetch reach them; the explicit run is used rather than waiting for
a hook-path sweep so the result is observed, not assumed. The row check:

```bash
sqlite3 <Repo-C-project-dir>/.companion/effort.db \
  "SELECT id, model, tokens_total, outcome FROM attempts WHERE id IN (33,34);"
```

**F4. The result is recorded in the phase doc's CP-112 cold-eyes checklist**
(orchestrator-filled, per project convention) with the date it was run and the
observed outcomes. **Phase 112 cannot be checkpointed with F3 unrun.** If the
sweep is run after 2026-08-11 the rows are outside `RECONCILE_MAX_AGE_DAYS` and
the acceptance is permanently unavailable — record that as a FAIL, not as a
skip, and do not widen the age cutoff to recover it.

**F5. `RECONCILE_MAX_AGE_DAYS` is not changed by this story.** It stays
single-sourced from `effort_db.PENDING_MAX_AGE_DAYS`. Widening the window to
make F3 easier would trade a bounded, dated obligation for an unbounded sweep
surface; the deadline is the point.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order A → C → B → D → E, running the suite after A, after C, and again
at the end. A and C are in the same file and are the campaign-critical half; B
is the larger diff.

**0. Re-read before editing.** The line numbers in this spec are anchors, not
coordinates. Read `parse_worker_outcome` and its surrounding constants
(`subagent_transcript.py` ≈ `:280-355`), the `include_quiescent` branch of
`reconcile_pending_attempts` (≈ `:1745-1800`), and
`pairmode_sync.py`'s `_heading_concept_key` → `_merge_body_sections` block
(≈ `:225-350`) as they exist *now*.

**1. (A) Parser tolerance.** Add the two module constants below
`RECOGNISED_REVIEW_VERDICTS` — the anchored line regex (A1) and the BUILD
verdict map with its rationale comment (A2, A3). Then, inside
`parse_worker_outcome`, insert a legacy pass **between** the existing JSON
`re.finditer` loop and the existing `FAIL-CAUSE:` fallback, guarded by
`if outcome is None:` (A5). Inside it, iterate the anchored matches, and for
each: if the label is `BUILD-RESULT`, look the verdict up in the map and assign
the mapped value; if `REVIEW-RESULT`, assign only when the verdict is in
`RECOGNISED_REVIEW_VERDICTS` (A4). Assign unconditionally on each recognised
match so the last one wins (A6). Do not import anything new (A10) and do not
change the signature (A9).

Anchoring matters more than it looks. Every migrated consumer's agent file
literally contains the string `BUILD-RESULT: DONE` as an example, and worker
transcripts sometimes quote their own instructions. The `^...$` anchor plus the
JSON-first precedence are the two things keeping a quoted example from being
read as a verdict. Do not relax either for convenience.

**2. (C) CER-099 containment parity.** In the `include_quiescent` branch, add
`"uncontained"` to the skipped-reason tuple (C1), then replace the two raw-path
uses. The cleanest shape: call
`_contained_spawn_output(output_file, tasks_root=tasks_root, home=home)` once
before the `stat()`, `continue` on `None`, and use the returned path for both
`stat()` and `_stream_spawn_output` (C2). Forward `tasks_root` and `home`
exactly as the `read_completed_spawn` call at ≈ `:1710` does — INFRA-287 made
`home` injectable end-to-end so tests can pin the `~/.claude` root, and that
injectability must not be broken here. Leave the rest of the function alone
(C4).

**3. (B) Sync-side alias replacement.** Add `_LEGACY_HEADING_ALIASES` (B1) and
`_replace_aliased_sections` (B2) to `pairmode_sync.py`, then call the latter at
the top of `_merge_body_sections` before `_sections_to_add` (B3). Reuse
`_parse_body_sections` and `_heading_concept_key` — do not write a second
parser or a second normalizer; the alias map's keys are *outputs* of
`_heading_concept_key`, and a comment must say so, because the next reader will
otherwise be tempted to write `"## Final output to orchestrator"` as a key and
it will silently never match.

Preserve position (B2). The reason is the whole defect: the stale block sits
earlier in the file than the appended `## Return`, and a top-down reader
follows the first contract it meets. A fix that deletes the legacy section and
appends the template one at the end passes a naive `count("## Return") == 1`
check and does not fix Repo-C.

Update `_merge_body_sections`'s docstring (B4) — it currently promises
project-specific sections are never removed, and after this change that promise
has one enumerated exception. Leaving a docstring that now overstates a
guarantee is worse than the original defect, because the next agent will trust
it.

Do not touch `pairmode_migrate.py` (B0). If it looks cheaper to put the fix in
`to-030`'s agent-cleanup, it is not: that step runs once per migration and
currently cannot act at all (`_ERA2_AGENT_HASHES` is empty, so every file takes
the WARN-and-manual-port path), and a second writer for the same fact is the
duplicate-state condition CP-112's checklist explicitly asks about.

**4. (B7) Rewrite the inverted assertion.** `test_pairmode_sync.py:408` encodes
the old behaviour. Rewrite it in place with an INFRA-293 comment. Run
`test_sync_agents.py` before assuming its two legacy-heading fixtures
(`:489`, `:514`) are unaffected — they should be, because they put the legacy
heading in the *template* as well, which prevents the alias from matching, but
confirm it rather than reasoning about it. If either fails, the production code
is wrong; do not edit the fixture to make it pass.

**5. (F1) Write the transcript-shaped regression tests.** These are the tests
that prove E6b is closed. Drive them through the same code path the sweep uses
so they would have caught the live defect. Do not write the "tokens present,
outcome NULL" assertion (F2) — that shape does not exist in the database.

**6. (D) Annotate the CER backlog.** Extend the CER-099 and CER-033 rows
(D1, D2). Extend — never replace — and keep the table's column count intact.

**7. (E) Update architecture.md.** Two passages only (E1, E2, E3).

**8. Ideology note (Step 4a — checked, resolved inline, no conflict).** Three
entries shaped this spec. *"Rationale-bearing decisions over bare rules"* is
why A3 makes the `DONE → PASS` rationale a mandatory comment rather than a
commit-message detail: a bare mapping entry looks like a typo to anyone who
does not know that the 0.2 builder had no plain-text FAIL, and "cleaning it up"
would silently re-strand every legacy row. The same conviction drives B4's
docstring update and B0's recorded single-owner reasoning. *"Never silently
pass contradictions"* is why the legacy pass is a strict fallback below JSON
(A5) and why unrecognised verdicts yield no outcome (A2, A4) — a tolerant
parser that guesses would write a false `outcome` into `effort.db`, and a
wrong-but-confident row is exactly the false confidence that constraint
protects against; leaving the row pending is the honest failure. *"Codifying
policy over implicit convention"* is why the alias map is an enumerated
allowlist rather than a heuristic. The *"Hooks are thin relays"* constraint is
adjacent and respected: `subagent_transcript.py` is on the hook path, so A10
forbids the new import that would otherwise be the obvious way to reuse
`worker_result.py`'s enum, and C's fix removes work from the hook path rather
than adding to it. The *"Sidebar owns all state writes"* constraint is
untouched. No conflict required flagging.

## Tests

Run from the story worktree root.

Targeted first:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_pairmode_sync.py \
  tests/pairmode/test_sync_agents.py \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_worker_result.py \
  tests/pairmode/test_session_start_hook.py \
  -q 2>&1 | tail -40
```

Then the full suite **without `-x`**:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

New test coverage required (names indicative; the assertions are what matter):

- `TestParseWorkerOutcome::test_legacy_build_done_maps_to_pass` (A2, F1)
- `TestParseWorkerOutcome::test_legacy_review_pass` and `..._fail` (A4)
- `TestParseWorkerOutcome::test_legacy_review_aligned` (A4, the ALIGNED member)
- `TestParseWorkerOutcome::test_legacy_unknown_build_verdict_yields_none` (A2)
- `TestParseWorkerOutcome::test_legacy_line_must_be_whole_line` — asserts
  `"return BUILD-RESULT: DONE when finished"` yields `(None, None)` (A1)
- `TestParseWorkerOutcome::test_json_beats_legacy_plain_text` (A5)
- `TestParseWorkerOutcome::test_last_legacy_match_wins` (A6)
- `TestParseWorkerOutcome::test_legacy_review_fail_with_fail_cause_line` (A7)
- a `read_completed_spawn`-level test reproducing Repo-C rows 33/34 (F1)
- an uncontained-path quiescent-retirement test (C3)
- `pairmode_sync`: legacy heading replaced in place, no duplicate `## Return`
  (B3); bespoke section survives (B4); second sync is a no-op (B5)

Machine-checkable Ensures:

```bash
# A9 — call surface unchanged (5: one def + four call sites)
grep -c 'parse_worker_outcome(' skills/pairmode/scripts/subagent_transcript.py   # 5

# A10 — no new import, and worker_result is still not imported
grep -c 'import worker_result\|from worker_result' skills/pairmode/scripts/subagent_transcript.py  # 0

# A4 — the verdict vocabulary is not duplicated
grep -c 'ALIGNED' skills/pairmode/scripts/subagent_transcript.py   # same as HEAD

# B0 — single owner: the migration command is untouched
git diff --name-only | grep -c 'pairmode_migrate.py'               # 0

# B1 — the alias map exists with the normalized legacy key
grep -n 'final output to orchestrator' skills/pairmode/scripts/pairmode_sync.py  # >= 1

# C1 — the uncontained reason is skipped by the quiescent branch
grep -n 'uncontained' skills/pairmode/scripts/subagent_transcript.py            # includes the skip tuple

# D — both CER rows annotated
grep -c 'INFRA-293' docs/cer/backlog.md                            # >= 2

# F5 — the age cutoff is unchanged
grep -n 'RECONCILE_MAX_AGE_DAYS' skills/pairmode/scripts/subagent_transcript.py
# still: RECONCILE_MAX_AGE_DAYS = effort_db.PENDING_MAX_AGE_DAYS
```

Acceptance:

- every new test above passes;
- the six pre-existing `TestParseWorkerOutcome` tests pass **unmodified** (A8);
- `test_pairmode_sync.py:408` is rewritten, not duplicated (B7);
- every grep above returns the stated result;
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so explicitly in the build
  result.
- § Ensures F3/F4 are **not** builder work — they are the operator's
  post-release step and the CP-112 gate. State in the `BUILD-RESULT` reason
  that F3 remains outstanding with its 2026-08-11 deadline, so it is not lost
  between the merge and the checkpoint.

## Out of scope

- **Validating the JSON-path BUILD `outcome`.** Cold-eyes item 2 is right that
  there is a real asymmetry: JSON `BUILD-RESULT` outcomes are written through
  unvalidated (`subagent_transcript.py:339`) while REVIEW verdicts are
  enum-checked. This story validates only the **new plain-text** BUILD path
  (A2). Retro-tightening the JSON path could newly strand rows that today
  record a non-enum outcome string — a behaviour change with its own blast
  radius, unrelated to E6b. **File it as a new CER** (MEDIUM, source
  "INFRA-293 spec recon") describing the asymmetry and the proposed
  enum check; do not fix it here.
- **`pairmode_migrate.py` and `to-030` agent-cleanup** — see B0. Including
  populating `_ERA2_AGENT_HASHES`, changing the WARN text, or making
  agent-cleanup act.
- **CER-111** (`to-030` overwriting custom `expected_step_tokens`). Explicitly
  not pulled: the operator conditioned the pull on this story routing through
  `to-030`, and it routes through `sync-agents` instead.
- **CER-110** (fleet-wide plugin-sourced duplicate-hook signal). Named in the
  phase doc as out of this phase's scope.
- **Backfilling historical NULL-outcome rows** in any project's `effort.db`.
  The fix is forward-only plus whatever the 14-day sweep window reaches, which
  is the same posture INFRA-287 took (CER-101's resolution note). Rows older
  than `RECONCILE_MAX_AGE_DAYS` stay pending forever, deliberately.
- **Widening `RECONCILE_MAX_AGE_DAYS`** or adding a "reconcile anything"
  escape hatch (F5).
- **Running `sync-agents` against any consumer project** from this story. The
  fleet re-sync is campaign work (RELEASE-066..070), gated on this phase's
  checkpoint; this story ships the mechanism and its tests only.
- **INFRA-294's `_check_cer_do_now` placeholder fix and INFRA-295's
  `fleet_discovery` snapshot targeting.** Disjoint files, separate stories in
  this phase.
- **Any change to the `## Return` section content in
  `skills/pairmode/templates/agents/*.j2`.** The templates are already correct;
  the defect is that consumers never receive them in the right position.
- **A general heading-migration framework.** `_LEGACY_HEADING_ALIASES` is a
  small enumerated allowlist (one entry is enough to close E6b), not an
  extension point. If another legacy heading appears, add a row; do not
  generalise on speculation.

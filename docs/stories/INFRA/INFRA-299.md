---
id: INFRA-299
rail: INFRA
title: "Recording data integrity: enum-validate JSON BUILD outcomes; document attempts.phase and the acknowledged_at misnomer"
status: complete
phase: "113"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/subagent_transcript.py
touches:
  - hooks/pre_tool_use.py
  - skills/pairmode/scripts/context_budget.py
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_worker_result.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-299.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 113 closes the defects both rails stand on. This story closes the
**recording** half: one real integrity gap and two documentation debts that
share a single subject — what the effort record actually means.

**CER-113 (the gap).** `parse_worker_outcome` reads the WORKER-004 JSON result
grammar out of a completed worker's returned text. The two branches are
asymmetric:

```python
if rtype == "BUILD-RESULT":
    outcome = obj.get("outcome") or outcome        # :368 — written through unvalidated
    fail_cause = obj.get("fail_cause") or fail_cause
elif rtype == "REVIEW-RESULT":
    verdict = obj.get("verdict")
    if verdict in RECOGNISED_REVIEW_VERDICTS:      # :372 — enum-checked
        outcome = verdict
```

A builder that returns `{"type": "BUILD-RESULT", "outcome": "SUCCESS"}` — or
`"done"`, or a sentence — has that string committed verbatim into
`attempts.outcome`, where every downstream reader (`checkpoint-report`'s
`_query_effort_by_story_ids`, the escalation ladder's `outcome == "FAIL"` test,
the SPA's waypoint timeline) treats it as a verdict it does not recognise and
silently mis-buckets it. INFRA-293 tightened only the *new* plain-text path it
introduced (`_LEGACY_BUILD_VERDICTS`, :333-338) and recorded the JSON path as
deliberately out of scope: retro-tightening could newly strand rows that today
record a non-enum string, which is a behaviour change with its own blast radius.
That deferral is the reason **Ensures A comes first**: the audit is what
converts "could strand rows" from a hypothesis into a counted fact before the
check ships. It is not a formality and it is not optional.

**CER-105 and CER-106 (the debts).** Both were filed by the phase-110 data-flow
audit as LOW "either fix or document" rows, and both are settled here as
**document, don't change**:

- `attempts.phase` is NULL on 100% of story rows and populated only on
  checkpoint-worker rows. This is not drift — it is `_derive_attribution`'s
  design, spelled out at length in the comment above `CHECKPOINT_ROLES`
  (:100-114): attributing a checkpoint spawn by first-match story regex stamps
  a whole phase's cost onto whichever story the prompt names first (observed
  live: rows 339-340). Populating `phase` on story rows too would create a
  second attribution scheme in the same column for no reader that wants it.
  The cost of the current design is legibility, and legibility is fixed by
  writing it down.
- `context_budget_acknowledged_at` stores a token count (e.g. `222252`), not a
  timestamp. It works — `context_budget.py:891` reads it through `int()` and
  `should_block` compares it to `current_tokens` — and renaming it is a
  fleet-wide state-key migration across every registered project's
  `state.json`, which 0.3.1 does not need.

There is no third thing here. The story validates one parse branch, adds one
observable log decision, and writes three short pieces of documentation. It
changes no schema, renames no key, and touches no writer.

## Requires

Every line number below is an **anchor, not a coordinate** — read the current
body before editing. All anchors were re-verified against clean `main` at
`1c4af83d` on 2026-07-29.

- **`skills/pairmode/scripts/subagent_transcript.py`**
  - `parse_worker_outcome(tool_response) -> "tuple[str | None, str | None]"`
    at `:340`. Its JSON scan iterates `re.finditer(r"\{[^{}]*\}", text)`; the
    `BUILD-RESULT` branch assigns `outcome = obj.get("outcome") or outcome` at
    `:368` with **no** membership test; the `REVIEW-RESULT` branch gates on
    `verdict in RECOGNISED_REVIEW_VERDICTS` at `:372`.
  - The INFRA-293 legacy plain-text fallback runs strictly **below** the JSON
    loop, guarded by `if outcome is None:` at `:380-390`, with
    `_LEGACY_RESULT_LINE_RE` (`:317-320`) and `_LEGACY_BUILD_VERDICTS =
    {"DONE": "PASS", "PASS": "PASS", "FAIL": "FAIL"}` (`:333-338`).
  - `RECOGNISED_REVIEW_VERDICTS: frozenset[str] = frozenset({"PASS", "FAIL",
    "ALIGNED"})` at `:308`, preceded by the CER-091 comment (`:300-307`) that
    states it **mirrors** `worker_result.py`'s
    `_SCHEMAS[REVIEW_RESULT]["enums"]["verdict"]` and is deliberately **not
    imported**, because this module is on the hook path and must stay
    import-light. This comment is load-bearing for this story — see
    Instructions 2.
  - `CHECKPOINT_ROLES: frozenset[str] = frozenset({"security-auditor",
    "intent-reviewer"})` at `:114`, preceded by the INFRA-258 design comment at
    `:100-113`; consumed by `_derive_attribution` at `:677`.
  - `RECORDING_DECISIONS` (`:174-195`) is the single declared vocabulary of
    `log_recording_event` decision strings; `log_recording_event(project_dir,
    **fields)` is at `:1543` and never raises.
  - Four call sites of `parse_worker_outcome`: `classify_pending_reason`
    (`:1333`, no project dir), `read_completed_spawn` (`:1401`, no project
    dir), the quiescent branch of `reconcile_pending_attempts` (`:1869`, whose
    result feeds `outcome_val or "UNKNOWN"` at `:1878`), and
    `record_attempt_from_transcript` (`:2048`, `target_path` in scope).
    `reconcile_pending_attempts` calls `read_completed_spawn` at `:1753` and
    already calls `log_recording_event` at `:1791`/`:1800`.
- **`skills/pairmode/scripts/worker_result.py`** — `BUILD_RESULT = "BUILD-RESULT"`
  (`:26`) and `_SCHEMAS[BUILD_RESULT]["enums"]["outcome"] == {"PASS", "FAIL"}`
  (`:47-50`).
- **`hooks/pre_tool_use.py:173`** — `state["context_budget_acknowledged_at"] =
  result["acknowledged_at"]` inside the `_mutate` closure passed to
  `update_state_json`, under the INFRA-285 comment block at `:164-169`.
- **`skills/pairmode/scripts/context_budget.py:891`** —
  `acknowledged_at_raw = state.get("context_budget_acknowledged_at")`, coerced
  through `int()` at `:897`; the module docstring names the key at `:25`.
- **`docs/architecture.md`** — `## Effort tracking` at `:2590` (its **Data
  model** paragraph enumerates `attempts` columns including `phase` and does
  **not** say `phase` is checkpoint-only); the `state.json` key inventory under
  `## Companion data files` (`:1979`), where
  `context_budget_acknowledged_user_turn_seq` has an entry at `:2188-2190` but
  **`context_budget_acknowledged_at` has none**; `## Hook architecture` at
  `:2294` mentions the key at `:2325`.
- **`skills/observability/api/src/readers/effortDb.ts`** — the phase rollup at
  `:209` is `SELECT DISTINCT phase FROM attempts WHERE phase IS NOT NULL`, a
  live reader whose output today is checkpoint rows only. Read-only input to
  this story: **do not edit this file.**
- **`docs/cer/backlog.md`** contains `CER-113` (`:69`), `CER-105` (`:74`) and
  `CER-106` (`:75`), each with `—` in the `Phase` cell.
- INFRA-296 and INFRA-297 need **not** be complete: this story shares no file
  with either.
- `sqlite3(1)` is **not installed** on this host. Every database read in this
  story uses Python's stdlib `sqlite3` module.

## Ensures

### A — Audit before tightening (blocking; precedes any code change)

**A1. The fleet audit is run and its raw output is pasted into this story's
`## Evidence` section before `parse_worker_outcome` is edited.** For every path
in `registered_projects` from this checkout's `.companion/state.json`
(currently `/mnt/work/Repo-A`, `/mnt/work/Repo-B`, `/mnt/work/Repo-C`,
`/mnt/work/Repo-D`, `/mnt/work/Repo-F`) plus this project itself, the
audit reports, per project: whether `.companion/effort.db` exists, and
`SELECT outcome, agent_role, COUNT(*) FROM attempts GROUP BY outcome,
agent_role`. A project with no database contributes a line saying so; an
unreadable database contributes a line saying so. The audit **never writes** —
it opens each database read-only and issues no `INSERT`/`UPDATE`/`CREATE`.

**A2. The distinct-value verdict is stated explicitly.** `## Evidence` states
the union of distinct `outcome` values observed across all audited databases and
classifies each as one of: `PASS`, `FAIL` (the BUILD enum); `ALIGNED` (REVIEW
only); `UNKNOWN` (written by the quiescent retirement branch at `:1878`, not by
`parse_worker_outcome`); `NULL` (pending). **Any value outside that set is a
finding**, and this story's `## Evidence` must name it, name the rows it
appears on, and state the handling decision — the default handling being that
the value would newly parse as `None` after this change, leaving the row
pending, and that already-written rows are **not** rewritten.

**A3. The audit's negative result is as recordable as a positive one.** If the
union is exactly `{PASS, FAIL, ALIGNED, UNKNOWN, NULL}` (or a subset),
`## Evidence` says so with the per-project counts that prove it, and the
tightening proceeds. "No non-enum values found" without the counts behind it is
not an acceptable Evidence entry.

**A4. A1-A3 are complete before the first edit to `parse_worker_outcome`.**
The builder states in its `BUILD-RESULT` `reason` that the audit ran first. A
diff that changes the parser without a populated `## Evidence` section fails
this story.

### B — the JSON BUILD outcome is enum-validated

**B1. A named BUILD outcome vocabulary exists, mirroring `worker_result.py`.**
`subagent_transcript.RECOGNISED_BUILD_OUTCOMES: frozenset[str] ==
frozenset({"PASS", "FAIL"})`, declared adjacent to `RECOGNISED_REVIEW_VERDICTS`
and carrying a comment in the **same form** as the CER-091 comment above it: it
mirrors `worker_result.py`'s `_SCHEMAS[BUILD_RESULT]["enums"]["outcome"]`, it is
deliberately not imported because this module is on the hook path and must stay
import-light, and the mirror is pinned by a test (B5). The comment names
CER-113.

**B2. The JSON `BUILD-RESULT` branch gates on membership.** At the `:368`
assignment, a `BUILD-RESULT` object's `outcome` is assigned **only** when it is
a member of `RECOGNISED_BUILD_OUTCOMES`, structurally mirroring the
`REVIEW-RESULT` branch at `:372`. `fail_cause` extraction is **unchanged**: a
rejected outcome still yields its object's `fail_cause`, because the reason a
worker failed is worth keeping even when its verdict word is unrecognised. A
test asserts `parse_worker_outcome('{"type": "BUILD-RESULT", "outcome":
"SUCCESS", "fail_cause": "x"}') == (None, "x")`.

**B3. Valid outcomes are unaffected.** `parse_worker_outcome` returns `"PASS"`
for a `BUILD-RESULT` object with `"outcome": "PASS"` and `"FAIL"` for
`"outcome": "FAIL"`, with `fail_cause` behaviour unchanged. Every pre-existing
test in `tests/pairmode/test_subagent_transcript.py`'s `parse_worker_outcome`
block (`:96-215`) passes **by its original name**.

**B4. Rejection is not case-normalised, trimmed, or otherwise rescued.**
`"pass"`, `"Pass"`, `" PASS "` and `"DONE"` all yield `outcome=None` from the
**JSON** path. (`"DONE"` remains accepted from the *plain-text* path via
`_LEGACY_BUILD_VERDICTS` — see D2; the two grammars stay distinct.) A test pins
`"pass"` and `"DONE"` as JSON-path rejections. Fuzzy acceptance would recreate
CER-113 with extra steps.

**B5. The mirror is pinned to its source by an import-identity test.**
`tests/pairmode/test_worker_result.py` gains a test that imports **both**
modules and asserts
`subagent_transcript.RECOGNISED_BUILD_OUTCOMES == worker_result._SCHEMAS[worker_result.BUILD_RESULT]["enums"]["outcome"]`
**and**
`subagent_transcript.RECOGNISED_REVIEW_VERDICTS == worker_result._SCHEMAS[worker_result.REVIEW_RESULT]["enums"]["verdict"]`
— both mirrors, one test, so a future edit to either enum in `worker_result.py`
fails the suite rather than drifting silently. The test's docstring states that
this test is the reason the runtime code is allowed to hold a copy.

**B6. `subagent_transcript.py` gains no new module-level import.**
`grep -n '^import \|^from ' skills/pairmode/scripts/subagent_transcript.py`
returns exactly what it returns today (`__future__`, `json`, `os`, `re`,
`tempfile`, `datetime`, `pathlib`, `typing`). No `worker_result` import is
added at module level or inside `parse_worker_outcome`.

### C — a rejected outcome is observable

**C1. A distinct recording decision exists.** `RECORDING_DECISIONS` gains
`"skip:non-enum-outcome"`, with a comment naming CER-113 and stating that it
means a worker returned a syntactically valid `BUILD-RESULT`/`REVIEW-RESULT`
JSON object whose verdict word is outside the WORKER-004 enum — a worker-contract
violation, not a transport failure. `RECORDING_DECISIONS` remains the single
declared vocabulary; no free-form decision string is introduced.

**C2. The parser reports rejections without changing its return type.**
`parse_worker_outcome` gains a keyword-only `rejected: "list[str] | None" =
None`. When a list is supplied, every JSON verdict value the parser refuses
(BUILD or REVIEW) is appended to it as a string (`repr`-safe: non-string values
are coerced with `str()` and truncated to 120 characters). The return type stays
`tuple[str | None, str | None]` — Era 003's DP4 additive-until-flip contract
forbids changing an existing function's signature shape during the migration
window, and three of the four call sites do not want the third value. When
`rejected` is `None` (every existing caller), behaviour is byte-identical to
today.

**C3. `read_completed_spawn` forwards the list.** It gains the same keyword-only
`rejected: "list[str] | None" = None` and passes it straight through to its
`parse_worker_outcome` call at `:1401`. Its return dict is unchanged.

**C4. The two call sites that hold a project directory log the rejection.**
`record_attempt_from_transcript` (`:2048`) and `reconcile_pending_attempts`'s
`read_completed_spawn` call (`:1753`) each pass a fresh list and, when it is
non-empty, emit one `log_recording_event(...)` with
`decision="skip:non-enum-outcome"` carrying the rejected value(s) under a
`rejected_outcomes` field, alongside the identifying fields that call site
already passes. `classify_pending_reason` (`:1333`) and the quiescent branch
(`:1869`) pass nothing and are otherwise untouched.

**C5. Logging never changes recording.** The rejection log is emitted **in
addition to**, never instead of, the decision the call site already logs; the
row is still written (with `outcome` NULL / left pending), and no branch exits
early because a rejection was logged. A test drives a `record_attempt_from_transcript`
payload whose `tool_response` carries `{"type": "BUILD-RESULT", "outcome":
"SUCCESS", ...}` and asserts: exactly one `attempts` row exists, its `outcome`
is NULL, and `.companion/effort_recording.log` contains both the row's normal
`recorded` line and a `skip:non-enum-outcome` line naming `SUCCESS`.

**C6. The quiescent retirement path is not tightened.** The `outcome_val or
"UNKNOWN"` write at `:1878` is unchanged: `UNKNOWN` is written by the sweep as
a deliberate retirement marker and is **not** subject to the parse-time enum
(it never passes through it). A comment at that site states this, so a later
reader does not "complete" the enum work by breaking the sweep.

### D — INFRA-293's legacy path keeps its precedence

**D1. The plain-text fallback block (`:380-390`) is unchanged** except that a
REVIEW verdict it refuses is appended to `rejected` (C2). `_LEGACY_RESULT_LINE_RE`,
`_LEGACY_BUILD_VERDICTS` and the `if outcome is None:` guard are byte-identical.

**D2. `DONE` → `PASS` still maps on the plain-text path.**
`parse_worker_outcome("BUILD-RESULT: DONE") == ("PASS", None)` — the existing
test at `:164` passes by its original name.

**D3. JSON beats plain text on conflict, re-pinned.** A test feeds text
containing **both** `{"type": "BUILD-RESULT", "outcome": "FAIL", "story_id":
"X", "reason": "r"}` and a line `BUILD-RESULT: DONE`, and asserts the result is
`"FAIL"`. A second test feeds a **rejected** JSON outcome
(`"outcome": "SUCCESS"`) together with `BUILD-RESULT: DONE` and asserts the
result is `"PASS"` — i.e. a refused JSON verdict does **not** poison the
fallback, because `outcome` is still `None` when the legacy block runs. This
second case is the one the change could plausibly break and it must be pinned
explicitly.

### E — CER-105: `attempts.phase` documented, not changed

**E1. `docs/architecture.md` § Effort tracking records the column's split
semantics.** At most two short paragraphs under the existing heading (no new
`##`), stating: `attempts.phase` is populated **only** for
`subagent_transcript.CHECKPOINT_ROLES` spawns (`security-auditor`,
`intent-reviewer`) and is NULL on every story row; the reason is INFRA-258's
finding that attributing a checkpoint spawn by first-match story regex stamps a
whole phase's cost onto one story; per-story rollups therefore scope by
story-ID list (`flex_build._query_effort_by_story_ids`, `:2703-2744`) and never
by `phase`; and `effort_db.query_by_phase` (`:707`) consequently returns
checkpoint rows only.

**E2. The live SPA consequence is named.** The same passage states that
`skills/observability/api/src/readers/effortDb.ts`'s `SELECT DISTINCT phase
FROM attempts WHERE phase IS NOT NULL` (`:209`) therefore reports a
checkpoint-only per-phase breakdown, which is correct-by-design and not a bug to
be "fixed" by back-filling `phase` on story rows.

**E3. The code comment cross-references the documentation.** The comment block
above `CHECKPOINT_ROLES` (`:100-113`) gains one line naming CER-105 and pointing
at `docs/architecture.md` § Effort tracking. `CHECKPOINT_ROLES`'s value and the
existing comment text are otherwise unchanged.

**E4. No schema change.** `git diff` shows no new `_MIGRATIONS` entry, no
`ALTER TABLE`, no change to `_INSERT_COLUMNS`, and no change to
`_derive_attribution`'s return for any role. `schema_introduces` stays `false`
and `docs/phases/phase-113.md` § Schema delivery owes no row for this story.

**E5. The CER row is annotated.** `docs/cer/backlog.md`'s `CER-105` Finding cell
gains a bolded `**RESOLVED Phase 113 — INFRA-299 …**` note stating the
disposition is *documented, not changed*, naming the architecture section, and
its `Phase` cell reads `113`. The row is not deleted or moved between quadrants.

### F — CER-106: the `_at` misnomer documented, not renamed

**F1. Both ends of the key carry a one-line comment.** `hooks/pre_tool_use.py`
immediately above `:173` and `skills/pairmode/scripts/context_budget.py`
immediately above `:891` each gain a comment stating that
`context_budget_acknowledged_at` holds a **token count, not a timestamp**,
despite the `_at` suffix, and naming CER-106. `grep -c 'token count, not a
timestamp'` returns `1` in each file.

**F2. The state-key inventory gains the missing entry.**
`docs/architecture.md`'s `state.json` key list under `## Companion data files`
gains a `context_budget_acknowledged_at` bullet in the same shape as its
neighbour `context_budget_acknowledged_user_turn_seq` (`:2188-2190`):
**optional**; integer; the `context_current_tokens` value at the moment
`hooks/pre_tool_use.py` last wrote a block; read by `context_budget.decide()`
and compared against `current_tokens + reprompt_margin` by `should_block()`;
and an explicit note that the `_at` suffix is a misnomer retained deliberately
(CER-106) because renaming it is a fleet-wide `state.json` migration.

**F3. No behaviour changes.** `git diff` on `hooks/pre_tool_use.py` and
`context_budget.py` shows **comment lines only**. The key is neither renamed,
aliased, dual-written, nor read under a second name; no test's expected
`state.json` shape changes; `tests/pairmode/test_pre_tool_use_hook.py` and
`tests/pairmode/test_context_budget.py` pass unchanged, by their original names.

**F4. The CER row is annotated.** `docs/cer/backlog.md`'s `CER-106` Finding cell
gains a bolded `**RESOLVED Phase 113 — INFRA-299 …**` note recording
*documented, not renamed*, naming both comment sites and the architecture entry,
and stating that the rename is deferred; its `Phase` cell reads `113`.

**F5. CER-113's row is annotated too.** `CER-113`'s Finding cell gains a bolded
`**RESOLVED Phase 113 — INFRA-299 …**` note naming the enum check, the
`skip:non-enum-outcome` decision, and the audit result from `## Evidence`
(specifically: how many non-enum values the fleet audit found). Its `Phase` cell
reads `113`.

### G — channel promotion (operator-run; INFRA-293 F3/F4 pattern)

**G1. The fix is invisible to the campaign until it reaches the channel.** The
phase-106 campaign runs CLIs from `/mnt/work/flex-harness`, not from this
checkout. After this story merges to `main`, the change is promoted to the
channel by **ff-only** merge, and the promotion commit is recorded.

**G2. The promoted channel is verified, not assumed.** Against the channel
checkout:

```bash
PATH=$HOME/.local/bin:$PATH uv run python - <<'PY'
import importlib.util, pathlib
p = pathlib.Path("/mnt/work/flex-harness/skills/pairmode/scripts/subagent_transcript.py")
spec = importlib.util.spec_from_file_location("st", p)
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
print(sorted(st.RECOGNISED_BUILD_OUTCOMES))
print(st.parse_worker_outcome('{"type": "BUILD-RESULT", "outcome": "SUCCESS", "fail_cause": "x"}'))
print(st.parse_worker_outcome('{"type": "BUILD-RESULT", "outcome": "PASS", "story_id": "X", "reason": "r"}'))
PY
```

must print `['FAIL', 'PASS']`, then `(None, 'x')`, then `('PASS', None)`.

**G3. The result is recorded in `docs/phases/phase-113.md`'s CP-113 cold-eyes
checklist** (orchestrator-filled, per project convention) with the date it was
run and the observed output. **Phase 113 cannot be checkpointed with G2 unrun.**

**G4. G1-G3 are operator work, not builder work.** The builder does not push,
merge, or write to `/mnt/work/flex-harness`; it states in its `BUILD-RESULT`
`reason` that G remains outstanding so the obligation is not lost at handoff.

### H — suite

**H1. Full suite green without `-x`.** `uv run pytest tests/pairmode/ -q`
reports no failure other than the known `test_observability_ui` failure, and the
build result states that this failure was **verified to reproduce on clean
`HEAD`** before being attributed elsewhere.

## Evidence

<!-- Ensures A1-A3: the builder pastes the fleet audit output here BEFORE
     editing parse_worker_outcome. Do not delete this heading; an empty
     Evidence section is a story failure, not a formatting choice. -->

### A1 — fleet audit, raw output

Run 2026-07-29 from the INFRA-299 story worktree, **before** any edit to
`parse_worker_outcome`. Read-only (`sqlite3.connect("file:...?mode=ro",
uri=True)`, `SELECT ... GROUP BY` only — no `INSERT`/`UPDATE`/`CREATE` was
issued against any database). `sqlite3(1)` is not installed on this host; the
stdlib module was used.

Note on the project list: a git worktree carries no `.companion/` directory, so
the worktree has no `state.json` of its own. The audit read
`/mnt/work/flex/.companion/state.json` (the main checkout's, read-only) for
`registered_projects` and prepended `/mnt/work/flex` itself. That list now
contains **seven** projects — the five named in § Requires plus
`/mnt/work/Repo-F` and `/mnt/work/Repo-G`, the latter registered since this
story was specced.

```
(worktree has no .companion/state.json; using main checkout /mnt/work/flex/.companion/state.json)
/mnt/work/flex:
   outcome=None role=builder n=42
   outcome=None role=intent-reviewer n=3
   outcome=None role=reviewer n=14
   outcome=None role=security-auditor n=5
   outcome='ALIGNED' role=intent-reviewer n=9
   outcome='FAIL' role=builder n=7
   outcome='FAIL' role=reviewer n=7
   outcome='FAIL' role=sidebar-extractor n=100
   outcome='PASS' role=builder n=39
   outcome='PASS' role=reviewer n=54
   outcome='PASS' role=security-auditor n=9
   outcome='PASS' role=sidebar-extractor n=200
/mnt/work/Repo-A:
   outcome=None role=builder n=362
   outcome=None role=loop-breaker n=1
   outcome=None role=reviewer n=12
   outcome='FAIL' role=reviewer n=65
   outcome='PASS' role=builder n=1
   outcome='PASS' role=intent-reviewer n=1
   outcome='PASS' role=reviewer n=301
   outcome='PASS' role=security-auditor n=1
/mnt/work/Repo-B:
   outcome=None role=builder n=122
   outcome=None role=intent-reviewer n=5
   outcome=None role=reviewer n=19
   outcome=None role=security-auditor n=4
   outcome='FAIL' role=reviewer n=21
   outcome='PASS' role=builder n=18
   outcome='PASS' role=reviewer n=99
   outcome='PASS' role=security-auditor n=1
   outcome='PASS' role=seed-miner n=4
   outcome='PASS' role=seed-reconcile n=6
/mnt/work/Repo-C:
   outcome=None role=builder n=18
   outcome='ALIGNED' role=intent-reviewer n=1
   outcome='FAIL' role=reviewer n=3
   outcome='PARTIAL' role=builder n=1
   outcome='PASS' role=builder n=1
   outcome='PASS' role=reviewer n=12
   outcome='PASS' role=security-auditor n=1
/mnt/work/Repo-D:
   outcome=None role=builder n=6
   outcome='FAIL' role=reviewer n=2
   outcome='PASS' role=builder n=1
   outcome='PASS' role=reviewer n=5
/mnt/work/Repo-F:
   outcome='PASS' role=builder n=1
   outcome='PASS' role=reviewer n=1
/mnt/work/Repo-G:
   outcome=None role=builder n=53
   outcome='FAIL' role=reviewer n=8
   outcome='FAIL' role=sidebar-extractor n=1
   outcome='PASS' role=reviewer n=46
   outcome='PASS' role=sidebar-extractor n=20
   outcome='pass' role=builder n=1
   outcome='pass' role=reviewer n=1
```

Every one of the seven projects has a readable `.companion/effort.db`; none
reported `NO DB` or `unreadable`.

### A2 — distinct-value verdict

Union of distinct `outcome` values across all seven databases (1715 rows at the
time of the roll-up query; this checkout's own `effort.db` gains rows while the
build session runs, so the totals are a live snapshot — the *set* of distinct
values is the stable result):

| value | classification | count | projects |
|---|---|---|---|
| `NULL` | pending (not yet reconciled) | 666 | flex, Repo-A, Repo-B, Repo-C, Repo-D, Repo-G |
| `PASS` | BUILD/REVIEW enum member | 822 | all seven |
| `FAIL` | BUILD/REVIEW enum member | 214 | flex, Repo-A, Repo-B, Repo-C, Repo-D, Repo-G |
| `ALIGNED` | REVIEW enum member (intent-reviewer) | 10 | flex (9), Repo-C (1) |
| `UNKNOWN` | quiescent retirement marker (`:1878`) | 0 | — none observed |
| `PARTIAL` | **FINDING — outside the enum** | 1 | Repo-C |
| `pass` | **FINDING — outside the enum** | 2 | Repo-G |

The union is therefore **not** a subset of `{PASS, FAIL, ALIGNED, UNKNOWN,
NULL}`. Per A2 this is a finding; the rows are named and the handling decision
is stated below. (Per A3, the negative-result path does not apply — the counts
above are given regardless.)

**Finding 1 — `PARTIAL`, 1 row.** `/mnt/work/Repo-C/.companion/effort.db`
`attempts.id = 31`: `story_id='PAIRMODE-001'`, `phase='EH005-main'`,
`rail='PAIRMODE'`, `agent_role='builder'`, `model='claude-sonnet-4-5'`,
`attempt_number=1`, `tokens_total=42317`, `ts='2026-07-24T03:16:35Z'`,
`notes='Builder stuck: sync-all --apply touched settings.json/CLAUDE.md/
gate-worker.md outside story surface; rolled back to HEAD per step-5 failure
mode'`. A builder returned a `BUILD-RESULT` whose `outcome` word was
`"PARTIAL"` — a worker-contract violation. Semantically the run failed
(the note describes a rollback), but it is bucketed as neither `PASS` nor
`FAIL` by any reader, so it silently escaped the escalation ladder.

**Finding 2 — `pass` (lowercase), 2 rows.**
`/mnt/work/Repo-G/.companion/effort.db` `attempts.id = 8`
(`story_id='SMOKE-001'`, `agent_role='builder'`, `model='claude-sonnet-4-6'`,
`ts='2026-05-17T02:48:23Z'`) and `attempts.id = 12` (same story,
`agent_role='reviewer'`, `ts='2026-05-17T03:49:31Z'`). Both are smoke-test rows
with all token columns NULL. Lowercase `pass` is exactly the case-variant
B4 refuses to rescue.

**Handling decision (the A2 default, adopted unchanged).**

1. Neither value is added to `RECOGNISED_BUILD_OUTCOMES`. The enum's source of
   truth is `worker_result.py`'s `_SCHEMAS[BUILD_RESULT]["enums"]["outcome"] ==
   {"PASS", "FAIL"}`; a live non-enum value is evidence about a *worker*, not
   about the enum (Instructions 1).
2. Forward-only: after this change, a `BUILD-RESULT` object carrying `PARTIAL`
   or `pass` parses as `outcome=None`, so the row is left **pending** — the
   recoverable state — and a `skip:non-enum-outcome` line naming the rejected
   value is written to `.companion/effort_recording.log`. The
   worker-contract violation becomes observable instead of silent.
3. **No already-written row is rewritten, back-filled, or deleted.** Repo-C
   id 31 and Repo-G ids 8/12 stay exactly as they are; historical cleanup is
   explicitly out of scope. The three rows were read read-only and not
   modified.
4. The blast radius the INFRA-293 deferral worried about is now counted: **3
   rows out of 1715 fleet-wide (0.17%)**, on two projects, none of them this
   one, and none of them a row this change can retroactively strand — the
   check applies at parse time, and all three are already committed.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build strictly in order **1 → 2 → 3 → 4 → 5**; step 1 gates step 2 and is not a
formality.

**0. Recon.** Read the current bodies of `parse_worker_outcome` (`:340-397`),
the comment above `RECOGNISED_REVIEW_VERDICTS` (`:300-308`), the comment above
`CHECKPOINT_ROLES` (`:100-114`), `RECORDING_DECISIONS` (`:174-195`),
`log_recording_event` (`:1543`), the `read_completed_spawn` call and its
surroundings in `reconcile_pending_attempts` (`:1740-1810`), the quiescent
branch (`:1855-1885`), and the `parse_worker_outcome` call in
`record_attempt_from_transcript` (`:2048`). Every line number in this spec is an
anchor, not a coordinate.

**1. Run the audit first and write `## Evidence` (Ensures A).** Nothing in
`parse_worker_outcome` is edited until this section is populated. `sqlite3(1)` is
not installed here — use stdlib `sqlite3` in read-only URI mode:

```bash
PATH=$HOME/.local/bin:$PATH uv run python - <<'PY'
import json, pathlib, sqlite3
state = json.loads(pathlib.Path(".companion/state.json").read_text())
projects = list(dict.fromkeys([str(pathlib.Path.cwd())] + list(state.get("registered_projects") or [])))
for proj in projects:
    db = pathlib.Path(proj) / ".companion" / "effort.db"
    if not db.exists():
        print(f"{proj}: NO DB")
        continue
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT outcome, agent_role, COUNT(*) FROM attempts "
            "GROUP BY outcome, agent_role ORDER BY 1, 2"
        ).fetchall()
        con.close()
    except Exception as exc:
        print(f"{proj}: unreadable — {exc}")
        continue
    print(f"{proj}:")
    for outcome, role, n in rows:
        print(f"   outcome={outcome!r} role={role} n={n}")
PY
```

Paste the raw output into `## Evidence`, then write the A2 verdict line: the
union of distinct `outcome` values and its classification. If any value falls
outside `{PASS, FAIL, ALIGNED, UNKNOWN, NULL}`, **stop and state the handling
decision in `## Evidence` before continuing** — the default is that such a value
would now parse as `None` (row left pending) and that no existing row is
rewritten. Do not widen `RECOGNISED_BUILD_OUTCOMES` to accommodate a value the
audit finds; the enum's source of truth is `worker_result.py`, and a live
non-enum value is evidence about a *worker*, not about the enum. Read-only
access only: never open a fleet database for writing.

**2. Add the mirrored enum and gate the branch (Ensures B).** Declare
`RECOGNISED_BUILD_OUTCOMES` next to `RECOGNISED_REVIEW_VERDICTS` and gate the
`:368` assignment on membership.

*Ideology note (Step 4a — resolved inline, no conflict).* The plan for this
story said the enum should be **imported** from `worker_result.py` rather than
copied. That instruction collides with a standing rationale-bearing decision
recorded at `:300-307`: `subagent_transcript.py` is on the hook path and
deliberately does not import `worker_result.py`, whose module pulls in the
broader WORKER-004 grammar machinery this module has no other need for. The
ideology's *"Hooks are thin relays only"* constraint (no override permitted)
protects exactly that: no new blocking or heavyweight work on the hook path.
The conflict is resolved **inline**, by satisfying the plan's actual intent —
"one source of truth, no silent drift" — through the project's own existing
pattern instead of an import: a mirrored frozenset carrying the same
mirror-and-why comment as its REVIEW sibling, pinned to its source by an
import-identity **test** (B5), where the heavyweight import is free. Do not add
a runtime import of `worker_result` (B6). If you believe the import is
nonetheless correct, stop and report `FAIL-CAUSE` rather than deciding it in the
diff.

Symmetry with the REVIEW branch is the goal, including its shape: gate the
assignment, leave `fail_cause` alone. A worker that returns an unrecognised
verdict word has still told you why it failed, and discarding that is a second
data loss on top of the first.

**3. Make the rejection observable (Ensures C).** Add
`"skip:non-enum-outcome"` to `RECORDING_DECISIONS`, add the `rejected` keyword
to `parse_worker_outcome` and `read_completed_spawn`, and emit the log line from
the two call sites that hold a project directory.

`parse_worker_outcome` cannot log by itself: it takes no `project_dir`, and
giving it one would turn a pure text parser into a filesystem writer on the hook
path — the *"Sidebar owns all state writes"* / thin-relay boundary again. The
out-list keyword is the mechanism, and the reason goes in the docstring so the
next reader does not "simplify" it by passing a path. Keep the collection total:
a non-string value is `str()`-coerced and truncated, never allowed to raise;
`parse_worker_outcome` still never raises.

Do not add a second `log_recording_event` call to a site that already logs for
the same event where the existing call can carry the field — but a rejection is
a *distinct* fact from the row-write decision, so an additional line is correct
here (C5) as long as the row is still written. The row staying pending is the
point: a pending row is recoverable by the sweep; a row committed with a
nonsense verdict is not.

**4. Write the three documentation pieces (Ensures E, F).** E1/E2's architecture
paragraphs, E3's cross-reference comment, F1's two code comments, F2's state-key
inventory entry. Keep each to the size stated; this is a documentation debt, not
a rewrite. Then annotate `CER-105`, `CER-106` and `CER-113` per E5/F4/F5. The
notes must not overclaim: CER-105 and CER-106 are resolved **as documented
decisions**, and each note must say so in those words, so a future reader does
not mistake the row for a code fix that shipped.

**5. Tests.** Extend `tests/pairmode/test_subagent_transcript.py` (B2, B3, B4,
C1, C5, D2, D3) and `tests/pairmode/test_worker_result.py` (B5). Follow each
file's existing fixture style. Delete no test and rename no existing test.

## Tests

Run from the story worktree root.

Targeted, after step 3:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_worker_result.py \
  -q 2>&1 | tail -30
```

Adjacent surface, to catch collateral damage from the parser change and the
comment-only edits:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_post_tool_use.py \
  tests/pairmode/test_post_tool_use_hook.py \
  tests/pairmode/test_pre_tool_use_hook.py \
  tests/pairmode/test_context_budget.py \
  tests/pairmode/test_docs.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**, so the known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
grep -n 'RECOGNISED_BUILD_OUTCOMES' skills/pairmode/scripts/subagent_transcript.py
grep -n 'skip:non-enum-outcome' skills/pairmode/scripts/subagent_transcript.py
grep -n '^import \|^from ' skills/pairmode/scripts/subagent_transcript.py   # no worker_result
grep -c 'token count, not a timestamp' hooks/pre_tool_use.py                # 1
grep -c 'token count, not a timestamp' skills/pairmode/scripts/context_budget.py  # 1
grep -n 'context_budget_acknowledged_at' docs/architecture.md               # inventory entry present
git diff --stat hooks/pre_tool_use.py skills/pairmode/scripts/context_budget.py   # comments only
for c in CER-105 CER-106 CER-113; do \
  grep -c "$c.*RESOLVED Phase 113" docs/cer/backlog.md; done                # each prints 1
```

Acceptance:

- `## Evidence` is populated with the A1 audit output and the A2 verdict, and
  the build result states the audit ran **before** the parser edit;
- every new test from A-F passes;
- every pre-existing test in the five adjacent files passes **by its original
  name**;
- the full suite is green modulo the known `test_observability_ui` failure,
  verified to reproduce on clean `HEAD`;
- G remains outstanding and is named as such in the `BUILD-RESULT` `reason`.

## Out of scope

- **Renaming `context_budget_acknowledged_at`.** The rename is a fleet-wide
  `state.json` key migration across every registered project, with a
  read-both-write-one compatibility window and a `pairmode_migrate` rule; 0.3.1
  does not need it and the key works correctly today. CER-106's rename half stays
  on the backlog with that reason. No alias, no dual-write, no deprecation
  shim here.
- **Populating `attempts.phase` on story rows (or splitting the column).**
  CER-105's schema half is deliberately not built: a second attribution scheme in
  the same column serves no existing reader, and INFRA-258 chose the current
  design to stop checkpoint cost being stamped onto one story. This story
  documents the contract instead.
- **Back-filling, rewriting, or deleting rows already written.** Any non-enum
  `outcome` the audit finds stays in the database exactly as it is. This fix is
  forward-only; a historical cleanup would be a separate, operator-gated story.
- **Changing what the quiescent sweep writes.** `outcome="UNKNOWN"` at `:1878`
  and `QUIESCENT_AGE_SECONDS` are untouched. INFRA-298 owns the quiescence
  demotion; do not pre-empt it, and do not loosen or tighten the sweep to make an
  assertion here easier.
- **Anything INFRA-296 / INFRA-297 / INFRA-298 / INFRA-300 owns.** Flow-style
  frontmatter parsing, the table-split helper and commit-evidence scoping, the
  SubagentStop relay, and duplicate-hook keying. This story shares no file with
  any of them.
- **Editing `skills/observability/api/src/readers/effortDb.ts`.** Its
  `WHERE phase IS NOT NULL` behaviour is documented here (E2) and left alone;
  INFRA-309 owns read-side rollup hygiene.
- **Validating the other WORKER-004 result types.** `ADVICE` and `SPEC-RESULT`
  are not read by `parse_worker_outcome` at all; `worker_result.validate` remains
  the only enforcement point for those grammars.
- **Any change to `worker_result.py`.** Its `_SCHEMAS` are the source of truth
  this story mirrors; if the BUILD enum is wrong, that is a different story.

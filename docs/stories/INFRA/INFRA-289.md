---
id: INFRA-289
rail: INFRA
title: "Attribution and escalation: target-project recording, strict phase-key parsing, async FAIL-bump (CER-102, CER-103)"
status: draft
phase: "110"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/subagent_transcript.py
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_post_tool_use.py
  - docs/stories/INFRA/INFRA-289.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This is the **attribution** story of Phase 110. INFRA-287 fixes the
reconciliation pipeline (rows can complete at all) and INFRA-288 fixes
duplication (one row per spawn instead of two). Both make the recording
pipeline *work*; neither makes it record the **right thing in the right
place**. Three independent defects do that, and all three live in
`skills/pairmode/scripts/subagent_transcript.py`:

**(a) CER-103 — attribution is session-bound, not target-bound.**
`hooks/post_tool_use.py:65` computes `project_dir = Path(data.get("cwd") or ".")`
and hands it to `record_attempt_from_transcript`, which treats it as *the
project whose `.companion/effort.db` gets the row* (`:1411`,
`_read_state(project_path)`). For a native session those are the same thing.
For the fleet campaign this phase exists to unblock they are not: a spawn
dispatched from a flex session against another project — `--project-dir
/mnt/work/meander` in the prompt, or a cwd under that project's
`.pairmode-worktrees/` — records into **flex's** db. The RELEASE-063 canary
is the proof: `LEGAL-001` rows 419/420 sit in flex's `effort.db` and meander's
db has zero. The row is not merely mislabelled, it is *in the wrong file*, so
meander's `checkpoint-report` under-reports and flex's per-role medians are
polluted by another project's work.

The answer already exists in this codebase in a neighbouring form.
`scope_guard.resolve_call_story` (`scope_guard.py:436-475`) resolves "which
story is this call for?" from the call itself, in a documented precedence
(`worktree-cwd` → `worktree-path` → state → refuse), because a single global
slot cannot answer a question that now has more than one live answer. This
story applies the same shape to "which *project* is this spawn for?".

The one thing that shape must not import naively is trust. This function's own
docstring commits to sourcing every field "never from agent-authored prose the
hook has to trust blindly" (`:1373-1375`), and a target path lifted out of a
prompt is exactly that — plus `log_recording_event` does
`mkdir(parents=True, exist_ok=True)` (`:1050`), so an unchecked candidate path
would *create* directories at an agent-chosen location. The containment is an
operator-controlled allowlist that already exists and is already populated:
`state.json["registered_projects"]` (read today by
`fleet_discovery._read_registered_projects`, `fleet_discovery.py:85-98`; flex's
own entry currently lists coherra, meander, caddy and forqsite.help). A derived
candidate outside that allowlist is not silently used and not silently
discarded — it falls back to the session project and says so in the recording
log.

**(b) CER-103 — `_derive_phase_key`'s bare fallback matches English.**
`_PHASE_BARE_RE` (`:125`) is `\bPhase\s+([A-Za-z0-9][A-Za-z0-9._-]*)`, applied
to a checkpoint worker's prompt with no shape validation on the capture. It
matched the word after "Phase" in ordinary prose: flex row 416 carries
`story_id = "phase:key"` and meander rows 233-236 carry `"phase:checkpoint"`.
Those are not phases. They are synthetic story ids that no `query_by_phase`
will ever find and that no per-story rollup will ever exclude — the exact
mis-attribution `CHECKPOINT_ROLES` and `_derive_attribution` (`:534-560`) were
introduced to prevent, re-entering through the fallback's own back door. The
honest failure for an underivable phase key is the `unattributed:<role>`
sentinel the function already returns (`:558`), not a plausible-looking lie.

**(c) CER-102 — the FAIL-escalation ladder is dead on the async path.**
There are two FAIL-bump sites and, in the live loop, neither fires:

- The **insert-time** bump (`:1443-1446`) requires `outcome == "FAIL"` at
  PostToolUse time. `outcome` comes from `parse_worker_outcome(tool_response)`
  — and for an async-launched spawn `tool_response` is the launch stub, not
  the worker's return block, so `outcome` is *always* `None` there. This
  branch is structurally unreachable for every spawn the loop actually makes.
- The **reconcile-time** bump (`:1254-1261`) is the correct one — it fires when
  the row's real outcome becomes knowable, gated by `_story_accepts_late_bump`
  (`:948-978`) so it cannot resurrect a counter for a finished story. It is
  unreachable only because CER-101 stopped every row from reconciling at all.

So the observable symptom (RELEASE-062: two consecutive reviewer FAILs,
`.companion/attempt_counter.json` never created, `next-action` stuck emitting
`spawn-builder` attempt 1 / haiku with no escalation and no loop-breaker) has
its root cause in INFRA-287's territory. What is genuinely missing *here* is
that the reconcile-time bump has **no test on the async path** and **no
observable trace**: it is a silent side effect of a sweep, so when it fails
again nobody will know until an escalation ladder visibly stalls for a second
time. This story does not re-fix the bump; it makes it tested and legible.

**(d) Collateral, per the phase dossier.** `attempts.model` is `NULL` on
reviewer rows. Two causes: the orchestrator omits `model=` on reviewer spawns
(a `CLAUDE.build.md` / `next_action.py` concern, deliberately not this story's
file set), and pre-reconcile async usage extraction has no model to report.
The reconcile-time backfill already exists (`:1240-1241`, `if row.get("model")
is None and result.get("model")`). The dossier says "fix if cheap, else note" —
the half of it that is cheap is the note, so item D records it rather than
reaching into the orchestrator's files from an attribution story.

## Requires

- **INFRA-288 is complete and merged**, and this story's worktree is cut from a
  `HEAD` that contains it. INFRA-288 rewrote the tail of
  `record_attempt_from_transcript` (agent_id / output_file threading through
  `record_effort_ex`) — the same function item A changes. Verify before
  building: `git log --oneline --grep 'INFRA-288'` returns a commit reachable
  from `HEAD`, and `grep -n 'recorded:deduped'
  skills/pairmode/scripts/subagent_transcript.py` prints a line.
- **INFRA-287 may or may not be merged.** At spec time it was still `status:
  draft` while INFRA-288 had landed, so this story must not assume the
  reconciliation predicate is fixed. Item C's assertions are written to hold
  either way (C4 drives `reconcile_pending_attempts` with a stubbed
  `read_completed_spawn`, which is independent of the terminator predicate).
  If INFRA-287 *is* in `HEAD`, C5's end-to-end test also runs; if it is not,
  C5 skips with an explicit reason. Never weaken C4 to compensate.
- `skills/pairmode/scripts/subagent_transcript.py` defines
  `RECORDING_DECISIONS` (`:161-173`), `log_recording_event`,
  `_read_state`, `_STORY_ID_RE`, `_PHASE_KEY_CHARS`, `_PHASE_DOC_PATH_RE`,
  `_PHASE_BARE_RE`, `_strip_trailing_punct`, `_derive_story_id`,
  `_derive_phase_key`, `_derive_attribution`, `CHECKPOINT_ROLES`,
  `_story_accepts_late_bump`, `reconcile_pending_attempts`, and
  `record_attempt_from_transcript`.
- `skills/pairmode/scripts/fleet_discovery.py` defines
  `_read_registered_projects` reading `state["registered_projects"]`
  (`:85-98`).
- `hooks/post_tool_use.py` calls
  `subagent_transcript.record_attempt_from_transcript(project_dir=project_dir,
  ...)` at `:163-171` and computes `project_dir` from `data["cwd"]` at `:65`.
- `tests/pairmode/test_post_tool_use.py` contains `class TestHookStaysThin`
  with the two source-level assertions at `:51-71`, plus the helpers
  `_run_hook` and `_enable_tracking`.
- `tests/pairmode/test_subagent_transcript.py` exists.
- `docs/cer/backlog.md` contains rows for `CER-102` (`:65`) and `CER-103`
  (`:66`).

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command. All new symbols named below are **created by this story** —
`spec-preflight` flagging them as unverifiable is expected and intentional.

### A — CER-103(a): the recording target is resolved from the spawn

**A1. A named resolver exists with an enumerable source vocabulary.**
`subagent_transcript.py` defines a module-level
`RECORDING_TARGET_SOURCES: tuple[str, ...]` whose members are exactly
`("explicit-flag", "explicit-label", "worktree-path", "session-cwd",
"rejected-unregistered")`, and a function

```python
def resolve_recording_project(
    tool_input: "dict | None",
    session_project_dir: "Path | str",
    session_state: "dict | None" = None,
) -> "tuple[Path, str]":
```

returning `(project_path, source)` where `source` ∈ `RECORDING_TARGET_SOURCES`.
It performs **no writes**, creates no directories, and never raises — any
exception resolves to `(Path(session_project_dir), "session-cwd")`.

**A2. Precedence is documented and ordered, mirroring
`scope_guard.resolve_call_story`.** The docstring states the order and the
reason for it. Candidates are derived from `tool_input["prompt"]` and
`tool_input["description"]` in this order:

1. `explicit-flag` — an absolute path following `--project-dir` (optionally
   `=`-joined, optionally quoted);
2. `explicit-label` — an absolute path following a `Project dir:` /
   `project_dir:` / `project_dir=` label (case-insensitive on the label);
3. `worktree-path` — an absolute path containing a
   `/.pairmode-worktrees/<ID>/` segment, collapsed to the path **above**
   `.pairmode-worktrees`;
4. `session-cwd` — no candidate derivable: return
   `Path(session_project_dir)`, today's behaviour, unchanged.

The first candidate that survives A3's admission test wins. A candidate that
fails admission does **not** fall through to the next candidate — it returns
`(Path(session_project_dir), "rejected-unregistered")`, because a prompt that
names a target flex must not write to is a fact worth surfacing, not a reason
to keep guessing.

**A3. Admission is an operator-controlled allowlist, not prompt trust.** A
derived candidate is admitted only when **all** hold: it is absolute; it
resolves to an existing directory; `<candidate>/.companion` is an existing
directory (never created); and it is either (i) the resolved
`session_project_dir` itself, or (ii) present, after `Path.resolve()`, in the
session project's `state.json["registered_projects"]` (read from
*session_state* when supplied, otherwise via `_read_state(session_project_dir)`).
A non-list or absent `registered_projects` admits nothing but the session
project itself.

**A4. `record_attempt_from_transcript` records into the resolved target.**
The function calls `resolve_recording_project` once, immediately after it has
validated `tool_input` is a dict and *before* `_read_state`, and every
subsequent use of the project path in that function body — `_read_state`, the
`effort_tracking` gate, the db path, `reconcile_pending_attempts`,
`bump_attempt_count`, and every `log_recording_event` call after that point —
uses the resolved target, not the incoming `project_dir`. Its `project_dir`
parameter keeps its name and position (no caller changes) and its docstring is
amended to say it is now the **session fallback**, not the recording target.
The two early-return `log_recording_event` calls that fire *before* resolution
(`skip:no-tool-input`, and the outer `except`) keep using the session path —
they are diagnostics about a spawn flex could not interpret at all.

**A5. The chosen target is visible in the recording log.** Every
`log_recording_event` call made after resolution carries two extra fields:
`target_project` (the resolved path as a string) and `target_source` (the
`RECORDING_TARGET_SOURCES` member). No new `decision` value is needed for the
happy path — the existing `recorded` / `recorded:deduped` / `skip:*` values are
unchanged — but `RECORDING_DECISIONS` gains `"skip:target-unregistered"`, used
when `source == "rejected-unregistered"`, in *addition to* (not instead of) the
row still being recorded against the session project. Recording never stops on
a rejected target; the fallback is the pre-existing behaviour and the log line
is the alarm.

**A6. `hooks/post_tool_use.py` is byte-identical.** `git diff --stat`
contains no entry for `hooks/`. Resolution lives in the module, per the
`## Instructions` ideology note; the hook stays a thin relay that passes its
cwd and delegates. `tests/pairmode/test_post_tool_use.py::TestHookStaysThin`
passes unmodified.

**A7. The context-budget call is untouched.** `hooks/post_tool_use.py`'s first
delegated call (`context_budget.read_current_tokens`, `:105-108`) and the
`state.json` write around it continue to use the **session** project. The diff
contains no change to `context_budget.py` or `session_state.py`. This is
load-bearing (DP7): the orchestrator's own context window belongs to the
session that holds it, no matter which project its spawn targeted; only the
subagent's effort row follows the target.

**A8. Unit coverage for the resolver.** `tests/pairmode/test_subagent_transcript.py`
gains a class `TestResolveRecordingProject` asserting, with `tmp_path`-built
projects: each of the four positive sources resolves to the right path with
the right source string; a registered target missing `.companion/` is rejected;
an unregistered but existing target is rejected; a nonexistent path is
rejected; a rejected candidate returns the session path with
`"rejected-unregistered"`; a relative path in the prompt is never a candidate;
and that after any rejected resolution no directory was created under the
rejected path.

**A9. End-to-end target routing.** A test builds two projects under `tmp_path`
(`sess/` and `target/`, both with `.companion/state.json` and
`effort_tracking: true`, `sess`'s state listing `target` in
`registered_projects`), calls `record_attempt_from_transcript` with
`project_dir=sess` and a `tool_input` whose prompt contains
`--project-dir <target>`, and asserts: `target/.companion/effort.db` exists and
holds exactly one attempts row for the story; `sess/.companion/effort.db`
either does not exist or holds zero rows for that story; and
`target/.companion/effort_recording.log`'s last line has
`target_source == "explicit-flag"`.

### B — CER-103(b): phase-key derivation is strict

**B1. A strict shape gate exists.** `subagent_transcript.py` defines
`_PHASE_KEY_STRICT_RE` matching a whole candidate that is either all digits
(`110`, `8`) or an alphanumeric run ending in a digit optionally followed by a
`-main` / `-ante<N>` / `-post<N>` suffix (`HARNESS001-main`,
`HARNESS009-post1`, `HARNESS001-ante1`). It does **not** match `key`,
`checkpoint`, `doc`, `docs`, `report`, or any all-alphabetic word.

**B2. `_derive_phase_key` takes an optional project and verifies the doc.**
Its signature becomes
`_derive_phase_key(tool_input: dict, project_dir: "Path | str | None" = None)`.
A candidate from either pattern must pass `_PHASE_KEY_STRICT_RE` after
`_strip_trailing_punct`. When *project_dir* is supplied **and**
`<project_dir>/docs/phases/` is an existing directory, the candidate must
additionally satisfy `(<project_dir>/docs/phases/phase-<key>.md).is_file()`.
When `docs/phases/` does not exist (a consumer project mid-bootstrap, or a
unit test), the existence check is skipped and the shape gate alone decides —
never the reverse. The function still tries `_PHASE_DOC_PATH_RE` before
`_PHASE_BARE_RE`, still returns `None` when nothing qualifies, and still never
raises.

**B3. Rejection is honest, not plausible.** `_derive_attribution` gains the
same optional `project_dir` parameter and forwards it; when
`_derive_phase_key` returns `None` for a `CHECKPOINT_ROLES` spawn, the existing
`unattributed:<subagent_type>` sentinel is returned unchanged (`:558`). No new
sentinel shape is introduced. `record_attempt_from_transcript` passes the
**resolved target** (item A) as `project_dir`, so the phase doc is looked up in
the project the checkpoint is actually for.

**B4. The two observed lies are now impossible.** Tests assert
`_derive_phase_key({"prompt": "... Phase key: see the phase doc ..."})` returns
`None`, and `_derive_phase_key({"prompt": "... Phase checkpoint step 3 ..."})`
returns `None`. A test drives `_derive_attribution` with
`subagent_type="security-auditor"` and each of those prompts and asserts the
returned `story_id` is `"unattributed:security-auditor"` — never `"phase:key"`
or `"phase:checkpoint"`.

**B5. Real keys still resolve.** Tests assert that
`docs/phases/phase-110.md` in a prompt yields `"110"`;
`docs/phases/phase-HARNESS005-main.md` yields `"HARNESS005-main"`; a bare
`Phase 110` yields `"110"`; a bare `Phase HARNESS009-post1` yields
`"HARNESS009-post1"`; and trailing punctuation (`Phase 110.`) is still
stripped. A test with a `tmp_path` project containing only
`docs/phases/phase-110.md` asserts `Phase 111` yields `None` while
`Phase 110` yields `"110"`.

**B6. No historical rows are rewritten.** The diff contains no `UPDATE` of
existing `attempts` rows, no migration, and no CLI to repair `phase:key` /
`phase:checkpoint` rows already on disk (see `## Out of scope`).

### C — CER-102: the async FAIL-bump is tested and legible

**C1. Both bump sites keep their existing gating.** The insert-time bump
(`:1443-1446`) still fires only on `story_id and outcome == "FAIL" and ":" not
in story_id` and is still **not** gated by `_story_accepts_late_bump`; the
reconcile-time bump (`:1254-1261`) still is. Neither gate is loosened, removed,
or merged. `grep -c 'bump_attempt_count(' skills/pairmode/scripts/subagent_transcript.py`
returns the same count as on `HEAD` before this story.

**C2. The insert-time branch says why it is dead on the async path.** A
comment above the insert-time bump records that `tool_response` for an
async-launched spawn is the launch stub, so `parse_worker_outcome` yields
`None` and this branch cannot fire for the live build loop; that it is retained
for synchronous spawns and for direct callers; and that the reconcile-time bump
is the ladder's real path. Naming CER-102.

**C3. A late bump leaves a trace.** In `reconcile_pending_attempts`, the
reconcile-time FAIL branch calls `log_recording_event` exactly once per
decision: `decision="bump:late-fail"` (with `story_id` and `row_id`) when
`_story_accepts_late_bump` returned `True` and `bump_attempt_count` was called
without raising, and `decision="skip:late-bump-blocked"` when it returned
`False`. Both strings are added to `RECORDING_DECISIONS`. Both calls are inside
the existing best-effort `try`/`except` discipline — a logging failure never
propagates and never prevents the bump.

**C4. The async path is tested without depending on INFRA-287.** A test:
creates a `tmp_path` project with `.companion/state.json`
(`effort_tracking: true`) and a story file
`docs/stories/TEST/TEST-001.md` with `status: in-progress`; inserts a pending
attempts row for `TEST-001` with a non-null `output_file`; monkeypatches
`subagent_transcript.read_completed_spawn` to return a dict with
`outcome="FAIL"` and non-null token fields; calls
`reconcile_pending_attempts(project_dir=..., ...)`; then asserts
`.companion/attempt_counter.json` records `TEST-001` at `1`, the row's
`outcome` is `FAIL`, and `effort_recording.log` contains a `bump:late-fail`
line naming `TEST-001`. A sibling test flips the story's frontmatter to
`status: complete` and asserts the counter file is **not** created and the log
carries `skip:late-bump-blocked`.

**C5. The genuine end-to-end path is tested when INFRA-287 is present.** A
test that writes a real completed spawn-output file (as a **symlink**, the
shape CER-101 names) and drives `reconcile_pending_attempts` with no
monkeypatch, asserting the same counter bump. It is guarded by a skip whose
reason names INFRA-287 — e.g. skip unless the shared containment+terminator
predicate INFRA-287 introduces is importable from `subagent_transcript` — so
this story is buildable in either order. The guard must be a genuine
`pytest.skip` with a reason string, never a weakened assertion.

**C6. No change to `next_action.py`, `flex_build.py`, or `CLAUDE.build.md`.**
The escalation ladder's *consumers* are correct already; this story only makes
its input arrive and be observable. The diff touches neither the resolver nor
the harness template.

### D — Documentation and CER closure

**D1. Architecture records the target-resolution rule.**
`docs/architecture.md` gains one paragraph (bolded lead, in the style of its
neighbours) in the section that already documents effort recording / the
PostToolUse hook, citing `INFRA-289, CER-103`. It records: that the effort row
follows the **spawn's target project** while the context-budget count follows
the **session**, and why the two must never be merged (DP7); the four-step
precedence and the `registered_projects` allowlist, including that a prompt
path is agent-authored input and is therefore admitted, not trusted; and that a
rejected target falls back to the session project with a
`skip:target-unregistered` log line rather than being silently dropped. No new
`##`-level heading is added.

**D2. Architecture records the strict phase-key rule.** The same section (or
the existing prose describing `_derive_attribution` / `CHECKPOINT_ROLES`, if
one exists) gains a sentence stating that a bare `Phase <key>` mention is only
accepted when it matches a real phase-key shape and, where the project's
`docs/phases/` is visible, names a phase doc that exists — and that an
underivable key resolves to `unattributed:<role>`, because a synthetic
`phase:<English word>` id is invisible to both `query_by_phase` and per-story
rollups.

**D3. CER-103 is closed.** Its row in `docs/cer/backlog.md` gains a bolded
`**RESOLVED Phase 110 — INFRA-289 …**` note appended to its Finding cell,
naming the target resolver, the allowlist containment, and the strict
phase-key parse. Its `Phase` cell is set to `110`. The historical finding text
is not deleted.

**D4. CER-102 is closed with an honest split.** Its row gains a bolded
`**RESOLVED Phase 110 — INFRA-287 + INFRA-289 …**` note stating that the root
cause was CER-101's unreachable reconciliation (fixed in INFRA-287) and that
INFRA-289 added the async-path test and the `bump:late-fail` /
`skip:late-bump-blocked` log trace. It must **not** claim the insert-time bump
was made to work on async spawns — it was not, and cannot be. Its `Phase` cell
is set to `110`.

**D5. The `attempts.model` collateral is recorded, not silently dropped.**
CER-102's note (or CER-103's — one of the two, not both) additionally records
the phase dossier's collateral finding: `attempts.model` is `NULL` on reviewer
rows because the orchestrator omits `model=` on reviewer spawns and
pre-reconcile async usage extraction has no model to report; that the
reconcile-time backfill at `subagent_transcript.py:1240-1241` already covers
the second half; and that fixing the first half means changing the
orchestrator's spawn call, which is out of this story's file set. No new CER id
is created (the backlog-routing default is not applied unilaterally here — the
dossier already assigned this item to this story as "fix if cheap, else note").

### Cross-cutting

**E1. `schema_introduces` stays `false`.** No table, column, or migration is
added. `target_project` / `target_source` are fields of an append-only
diagnostic log line, not columns; the `docs/phases/phase-110.md` § Schema
delivery table is not owed a row by this story.

**E2. No behaviour change for a native session.** When a spawn's prompt names
no target, or names the session project itself, every observable outcome is
identical to `HEAD`: same db, same rows, same `source == "session-cwd"`. A test
asserts this explicitly against a prompt containing no path at all.

**E3. The full test suite is green** (`tests/pairmode/`), run once **without**
`-x` so a known pre-existing failure cannot mask a new one.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order B → A → C → D: B is self-contained and its tests are the
cheapest signal that you have the module's conventions right; A is the largest
change and depends on nothing in B except `_derive_attribution`'s new
parameter; C is small and mostly tests; D is prose written last, against what
actually shipped. Run the suite after A and after C.

**0. Rebase check.** Confirm INFRA-288 is in your `HEAD` (`## Requires`), and
check whether INFRA-287 is too — C5's guard depends on the answer. Read the
current bodies of `_derive_phase_key`, `_derive_attribution`,
`reconcile_pending_attempts` and `record_attempt_from_transcript` as they exist
*now*; the line numbers throughout this spec are anchors, not coordinates. If a
sibling story changed one of these, layer on top of its version — never revert
its work to make an assertion here easier to satisfy. If a genuine conflict
exists, stop and report `FAIL-CAUSE`.

**1. (B) Strict phase keys.** Add `_PHASE_KEY_STRICT_RE` next to the existing
`_PHASE_*` regexes (`:120-125`) with a comment naming the two observed lies
(`phase:key`, `phase:checkpoint`) and the rows that carried them. Add the
optional `project_dir` parameter to `_derive_phase_key` and
`_derive_attribution`, defaulting to `None` so every existing caller and test
keeps working. Apply the shape gate to **both** patterns' captures — the
`docs/phases/phase-<key>.md` pattern is much harder to trip accidentally, but a
key it produces is still a key and there is no reason to hold it to a weaker
standard. Keep the doc-existence check strictly optional and strictly
additive: `docs/phases/` missing means "cannot check", never "reject".

**2. (A) The resolver.** Write `resolve_recording_project` and
`RECORDING_TARGET_SOURCES` near `_derive_attribution`, not in the hook. Write
the docstring — precedence, admission rule, and the "admitted, not trusted"
sentence — *before* the code; if you cannot state plainly why a prompt-derived
path is safe to write to, the design is wrong. Model the structure on
`scope_guard.resolve_call_story` (`scope_guard.py:436-530`): an outer
`try`/`except` that resolves to the fallback, a documented ordered cascade, and
an explicit refusal value rather than a guess.

Extract candidate paths with narrow regexes over `prompt` and `description`.
Accept absolute paths only. Strip surrounding quotes and trailing sentence
punctuation, matching `_strip_trailing_punct`'s existing behaviour. For the
worktree form, find the `.pairmode-worktrees` segment and take everything above
it — do not re-derive a story id here; `scope_guard` owns that question and
duplicating it would create a second, drifting copy.

Do **not** create directories, do **not** write a marker file, and do **not**
call `log_recording_event` from inside the resolver — it is a pure function and
its caller owns the logging. This matters: `log_recording_event` mkdirs
(`:1050`), so a resolver that logged its own rejection would materialise
`.companion/` at the very path it just refused.

**3. (A) Rewire `record_attempt_from_transcript`.** Resolve once, right after
the `isinstance(tool_input, dict)` guard, into a local (e.g. `target_path`,
`target_source`) and use it for everything downstream. Keep `project_path` as
the session fallback for the two pre-resolution log calls only. Thread
`target_project` / `target_source` into every post-resolution
`log_recording_event` call — including the ones inside the `effort_tracking`
early return, which is exactly where an operator debugging "why is there no row
in meander's db" will look first. Emit the additional
`skip:target-unregistered` line when `target_source ==
"rejected-unregistered"`, then carry on and record against the session project;
do not return early. Pass `target_path` to `_derive_attribution` for item B's
doc-existence check.

Leave the function signature alone. `hooks/post_tool_use.py` must not change
(A6) — resist the temptation to "clean up" the hook while you are here; it is
under `PROTECTED_GLOBS` (`scope_guard.py:32-40`) and this story's permissions
artifact does not include it.

**4. (C) The bump.** Add the two comments and the two log calls; change no
gating. When you write C4's test, insert the pending row through the same API
the hook path uses rather than raw SQL if one is available in
`effort_db.py`/`effort_recorder.py` — a test that writes rows by hand will keep
passing after the real writer changes shape. C5's guard should test for a
capability, not for a commit: `pytest.skip` when the INFRA-287 predicate is not
importable, with a reason string naming INFRA-287.

**5. (D) The prose.** Write D1/D2 into `docs/architecture.md` and D3/D4/D5 into
`docs/cer/backlog.md`. On CER-102, the wording discipline matters more than the
length: the ladder was revived by *removing an obstruction*, and the note must
read that way. Do not delete historical finding text on either row.

**6. Ideology note (Step 4a — resolved inline, no unresolved conflict).**
Three entries shaped this spec.

- *"Hooks are thin relays only"* (`docs/ideology.md`, § Accepted constraints,
  override path: **none permitted**) is why every line of item A lives in
  `subagent_transcript.py` and the hook diff is empty (A6). The naive fix —
  teach `hooks/post_tool_use.py:65` to parse the prompt — would put path
  parsing, filesystem stats and allowlist logic on the hook path. Routing it
  through the module the hook already delegates to satisfies the rule *and*
  its rationale (millisecond exit, sidebar/module owns the work); the resolver
  adds only pure in-memory work plus two `stat` calls to a call that already
  reads `state.json` and a JSONL transcript.
- *"Never silently pass contradictions"* is why A2 refuses to fall through to
  the next candidate after a rejection, and why A5 logs
  `skip:target-unregistered` instead of quietly using the session db. A prompt
  naming a target flex will not write to is a contradiction between intent and
  configuration; the constraint's whole point is that the system must say so.
  It is equally why B3 returns `unattributed:<role>` rather than a
  plausible-looking `phase:<word>` — false confidence is the failure mode the
  constraint protects against.
- *"Rationale-bearing decisions over bare rules"* is why C2's and A7's comments
  are Ensures rather than niceties. A future reader who does not know that
  `tool_response` is a launch stub will "fix" the dead insert-time branch by
  loosening its gate; a reader who does not know DP7 will "simplify" the hook
  by pointing both delegated calls at the same project. Both are regressions
  that look like cleanups.

No conviction or constraint was overridden, and none had to be routed around
at the cost of the story's premise.

## Tests

Run from the story worktree root. After item A, and again after item C:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_post_tool_use.py \
  tests/pairmode/test_post_tool_use_hook.py \
  -q 2>&1 | tail -30
```

Then the adjacent recording surface, to catch collateral damage:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_effort_concurrency.py \
  tests/pairmode/test_pairmode_effort.py \
  tests/pairmode/test_hook_view.py \
  tests/pairmode/test_hooks.py \
  tests/pairmode/test_scope_guard.py \
  -q 2>&1 | tail -30
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -40
```

Machine-checkable Ensures:

```bash
# A1/A6 — the resolver exists in the module, and the hook is untouched
grep -n 'RECORDING_TARGET_SOURCES\|def resolve_recording_project' \
  skills/pairmode/scripts/subagent_transcript.py
git diff --stat -- hooks/            # empty

# A5/C3 — the new decision values are registered
grep -n 'skip:target-unregistered\|bump:late-fail\|skip:late-bump-blocked' \
  skills/pairmode/scripts/subagent_transcript.py

# B1 — the strict shape gate exists
grep -n '_PHASE_KEY_STRICT_RE' skills/pairmode/scripts/subagent_transcript.py

# C1 — no bump site was added or removed
grep -c 'bump_attempt_count(' skills/pairmode/scripts/subagent_transcript.py

# C6 — the resolver and harness are untouched
git diff --stat -- skills/pairmode/scripts/next_action.py \
  skills/pairmode/scripts/flex_build.py CLAUDE.build.md    # empty

# D3/D4 — the CER rows are closed
grep 'CER-103' docs/cer/backlog.md | grep -c 'RESOLVED Phase 110'   # 1
grep 'CER-102' docs/cer/backlog.md | grep -c 'RESOLVED Phase 110'   # 1
```

Acceptance:

- every new test from A8, A9, B4, B5, C4, C5, E2 passes (C5 may report as
  **skipped** when INFRA-287 is not in `HEAD` — a skip with the specified
  reason is acceptable, a deletion or a weakened assertion is not);
- every pre-existing test in `tests/pairmode/test_post_tool_use.py` passes
  under its original name, with no edit to `TestHookStaysThin` (A6);
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so explicitly in the build
  result.

## Out of scope

- **Repairing historical rows.** `phase:key` (flex row 416),
  `phase:checkpoint` (meander rows 233-236) and the misattributed `LEGAL-001`
  rows 419/420 in flex's db stay exactly where they are. A cross-project row
  migration is a destructive data operation across two projects' databases and
  needs its own spec with its own reversibility argument. This story fixes the
  writer; the backfill, if it is ever wanted, is a separate story.
- **Changing `hooks/post_tool_use.py`.** Explicitly excluded by A6 and by the
  ideology note in `## Instructions` step 6.
- **Fixing the orchestrator's omitted `model=` on reviewer spawns.** Recorded
  as a note (D5). The fix lives in `next_action.py` / `CLAUDE.build.md`, which
  C6 forbids touching.
- **Re-fixing the reconciliation predicate.** CER-101 is INFRA-287's story.
  This story consumes whatever predicate exists and must not add a second,
  competing containment or terminator check.
- **The duplicate-hook / `agent_id` dedupe path.** CER-104 is INFRA-288's
  story, already merged. Item A changes the same function; layer on top of it.
- **An explicit `phase_key` field on the spawn payload.** The dossier offers
  "parse strictly **or** take an explicit field"; this story takes the first,
  because a new payload field requires every spawn site in `CLAUDE.build.md`
  and `next_action.py` to be updated in lockstep — which C6 excludes — and
  because strict parsing fixes the existing rows' shape without a coordinated
  rollout. If the parse proves insufficient in the field, the explicit field is
  the documented next step, not a widening of this story.
- **Extending the allowlist beyond `registered_projects`** — no env var, no CLI
  flag, no `--allow-any-target` escape hatch. An operator who wants a project
  recorded into adds it to `registered_projects`, which is the same list
  `fleet_discovery` already treats as the fleet's roster.
- **A management UI or CLI for `registered_projects`.** Pre-existing state key,
  not introduced here; no new persistent object is created by this story (E1).
- **Any further `docs/cer/backlog.md` grooming** beyond the CER-102 and CER-103
  rows named in D3/D4/D5. CER-101 and CER-104 are closed by their own stories.

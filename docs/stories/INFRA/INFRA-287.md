---
id: INFRA-287
rail: INFRA
title: "Reconciliation pipeline: symlink-aware containment and current-format terminator predicate (CER-101)"
status: complete
phase: "110"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/subagent_transcript.py
touches:
  - skills/pairmode/scripts/flex_build.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_flex_build_checkpoint_report.py
  # Builder addition (B5/step-5 fixture movement): two TestPending fixtures in
  # this file were written against the pre-INFRA-287 uncontained path shape
  # (output_file directly under project_dir, no tasks/ component) and now
  # classify "uncontained" instead of the reason they pin. Fixture-path-only
  # update; pairmode_effort.py itself is untouched (B8).
  - tests/pairmode/test_pairmode_effort.py
  - docs/stories/INFRA/INFRA-287.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This is the **root-cause** story of Phase 110. Every other story in the phase
sits downstream of it: INFRA-288 stops rows being written twice, INFRA-289
makes rows land in the right project and revives the FAIL ladder — but none of
that matters while **no async row ever reconciles at all**. Since the 0.3
async-spawn loop went live, `attempts.tokens_total` and `attempts.outcome` have
been `NULL` on effectively every row this repo and every migrated consumer
wrote. `checkpoint-report` printed "no attempts recorded" for a fully-built
phase (cp-109, INFRA-280..286); RELEASE-063's canary failed E6 on the same
symptom; the FAIL-escalation ladder went dark (CER-102) because an outcome that
is permanently `NULL` is never `FAIL`.

`reconcile_pending_attempts` exists precisely to complete those rows later, and
it runs — on every PostToolUse spawn and on every SessionStart. It reconciles
zero rows. Three independent breaks, verified live on 294 spawn-output files in
this session's `tasks/` directories on 2026-07-28:

**(a) Containment rejects 100% of real output files.** Claude Code does not
write the spawn output at `<tmp>/claude-<uid>/<slug>/<session>/tasks/<hash>.output`.
It writes a **symlink** there, pointing at
`~/.claude/projects/<slug>/<session>/subagents/agent-<id>.jsonl`.
`_contained_spawn_output` calls `Path.resolve()` **before** applying its
containment rule, so the rule is applied to the *link target*: a path outside
every temp root, with no `tasks` component. It returns `None`, so
`read_completed_spawn` returns `None`, so the sweep `continue`s. Measured:
294 of 294 live output files fail containment today. This is not an edge case —
it is the whole pipeline.

The fix is *not* to delete the containment check. CER-089 added it for a real
reason: `output_file` is a persisted string, and an unchecked one pointing at
`/etc/passwd`, a repo file, or `~/.ssh/*` would be opened and parsed by a
hook-path function. The fix is to stop conflating two different questions.
"Is this path in a location the harness writes spawn output to?" is a question
about the **link path** and must be answered lexically. "Does this link point
somewhere we are willing to read from?" is a question about the **target** and
needs its own allowlist — which, now that the real shape is known, is
`~/.claude/` (the same transcript root `context_budget._derive_transcript_path`
already confines itself to) plus the temp roots themselves.

**(b) The terminator predicate matches a format that is no longer universal.**
Both `read_completed_spawn` and `classify_pending_reason` require the last
parseable entry to be `type == "assistant"` with
`message.stop_reason == "end_turn"`. The phase dossier states `end_turn` no
longer exists; that is **too strong**, and this spec corrects it with measured
data rather than inheriting the claim. Across the same 294 files:

| last parseable entry | count |
|---|---|
| `assistant` / `end_turn` | 215 |
| `assistant` / absent-or-null `stop_reason` | 51 |
| no parseable entry at all | 26 |
| `assistant` / `tool_use` | 1 |
| `user` | 1 |

So `end_turn` is still the majority terminator and must keep working. But ~18%
of completed spawns end on an assistant entry whose `stop_reason` is simply
absent — a written-out final turn that was never stamped — and **50 of those 51
files have not been touched in over an hour**. Those are finished agents, not
in-flight ones. The honest terminator is therefore *last-entry-assistant* **and**
(`stop_reason == "end_turn"` **or** the file has been quiescent for
`QUIESCENT_AGE_SECONDS`). The mtime half of that test is not new machinery —
`reconcile_pending_attempts`'s `include_quiescent` branch already does exactly
this stat-and-compare; this story promotes it from an opt-in retirement path
into the shared predicate, where it belongs.

**(c) The predicate is split in two, so the diagnostic lies.** `pairmode_effort
pending` reported **14 reconcilable** rows at cp-109 while a direct sweep
reconciled **0** — the exact contradiction CER-101 was filed on.
`classify_pending_reason` opens `row["output_file"]` directly and never calls
`_contained_spawn_output`; `read_completed_spawn` does. Two functions, two
answers, one file. CER-091 already recognised this failure class and extracted
`_stream_spawn_output` as a shared *reader*; it did not extract a shared
*predicate*, so the reachability judgment stayed duplicated and drifted. This
story finishes that job: one function decides containment **and** termination,
both callers consume it, and `uncontained` becomes a first-class
`PENDING_REASONS` member so a rejected path is a visible diagnosis instead of an
indistinguishable `file-missing`.

**(d) Two silent collaterals of the same `resolve()` bug.**
`session_output_prefix` (INFRA-285, CER-097) derives a session-ownership prefix
by resolving the output path and locating its `tasks` component — so it, too,
returns `None` for every real symlinked path (verified live). The
`spawn_output_prefix` ownership filter that CER-097 built has therefore never
been armed in production: `record_attempt_from_transcript` always sweeps
globally. And `checkpoint-report`, the surface CER-101 was actually reported
from, prints `no attempts recorded` for a story whose rows exist but are
pending — a message that reads as data loss when it means deferred
reconciliation. CER-101's own filed "Fix:" names both the shared predicate and
the report; closing the CER while shipping only half of it would be precisely
the half-implementation pattern INFRA-290 adds a standing review check for.

**Contract with INFRA-289 (already merged).**
`tests/pairmode/test_subagent_transcript.py::TestAsyncFailBumpTraceability::test_c5_end_to_end_symlink_output_skips_without_infra_287`
currently `pytest.skip`s on `getattr(st, "is_reconcilable_spawn_output", None) is None`.
That name is a **hard interface constraint on this story**, not a suggestion:
the shared predicate must be importable from `subagent_transcript` under exactly
that name, and that test must go from skipped to passing on this story's diff.

## Requires

- **INFRA-288 and INFRA-289 are complete and merged**, and this story's worktree
  is cut from a `HEAD` containing both. INFRA-289 rewrote
  `record_attempt_from_transcript` and `reconcile_pending_attempts`'s FAIL
  branch — this story edits the same regions. Verify before building:
  `git log --oneline --grep 'INFRA-289'` returns a commit reachable from `HEAD`,
  and `grep -n 'bump:late-fail' skills/pairmode/scripts/subagent_transcript.py`
  prints a line.
- `skills/pairmode/scripts/subagent_transcript.py` defines
  `SPAWN_TASKS_DIR_NAME`, `RECONCILE_MAX_LINES`, `QUIESCENT_AGE_SECONDS`,
  `PENDING_REASONS`, `default_spawn_output_roots`, `_contained_spawn_output`,
  `_is_relative_to`, `session_output_prefix`, `_stream_spawn_output`,
  `classify_pending_reason`, `read_completed_spawn`,
  `reconcile_pending_attempts`, `_older_than_seconds`, and
  `record_attempt_from_transcript`.
- `tests/pairmode/test_subagent_transcript.py` contains
  `TestContainedSpawnOutput`, `TestReadCompletedSpawn`,
  `TestReadCompletedSpawnContainment`, `TestClassifyPendingReason`,
  `TestQuiescentReconciliation`, `TestSweepOwnershipForwarded`,
  `TestRecordAttemptSweepOwnership`, and
  `TestAsyncFailBumpTraceability::test_c5_end_to_end_symlink_output_skips_without_infra_287`.
- `skills/pairmode/scripts/flex_build.py` defines `_query_effort_by_story_ids`
  and a `checkpoint-report` command that prints
  `no attempts recorded for phase <key>` and `<sid>: no attempts recorded`.
- `skills/pairmode/scripts/context_budget.py` defines `_derive_transcript_path`
  with its `home: Path | None = None` injection parameter (the convention this
  story's `home` parameter mirrors).
- `docs/cer/backlog.md` contains an open row for `CER-101` with `—` in its
  Phase cell.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command. Symbols named below that do not exist on `HEAD` are **created by this
story** — `spec-preflight` flagging them as unverifiable is expected and
intentional.

### A — containment is symlink-aware

**A1. Containment is judged lexically, on the path as given.**
`_contained_spawn_output` no longer calls `Path.resolve()` before applying its
containment rule. It normalises the candidate with `os.path.abspath` (which
applies `normpath` — collapsing `..` and `.` — **without** following symlinks)
and applies the existing three-part default rule to that lexical path: contained
under one of `default_spawn_output_roots()`, a literal `SPAWN_TASKS_DIR_NAME`
component in `.parts`, and `is_file()` (which may follow a link — the file must
genuinely exist and be a file, not a directory or a broken link). The explicit
`tasks_root` mode is likewise judged lexically against
`os.path.abspath(tasks_root)`.

**A2. The returned path is the lexical path, not the link target.** For a
symlinked `output_file`, `_contained_spawn_output` returns the path *in the
`tasks` directory*. This is load-bearing: it keeps `output_file`,
`session_output_prefix`, the `pending_reconcilable` ownership filter and the
recording log all expressed in the same session-identifying namespace. A test
asserts `_contained_spawn_output(link) == Path(os.path.abspath(link))` and
`!= link.resolve()` for a link whose target lives elsewhere.

**A3. The link target is allowlisted, not trusted.** A new module-level helper
— `_permitted_output_target(path: Path, home: "Path | None" = None) -> bool` —
returns `True` only when the path is **not** a symlink, or when
`os.path.realpath(path)` is contained under at least one of: the resolved
`(home or Path.home()) / ".claude"`, or any member of
`default_spawn_output_roots()`. `_contained_spawn_output` gains a
`home: "Path | None" = None` keyword parameter, calls this helper after its
lexical checks, and returns `None` when the helper returns `False`. Rationale is
stated in the docstring: CER-089's protection is preserved by moving it from the
link *path* to the link *target*, and `~/.claude/` is where Claude Code
genuinely puts subagent transcripts — the same root
`context_budget._derive_transcript_path` already confines itself to.

**A4. CER-089's original attack shapes are still rejected.** Tests assert
`_contained_spawn_output` returns `None` for: a plain (non-symlink) path outside
every temp root; a path inside a temp root with no `tasks` component; a
directory; and — new — a symlink correctly placed under `<root>/tasks/` whose
target is a file outside both `~/.claude` and every temp root (built under
`tmp_path` with an injected `home`, never touching a real sensitive file). A
test asserts that for the rejected-target case **no `open()` occurs**, e.g. by
monkeypatching `_stream_spawn_output` to raise and confirming
`read_completed_spawn` still returns `None`.

**A5. The real live shape is accepted.** A test constructs
`<root>/claude-1000/-mnt-work-flex/<session>/tasks/<hash>.output` as a symlink
to `<home>/.claude/projects/-mnt-work-flex/<session>/subagents/agent-<hash>.jsonl`
(both under `tmp_path`, with `default_spawn_output_roots` monkeypatched and
`home` injected) and asserts `_contained_spawn_output` returns the lexical
`tasks/` path.

### B — one shared containment + terminator predicate

**B1. `is_reconcilable_spawn_output` exists with exactly that name.** Module
level in `subagent_transcript.py`:

```python
def is_reconcilable_spawn_output(
    output_file: "str | Path | None",
    *,
    tasks_root: "Path | str | None" = None,
    home: "Path | None" = None,
) -> "tuple[Path | None, str, dict]":
```

returning `(path, reason, data)` where `path` is the contained lexical path (or
`None`), `reason` is a member of `PENDING_REASONS` or
`SPAWN_TERMINATED` (B2), and `data` is the `_stream_spawn_output` result shape
(the all-default shape when nothing was read). Pure: no writes, no db access,
never raises — any exception yields `(None, "file-empty", <empty shape>)`,
matching `classify_pending_reason`'s existing except-branch value.

**B2. The success sentinel is a named constant.**
`SPAWN_TERMINATED: str = "terminated"` is defined at module level and is
**not** a member of `PENDING_REASONS` (it is the absence of a pending reason).
A test asserts `SPAWN_TERMINATED not in PENDING_REASONS`.

**B3. `uncontained` is a first-class pending reason.** `PENDING_REASONS` gains
`"uncontained"`, returned when `output_file` is non-empty but
`_contained_spawn_output` rejects it. It is distinct from `file-missing`: a
row stuck because of a containment rule and a row stuck because `/tmp` was
evicted are different operational problems and must not print the same word.

**B4. The terminator accepts `end_turn` or quiescence.** Given a contained,
existing, parseable file whose last parseable entry has `type == "assistant"`
and a `dict` `message`:

- `stop_reason == "end_turn"` → `SPAWN_TERMINATED`;
- otherwise, when the file's own mtime is older than `QUIESCENT_AGE_SECONDS`
  → `SPAWN_TERMINATED` (a spawn that stopped writing 15 minutes ago is
  finished, whatever its last entry was stamped with);
- otherwise, truthy non-`end_turn` `stop_reason` (e.g. `"tool_use"`) →
  `"in-flight"`;
- otherwise (falsy/absent `stop_reason`, file still fresh) →
  `"not-terminated"`.

A last entry that is not `type == "assistant"`, or whose `message` is not a
dict, is `"not-terminated"` **regardless of mtime** — the quiescence promotion
applies only where there is an assistant turn to extract usage from; the
`include_quiescent` `UNKNOWN` path (unchanged by this story) remains the
retirement route for the rest.

The mtime read is best-effort: an `OSError` on `stat()` means "not quiescent",
never an exception and never a promotion.

**B5. Ordering of reasons is preserved.** The predicate returns, in order:
`no-output-file` (falsy `output_file`), `uncontained`, `file-missing`
(`not data["exists"]`), `line-cap`, `file-empty` (`not data["any_parsed"]`),
then the B4 terminator verdicts. Existing `classify_pending_reason` tests that
assert a specific reason for a specific fixture keep passing unmodified, except
where a fixture's expected reason legitimately changes under B4 — in which case
the test is **updated with a comment naming INFRA-287**, never deleted.

**B6. Both callers route through it — no second copy remains.**
`read_completed_spawn` calls `is_reconcilable_spawn_output` and returns `None`
unless `reason == SPAWN_TERMINATED`, then does only usage/duration/outcome
extraction from the returned `data`. `classify_pending_reason` calls it and
returns `reason` directly unless `reason == SPAWN_TERMINATED`, in which case it
continues to its existing `no-usage` → `no-outcome` → `reconcilable` tail.
Machine-checkable: `grep -c 'stop_reason' skills/pairmode/scripts/subagent_transcript.py`
returns a count no greater than **2** after this story (down from 5), and
`grep -n '_contained_spawn_output(' skills/pairmode/scripts/subagent_transcript.py`
shows it called from exactly one place — `is_reconcilable_spawn_output` —
besides its own definition.

**B7. `classify_pending_reason` and the sweep can no longer disagree.** A test
builds a project with three pending rows — one symlinked-and-terminated, one
symlinked-and-fresh-`tool_use`, one whose `output_file` points outside every
root — asserts `classify_pending_reason` returns `reconcilable`, `in-flight`,
`uncontained` respectively, then runs `reconcile_pending_attempts` and asserts
it returns exactly `1` and that the reconciled row is the one classified
`reconcilable`. This is the cp-109 "14 reconcilable, 0 reconciled"
contradiction expressed as a regression test.

**B8. `classify_pending_reason` keeps its public signature.** It still takes a
single already-fetched `row` dict positionally and is still pure. It gains no
required parameter; if it needs `home`/`tasks_root` it takes them as
keyword-only with defaults, so `pairmode_effort.py pending`'s existing call site
is unchanged. `git diff --stat -- skills/pairmode/scripts/pairmode_effort.py`
is empty.

### C — the ownership prefix works on a symlinked path

**C1. `session_output_prefix` is lexical too.** It derives its parts from
`os.path.abspath(output_file)` instead of `Path(...).resolve()`, so a real
symlinked spawn-output path yields
`<root>/claude-<uid>/<slug>/<session>/` with the trailing separator, as its
docstring has always claimed. Its documented contract is otherwise unchanged: it
still does not require the file to exist, still returns `None` for `None`, for a
path with no `tasks` component, and for a `tasks` component at index 0, and
still never raises.

**C2. A regression test pins the symlink case.** A test creates
`<tmp>/claude-1000/-slug/sess-1/tasks/x.output` as a symlink to a target in an
unrelated directory and asserts
`session_output_prefix(link) == str(<tmp>/claude-1000/-slug/sess-1) + os.sep`.
A sibling test asserts the non-symlink case returns the identical value (no
behaviour change for the shape the existing tests cover).

**C3. The ownership filter is now genuinely armed, and that is stated.** The
docstring records that this prefix returned `None` for every production path
between INFRA-285 and this story because of the `resolve()`-through-the-symlink
bug, so `record_attempt_from_transcript`'s sweep has been running unfiltered —
and that it is filtered from here on. No call site changes; the value simply
stops being `None`.

**C4. No new starvation.** Because the PostToolUse sweep's inclusive
`output_prefix` filter becomes live for the first time, a test asserts the
SessionStart-side sweep is unaffected: `reconcile_pending_attempts` called with
`output_prefix=None` still reaches a row whose `output_file` belongs to a
different session prefix. `TestSweepOwnershipForwarded`,
`TestSweepExclusionForwarded`, `TestSweepStarvation` and
`TestRecordAttemptSweepOwnership` all pass unmodified.

### D — `checkpoint-report` stops reporting deferred work as absent

**D1. Pending rows are counted and printed.** `flex_build.py` gains a
`_query_pending_by_story_ids(db_path, story_ids) -> dict[str, int]` returning
`{story_id: pending_row_count}` for rows whose `tokens_total IS NULL OR outcome
IS NULL`, restricted by bound SQL parameters (never interpolated), returning
`{}` on an absent/unreadable db and never raising — the same contract as its
neighbour `_query_effort_by_story_ids`.

**D2. The misleading strings are qualified, not deleted.** In
`checkpoint-report`:
- the phase-level `no attempts recorded for phase <key>` line, when the pending
  map is non-empty, is followed by a line of the form
  `N attempt row(s) recorded but not yet reconciled — effort is pending, not absent`;
- the per-story `<sid>: no attempts recorded` line becomes
  `<sid>: no reconciled attempts (N pending)` when that story has pending rows,
  and is left exactly as-is when it has none.

A test asserts both the pending-suffix form and that a story with neither
reconciled nor pending rows still prints the original bare string.

**D3. `checkpoint-report` stays pure-read.** It does **not** call
`reconcile_pending_attempts`. Its docstring's "Pure-read: writes nothing"
promise is kept, and one sentence is added recording *why* the reconcile-first
option in CER-101's filed fix was declined: the sweep already runs on every
PostToolUse and SessionStart, so once this story lands there is nothing for a
report to fix, and a reporting command that mutates the database it reports on
is a boundary this project does not cross for convenience.
`grep -n 'reconcile_pending_attempts' skills/pairmode/scripts/flex_build.py`
returns no line inside the checkpoint-report function.

### E — documentation and CER closure

**E1. Architecture records the containment split.** `docs/architecture.md`
gains one paragraph (bolded lead, matching its neighbours) in the section that
already documents effort recording / async reconciliation, citing
`INFRA-287, CER-101`: that Claude Code writes the spawn output as a symlink
under `tasks/` pointing into `~/.claude/projects/.../subagents/`; that
containment is therefore judged **lexically on the link path** while the link
**target** is separately allowlisted to `~/.claude/` or a temp root; and that
`output_file` is stored and compared in the `tasks/` namespace because session
ownership (`session_output_prefix`) is derived from it.

**E2. Architecture records the terminator rule.** The same section gains a
sentence: a spawn is terminated when its last parseable entry is an assistant
turn **and** either `stop_reason == "end_turn"` or the file has been quiescent
for `QUIESCENT_AGE_SECONDS` — with the measured reason (≈18% of completed
spawns end on an assistant turn with no `stop_reason` stamp, and effectively all
of those are long quiescent), so a future reader does not "tighten" the
predicate back to `end_turn`-only.

**E3. CER-101 is closed.** Its row in `docs/cer/backlog.md` gains a bolded
`**RESOLVED Phase 110 — INFRA-287 …**` note appended to its Finding cell,
naming: the symlink-containment root cause (with the 294/294 measurement), the
terminator widening (with the 215/51/26/1/1 distribution), the shared
`is_reconcilable_spawn_output` predicate that ends the classify-vs-sweep
disagreement, the new `uncontained` pending reason, the `session_output_prefix`
collateral, and the `checkpoint-report` pending-count change together with the
declined reconcile-first option and why (D3). Its `Phase` cell is set to `110`.
The historical finding text is not deleted.

**E4. No new CER is filed by this story.** The two collaterals (C, D) are fixed
here rather than routed to the backlog, because both are the same `resolve()`
defect and the same CER's own filed fix. If the builder discovers a *further*
defect outside this story's Ensures, it is reported in the build result for the
operator to route — never filed unilaterally, and never fixed silently.

### Cross-cutting

**F1. `schema_introduces` stays `false`.** No table, column, or migration is
added; `docs/phases/phase-110.md` § Schema delivery is owed no row by this
story. `git diff --stat -- skills/pairmode/scripts/effort_db.py` is empty.

**F2. `hooks/` is byte-identical.** `git diff --stat -- hooks/` is empty. The
hooks remain thin relays; every change lives in the modules they already
delegate to.

**F3. INFRA-289's C5 test un-skips and passes.**
`pytest tests/pairmode/test_subagent_transcript.py -k c5_end_to_end -q` reports
`1 passed`, `0 skipped`. The test itself is **not edited** — not its guard, not
its assertions, not its name. It going green is the acceptance signal that this
story's predicate is real.

**F4. The full suite is green** (`tests/pairmode/`), run once **without** `-x`
so a known pre-existing failure cannot mask a new one.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order A → B → C → D → E. A and B are one continuous change and the
suite will be red between them — that is expected; run the suite after B, again
after C, and finally in full.

**0. Rebase check.** Confirm INFRA-288 and INFRA-289 are in your `HEAD`
(`## Requires`). Read the current bodies of `_contained_spawn_output`,
`session_output_prefix`, `_stream_spawn_output`, `classify_pending_reason`,
`read_completed_spawn` and `reconcile_pending_attempts` as they exist *now*;
the descriptions in this spec are anchors, not coordinates. Never revert a
sibling story's work to make an assertion here easier to satisfy. If a genuine
conflict exists, stop and report `FAIL-CAUSE`.

**1. Verify the premise before you change anything.** Run the measurement this
spec is built on, in your worktree, against this machine's live output files:

```bash
PATH=$HOME/.local/bin:$PATH uv run python - <<'EOF'
import glob, json, os, time, sys
sys.path.insert(0, "skills/pairmode/scripts")
import subagent_transcript as st
files = glob.glob("/tmp/claude-*/*/*/tasks/*.output")
print("files:", len(files))
print("contained:", sum(1 for f in files if st._contained_spawn_output(f)))
print("prefix:", sum(1 for f in files if st.session_output_prefix(f)))
EOF
```

On `HEAD` this prints a nonzero file count with `contained: 0` and `prefix: 0`.
If it does not — if containment already passes on this machine — **stop and
report `FAIL-CAUSE`**: the shape has changed since the audit and the spec's
premise needs re-deriving before any code moves. Re-run the same snippet at the
end; both counts must then be nonzero and roughly equal to the file count.

**2. (A) Lexical containment.** Replace `candidate.resolve()` with
`Path(os.path.abspath(str(candidate)))` in `_contained_spawn_output`, for both
the default-rule and the `tasks_root` branches (normalise `tasks_root` the same
way). `os` is already imported. Keep `is_file()` — it follows the link, which
is exactly what you want for "this must be a real, readable file". Keep
`_is_relative_to` for the root check; do not swap it for `Path.is_relative_to`.

Then write `_permitted_output_target`. Use `os.path.islink` to decide whether a
target check applies at all, and `os.path.realpath` (not `Path.resolve`, so the
symmetry with the lexical `abspath` above is visible) for the target. Take
`home` as an injectable parameter with a `Path.home()` default, mirroring
`context_budget._derive_transcript_path` — the tests depend on injecting it, and
a test that has to write into a real `~/.claude` is a test nobody will run.

Write the docstring for `_permitted_output_target` **before** the code, and make
it say plainly what CER-089 protects and how moving the check from the path to
the target preserves it. If you cannot state that clearly, the design is wrong —
stop and report rather than shipping a weaker check with a confident comment.

**3. (B) The shared predicate.** Add `SPAWN_TERMINATED` next to
`PENDING_REASONS`, and add `"uncontained"` to `PENDING_REASONS` in the position
that keeps the tuple readable (it is a tuple, not a set — order is documentation
here, so put it directly after `no-output-file`, following the order the
predicate itself evaluates in).

Write `is_reconcilable_spawn_output` immediately after `_contained_spawn_output`
and `_stream_spawn_output`, then **delete** the duplicated logic from both
callers rather than leaving it behind a flag. A shared predicate that coexists
with the two copies it was written to replace is the CER-101 bug with an extra
function in front of it. B6's `grep` counts are how the reviewer checks you
actually removed them.

For the quiescence half of B4, reuse `QUIESCENT_AGE_SECONDS` — do not introduce
a second, differently-named threshold for the same physical judgment. Compare
against `datetime.now(timezone.utc).timestamp()` and `path.stat().st_mtime`, the
same way `reconcile_pending_attempts`'s quiescent branch already does, and wrap
the `stat()` in its own `try`/`except OSError` returning "not quiescent".

**4. (B) Do not widen anything else while you are in here.** The
`no-usage`/`no-outcome`/`reconcilable` tail of `classify_pending_reason`, the
`include_quiescent` retirement branch, `RECONCILE_MAX_ROWS`,
`RECONCILE_OLDEST_ROWS`, the two-ended cursor, the FAIL-bump gating and
`_story_accepts_late_bump` all stay exactly as they are. This story makes rows
*reach* those code paths for the first time; several of them are about to
execute in production having never executed before, and changing them in the
same diff would make an incident unattributable.

**5. (B) Expect existing tests to move, and move them honestly.** Some fixtures
in `TestClassifyPendingReason` / `TestReadCompletedSpawn` were written against
the `resolve()`-based rule or the `end_turn`-only terminator. Where a fixture's
correct expected value genuinely changes, update the assertion and add a comment
naming INFRA-287 and the reason. Where a fixture would only pass if you weaken
the new rule, the fixture is right and your rule is wrong — fix the rule. Do not
delete a test to make a suite green, and do not add `pytest.skip` to one.

**6. (C) The prefix.** One-line change plus tests. Note in the docstring that
this was dead in production (C3) — a reader who finds `spawn_output_prefix`
populated in `state.json` for the first time deserves to know it is new
behaviour, not new data.

**7. (D) The report.** Model `_query_pending_by_story_ids` directly on
`_query_effort_by_story_ids` two functions above it — same `import sqlite3 as
_sqlite3` local-import style, same bound-parameter placeholders, same
never-raise/empty-result contract. Do not reach for `effort_db.pending_reconcilable`
here: it applies an age cutoff and row limits that are right for a bounded
hook-path sweep and wrong for a report that must count *every* pending row in
the phase.

Keep the wording changes small and factual. The failure this fixes is a message
that misled an operator into believing data was lost; the cure is precision, not
volume.

**8. (E) The prose.** Write E1/E2 into `docs/architecture.md` and E3 into
`docs/cer/backlog.md`. Include the measured numbers — they are the difference
between a note a future reader trusts and one they re-derive from scratch. Do
not delete historical finding text.

**9. Ideology note (Step 4a — resolved inline, no unresolved conflict).**
Three entries shaped this spec.

- *"Never silently pass contradictions"* (`docs/ideology.md`, § Accepted
  constraints, override path: acknowledged-and-recorded only) is the reason B3
  adds `uncontained` as a distinct reason rather than letting a rejected path
  masquerade as `file-missing`, and the reason D2 exists at all. CER-101's real
  damage was not that reconciliation failed — it was that every surface reported
  the failure as *absence of data*. The constraint's rationale ("a system that
  misses contradictions provides false confidence, which is worse than no
  system") is exactly this failure, and B7 pins the specific contradiction
  (classify says reconcilable, sweep reconciles nothing) as a test.
- *"Hooks are thin relays only"* (override path: **none permitted**) is why F2
  requires an empty `hooks/` diff. Everything here runs on the hook path, so the
  temptation to add a check "at the hook" is real; the containment and terminator
  logic stays in the module the hook already delegates to. The added cost is
  bounded and stated: one `os.path.islink` plus at most one `realpath` per
  candidate, replacing a `resolve()` that already stat-walked the whole path.
- *"Rationale-bearing decisions over bare rules"* is why A3's and E2's
  explanations are Ensures rather than niceties. A reader who does not know the
  output file is a symlink will "fix" A1 back to `resolve()` for tidiness; a
  reader who does not know the measured `stop_reason` distribution will tighten
  B4 back to `end_turn`-only. Both are regressions that look like cleanups, and
  both have already happened once in this codebase's history — CER-089's
  containment was itself a correct fix whose unstated assumption about the path
  shape is what caused CER-101.

No conviction or constraint was overridden, and none had to be routed around at
the cost of the story's premise.

## Tests

Run from the story worktree root. After item B, and again after item C:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_subagent_transcript.py \
  -q 2>&1 | tail -40
```

The INFRA-289 contract test specifically (F3 — must be `1 passed`, not
`1 skipped`):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_subagent_transcript.py -k c5_end_to_end -q -rs 2>&1 | tail -10
```

After item D:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_checkpoint_report.py \
  tests/pairmode/test_pairmode_effort.py \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_effort_concurrency.py \
  tests/pairmode/test_hooks.py \
  tests/pairmode/test_post_tool_use.py \
  -q 2>&1 | tail -30
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -40
```

Machine-checkable Ensures:

```bash
# B1/B2/B3 — the predicate, the sentinel, the new reason
grep -n 'def is_reconcilable_spawn_output\|SPAWN_TERMINATED\|"uncontained"' \
  skills/pairmode/scripts/subagent_transcript.py

# A1/C1 — resolve() no longer decides containment or ownership
grep -n 'resolve()' skills/pairmode/scripts/subagent_transcript.py

# B6 — no second copy of the terminator, one containment call site
grep -c 'stop_reason' skills/pairmode/scripts/subagent_transcript.py   # <= 2
grep -n '_contained_spawn_output(' skills/pairmode/scripts/subagent_transcript.py

# A3 — the target allowlist exists
grep -n 'def _permitted_output_target' skills/pairmode/scripts/subagent_transcript.py

# D3 — the report did not become a writer
grep -n 'reconcile_pending_attempts' skills/pairmode/scripts/flex_build.py   # none in checkpoint-report

# B8/F1/F2 — untouched files
git diff --stat -- hooks/ \
  skills/pairmode/scripts/effort_db.py \
  skills/pairmode/scripts/pairmode_effort.py    # empty

# E3 — the CER row is closed
grep 'CER-101' docs/cer/backlog.md | grep -c 'RESOLVED Phase 110'   # 1
```

Live end-to-end check (Instructions 1, re-run after the build). Both counts
must be nonzero and close to the file count:

```bash
PATH=$HOME/.local/bin:$PATH uv run python - <<'EOF'
import glob, sys
sys.path.insert(0, "skills/pairmode/scripts")
import subagent_transcript as st
files = glob.glob("/tmp/claude-*/*/*/tasks/*.output")
print("files:", len(files))
print("contained:", sum(1 for f in files if st._contained_spawn_output(f)))
print("prefix:", sum(1 for f in files if st.session_output_prefix(f)))
EOF
```

Acceptance:

- every new test from A2, A4, A5, B2, B7, C2, C4, D2 passes;
- `test_c5_end_to_end_symlink_output_skips_without_infra_287` reports
  **passed**, not skipped, with no edit to the test (F3);
- the live check reports nonzero `contained` and `prefix`;
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so explicitly in the build
  result.

## Out of scope

- **Backfilling historical rows.** Every `NULL`-token/`NULL`-outcome row already
  in flex's and meander's `effort.db` stays exactly as it is. Rows younger than
  `RECONCILE_MAX_AGE_DAYS` whose output files still exist will reconcile
  naturally on the next sweeps; the rest are permanently pending and that is the
  honest record. A retroactive repair pass across two projects' databases is a
  destructive data operation needing its own spec and its own reversibility
  argument.
- **Re-running the phase-109 / RELEASE-063 rollups.** Verifying that
  `checkpoint-report` now shows real numbers for a *previously* built phase is a
  post-merge operator observation, not an acceptance criterion of this story.
- **Changing `hooks/post_tool_use.py` or `hooks/session_start.py`.** Explicitly
  excluded by F2 and by the ideology note in `## Instructions` step 9.
- **The duplicate-hook / `agent_id` dedupe path (CER-104)** — INFRA-288's story,
  already merged. Do not add a second dedupe.
- **Target-project attribution, strict phase-key parsing, and the FAIL-bump
  trace (CER-102/CER-103)** — INFRA-289's story, already merged. This story
  makes INFRA-289's reconcile-time bump *reachable*; it does not touch the bump,
  its gating, or its logging.
- **The `attempts.model`-NULL-on-reviewer-rows collateral.** Recorded as a note
  on CER-102 by INFRA-289; the remaining half of the fix is the orchestrator's
  omitted `model=`, which lives in `next_action.py` / `CLAUDE.build.md`.
- **Tightening containment to the full
  `claude-<uid>/<slug>/<session>/tasks/` shape.** `_contained_spawn_output`'s
  existing docstring already argues against this — pinning the fuller shape makes
  every path uncontained the moment the harness changes its layout, which is the
  exact failure this story is repairing. Keep the loose rule; the new protection
  is the target allowlist, not a narrower path pattern.
- **A `--reconcile-first` flag or any other write path on `checkpoint-report`.**
  Declined with reasons in D3.
- **`pairmode_effort.py`'s `pending` CLI output format.** It gains the
  `uncontained` reason for free through `classify_pending_reason`; its rendering,
  flags and tests are unchanged (B8).
- **Retiring the `include_quiescent` `UNKNOWN` path.** It still has a job:
  files with no parseable entry (26 of 294 measured) and non-assistant last
  entries are still not terminable and still need retirement. Whether it can
  shrink once B4's quiescence promotion is live in the field is a future
  observation, not this story's change.

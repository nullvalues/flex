---
id: INFRA-271
rail: INFRA
title: "Scope-guard campaign readiness: stale current_story clear, idle-checkout tolerance, harness-owned write allow-list (CER-080, CER-087)"
status: complete
phase: "105"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/scope_guard.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_scope_guard.py
  - tests/pairmode/test_pre_tool_use_scope_guard.py
  - tests/pairmode/test_flex_build_clear_stale_stories.py
  - tests/pairmode/test_pre_tool_use_hook.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-271.md
---

<!-- Build note: tests/pairmode/test_pre_tool_use_hook.py was added to
touches during the build. `test_flex_factor_raises_ceiling_and_avoids_block`
seeded a `current_story: {"id": "RELF-001"}` entry with no `set_at` — under
A2/A4 that is stale, not fresh, so the fixture stopped resolving to
RELF-001's flex_factor via the state-legacy fallback. This is the same class
of fixture-timestamp repair Instructions Step 2 applied to
test_scope_guard.py / test_pre_tool_use_scope_guard.py, just in a third file
the Requires section did not enumerate; verified it does not reproduce on
clean HEAD before attributing it to this story. -->

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 105 de-risks the fleet migration campaign. Phase 106 will drive builds
across eight-plus already-migrated projects from this checkout, which means the
`pre_tool_use` → `scope_guard.check_path` path will fire against far more state
shapes than flex's own dogfooding has exercised. Two of those shapes are known
to block *legitimate* work today, and both were observed live rather than
theorised.

**CER-080 — a stale `current_story` stamp blocks a genuinely-idle checkout
indefinitely.** `scope_guard.check_path` resolves state from the main checkout
(`_resolve_main_project_root`, INFRA-238) so that a build spawn running in
`.pairmode-worktrees/<ID>/` still finds the one `state.json` that exists. That
resolution is correct, and it is exactly what makes a stale stamp dangerous: a
`current_story` written months ago and never cleared (the observed case was
`INFRA-209`, stamped 2026-07-20, hit during Phase 98's `checkpoint-docs` step)
keeps `resolve_call_story` returning `state-legacy`/`state-single` forever. Every
Edit/Write from that checkout — or from any linked worktree of it — is then
scored against a long-dead story's `allowed_paths` and denied with
`not in story scope for INFRA-209`. The workaround at the time was to write files
outside the hook path entirely, which is precisely the "operator learns to route
around the guard" failure mode that makes a guard worthless. The `set_at`
timestamp needed to detect this is already written by
`story_context.set_current_story` on every stamp; nothing reads it.

**CER-087 — fail-closed containment blocks harness-owned out-of-repo writes.**
INFRA-255 made `_normalise` return `None` for any path that resolves outside the
project root, and `check_path` deny it in every guard state. That is the right
security boundary and must not be relaxed — but its blast radius includes writes
the *harness itself* owns and that have nothing to do with story scope. Observed
minutes after cp100: a Write to `~/.claude/projects/-mnt-work-flex/memory/…` was
denied with `path escapes project root` where pre-INFRA-255 it fell through the
`no active story — allowing` return. The same applies to the session scratchpad
under `/tmp/claude-<uid>/<cwd-key>/…`. During a fleet campaign the orchestrator
writes memory notes and scratchpad files constantly; a guard that denies them
either stops the campaign or trains the operator to disable the guard.

The two fixes share one file and one contract, so they are one story. The third
element in the title — "stale `current_story` clear" — is the operator-facing
half of CER-080: a CLI that reports and clears stale stamps, so the campaign can
sweep eight projects before it starts rather than discovering each stale stamp as
a mid-build denial. flex's own `.companion/state.json` no longer carries the
`INFRA-209` stamp (verified at spec time: the file has neither a `current_story`
nor a `current_stories` key), so this story delivers the *mechanism* and proves it
against fixtures; there is no live stamp left in this repo to clear.

**Scope boundary against the sibling stories.** INFRA-269 and INFRA-270 own
`bootstrap.py` and `fleet_discovery.py`; this story touches neither. RELEASE-062
owns `docs/harness-cutover-runbook.md` — this story adds no runbook step, so the
two do not collide on that file. INFRA-272 owns `context_budget` state hygiene;
the only overlap is that both read `state.json`, and this story writes to it only
through `story_context`'s existing locked writers.

## Requires

- `skills/pairmode/scripts/scope_guard.py` exposes `check_path`,
  `resolve_call_story`, `_resolve_story_from_state`, `_read_current_story`,
  `_read_current_stories_keyed`, `_read_legacy_story_id`, `_read_state_dict`,
  `_normalise`, `_norm_str`, `_strip_worktree_prefix`, `_is_protected`, and the
  module constants `PROTECTED_GLOBS`, `RESOLVE_CALL_STORY_SOURCES`,
  `_WORKTREE_PREFIX`, `_STORY_ID_RE`.
- `skills/pairmode/scripts/story_context.py` exposes `set_current_story` (which
  stamps `set_at` as `datetime.now(timezone.utc).isoformat()` on every entry) and
  `clear_current_story(companion_dir, story_id=None)` with the two documented
  modes (scoped removal vs. clear-the-slate).
- `skills/pairmode/scripts/flex_build.py` defines the `@click.group()`
  `flex_build` and already imports `clear_current_story` from `story_context`.
- `tests/pairmode/test_scope_guard.py` defines `_write_state`,
  `_write_permissions`, `_write_keyed_state`, `_make_linked_worktree`,
  `_make_worktree_dir`, `GUARD_STATES`, and the classes
  `TestResolveCallStorySources`, `TestCheckPathAmbiguous`,
  `TestTwoConcurrentBuildersScopedIndependently`, `TestReadCurrentStoryWrapper`.
- `docs/cer/backlog.md` has a `CER-080` row and a `CER-087` row, both in the
  `## Do Later` section.
- INFRA-281's per-call resolution (`resolve_call_story`) and INFRA-255's
  containment contract are in `HEAD`. Every line number in this spec is an anchor
  from that state, not a coordinate — re-read each function before editing it.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command.

### A — idle-checkout tolerance (CER-080, enforcement half)

**A1. A staleness cutoff constant exists.** `scope_guard.py` defines
`STATE_STORY_MAX_AGE_HOURS: float = 24.0` at module level, next to
`RESOLVE_CALL_STORY_SOURCES`, with a comment giving the reason for the value: a
single story build never legitimately spans a day, and a stamp older than that is
far more likely to be an uncleaned checkout than an in-flight build.
(`spec-preflight` will warn that `STATE_STORY_MAX_AGE_HOURS` has no definition in
the source tree — intentional: this story creates it.)

**A2. A public freshness predicate exists.** `scope_guard.py` defines
`entry_is_fresh(entry: dict, now: "datetime | None" = None, max_age_hours: "float | None" = None) -> bool`.
It is public (no leading underscore) because `flex_build.py` calls it (C1). It:

- returns `False` when `entry` is not a dict, when `set_at` is absent, empty, or
  not a string, or when `datetime.fromisoformat` raises on it;
- treats a `set_at` with no timezone offset as UTC rather than raising;
- returns `True` when `set_at` is in the future (clock skew must not silently
  switch scope enforcement off — a forward-dated stamp is treated as fresh);
- returns `True` when the age is less than or equal to `max_age_hours` (defaulting
  to `STATE_STORY_MAX_AGE_HOURS`) and `False` when it is greater;
- never raises for any input.

**A3. `"stale"` is a first-class resolution source.**
`RESOLVE_CALL_STORY_SOURCES` gains the literal `"stale"`, and
`sorted(scope_guard.RESOLVE_CALL_STORY_SOURCES) == ["ambiguous", "none", "stale",
"state-legacy", "state-single", "worktree-cwd", "worktree-path"]`.

**A4. `_resolve_story_from_state` ages out stale entries.** Its resolution order
becomes, given `keyed = _read_current_stories_keyed(main)` and
`fresh = {k: v for k, v in keyed.items() if entry_is_fresh(v)}`:

- exactly one fresh entry → `(that_id, "state-single")`;
- two or more fresh entries → `(None, "ambiguous")` (unchanged refusal to guess);
- no fresh entries but `keyed` non-empty → `(None, "stale")`;
- `keyed` empty and the flat `current_story` names a story: fresh →
  `(id, "state-legacy")`, stale → `(None, "stale")`;
- nothing at all → `(None, "none")`.

Tests cover all five branches by asserting the returned `(story_id, source)`
tuple.

**A5. A worktree claim is never aged out.** `resolve_call_story` steps 1
(`worktree-cwd`) and 2 (`worktree-path`) do not consult `set_at` at all. A test
writes a `current_stories` entry with a `set_at` 30 days old, calls
`resolve_call_story` from that story's linked worktree cwd, and asserts
`(STORY_ID, "worktree-cwd")` — the worktree's existence is the claim (INFRA-280),
authoritative over the state file, and staleness applies only to the state
fallback.

**A6. A stale state resolves to no active story, fail-open for ordinary paths.**
`check_path` on a non-protected repo-relative path, against a project whose only
`current_stories` entry is 30 days old, returns `(True, reason)` where `reason`
contains the word `stale`, names the cutoff in hours, and names the remedy
(`flex_build.py clear-stale-stories`). It must not return the bare
`"no active story — allowing"` string — the operator needs to know *why* the
guard stood down.

**A7. A stale state stays fail-closed for protected paths.** `check_path` on
`hooks/pre_tool_use.py` against that same stale-state project returns
`(False, reason)` where `reason` contains `is a protected path`. A stale stamp
must never become a way to reach `PROTECTED_GLOBS` — ageing out a stamp removes
*authorization*, it does not grant any.

**A8. `_read_current_story` inherits the behaviour.** Because it wraps
`_resolve_story_from_state`, a stale-only state makes it return `None`. A test in
`TestReadCurrentStoryWrapper` asserts this.

**A9. Ambiguity still beats staleness where both apply.** With two entries, one
fresh and one stale, resolution is `state-single` on the fresh one (the stale one
is not counted). With two fresh entries it is `ambiguous`. With two stale entries
it is `stale`. Three tests, one per case.

**A10. No new I/O on the hook path.** The diff adds no file read, no file write,
no subprocess, and no network call to `check_path` or anything it calls. The only
new per-call work is a `datetime.fromisoformat` parse of a string already read
out of `state.json`. `grep -n 'open(\|read_text\|write_text\|subprocess' skills/pairmode/scripts/scope_guard.py`
returns no line that is not already present on `HEAD`.

### B — harness-owned out-of-root write allow-list (CER-087)

**B1. The allow-list is derived, not hardcoded to one machine.**
`scope_guard.py` defines
`harness_owned_prefixes(project: Path, raw_project_dir: "str | Path | None" = None, home: "Path | None" = None) -> list[Path]`
returning the resolved absolute prefixes that harness-owned out-of-root writes
are permitted under. For each of `project` and (when different) the resolved
`raw_project_dir`, with `key = str(p).replace("/", "-")` — the same derivation
`context_budget.py:140` already uses for the transcript directory — the list
contains:

- `<home>/.claude/projects/<key>/memory`
- `<tmp>/claude-<uid>/<key>` where `<tmp>` is `tempfile.gettempdir()` and `<uid>`
  is `os.getuid()` (the session scratchpad root)

plus, once, `<home>/.claude/plans`. Every entry is `.resolve()`-d. The function
never raises: any failure (no `os.getuid`, unresolvable home) drops that entry and
returns whatever else resolved.

**B2. The allow-list is deliberately narrow, and a test proves what it excludes.**
A test asserts `check_path` still returns `(False, "path escapes project root")`
for each of: `<home>/.claude/settings.json`, `<home>/.claude/CLAUDE.md`,
`<home>/.claude/policies/auth-rbac.md`, `<home>/.claude/plugins/x.json`,
`<home>/.claude/skills/x/SKILL.md`, `<home>/.claude/projects/<key>/<uuid>.jsonl`,
and `/etc/passwd`. The transcript exclusion is load-bearing and must be commented
as such: `subagent_transcript.py` derives the effort ledger from those `.jsonl`
files, so an agent that could write them could forge its own effort record.

**B3. The check runs after resolution, never before.** `scope_guard.py` defines
`_out_of_root_decision(file_path: "str | Path", project: Path, raw_project_dir: "str | Path | None") -> tuple[bool, str]`,
which resolves `file_path` to an absolute path with the same semantics
`_normalise` uses (`Path.resolve()`, non-strict, symlink-following, `..`
collapsed) and returns `(True, "harness-owned path outside project root — allowing: <prefix>")`
when the *resolved* path is `is_relative_to` one of B1's prefixes, and
`(False, "path escapes project root")` otherwise. A test asserts that a relative
traversal string that genuinely resolves into the memory directory is allowed
(there is nothing to forge — it lands where it lands) while a path string that
merely *contains* the prefix text but resolves elsewhere (e.g. a symlink under
the memory dir pointing at `/etc`) is denied.

**B4. `_normalise` is unchanged.** The containment function itself keeps its
signature, its docstring contract, and its `None` return for every out-of-root
input. `git diff` shows no change to `_normalise` or `_norm_str` beyond, at most,
a cross-reference comment. The allow-list is a decision layered *on top of* the
containment result, not a hole punched *in* it.

**B5. Both deny sites consult it.** Both
`return False, "path escapes project root"` sites in `check_path` (the no-story
branch and the active-story branch) are replaced by a call to
`_out_of_root_decision`. `grep -c '"path escapes project root"' skills/pairmode/scripts/scope_guard.py`
returns `1`, and that occurrence is inside `_out_of_root_decision`.

**B6. Harness-owned writes are allowed in every guard state.** A test
parametrised over `GUARD_STATES` (all five) asserts that a write to
`<home>/.claude/projects/<key>/memory/note.md` returns `(True, reason)` with
`harness-owned` in the reason — including mid-story with a populated
`allowed_paths` that does not list it. An out-of-repo harness path is not story
scope and is not scored against it.

**B7. Traversal denial survives unchanged.** The three existing
`GUARD_STATES`-parametrised traversal tests
(`test_relative_traversal_denied_in_every_guard_state`,
`test_dotslash_disguised_traversal_denied_in_every_guard_state`,
`test_absolute_out_of_root_denied_in_every_guard_state`) pass **by their original
names, with their original assertion strings**, against a `home` that is not the
real one. If satisfying B6 requires weakening any of these, the design is wrong —
stop and report `FAIL-CAUSE`.

**B8. Tests never depend on the developer's real home or `/tmp` contents.** Every
B-item test passes `home=tmp_path/"home"` through the seam and monkeypatches
`tempfile.gettempdir` / `os.getuid` as needed. `grep -n 'Path.home()' tests/pairmode/test_scope_guard.py`
returns nothing.

### C — stale-stamp reporting and clearing (CER-080, operator half)

**C1. A `clear-stale-stories` subcommand exists.** `flex_build.py` defines
`@flex_build.command("clear-stale-stories")` with options
`--project-dir` (default `.`, `dir_okay=True, file_okay=False`),
`--max-age-hours` (float, default `None` → `scope_guard.STATE_STORY_MAX_AGE_HOURS`),
and `--apply` (flag, default off). It imports `entry_is_fresh` and
`STATE_STORY_MAX_AGE_HOURS` from `scope_guard` rather than re-deriving the
staleness rule.

**C2. Report mode is the default and writes nothing.** Without `--apply`, the
command prints one `STALE <story_id> set_at=<ts> age=<n>h` line per stale entry
and exits 0, and `state.json` is byte-identical afterwards. A test asserts the
file's bytes are unchanged.

**C3. Clear mode removes only stale entries.** With `--apply`, each stale keyed
entry is removed via `story_context.clear_current_story(companion_dir, story_id)`
— the *scoped* mode, so a concurrently-building fresh story keeps its scope
enforcement — and one `CLEARED <story_id>` line is printed per removal. A test
with one fresh and one stale entry asserts the fresh entry survives with its
`set_at` intact and the stale one is gone.

**C4. A stale legacy-only stamp is cleared.** When `current_stories` is absent or
empty and the flat `current_story` is stale, `--apply` calls
`clear_current_story(companion_dir, None)` (clear-the-slate) and prints
`CLEARED <story_id>`. This is the literal CER-080 shape and must have its own
test.

**C5. A clean project produces no output.** With no stale entries — including the
no-`state.json`, no-`.companion`, and empty-state cases — the command prints
nothing and exits 0, with and without `--apply`.

**C6. It never raises and never exits non-zero.** A malformed `state.json`, a
non-dict `current_stories`, an entry with no `set_at`, and a missing project
directory each exit 0. Entries with an unparseable or absent `set_at` are
reported as stale (per A2) with `set_at=<none>` in the line.

**C7. `--max-age-hours` is honoured.** A test writes an entry 3 hours old and
asserts it is reported with `--max-age-hours 1` and not reported with
`--max-age-hours 48`.

**C8. flex's own state is verified clean.** Running
`clear-stale-stories --project-dir .` against this repo prints nothing. Record
that in the build result. No `.companion/state.json` edit appears in the diff —
`.companion/` is not a tracked build artifact of this story.

### D — documentation and CER rows

**D1. The scope_guard file-map line is updated.** `docs/architecture.md`'s
`scope_guard.py` entry (the § file-map line, anchor `:68`) gains both new
behaviours: the `STATE_STORY_MAX_AGE_HOURS` state-fallback cutoff with the
`stale` source, and the harness-owned out-of-root allow-list, each with its
story/CER reference (INFRA-271, CER-080/CER-087).

**D2. The input-normalisation contract records the allow-list.** The
**Input-normalisation contract (INFRA-255)** block (anchor `:639-660`) gains a
paragraph stating: the containment rule is unchanged; the allow-list is consulted
only *after* resolution, on the resolved path; the exact prefix set (B1); the
exclusions and why the transcript directory is one of them (B2); and that this is
an allow-list of *harness-owned* paths, not a relaxation of containment.

**D3. The story-resolution documentation records staleness.** The § 9.5
`resolve_call_story` documentation (anchor `:593-620`) and the `state.json`
`current_stories` key documentation (anchors `:1773`, `:1880`) state that the
state-file fallback ages out at `STATE_STORY_MAX_AGE_HOURS`, that a worktree
claim never does, and that a fully-stale state resolves to `(None, "stale")`
which is fail-open for ordinary paths and fail-closed for protected ones.

**D4. The CLI inventory lists the new subcommand.** `docs/architecture.md:56`'s
`flex_build.py` subcommand list includes `clear-stale-stories`.

**D5. The CER rows carry RESOLVED notes.** `docs/cer/backlog.md`'s `CER-080` and
`CER-087` rows each gain a bolded
`**RESOLVED Phase 105 — INFRA-271 …**` note appended to the Finding cell, and
each row's `Phase` cell reads `105` (CER-080's currently reads `98`; CER-087's
reads `—`). CER-080's note must state that the enforcement fix is the staleness
cutoff and the operator fix is `clear-stale-stories`, and that flex's own stamp
was already absent at build time. CER-087's note must name the allow-listed
prefixes and state explicitly that `_normalise`'s containment is unchanged. No
row is deleted or moved between quadrants. An overclaiming note is worse than an
open row.

**D6. No other file is touched.** The diff contains no change to
`hooks/pre_tool_use.py` (the hook is a thin dispatcher; the entire fix lives
behind `check_path`'s existing signature — and `hooks/**` is a `PROTECTED_GLOBS`
path this story deliberately does not need), no change to
`docs/harness-cutover-runbook.md` (RELEASE-062 owns it), and no change to
`bootstrap.py` or `fleet_discovery.py` (INFRA-269/INFRA-270 own them).

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build A, then B, then C, then D, running `tests/pairmode/test_scope_guard.py`
after A and after B — A changes the meaning of the fixture timestamps every other
test in that file depends on, and you want that isolated before B lands on top.

**0. Re-read before editing.** Read `check_path`, `resolve_call_story`,
`_resolve_story_from_state`, `_normalise` and `_read_current_story` as they exist
now. Every line number in this spec is an anchor, not a coordinate. Never revert
an INFRA-253/INFRA-255/INFRA-281 behaviour to make an assertion here easier to
satisfy; if a genuine conflict exists, stop and report `FAIL-CAUSE`.

**1. (A) Age out the state fallback.** Add
`from datetime import datetime, timezone` to `scope_guard.py` — stdlib only; this
module sits on the hook path and must stay import-light, so do not import
anything else. Define `STATE_STORY_MAX_AGE_HOURS` and `entry_is_fresh` per A1/A2,
then rewrite `_resolve_story_from_state`'s branch order per A4.

Two decisions must survive into the code as comments, because both are the sort a
later reader will "simplify" away:

- **A missing or unparseable `set_at` is stale, not fresh.** The whole point of
  CER-080 is a stamp that cannot be trusted; a stamp that cannot even be dated is
  strictly less trustworthy than one that can. This is safe because ageing out
  only ever *removes* authorization — protected paths stay fail-closed either way
  (A7).
- **A future `set_at` is fresh.** Clock skew between a hook process and whatever
  wrote the stamp must never silently switch scope enforcement off. Fail toward
  enforcement.

Do **not** touch `resolve_call_story`'s worktree steps. The staleness rule
belongs to the state fallback only, and adding it to the worktree branches would
break a long build (A5) for no gain — the worktree directory's existence on disk
is the claim.

In `check_path`'s no-story branch, handle `source == "stale"` alongside the
existing `source == "ambiguous"` note. Model it on the `ambiguous_note` shape
that is already there: build a note string, use it for both the protected-path
denial message and the fail-open allow reason, so the two can never describe the
state differently. The note must name the cutoff and the remedy command (A6).

**2. (A, tests) Repair the fixture timestamps first.**
`tests/pairmode/test_scope_guard.py:27`'s `_write_state` hardcodes
`set_at: "2026-01-01T00:00:00+00:00"`, and `:695-696` and
`tests/pairmode/test_pre_tool_use_scope_guard.py:243-244` do the same. Under A
those become stale, which silently converts roughly forty existing tests from
"active story" cases into "no active story" cases — they would still pass in some
cases, while no longer testing what their names claim.

Change every such fixture to stamp a *fresh* timestamp
(`datetime.now(timezone.utc).isoformat()`), preserving the relative ordering
where a test depends on it (the two-builder and ambiguity fixtures at `:695-696`
and `:243-244` need two distinct `set_at` values, both fresh — keep them one
second apart rather than one day). Add a dedicated helper for the new cases —
e.g. `_stale_iso(days: float)` returning
`(datetime.now(timezone.utc) - timedelta(days=days)).isoformat()` — and use it
only in the tests that mean to be stale. Do not add a stale variant to
`GUARD_STATES`: those five states exist to prove the traversal denial holds
across the guard's *authorization* states, and adding a sixth would change what
three security regression tests assert.

**3. (B) Layer the allow-list on top of containment.** Add `os` and `tempfile`
to `scope_guard.py`'s imports (stdlib, cheap). Implement
`harness_owned_prefixes` and `_out_of_root_decision` per B1/B3, then replace both
`return False, "path escapes project root"` sites with

```python
return _out_of_root_decision(file_path, project, project_dir)
```

passing the **raw** `project_dir` (the tool call's cwd) as well as the resolved
`project` — a session anchored in `/mnt/work/flex-harness` has harness-owned
paths keyed on `-mnt-work-flex-harness`, while `_resolve_main_project_root` has
already collapsed that to `/mnt/work/flex`. Both keys must be in the list, and
that reason must be in a comment.

Resolve the candidate path exactly the way `_normalise` does — `Path(file_path)`,
joined onto `project` when relative, then `.resolve()` — and compare with
`Path.is_relative_to`. Never compare strings: a `startswith` check on unresolved
text is the same class of mistake INFRA-255's docstring already warns about for
`..`, and it is what would let a symlink under an allow-listed prefix launder a
write to anywhere.

Keep the prefix list narrow (B2) and comment the two exclusions that look
arbitrary but are not: `~/.claude/projects/<key>/` is allow-listed **only** at
its `memory/` subdirectory, because the sibling `<session>.jsonl` transcripts are
what `subagent_transcript.py` derives the effort ledger from — an agent that can
write those can forge its own effort record; and nothing under `~/.claude/` other
than `plans/` and those `memory/` directories is listed, because `settings.json`,
`policies/`, `plugins/` and `skills/` are harness *configuration*, not harness
scratch state.

The `home` / `gettempdir` / `getuid` lookups must be injectable or
monkeypatchable so tests never touch the developer's real home (B8) — the `home`
parameter in B1's signature is there for exactly that.

**4. (C) Add the CLI.** Implement `clear-stale-stories` per C1–C7 next to the
other state-hygiene commands in `flex_build.py` (`clear-attempt-count` is the
closest neighbour in shape). Import the staleness rule from `scope_guard`; do not
re-derive it, or the CLI and the guard will disagree the first time the cutoff
changes. Use `story_context.clear_current_story` for every removal — it is the
sole writer of these keys (`docs/architecture.md:1773`) and it holds the advisory
state lock; a direct `state.json` write from this command would violate
single-writer ownership.

Prefer the scoped clear (C3) in every case except the legacy-only shape (C4),
where there is no keyed entry to scope to. Comment that asymmetry: the unscoped
clear is correct there precisely because there is nothing else in the slate to
protect.

Wrap the whole body so that no input can produce a non-zero exit (C6). This
command will be run across eight-plus fleet projects in a loop during the Phase
106 campaign; one malformed `state.json` must not abort the sweep.

**5. (D) Documentation and CER rows.** Apply D1–D5. Write the architecture
paragraphs to say *why* — the allow-list's narrowness and the staleness rule's
fail-open/fail-closed split are both decisions a future reader will otherwise
"tidy". Then update the two CER rows, being precise about what was and was not
done (D5).

**6. Ideology note (Step 4a — resolved inline, no conflict).** Three entries
shaped this spec. *"Hooks are thin relays only"* is why the entire fix lives in
`scope_guard.py` behind `check_path`'s existing signature, with no new I/O on the
hook path (A10) — the tempting alternatives (a hook-side allow-list config file
read, a "last seen active" heartbeat write) would each give the hook a new read
or a new state-write responsibility. *"Sidebar owns all state writes"* is why the
CLI clears through `story_context.clear_current_story` instead of writing
`state.json` itself, and why staleness is *derived* from the `set_at` the single
writer already stamps rather than tracked in a new field. *"Never silently pass
contradictions"* is why a stale state produces a reason string that names the
staleness and the remedy (A6) instead of quietly reusing
`"no active story — allowing"`: the operator must be able to tell "no story is
active" apart from "a story is stamped but I stopped believing it."

## Tests

Run from the story worktree root. After item A, and again after item B:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_scope_guard.py \
  tests/pairmode/test_pre_tool_use_scope_guard.py \
  -q 2>&1 | tail -30
```

After item C:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_flex_build_clear_stale_stories.py \
  tests/pairmode/test_story_context.py \
  tests/pairmode/test_state_utils.py \
  -q 2>&1 | tail -30
```

Then the adjacent state and hook surface, to catch collateral damage from the
fixture-timestamp change:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_context_budget.py \
  tests/pairmode/test_session_state.py \
  tests/pairmode/test_session_reset.py \
  tests/pairmode/test_sidebar_story_panel.py \
  tests/pairmode/test_record_attempt_companion.py \
  tests/pairmode/test_pairmode_sync.py \
  tests/pairmode/test_flex_build.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -40
```

Machine-checkable Ensures:

```bash
grep -c '"path escapes project root"' skills/pairmode/scripts/scope_guard.py   # must print 1 (B5)
grep -n 'STATE_STORY_MAX_AGE_HOURS' skills/pairmode/scripts/scope_guard.py     # must print (A1)
grep -n 'Path.home()' tests/pairmode/test_scope_guard.py                       # must print nothing (B8)
git diff --name-only main -- hooks/                                            # must print nothing (D6)
git diff --name-only main -- docs/harness-cutover-runbook.md                   # must print nothing (D6)
grep 'CER-080' docs/cer/backlog.md | grep -c 'RESOLVED Phase 105'              # must print 1 (D5)
grep 'CER-087' docs/cer/backlog.md | grep -c 'RESOLVED Phase 105'              # must print 1 (D5)
PATH=$HOME/.local/bin:$PATH uv run python \
  skills/pairmode/scripts/flex_build.py clear-stale-stories --project-dir .    # must print nothing, exit 0 (C8)
```

Acceptance:

- every new test from A1–A10, B1–B8, C1–C8 passes;
- the three `GUARD_STATES` traversal regression tests pass by their original
  names with their original assertion strings (B7);
- every pre-existing test in `test_scope_guard.py` and
  `test_pre_tool_use_scope_guard.py` passes by its original name — a fixture
  timestamp may change, a test name or assertion may not;
- verify by hand, once, before committing: revert `entry_is_fresh` to
  `return True` and confirm the A6/A7/A9 tests fail; revert
  `_out_of_root_decision` to the bare deny and confirm the B6 test fails. A
  staleness or allow-list test that passes against the old code is worthless;
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so in the build result.

## Out of scope

- **Relaxing `_normalise`'s containment.** The resolution-then-containment rule
  (INFRA-255) is unchanged; this story adds a decision layer above it (B4). Any
  design that makes `_normalise` return a repo-relative string for an out-of-root
  path is wrong.
- **An env-var-driven or config-file allow-list.** The prefixes are derived in
  code from the project root, the home directory and the temp directory. An
  allow-list an agent could extend by setting an environment variable or writing
  a file is not a boundary — it is a bypass with extra steps.
- **`hooks/pre_tool_use.py`.** The dispatcher already passes everything
  `check_path` needs (`file_path`, `cwd`); no hook change is required, and
  `hooks/**` is a protected path this story has no reason to enter (D6).
- **Fleet-wide execution of `clear-stale-stories`.** This story ships the
  command and proves it on fixtures plus flex itself. Running it across the
  registered projects is Phase 106's campaign work, and any runbook step naming
  it belongs to RELEASE-062, which owns that file.
- **`bootstrap.py` hook-registration dedupe (CER-081) and `fleet_discovery.py`
  Signal-1 accuracy (CER-058/CER-059).** INFRA-269 and INFRA-270 own those, and
  the phase doc's § Ordering places them first because they share
  `fleet_discovery.py`.
- **`context_budget` state hygiene (CER-040/CER-041).** INFRA-272's story. The
  only shared surface is `state.json`, and this story writes it exclusively
  through `story_context`'s existing locked writers.
- **A staleness cutoff for `.companion/attempt_counter.json`, `checkpoint_step`,
  or any other coordination state.** `current_stories` is the one whose staleness
  produces a *denial*; the others fail differently and would each need their own
  reversibility argument.
- **Making the cutoff configurable from `state.json`.** A module constant plus
  the CLI's `--max-age-hours` override is the proportionate surface; a
  per-project tunable for a value nobody has yet needed to tune is speculative
  configuration.
- **Backfilling `set_at` onto historical entries, or migrating the flat
  `current_story` mirror away.** The mirror's retirement is a separate concern
  with four documented readers (`docs/architecture.md:1773`); this story only
  ages it out.
- **A management UI.** No new persistent schema object is introduced
  (`schema_introduces: false`); the surfaces are the guard's block reason and the
  `clear-stale-stories` report.

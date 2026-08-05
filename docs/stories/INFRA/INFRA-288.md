---
id: INFRA-288
rail: INFRA
title: Attempt-row dedupe via agent_id idempotency key and merged-view duplicate-hook detection (CER-104)
status: complete
phase: "110"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/effort_recorder.py
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/hook_view.py
  - skills/pairmode/scripts/fleet_discovery.py
  - skills/pairmode/scripts/pairmode_sync.py
  - skills/pairmode/scripts/bootstrap.py
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_effort_concurrency.py
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_post_tool_use.py
  - tests/pairmode/test_hook_view.py
  - tests/pairmode/test_fleet_discovery.py
  - tests/pairmode/test_pairmode_sync.py
  - tests/pairmode/test_bootstrap.py
  - docs/stories/INFRA/INFRA-288.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 110 restores truthful effort recording end-to-end. INFRA-287 fixes *why no
row ever reconciles*; this story fixes *why every row exists twice*.

CER-104 (HIGH): Repo-B's first native 0.3.0 session after the RELEASE-063 canary
migration wrote perfect duplicate pairs — same `tool_use_id`, `decision=recorded`
logged twice 15–30 ms apart, for all 31 spawns of the day (rows 211–272). The
insert path is not doubled: `subagent_transcript.record_attempt_from_transcript`
runs once per hook invocation and inserts one row. The *hook* is doubled. A
migrated consumer project registers `post_tool_use.py` twice for the same event:

1. the project's own `.claude/settings.json` `PostToolUse` / `Task|Agent` block,
   written by `bootstrap._register_context_budget_hooks`
   (`CONTEXT_BUDGET_HOOK_SPECS`'s third entry) with an absolute
   `uv run python <plugin_root>/hooks/post_tool_use.py` command; and
2. the user-installed flex plugin's own `hooks/hooks.json`, whose `PostToolUse`
   `Task|Agent` block runs `${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py`.

flex's own sessions single-insert only because flex's `.claude/settings.json`
happens to carry no `PostToolUse` `Task|Agent` entry — which is exactly why the
defect was invisible on the repo that produces the fix.

The detection layer is structurally blind to this. INFRA-269's bootstrap dedupe,
`fleet_discovery._check_duplicate_hooks` (a *settings.json*-only read — see its
docstring and its `settings_path = project_dir / ".claude" / "settings.json"`
binding) and `pairmode_sync._audit_duplicate_hooks` (its declared twin, same
`{"event", "basename", "commands"}` shape) all group registrations *within one
settings.json*. A registration in `settings.local.json` or in a plugin's
`hooks.json` is not in their input at all, so fleet discovery reported **0
duplicate hooks** for a project where every effort row was doubled. The check
was not wrong about what it looked at; it looked at one third of the picture.

Two fixes, deliberately at both ends, because neither alone is sufficient:

- **(a) The recorder becomes idempotent.** `attempts.agent_id` is persisted today
  by `effort_db.set_spawn_ref` (INFRA-258) and **read by nothing** — a
  written-never-read column, one of the four data-flow smells this phase exists
  to close. It becomes the idempotency key: a second insert for a live pending
  `(agent_id, agent_role)` row *updates* that row instead of inserting a new one.
  This is defence in depth and it is bounded — it cannot help when the spawn's
  `tool_response` carries no recoverable agent id.
- **(b) Detection moves to a merged hook view.** Duplicate-hook detection and
  `audit-hooks` operate on the union of `.claude/settings.json`,
  `.claude/settings.local.json`, and every enabled plugin's `hooks.json`, with
  each entry carrying its source. The fleet rule follows: a project that gets
  `post_tool_use.py` from an installed plugin gets **no** settings-level
  `Task|Agent` `PostToolUse` entry.

Ordering: this story is independent of INFRA-287 (it touches neither
`_contained_spawn_output` nor the terminator predicate) and may land before or
alongside it. INFRA-289 owns attribution and the FAIL-escalation ladder and will
build on the deduped row; do not pre-empt it here.

## Requires

- **A clean `HEAD` on `main` containing Phase 109's merges.** Every line
  reference below is an anchor, not a coordinate — read the current bodies before
  editing.
- `skills/pairmode/scripts/effort_db.py` exposes `_INSERT_COLUMNS`,
  `_REQUIRED_FIELDS`, `_DERIVED_REQUIRED_FIELDS`, `insert_attempt`,
  `insert_attempt_derived(path, **fields) -> tuple[int, int]`, `set_spawn_ref`,
  `pending_reconcilable`, `_escape_like_prefix`, `_depth_guard`, `_connect`,
  `init_db`, `BUSY_TIMEOUT_SECONDS`, `BUSY_TIMEOUT_MS`, and `_MIGRATIONS`
  (which already contains `ALTER TABLE attempts ADD COLUMN agent_id TEXT`).
  The `attempts` table already has `agent_id TEXT` and `output_file TEXT`;
  **neither is in `_INSERT_COLUMNS`.**
- `skills/pairmode/scripts/effort_recorder.py` exposes the keyword-only
  `record_effort(...) -> int | None` with `attempt_number: "int | None" = 1`,
  where an explicit `None` routes to `insert_attempt_derived` (CER-096 item C).
- `skills/pairmode/scripts/subagent_transcript.py` exposes
  `record_attempt_from_transcript(...)`, `_extract_spawn_ref(tool_response) ->
  tuple[str | None, str | None]`, `log_recording_event(project_dir, **fields)`,
  `RECORDING_DECISIONS`, and `reconcile_pending_attempts(...)`.
- `skills/pairmode/scripts/fleet_discovery.py` exposes
  `_check_duplicate_hooks(project_dir) -> list[dict]` returning
  `{"event", "basename", "commands"}` dicts, surfaced at the scan's
  `"duplicate_hooks"` key.
- `skills/pairmode/scripts/pairmode_sync.py` exposes
  `_audit_duplicate_hooks(settings_path) -> list[dict]` (same shape),
  `_resolve_flex_root()`, and the `audit-hooks` click command with
  `--project-dir/--dry-run/--apply/--yes`.
- `skills/pairmode/scripts/bootstrap.py` exposes `CONTEXT_BUDGET_HOOK_SPECS`,
  `_register_context_budget_hooks`, `_register_pretooluse_hook`,
  `_find_block_by_command_basename`, and `_prune_stale_hook_entries`.
- `hooks/hooks.json` in this checkout registers `PostToolUse` `Task|Agent` →
  `${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py`.
- `docs/cer/backlog.md` contains a `CER-104` row whose `Phase` cell reads `—`.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command.

### A — `agent_id` becomes a real idempotency key

**A1. `agent_id` and `output_file` are insertable columns.**
`effort_db._INSERT_COLUMNS` contains `"agent_id"` and `"output_file"`. Neither is
added to `_REQUIRED_FIELDS` or `_DERIVED_REQUIRED_FIELDS`, so every existing
caller that omits them still writes `NULL`. `insert_attempt_derived`'s SELECT
list is still built by iterating `_INSERT_COLUMNS` (so the widening cannot
misalign `attempt_number`'s position), and a test asserts
`insert_attempt_derived(db, story_id="S", agent_role="builder", ts=<iso>,
agent_id="a-1")` writes `agent_id = "a-1"`.

**A2. A single deduping insert primitive exists.**
`effort_db.insert_or_update_attempt(path, *, dedupe_agent_id: "str | None" =
None, **fields) -> "tuple[int, int, bool]"` returns
`(row_id, attempt_number, deduped)`. It validates `story_id`/`agent_role`/`ts`
and rejects unknown keys and `attempt_number` with `ValueError`, exactly as
`insert_attempt_derived` does today.

**A3. `insert_attempt_derived` is preserved compatibly.** Its signature and its
`tuple[int, int]` return are unchanged; its body delegates to
`insert_or_update_attempt(..., dedupe_agent_id=None)` and drops the third
element. Every existing test in `tests/pairmode/test_effort_db.py` and
`tests/pairmode/test_effort_concurrency.py` passes **by its original name**.
(Era 003 DP4: the additive-until-flip contract forbids changing an existing
function or subcommand signature during the migration window.)

**A4. The dedupe lookup and the write share one transaction.** When
`dedupe_agent_id` is a non-empty string, `insert_or_update_attempt` opens the
same `BEGIN IMMEDIATE` transaction `insert_attempt_derived` uses today and runs
the match query *inside* it. The match predicate is:

```sql
SELECT id, attempt_number FROM attempts
 WHERE agent_id = ?
   AND agent_role = ?
   AND (tokens_total IS NULL OR outcome IS NULL)
   AND ts >= ?
 ORDER BY id ASC LIMIT 1
```

— every value bound as a parameter, never interpolated into the query text. The
`ts` bound is `now - AGENT_DEDUPE_WINDOW_SECONDS` in the same
`datetime.now(tz=timezone.utc).isoformat()` lexicographic form every writer
stamps. `effort_db.AGENT_DEDUPE_WINDOW_SECONDS == 300`.

**A5. A match updates rather than inserts, and never destroys data.** On a match
the row is updated with coalescing semantics: for every column in
`_INSERT_COLUMNS` except `attempt_number` and `story_id`, a supplied
**non-`None`** value overwrites and a supplied `None` leaves the existing value
untouched. `attempt_number` is never re-derived or changed on the update path;
`story_id` is never rewritten. The call returns `(matched_id,
existing_attempt_number, True)`. A test inserts a pending row with
`tokens_total=None, outcome=None, model="haiku"`, then calls
`insert_or_update_attempt` with the same `agent_id`/`agent_role` and
`model=None, outcome="PASS"`, and asserts the table holds exactly one row whose
`model == "haiku"` and `outcome == "PASS"`.

**A6. No match inserts, exactly as today.** With `dedupe_agent_id` falsy, or with
no matching row, behaviour is byte-for-byte `insert_attempt_derived`'s and the
third return element is `False`. A test asserts that two calls with the *same*
`agent_id` but *different* `agent_role` produce two rows, and that a second call
whose only candidate is already complete (`tokens_total` and `outcome` both
non-NULL) also produces two rows.

**A7. Concurrency: two racing writers produce one row.**
`tests/pairmode/test_effort_concurrency.py` gains a test that starts two
processes (or threads) calling `insert_or_update_attempt` with identical
`agent_id`/`agent_role`/`story_id` as close to simultaneously as the harness
allows, and asserts `SELECT COUNT(*) FROM attempts` is `1` and both calls
returned the same `row_id`. This is the assertion that matches CER-104's 15–30 ms
interval; a single-process test does not exercise it.

**A8. `record_effort` can carry the spawn ref and opt into dedupe.**
`effort_recorder.record_effort` gains keyword-only `agent_id: "str | None" =
None` and `output_file: "str | None" = None`. When `attempt_number is None`
**and** `agent_id` is a non-empty string it routes to
`insert_or_update_attempt(..., dedupe_agent_id=agent_id)`; otherwise its
behaviour and its `int | None` return are unchanged. `agent_id`/`output_file`
are passed through as ordinary column values in every case. No existing keyword
is renamed, reordered, or given a new default.

**A9. The hook path extracts the spawn ref *before* it writes.**
`subagent_transcript.record_attempt_from_transcript` calls
`_extract_spawn_ref(tool_response)` **above** its `record_effort(...)` call and
passes `agent_id=`/`output_file=` into it. The existing post-insert
`effort_db.set_spawn_ref` block is retained unchanged as the fallback for the
non-derived path — it rewrites the same values and is idempotent — and its
`if row_id is not None` / bare-`except` best-effort shape is preserved. A test
asserts that one Task PostToolUse payload whose `tool_response` carries an agent
id produces a row with `agent_id` set **without** relying on `set_spawn_ref`
(monkeypatch `set_spawn_ref` to raise; the row still carries `agent_id`).

**A10. The duplicate invocation is observable in the log.**
`subagent_transcript.RECORDING_DECISIONS` gains `"recorded:deduped"`. When the
write was deduped, `log_recording_event` is called with
`decision="recorded:deduped"` and the **matched** `row_id`; the first invocation
still logs `decision="recorded"`. A test drives the same payload twice and
asserts the two `.companion/effort_recording.log` lines read `recorded` then
`recorded:deduped` with the same `row_id`, and that `effort.db` holds one row.
`RECORDING_DECISIONS` remains the single declared vocabulary — no free-form
decision string is introduced.

**A11. Dedupe is best-effort and says so.** `insert_or_update_attempt`'s
docstring states that a `tool_response` with no recoverable agent id yields
`dedupe_agent_id=None` and therefore today's double row, and that the merged-view
hook fix (§ B) is the primary cure while the idempotency key is defence in depth.
Recording this rationale in the code is required, not optional — a later reader
must not conclude the recorder alone makes duplicates impossible.

### B — duplicate-hook detection reads the merged hook view

**B1. A shared hook-view module exists.** New
`skills/pairmode/scripts/hook_view.py`, stdlib-only (`json`, `os`, `pathlib`,
`typing` only — no click, no third-party import;
`grep -n '^import \|^from ' skills/pairmode/scripts/hook_view.py` shows nothing
outside the standard library). It is a *third* module that both
`fleet_discovery.py` and `pairmode_sync.py` may import, which is what resolves
`pairmode_sync.py`'s standing comment that a fleet-scanning module and a
per-project sync module must not depend on each other. Every public function is
total: malformed input returns the safe empty value, never raises.
(`spec-preflight` will report `hook_view`, `merged_hook_view`,
`duplicate_hook_groups`, `hook_sources`, `plugin_hook_files`,
`HOOK_SOURCE_SETTINGS`, `HOOK_SOURCE_SETTINGS_LOCAL`, `HOOK_SOURCE_PLUGIN` and
`FLEX_PLUGIN_HOOKS_ENV` as undefined — intentional; this story creates them.)

**B2. Source constants are named.** `hook_view.HOOK_SOURCE_SETTINGS ==
"settings"`, `HOOK_SOURCE_SETTINGS_LOCAL == "settings.local"`,
`HOOK_SOURCE_PLUGIN == "plugin"`.

**B3. `merged_hook_view` flattens every registration with its provenance.**
`hook_view.merged_hook_view(project_dir, *, home=None) -> list[dict]` returns one
dict per registered hook *entry*, in source order (`settings`, then
`settings.local`, then plugins), each with keys `event`, `matcher`
(`str | None`), `command`, `basename` (`command.rsplit("/", 1)[-1]` — the same
grouping key both existing detectors already use), `source`, and `path` (the file
the entry was read from, as a string). A missing, unparseable, or
malformed-shape file contributes nothing and is not an error.
`hook_view.hook_sources(project_dir, *, home=None)` returns the ordered
`{"source", "path"}` list the view was built from.

**B4. Plugin hook files are discovered tolerantly.**
`hook_view.plugin_hook_files(home=None) -> list[Path]` returns the plugin
`hooks/hooks.json` files visible to the given home directory: a bounded glob
(depth ≤ 6) under `<home>/.claude/plugins/`, plus every path listed in the
`FLEX_PLUGIN_HOOKS` environment variable
(`hook_view.FLEX_PLUGIN_HOOKS_ENV == "FLEX_PLUGIN_HOOKS"`, `os.pathsep`-separated
absolute paths). It returns `[]` — never raises, never scans outside `home` —
when the directory is absent or the layout is unrecognised. The module docstring
states plainly that Claude Code's plugin on-disk layout is **not a stable public
contract**, which is why discovery globs, degrades to today's settings-only view
on an unknown layout, and offers the env override as the escape hatch. A test
points `home` at a tmpdir containing `.claude/plugins/x/y/hooks/hooks.json` and
asserts it is found; another points `home` at an empty tmpdir and asserts `[]`.

**B5. `${CLAUDE_PLUGIN_ROOT}` commands are matched by basename, not by path.**
A plugin entry's command is recorded verbatim (including an unexpanded
`${CLAUDE_PLUGIN_ROOT}`), and grouping uses `basename`, so
`uv run python /mnt/work/flex/hooks/post_tool_use.py` and
`python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py` group together. A test
asserts exactly this pair is reported as one duplicate group. No environment
variable is expanded and no path is resolved — the view is a pure read.

**B6. `duplicate_hook_groups` reports cross-source duplicates.**
`hook_view.duplicate_hook_groups(view) -> list[dict]` returns one dict per
`(event, basename)` pair holding more than one entry, with keys `event`,
`basename`, `commands` (full command strings in view order — the existing
contract) and the new `sources` (the parallel list of source labels). The first
three keys and their meanings are unchanged from
`fleet_discovery._check_duplicate_hooks` /
`pairmode_sync._audit_duplicate_hooks`, so every existing consumer of that shape
keeps working.

**B7. Both existing detectors consume the shared view.**
`fleet_discovery._check_duplicate_hooks(project_dir)` is re-expressed as
`duplicate_hook_groups(merged_hook_view(project_dir))`; its signature, its
`list[dict]` return, its read-only discipline, and the `"duplicate_hooks"` scan
key are unchanged. `pairmode_sync._audit_duplicate_hooks(settings_path)` keeps
its signature (callers pass a settings path) and derives the project dir as
`settings_path.parent.parent` before delegating to the same pair. Both docstrings
are updated to state that the input is now the merged view and to name the
CER-104 blindness being fixed. A test asserts `_check_duplicate_hooks` reports
the settings-vs-plugin `post_tool_use.py` pair that pre-INFRA-288 code reported
as `[]`.

**B8. `audit-hooks` reports the source of each duplicate.** Its per-duplicate
output line gains the sources, e.g.
`DUPLICATE: event=PostToolUse basename=post_tool_use.py sources=['settings', 'plugin'] commands=[...]`.
The exit-code contract is unchanged: `0` when clean, `1` when duplicates are
found without `--apply`, `--dry-run` still the default.

**B9. `--apply` never writes another install's files.** When a duplicate group
spans sources, `audit-hooks --apply` removes the entry from
`.claude/settings.json` (and, if present, `.claude/settings.local.json`) and
**keeps** the plugin-sourced entry; it never edits any plugin `hooks.json`. When
every member of a group is settings-sourced, today's
keep-the-entry-under-the-plugin-root behaviour is preserved. A test with a
plugin-vs-settings duplicate asserts the plugin file is byte-for-byte unchanged
after `--apply` and the settings entry is gone.

**B10. Bootstrap stops creating the duplicate.**
`bootstrap._register_context_budget_hooks` skips registering a
`CONTEXT_BUDGET_HOOK_SPECS` entry when `hook_view.merged_hook_view` already
reports a **plugin-sourced** entry for that `(event, basename)` pair, and emits
one line naming the spec it skipped and why. Its by-command find/migrate
idempotency, its `_prune_stale_hook_entries` call, its
read-once/mutate/write-once shape, and `_register_pretooluse_hook` are otherwise
unchanged. A test runs the registrar twice against a project whose plugin
hooks.json already carries `PostToolUse` `Task|Agent` → `post_tool_use.py` and
asserts `.claude/settings.json` gains **no** `PostToolUse` block for that
basename, while `UserPromptSubmit` and `SessionStart` are still registered.

**B11. The fleet rule is written down.** `docs/architecture.md` gains at most two
short paragraphs, under an existing heading (no new `##`): that duplicate-hook
detection reads the merged view (settings + settings.local + enabled plugin
hooks.json) rather than settings.json alone, and the rule that a plugin-installed
project must carry **no** settings-level `Task|Agent` `PostToolUse` entry for a
hook the plugin already registers — with the reason (one registration per event
per script, because the recording path runs per invocation and a doubled
registration doubles every row).

### Cross-cutting

**C1. The CER row carries a RESOLVED note.** `docs/cer/backlog.md`'s `CER-104`
row gains a bolded `**RESOLVED Phase 110 — INFRA-288 …**` note appended to its
Finding cell, naming both ends of the fix, and its `Phase` cell reads `110`. The
row is not deleted or moved between quadrants. The note must state that the
idempotency key is best-effort (it requires a recoverable `agent_id`) and that
the merged-view detection is the primary cure — and must **not** claim CER-101 or
CER-102 are fixed here.

**C2. `schema_introduces` stays `false`.** No new table and no new column are
created: `agent_id` and `output_file` already exist on `attempts` via
`_MIGRATIONS`; this story only makes them insertable and read. No
management-surface row is owed in `docs/phases/phase-110.md` § Schema delivery,
and no new migration entry is added.

**C3. No legacy database or settings file breaks.** An `effort.db` written before
this story (rows with `agent_id` NULL) is read and swept unchanged; a project
with no `settings.local.json` and no plugin install produces a merged view
identical to today's settings-only view, and `_check_duplicate_hooks` returns
what it returned before. A test asserts the settings-only case explicitly.

**C4. Hooks stay thin relays.** No new file read, `open()`, network call, or
blocking wait is added to any file under `hooks/`. The dedupe happens inside the
database write the hook already performs, and the merged hook view is read only
by `fleet_discovery`, `pairmode_sync` and `bootstrap` — never on the hook path.
`git diff --stat hooks/` shows no change, or only the change A9 requires in the
call the hook already makes.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build A before B; they are independent, but A is the smaller surface and its
tests tell you quickly whether the effort-db plumbing is right.

**0. Recon.** Read the current bodies of `effort_db.insert_attempt_derived`,
`_INSERT_COLUMNS`, `_connect`, `effort_recorder.record_effort`,
`subagent_transcript.record_attempt_from_transcript` (the `record_effort` →
`set_spawn_ref` → `log_recording_event` tail),
`fleet_discovery._check_duplicate_hooks`, `pairmode_sync._audit_duplicate_hooks`
and `audit_hooks`, and `bootstrap._register_context_budget_hooks`. Every line
number in this spec is an anchor, not a coordinate. Do not revert anything
INFRA-280..286 built to make an assertion here easier to satisfy; if a genuine
conflict exists, stop and report `FAIL-CAUSE`.

**1. (A) Widen `_INSERT_COLUMNS`, then factor the insert.** Add `"agent_id"` and
`"output_file"` to `_INSERT_COLUMNS` only — not to either required-fields tuple.
Then extract today's `insert_attempt_derived` body into
`insert_or_update_attempt`, add the `dedupe_agent_id` keyword, and make
`insert_attempt_derived` a two-line delegation. Keeping the old function's exact
signature and return is not politeness: Era 003's DP4 additive-until-flip
contract makes a changed signature a breaking change for consumers still on the
0.2.x line, and this repo dogfoods its own recorder.

Run the match query **inside** the existing `BEGIN IMMEDIATE` transaction, not
before it. A SELECT outside the transaction is exactly the read-then-write race
CER-096 item C removed from the attempt-ordinal derivation, and re-introducing it
here would let the two hook processes 15–30 ms apart both miss and both insert.
The `ts >= ?` recency bound uses the same lexicographic ISO-8601 comparison
`pending_reconcilable` relies on; comment it with the same warning (a
differently-formatted `ts` silently breaks the bound).

`AGENT_DEDUPE_WINDOW_SECONDS = 300` is deliberately tight and must be commented
with its reason: the duplicate this defends against arrives milliseconds later,
so a wide window buys nothing and risks collapsing two genuinely distinct spawns
that happen to share a recycled agent id. Pair it with the
`(tokens_total IS NULL OR outcome IS NULL)` pending predicate — the same
predicate `pending_reconcilable` uses — so that CER-104's own question ("which of
the pair should the reconciliation sweep own?") has one answer by construction:
there is only one row, and it is the row the sweep already matches.

On the update path, build the `SET` list from `_INSERT_COLUMNS` minus
`attempt_number` and `story_id`, skipping any field whose supplied value is
`None`. Do **not** write `NULL` over an existing value — the second hook
invocation is not more authoritative than the first, and blanket-overwriting is
how a partially-reconciled row loses its tokens.

**2. (A) Thread the ref through `record_effort` and the hook path.** Add
`agent_id`/`output_file` keywords to `record_effort` after the existing ones, and
route to the deduping primitive only when `attempt_number is None` and `agent_id`
is truthy. `record_effort` must also report *whether* the write was deduped, and
a second return value would break its `int | None` contract — so express that
with a sibling `record_effort_ex(...) -> "tuple[int | None, bool]"` that holds
the logic, and make `record_effort` a delegation returning only the row id.
Whatever shape you choose, `record_effort`'s existing signature and return type
must not change (A8), and the reason for the split goes in its docstring.

In `record_attempt_from_transcript`, hoist the `_extract_spawn_ref` call above
`record_effort`. Keep the existing post-insert `set_spawn_ref` block: it is now
redundant on the derived path but is still the only writer on every other path,
and deleting it would trade one written-never-read column for a
required-never-written one. Add `"recorded:deduped"` to `RECORDING_DECISIONS` and
emit it from the **existing** `log_recording_event` call site — do not add a
second logging call.

**3. (B) Write `hook_view.py` first; both detectors then shrink.** Implement
`HOOK_SOURCE_*`, `FLEX_PLUGIN_HOOKS_ENV`, `hook_sources`, `plugin_hook_files`,
`merged_hook_view`, and `duplicate_hook_groups`. Reuse the existing traversal
shape from `_audit_duplicate_hooks` (`hooks` → event → block list → block `hooks`
→ entry `command`), including its isinstance guard at every level — a hand-edited
settings file with a malformed shape must be treated as absent, not crash a fleet
scan.

The `basename` grouping key is deliberately retained rather than "improved" to a
resolved path: `${CLAUDE_PLUGIN_ROOT}` is unexpanded in a plugin's hooks.json
while the settings entry holds an absolute path, so resolving paths would make
the two *stop* matching — which is the precise blindness this story exists to
remove (B5). Say so in a comment.

`plugin_hook_files`'s tolerance is the load-bearing property, not its accuracy:
the plugin layout is an implementation detail of the harness, so an unrecognised
layout must degrade to "no plugin sources found" — i.e. exactly today's
settings-only behaviour — and must never raise inside a fleet scan or a bootstrap
run. Bound the glob depth and never follow a path outside `home`.

**4. (B) Rewire the two detectors and `audit-hooks`.** Re-express
`fleet_discovery._check_duplicate_hooks` and
`pairmode_sync._audit_duplicate_hooks` as thin wrappers over the shared pair,
keeping both signatures. Update `pairmode_sync.py`'s "deliberately not imported
from/into fleet_discovery.py" comment to record that the shared logic now lives
in `hook_view.py` — the original reasoning (a fleet module and a per-project
module must not depend on each other) still holds and is *why* the third module
exists, so amend the comment rather than deleting it.

For `--apply` (B9): the plugin-sourced entry always wins, because flex must never
write into another install's files and because the plugin registration is the one
that survives a re-bootstrap. Removing an entry from `settings.local.json`
requires reading and writing that file too — keep the same read-once/write-once,
`json.dumps(..., indent=2) + "\n"` shape the existing writers use, and do not
touch any key outside `hooks`.

**5. (B) Bootstrap.** Add the plugin-sourced skip to
`_register_context_budget_hooks` per B10. Import `hook_view` at module level (it
is stdlib-only and cheap). If the merged view cannot be computed for any reason,
register as today — a bootstrap that failed closed here would leave a project
with *no* recording hook, which is strictly worse than a duplicated one.

**6. Tests.** New `tests/pairmode/test_hook_view.py` (B2–B6, C3). Extend
`test_effort_db.py` (A1–A6), `test_effort_concurrency.py` (A7),
`test_subagent_transcript.py` (A9, A10), `test_post_tool_use.py` (A10, C4),
`test_fleet_discovery.py` (B7), `test_pairmode_sync.py` (B8, B9) and
`test_bootstrap.py` (B10). Follow each file's existing fixture style; build hook
fixtures as tmpdir trees with a fake `home`, never against the real `~/.claude/`.
Delete no test.

**7. Docs and CER row.** Write B11's architecture paragraphs and C1's RESOLVED
note. The note must not overclaim: the idempotency key needs a recoverable
`agent_id`, and CER-101/CER-102 belong to INFRA-287/INFRA-289, not to this story.

**8. Ideology note (Step 4a — resolved inline, no conflict).** Three entries
shaped this spec. *"Hooks are thin relays only"* (no override permitted) is why
C4 forbids any new read or blocking wait on the hook path: the dedupe rides
inside the database write the hook already performs, and the merged hook view —
which does touch the filesystem — is read only by CLI and fleet code. *"Sidebar
owns all state writes"* (no override permitted) is respected by not widening the
grandfathered hook-writer surface; the hooks that write today are exactly the
hooks that write after this story. *"Rationale-bearing decisions over bare
rules"* is why four reasons must survive into the code as comments rather than
living only here: why the dedupe window is 300 s and not larger, why the match
must sit inside the transaction, why grouping is by basename and not by resolved
path, and why an unknown plugin layout degrades instead of failing.

## Tests

Run from the story worktree root. After each item:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_effort_concurrency.py \
  tests/pairmode/test_hook_view.py \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_post_tool_use.py \
  tests/pairmode/test_fleet_discovery.py \
  tests/pairmode/test_pairmode_sync.py \
  tests/pairmode/test_bootstrap.py \
  -q 2>&1 | tail -30
```

Then the adjacent surface, to catch collateral damage from the `_INSERT_COLUMNS`
widening and the detector rewiring:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_post_tool_use_hook.py \
  tests/pairmode/test_pairmode_effort.py \
  tests/pairmode/test_effort_guardrail.py \
  tests/pairmode/test_refresh_effort_baseline.py \
  tests/pairmode/test_sync.py \
  tests/pairmode/test_sync_agents.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
grep -n '"agent_id"\|"output_file"' skills/pairmode/scripts/effort_db.py   # both in _INSERT_COLUMNS
grep -n 'AGENT_DEDUPE_WINDOW_SECONDS = 300' skills/pairmode/scripts/effort_db.py
grep -n 'recorded:deduped' skills/pairmode/scripts/subagent_transcript.py  # in RECORDING_DECISIONS
grep -n '^import \|^from ' skills/pairmode/scripts/hook_view.py            # stdlib only
grep -ln 'hook_view' skills/pairmode/scripts/fleet_discovery.py \
                     skills/pairmode/scripts/pairmode_sync.py \
                     skills/pairmode/scripts/bootstrap.py                  # all three consume it
git diff --stat hooks/                                                     # no new hook-path I/O
grep -n 'CER-104' docs/cer/backlog.md | grep -c 'RESOLVED Phase 110'       # must print 1
```

Acceptance:

- every new test from A1–A11, B2–B11, C3, C4 passes;
- every pre-existing test in the eight primary test files passes **by its
  original name** — especially `test_effort_db.py` and
  `test_effort_concurrency.py`, whose subject function is refactored rather than
  extended;
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so explicitly in the build
  result.

## Out of scope

- **Everything CER-101 / INFRA-287 owns.** `_contained_spawn_output`'s symlink
  containment, the `end_turn` terminator predicate, the
  `classify_pending_reason` / sweep predicate split, and the `uncontained`
  pending reason. This story must not touch `read_completed_spawn` or the
  containment helpers; doing so would collide with INFRA-287's diff. The dedupe
  is deliberately designed to leave exactly one row matching
  `pending_reconcilable`'s existing predicate, so INFRA-287's fix lands on it
  unchanged.
- **Everything CER-102 / CER-103 / INFRA-289 owns.** Target-project attribution
  (`project_dir = Path(data.get("cwd") or ".")`), strict `_derive_phase_key`
  parsing, the reconcile-time FAIL bump and the escalation ladder, and the NULL
  `attempts.model` on reviewer rows.
- **Backfilling or de-duplicating rows already written.** The 31 doubled Repo-B
  pairs (rows 211–272) and any flex equivalents stay as they are; a historical
  cleanup is a separate, operator-gated story. This fix is forward-only.
- **A cross-process lock around the recorder.** The `BEGIN IMMEDIATE` transaction
  plus SQLite's `busy_timeout` is the whole concurrency mechanism (CER-096's
  settled design); no new lock file, mutex, or daemon.
- **Expanding `${CLAUDE_PLUGIN_ROOT}` or otherwise resolving hook command paths.**
  The merged view is a pure read; resolution would break the basename grouping
  that makes cross-source duplicates visible at all (B5).
- **Editing, disabling, or installing plugins.** `audit-hooks --apply` never
  writes a plugin's `hooks.json`, and nothing here manages plugin enablement.
- **Acting on duplicates in other hook events as a fleet action.** The merged view
  reports every event; anything beyond the `post_tool_use.py` `Task|Agent` case is
  left to the operator running `audit-hooks`.
- **INFRA-290's hygiene work.** Dead state keys, stale `attempt_counter.json`
  shapes, stranded `docs/phases/permissions/*.json` artifacts, and the
  cold-eyes-procedure data-flow checks.

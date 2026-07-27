---
id: INFRA-281
rail: INFRA
title: Story-keyed current_story and scope_guard resolution; merge/discard clear only their own key (CER-095.2)
status: draft
phase: "109"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_context.py
  - skills/pairmode/scripts/scope_guard.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - hooks/pre_tool_use.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_story_context.py
  - tests/pairmode/test_scope_guard.py
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_pre_tool_use_scope_guard.py
  - docs/stories/INFRA/INFRA-281.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-280 made the resolver willing to *name* a second story while the first is
building. This story is the other half of the enabling pair: it makes it safe to
actually *build* two stories at once, by removing the single global slot that
decides whose file-scope rules apply to a write.

**The defect (CER-095 item 2).** `state.json["current_story"]` is one slot holding
one story dict. `create-story-worktree` stamps it (`flex_build._stamp_active_story`
→ `story_context.set_current_story`), and `scope_guard._read_current_story` reads
it on every `Edit`/`Write` to decide (a) which story's permissions artifact to
load and (b) whether a `.pairmode-worktrees/<segment>/` prefix may be stripped
from the candidate path. With two builders in flight the slot holds whichever
story was stamped last, so **builder A's writes are evaluated against builder B's
allow-list**: every write is denied, and the denial is misattributed to the wrong
story in the reason string. Worse, both teardown commands clear the slot
unconditionally — `cmd_merge_story_worktree` and `cmd_discard_story_worktree` both
call `_clear_active_story(project_path)`, which calls
`story_context.clear_current_story(companion_dir)` with no story argument. So the
moment story A lands, story B's stamp disappears and B's still-running builder
falls through to the `not story_id` branch: **story-scope enforcement is silently
switched off mid-build** for a builder that is still writing. Protected paths still
fail closed there (INFRA-253), but every non-protected path becomes "no active
story — allowing".

**The fix is to stop asking a global question.** A single shared slot cannot answer
"which story is this write for?" once more than one story is in flight, and no
amount of care in *writing* the slot fixes a read that is ambiguous by
construction. The correct answer is already carried by the call itself: a builder's
tool calls come from **its own worktree** (`.pairmode-worktrees/<ID>/`), which is
the same claim INFRA-280 taught the resolver to read. So `scope_guard` resolves the
story **per call**, from the cwd (and, failing that, from the target path), and
only falls back to `state.json` when the call demonstrably comes from the main
checkout. `state.json` itself becomes story-keyed (`current_stories`), so the
fallback can at least say "exactly one story is in flight, it must be that one" —
and, crucially, can say "more than one is in flight and this call came from
nowhere in particular" instead of guessing.

**Never guess is the load-bearing rule here.** The ambiguous case — main-checkout
cwd, non-worktree target path, two or more stories claimed — resolves to *no story*,
which means fail-open for ordinary paths and fail-closed for `PROTECTED_GLOBS`,
exactly the semantics that already apply to orchestrator work between stories. It
does **not** resolve to "pick the most recent". `docs/ideology.md` § "Never silently
pass contradictions" makes false confidence worse than no answer, and a wrongly
attributed *allow* on a protected path is the failure this whole gate exists to
prevent.

**Why `current_story` survives as a mirror.** Five readers outside this story's
scope consume the flat key: `hooks/session_start.py:114`, `global_session_check`,
`skills/observability/api/src/routes/context.ts:172`, `skills/companion/SKILL.md`'s
documented schema, and `subagent_transcript._story_accepts_late_bump` (INFRA-264,
E9). Era 003's additive-until-flip contract
(`docs/eras/003-flex-orchestrator-as-harness.md` § Versioning) says the CLI and
state surfaces stay backward-compatible until `HARNESS006`'s flip, and INFRA-264's
E9 explicitly recorded the forward-compatibility requirement that its logic must
survive this conversion "aside from a mechanical accessor swap". So
`current_stories` becomes the authority and `current_story` is maintained as a
derived mirror of one of its entries. `context_story_tokens` (INFRA-180) is the
existing precedent for a story-keyed dict living in the same file.

This story is CER-095 **item (2) only**. The keyed attempt counter is INFRA-282,
keyed checkpoint state is INFRA-283, and the concurrent read-modify-write hazard on
`state.json` itself is INFRA-285. Nothing here adds a lock.

## Recon

Verified by reading the files at HEAD; line numbers are anchors for the builder,
not assertions to preserve.

| Anchor | What is there now |
|---|---|
| `story_context.py:57` `set_current_story` | builds `{"id", "set_at", optional "title"}` and assigns it to `state["current_story"]`, then `write_state` (atomic via `state_utils._atomic_write_json`). |
| `story_context.py:87` `clear_current_story(companion_dir)` | `state.pop("current_story", None)` — no story argument exists. Deliberately retains `context_current_tokens*`. |
| `story_context.py:103` `get_current_story` | returns `state.get("current_story")`. |
| `story_context.py:219` CLI `--clear` | operator-facing; calls `clear_current_story(companion_dir)` and prints `Story cleared.` |
| `flex_build.py:69` `_stamp_active_story` | reads story frontmatter for the title, `mkdir` `.companion/`, calls `set_current_story`. |
| `flex_build.py:84` `_clear_active_story(project_path)` | no story argument; silent no-op when `.companion/` is absent; swallows exceptions. |
| `flex_build.py:2935` / `:2986` | the two `_clear_active_story(project_path)` call sites, in `cmd_merge_story_worktree` and `cmd_discard_story_worktree`. Both already know their `story_id`. `clear_permissions_artifact(story_id, ...)` next to each is *already* story-scoped — the asymmetry is the bug. |
| `flex_build.py:198` `claimed_story_ids` | INFRA-280's claim reader over `.pairmode-worktrees/`; `_worktree_paths` (186) is the single home of the path convention; `_STORY_ID_RE` (105) is `^[A-Z][A-Z0-9_]*-\d{3}$`. |
| `scope_guard.py:34` `check_path` | `_resolve_main_project_root(project_dir)` → `_read_current_story(project)` → early `not story_id` branch → `_normalise` → `_strip_worktree_prefix(normalised, story_id)` → `_read_allowed_paths(project, story_id)` → three-way `missing`/`malformed`/`ok`. |
| `scope_guard.py:105` `_resolve_main_project_root` | maps a linked-worktree root back to the main checkout by parsing the `.git` pointer file (`gitdir: <main>/.git/worktrees/<name>`); returns *project* unchanged when it is not a linked worktree. **It discards the worktree identity it just computed** — that identity is what this story needs. |
| `scope_guard.py:140` `_read_current_story(project)` | `state["current_story"]["id"]`, `except Exception: return None`. Imported by `hooks/pre_tool_use.py:90`. |
| `scope_guard.py:174` `_strip_worktree_prefix(path, active_story_id)` | strips `.pairmode-worktrees/<segment>/` only when `segment == active_story_id`. Its docstring already names the concurrent-story hazard — the guarantee is correct, the input is not. |
| `hooks/pre_tool_use.py:79` `_resolve_flex_factor` | imports `scope_guard._read_current_story`, fails open to `1.0` on any error. Called with `data["cwd"]`, which for a `Task`/`Agent` spawn is the **orchestrator's** cwd (the main checkout), not a worktree. |
| `docs/architecture.md:266-283` | § Permission pre-write, the INFRA-238 stamp/clear paragraph and the `_strip_worktree_prefix` paragraph. |
| `docs/architecture.md:481` | § 9.5 Story file-scope enforcement — names `state.json["current_story"]["id"]` as the lookup. |
| `docs/architecture.md:1577` | state-ownership table row: `active story (state.json current_story) | orchestrator (story_context.py) | read-only`. |
| `docs/architecture.md:1647-1664` | the `state.json` schema block and field list. |

## Requires

- **INFRA-280 is merged.** `flex_build.claimed_story_ids(project_dir) -> set[str]`
  exists, immediately after `_worktree_paths`, and `docs/architecture.md` §
  Pairmode build loop contains the **Worktree as in-flight claim (CER-095.1,
  INFRA-280)** paragraph. This story's fallback rules and its architecture edits
  both reference that claim contract. If INFRA-280 has not landed, rebase onto it
  first rather than reimplementing the claim reader.
- `skills/pairmode/scripts/story_context.py` exposes `read_state`, `write_state`,
  `set_current_story`, `clear_current_story`, `get_current_story`, and the
  `click` CLI with `--set` / `--get` / `--clear`.
- `skills/pairmode/scripts/scope_guard.py` exposes `check_path`,
  `_resolve_main_project_root`, `_read_current_story`, `_read_allowed_paths`,
  `_strip_worktree_prefix`, `_normalise`, `PROTECTED_GLOBS`, `_is_protected`.
- `skills/pairmode/scripts/flex_build.py` exposes `_stamp_active_story`,
  `_clear_active_story`, `cmd_create_story_worktree`, `cmd_merge_story_worktree`,
  `cmd_discard_story_worktree`, `_worktree_paths`, `_STORY_ID_RE`.
- `docs/cer/backlog.md` contains a `CER-095` row whose `Phase` cell reads `109`
  and which already carries INFRA-280's item-(1) resolution note.
- `hooks/pre_tool_use.py` is a **protected path** (`PROTECTED_GLOBS` includes
  `hooks/**`), so it is only writable because it is declared in this story's
  `touches` and therefore present in `docs/phases/permissions/INFRA-281.json`.
  Do not attempt to edit it before `create-story-worktree` has generated that
  artifact from this frontmatter.
- Known environmental failure inside fresh story worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story.

## Ensures

Numbered assertions; the reviewer verifies each independently from the diff and
the test run.

**B1. `state.json` carries a story-keyed record of active stories.**
`story_context.set_current_story(companion_dir, story_id, title=None)` keeps its
existing signature and return type (the updated state dict) and additionally
writes `state["current_stories"][story_id] = {"id", "set_at", optional "title"}` —
the same entry shape it already builds. Stamping a second story leaves the first
story's entry **present and byte-identical** (same `set_at`, same `title`). The
key name is `current_stories`.

**B2. `current_story` is maintained as a derived mirror.** After
`set_current_story`, `state["current_story"]` equals the entry just written, so
every existing reader of the flat key (`hooks/session_start.py`,
`global_session_check`, `skills/observability/api/src/routes/context.ts`,
`subagent_transcript._story_accepts_late_bump`) continues to see a well-formed
dict. `get_current_story` is unchanged in signature and still returns that flat
entry. A new `story_context.get_current_stories(companion_dir) -> dict[str, dict]`
returns the keyed dict, or `{}` when the key is absent.

**B3. A clear scoped to one story leaves the others alone.**
`clear_current_story(companion_dir, story_id: str | None = None)`:
- with `story_id` — removes **only** `current_stories[story_id]`; every other
  entry survives byte-identical; when the removed story was the one mirrored in
  `current_story`, the mirror is re-pointed to the remaining entry with the
  latest `set_at` (ties broken by story ID, ascending, so the result is
  deterministic), and removed entirely only when no entries remain; when the
  removed story was *not* the mirrored one, `current_story` is unchanged;
- with `story_id=None` (the legacy operator path) — clears `current_stories`
  entirely **and** removes `current_story`, i.e. exactly today's "clear the
  slate" behaviour;
- in both cases `context_current_tokens` and
  `context_current_tokens_recorded_at` are retained (the INFRA-170 guarantee),
  and the function still returns the updated state dict.

**B4. Reading tolerates a pre-INFRA-281 `state.json`.** For a state file that has
`current_story` but no `current_stories` key, `get_current_stories` returns a
single-entry dict derived from the flat key, so a project mid-migration is never
seen as having zero active stories. For a state file with neither key it returns
`{}`. Neither read writes to disk (asserted by an mtime/bytes check).

**B5. `scope_guard` resolves the story per call, from the call itself.** A new
public function
`scope_guard.resolve_call_story(project_dir, file_path=None) -> tuple[str | None, str]`
returns `(story_id, source)` where `source` is one of the literals
`worktree-cwd`, `worktree-path`, `state-single`, `state-legacy`, `ambiguous`,
`none`, defined as a module-level tuple/frozenset so tests can enumerate them.
Resolution order is exactly:

1. `worktree-cwd` — the passed `project_dir` is, or is inside,
   `<main>/.pairmode-worktrees/<ID>/` with `<ID>` matching `_STORY_ID_RE`;
2. `worktree-path` — otherwise, the repo-relative target path begins with
   `.pairmode-worktrees/<ID>/` with `<ID>` matching `_STORY_ID_RE`;
3. `state-single` — otherwise, `current_stories` holds **exactly one** entry;
4. `state-legacy` — otherwise, `current_stories` is absent/empty and the flat
   `current_story` names a story;
5. `ambiguous` — otherwise, `current_stories` holds two or more entries →
   `story_id is None`;
6. `none` — no signal at all → `story_id is None`.

The function performs **no writes**, never raises (any exception resolves to
`(None, "none")`), and does not require the resolved story to appear in
`current_stories`: the worktree *is* the claim (INFRA-280), and a worktree-derived
ID is authoritative over the state file, not subordinate to it.

**B6. The ambiguous case is treated as no active story, never as a guess.** With
two entries in `current_stories`, a call whose cwd is the main checkout and whose
target path is not under any worktree is evaluated by `check_path` exactly as the
existing no-active-story branch: a non-protected path returns
`(True, ...)` and a `PROTECTED_GLOBS` path returns `(False, ...)`. The returned
reason for the ambiguous case names the condition and the claimed story IDs — the
substring `ambiguous` and each claimed ID appear in it — so an operator reading a
denial can tell "two builds in flight" apart from "no build in flight". No code
path selects the newest, the first, or the alphabetically-first story when more
than one is active.

**B7. Two builders in two worktrees are scoped independently — the phase-109
checkpoint-proves scenario.** With permissions artifacts on disk for both `A-001`
(`allowed_paths: ["a.py"]`) and `B-002` (`allowed_paths: ["b.py"]`) and both
stamped in `current_stories`:
- `check_path("a.py", <main>/.pairmode-worktrees/A-001)` → allowed;
- `check_path("b.py", <main>/.pairmode-worktrees/A-001)` → denied, reason naming
  `A-001`;
- `check_path("b.py", <main>/.pairmode-worktrees/B-002)` → allowed;
- `check_path("a.py", <main>/.pairmode-worktrees/B-002)` → denied, reason naming
  `B-002`.
The stamping order does not affect any of the four results (asserted by a test
that runs the set twice, stamping in each order).

**B8. Merge and discard clear only their own key.** `flex_build._clear_active_story`
takes the story ID (`_clear_active_story(project_path, story_id)`) and both call
sites — `cmd_merge_story_worktree` and `cmd_discard_story_worktree` — pass their
own `--story-id`. After `create-story-worktree` for `A-001` and `B-002` followed
by `merge-story-worktree --story-id A-001`, `current_stories` contains `B-002`
and not `A-001`, and `check_path` from `B-002`'s worktree still resolves `B-002`
and still enforces its allow-list. The same holds with
`discard-story-worktree --story-id A-001` in place of the merge. `_clear_active_story`
keeps its existing never-raises / no-op-when-`.companion/`-absent contract.

**B9. The mid-build enforcement gap is closed, and a test pins it.** A regression
test named for CER-095.2 asserts that after `merge-story-worktree --story-id A-001`,
a write from `B-002`'s worktree to a path **not** in `B-002`'s allow-list is
**denied**. On the pre-fix code this write is allowed with reason
`no active story — allowing`; that string must not appear in the result.

**B10. `_read_current_story` keeps working and gains the keyed semantics.**
`scope_guard._read_current_story(project)` retains its signature and its
never-raises contract, and is now a thin wrapper over `resolve_call_story`'s
state-only rules (`state-single` → the single ID, `state-legacy` → the flat ID,
`ambiguous`/`none` → `None`). `hooks/pre_tool_use.py:90`'s import keeps resolving.

**B11. The context-budget gate resolves flex_factor without guessing.**
`hooks/pre_tool_use._resolve_flex_factor(project_dir)` calls
`scope_guard.resolve_call_story(project_dir)` instead of `_read_current_story`,
takes the resolved ID when there is one, and returns the documented `1.0`
fail-open default when the resolution is `ambiguous` or `none`. The hook gains
**no** file reads, **no** JSON parsing, and **no** writes of its own — the net
change to `hooks/pre_tool_use.py` is the swapped import, the swapped call, and a
comment recording that under parallel dispatch an orchestrator-cwd spawn resolves
ambiguously and therefore uses the pre-INFRA-160 default rather than another
story's factor (`docs/ideology.md` § "Hooks are thin relays only", no override
permitted). The change is under 15 lines.

**B12. Nothing in this story takes a lock or adds a second claim record.** No lock
file, no PID, no TTL, no new file under `.companion/`. `grep -c 'pairmode-worktrees'
skills/pairmode/scripts/story_context.py` prints `0` — `story_context.py` knows
nothing about worktrees; the worktree convention stays owned by `flex_build.py`
(`_worktree_paths`, `claimed_story_ids`) and is consumed by `scope_guard.py`
through its own already-present `_WORKTREE_PREFIX` constant and
`_resolve_main_project_root`, with no new literal spelling of the path added
anywhere.

**B13. Architecture records the new state shape and resolution order.**
`docs/architecture.md` is updated in place, adding **no** `##`-level heading:
(a) the `state.json` schema block (~line 1647) and its field list gain
`current_stories` — keyed by story ID, entries identical in shape to
`current_story`, with `current_story` documented as a **derived mirror kept for
backward compatibility** and the named readers that depend on it;
(b) the state-ownership table row `active story (state.json current_story)`
(~line 1577) becomes a `current_stories` row naming `story_context.py` as sole
writer, recording that `create-story-worktree` adds a key and
`merge`/`discard-story-worktree` remove **only their own**, and that the flat
mirror is derived, never independently written;
(c) § 9.5 (~line 481) replaces "reads `state.json["current_story"]["id"]`" with
the six-step `resolve_call_story` order, stating that the ambiguous case is
treated as no-active-story, and **why** — a wrong attribution would grant one
story's allow-list to another story's write, which is worse than the fail-open /
protected-fail-closed behaviour that already covers orchestrator work;
(d) the § Permission pre-write paragraphs (~lines 266-283) record that the
INFRA-238 stamp/clear pair is now story-scoped on both ends, and that
`_strip_worktree_prefix`'s per-story guarantee is now fed the per-call resolved
story rather than a global slot — its docstring's concurrent-story hazard was a
prediction, and this story is where it became reachable.
Every one of these edits carries its reason, not just its rule
(`docs/ideology.md` § "rationale-bearing decisions over bare rules").

**B14. CER-095 is annotated, not closed.** The `CER-095` row in
`docs/cer/backlog.md` gains an `**INFRA-281 (Phase 109) — item (2) resolved:**`
note describing the keyed `current_stories` record, the per-call
`resolve_call_story` order, and the story-scoped clear, and explicitly recording
that items (3) and (4) remain open under INFRA-282/INFRA-283. The row is not
deleted, not moved, and its status is not flipped to resolved
(`docs/cer/backlog.md:6`). Its `Phase` cell still reads `109`.

**B15. No new persistent schema object.** `current_stories` is a key inside the
existing `.companion/state.json`, not a table, collection, or migration.
`schema_introduces: false` stands and phase 109's § Schema delivery table stays
empty. It is operator-manageable through the existing
`story_context.py --get/--set/--clear` CLI, which continues to work unchanged.

**B16. The suite is green.** `uv run pytest tests/pairmode/` passes, except the
known CER-090 worktree-environmental failure named in `## Requires`. Every
pre-existing test in `tests/pairmode/test_story_context.py`,
`tests/pairmode/test_scope_guard.py` and
`tests/pairmode/test_pre_tool_use_scope_guard.py` passes **unmodified** — the flat
`current_story` assertions in `test_story_context.py` (e.g.
`test_writes_current_story_with_id`, `test_removes_current_story_when_present`,
`test_overwrites_previous_current_story`) are exactly the backward-compatibility
contract B2/B3 promises, and none of them may be weakened or deleted.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Do not create a git tag, do not push, and run no command against
`/mnt/work/flex-harness`. Do not touch `.companion/attempt_counter.json`, the
`checkpoint_step`/`checkpoint_phase` keys, `next_story.py`, or `next_action.py` —
those are INFRA-282, INFRA-283 and INFRA-280 respectively.

1. **`story_context.py` — the keyed record** (B1–B4). Add a module-level
   `CURRENT_STORIES_KEY = "current_stories"` rather than repeating the literal.
   In `set_current_story`, build the entry exactly as today, then write it to
   **both** `state[CURRENT_STORIES_KEY][story_id]` and `state["current_story"]`
   in the one `write_state` call — one atomic write, two views of the same entry,
   so the mirror can never diverge from the keyed record by a partial write.
   Add `get_current_stories(companion_dir) -> dict[str, dict]` with the
   legacy-derivation rule from B4. Docstrings must say *why* the flat key
   survives: it is a compatibility mirror for readers outside this story's scope,
   listed by name, and it is derived — never written independently.

2. **`clear_current_story` — scoped and unscoped** (B3). Add
   `story_id: str | None = None` as the second parameter (keeping
   `companion_dir` first, so the two existing positional call sites keep
   working). Scoped: `pop` the one key, then recompute the mirror from the
   remaining entries — latest `set_at`, ties broken by ascending story ID, so the
   result is deterministic and does not depend on dict ordering; remove the
   mirror only when nothing remains. Unscoped: clear both keys, as today.
   Preserve the `context_current_tokens*` retention and its existing docstring
   paragraph verbatim (INFRA-170 — that guarantee is not this story's to
   revisit). The CLI `--clear` branch stays on the unscoped call: an operator
   asking to clear the slate means the slate.

3. **`scope_guard.resolve_call_story`** (B5). Place it immediately after
   `_resolve_main_project_root`, whose worktree parsing it extends. Reuse that
   function to find the main root, then derive the worktree segment from the
   *relationship* between the passed `project_dir` and the resolved main root
   (`project_dir.resolve().relative_to(main)`, first two segments) — do **not**
   re-parse the `.git` pointer file and do **not** add a second spelling of
   `.pairmode-worktrees`; the module already has `_WORKTREE_PREFIX`. Validate the
   segment against a story-ID regex; copy the pattern text from
   `flex_build._STORY_ID_RE` with a comment naming it as the source of truth
   rather than importing `flex_build` — this module is on the `pre_tool_use` hook
   path and must stay import-light (`flex_build` pulls in `click`, `effort_db`,
   `next_action` and more). Return the `(story_id, source)` tuple; wrap the whole
   body so no exception escapes.

4. **Rewire `check_path`** (B6, B7). Replace the `_read_current_story(project)`
   call with `resolve_call_story(project_dir, file_path)` — note it takes the
   **raw** `project_dir` argument, before `_resolve_main_project_root` collapses
   it, because the worktree identity is precisely what that collapse discards.
   Keep every downstream branch structurally as it is: the `not story_id` early
   branch, `_normalise`, `_strip_worktree_prefix(normalised, story_id)`,
   `_read_allowed_paths`, and the three-way `missing`/`malformed`/`ok` handling
   are all correct once the story ID is right, and rewriting them would put
   INFRA-253's fail-closed protected-path work at risk for no gain. The only
   behavioural addition is the reason string for `source == "ambiguous"` (B6),
   which must name the claimed IDs. Do not change `PROTECTED_GLOBS` or
   `_is_protected`.

5. **Keep `_read_current_story`** (B10) as a thin wrapper over the state-only
   half of `resolve_call_story`, with a docstring saying it exists for
   `hooks/pre_tool_use.py`'s import and returns `None` rather than a guess when
   two stories are active. Do not delete it and do not change its signature.

6. **`flex_build.py` — scope the clear** (B8). Change `_clear_active_story` to
   `_clear_active_story(project_path: Path, story_id: str) -> None` and pass
   `story_id` through to `clear_current_story`. Update both call sites in
   `cmd_merge_story_worktree` and `cmd_discard_story_worktree`, and update the
   INFRA-238 comment above each: the clear is now story-scoped, and the reason is
   that an unconditional clear disables scope enforcement for a *different*
   builder that is still running. `_stamp_active_story` needs no change — B1 puts
   the additive behaviour inside `set_current_story`, which keeps
   `create-story-worktree` free of any knowledge of the state layout. Make no
   other edit to `flex_build.py`; it is the file INFRA-282/283/284/286 also touch,
   and a wide diff here becomes a rebase conflict for all of them.

7. **`hooks/pre_tool_use.py`** (B11). Swap the lazy
   `from scope_guard import _read_current_story` for
   `from scope_guard import resolve_call_story`, unpack the tuple, keep the
   `if not story_id: return 1.0` shape, and add the comment required by B11. The
   hook must gain no logic beyond that — the resolution lives in the skill
   script, per `docs/ideology.md` § "Hooks are thin relays only" (no override
   permitted). Nothing else in this file changes.

8. **Tests.**
   - `tests/pairmode/test_story_context.py` — B1 (second stamp preserves the
     first entry byte-identically), B2 (mirror equals the latest entry;
     `get_current_stories` shape), B3 (all three clear cases, including the
     deterministic re-point and the tie-break, and the
     `context_current_tokens*` retention), B4 (legacy-state derivation, and a
     no-write assertion on both readers). Do **not** edit the existing cases.
   - `tests/pairmode/test_scope_guard.py` — B5 (one case per `source` literal,
     including a nested path inside a worktree and a non-matching segment name),
     B6 (ambiguous → non-protected allowed, protected denied, reason contains
     `ambiguous` and both IDs), B7 (the four-way matrix, run under both stamping
     orders), B10 (wrapper behaviour).
   - `tests/pairmode/test_flex_build.py` — extend the existing
     `create/merge/discard-story-worktree (INFRA-224)` class, which already has
     `_git`/`_commit_in` helpers and a real git tmp project: B8 (create A + B →
     merge A → `current_stories` holds only B; same for discard) and B9 (the
     CER-095.2 regression, named for it, asserting the denial and the absence of
     the `no active story — allowing` reason).
   - `tests/pairmode/test_pre_tool_use_scope_guard.py` — B11 (flex_factor
     resolves from a worktree cwd; returns `1.0` when two stories are active and
     the cwd is the main checkout).
   - B12's greps are assertions for the reviewer; state them in the build result.

9. **Docs** — apply B13 to `docs/architecture.md` and B14 to
   `docs/cer/backlog.md` (append to the existing CER-095 Finding cell alongside
   INFRA-280's note; leave the row in place and its `Phase` cell at `109`).

10. **Ideology note (Step 4a — resolved inline, no conflict).** Three entries in
    `docs/ideology.md` shaped this spec. *"Never silently pass contradictions"*
    (no silent bypass permitted) is the whole of B6: the tempting implementation
    picks the most recently stamped story and is right most of the time, and the
    times it is wrong are exactly the times a builder is writing outside its
    declared scope — the constraint's rationale is that false confidence is worse
    than no answer, so the ambiguous case degrades to the already-understood
    no-active-story semantics instead. *"Hooks are thin relays only"* (no override
    permitted) is why B11 confines the hook to an import swap and pushes all
    resolution into `scope_guard.py`, and why `story_context.py` — not the hook —
    owns every state write. *"Sidebar owns all state writes"* (no override
    permitted) is why `scope_guard.resolve_call_story` is a pure read that never
    repairs, prunes, or normalises what it finds: a reader that tidied a stale
    `current_stories` entry would become a second writer of build state, which is
    the same argument INFRA-280 used to refuse auto-pruning stale worktrees. The
    *"Python everywhere"* fingerprint is unaffected — no new language, no new
    dependency, stdlib only.

## Tests

Run from the story worktree root. Targeted first:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_story_context.py \
  tests/pairmode/test_scope_guard.py \
  tests/pairmode/test_pre_tool_use_scope_guard.py \
  tests/pairmode/test_pre_tool_use_hook.py \
  tests/pairmode/test_flex_build.py \
  tests/pairmode/test_flex_build_check_story_scope.py \
  tests/pairmode/test_session_start_hook.py \
  tests/pairmode/test_global_session_check.py -q 2>&1 | tail -30
```

Then the full suite, **without `-x`** so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable assertions the reviewer may run directly:

```bash
grep -c 'pairmode-worktrees' skills/pairmode/scripts/story_context.py  # must print 0
grep -c 'current_stories' skills/pairmode/scripts/story_context.py     # must be >= 1
grep -c 'resolve_call_story' skills/pairmode/scripts/scope_guard.py    # must be >= 2
grep -c '_read_current_story' hooks/pre_tool_use.py                    # must print 0
git diff --stat -- hooks/pre_tool_use.py                               # under 15 changed lines
```

Acceptance:

- every new test from `## Instructions` step 8 passes, in particular B7's
  four-way matrix under both stamping orders and B9's named CER-095.2 regression;
- the pre-existing cases in `test_story_context.py`, `test_scope_guard.py` and
  `test_pre_tool_use_scope_guard.py` pass **unmodified** (B16);
- `test_flex_build_check_story_scope.py` and `test_session_start_hook.py` still
  pass — the flat-key readers must not notice this change;
- the full suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if
  it appears, state that it reproduces on clean `HEAD` and is unrelated.

Documentation-only assertions (B13, B14) are verified by the reviewer from the
diff.

Note for `spec-preflight`: `current_stories`, `resolve_call_story`,
`get_current_stories`, `CURRENT_STORIES_KEY` and the source literals
`worktree-cwd` / `worktree-path` / `state-single` / `state-legacy` / `ambiguous`
do not exist in the codebase yet — they are created by this story, and any
preflight finding naming them is expected. The scan also emits
`Route warning: '/api/src/routes/context'` — a false positive from the file path
`skills/observability/api/src/routes/context.ts`, which does exist on disk (it
reads `state.json['current_story']` at line 172) and is not an API route
reference.

## Out of scope

- **CER-095 items (3) and (4)** — the story-keyed attempt counter (INFRA-282) and
  phase-keyed checkpoint state (INFRA-283). `.companion/attempt_counter.json`,
  `state.json["checkpoint_step"]` and `state.json["checkpoint_phase"]` are not
  touched here. Note for INFRA-282: `subagent_transcript._story_accepts_late_bump`
  (INFRA-264 E9) reads the flat `current_story`, which B2 keeps well-formed, so it
  keeps working through this story and gets its mechanical accessor swap in
  INFRA-282 as that story's E9 note anticipated.
- **Concurrent read-modify-write on `state.json`.** Two `set_current_story` calls
  racing can still lose one entry: each does read → mutate → atomic replace, and
  atomicity of the *write* is not atomicity of the *sequence*. That is CER-097 /
  INFRA-285 (advisory state lock, atomic state writers) by the phase's own
  ordering. This story removes the *semantic* single slot; it does not serialise
  writers, and no lock, lease, or PID file is added.
- **The resolver.** `next_story.py` and `next_action.py` are untouched. The
  resolver reads the worktree claim (INFRA-280), never `current_story`; nothing
  here changes what `next-action` returns.
- **The build loop's prose.** `CLAUDE.build.md` and
  `skills/pairmode/templates/CLAUDE.build.md.j2` keep their serial phrasing and
  their INFRA-238 comments; rewriting them is INFRA-286, deliberately last
  (`docs/phases/phase-109.md` § Ordering). Editing the template here would also
  churn `tests/pairmode/test_templates.py` drift assertions for no delivered
  capability.
- **Per-spawn `flex_factor` under parallel dispatch.** B11 makes the gate honest
  (default `1.0` when the resolution is ambiguous) rather than accurate. Making it
  accurate needs the spawn's story ID out of the `Task`/`Agent` `tool_input`,
  which is a change to what the orchestrator passes at spawn time — a separate
  finding, not a defect fix. Do not smuggle it in via a "most recent story" read.
- **Stale-entry expiry.** A `current_stories` entry left by a crashed loop
  persists until the operator runs `discard-story-worktree` or
  `story_context.py --clear`, exactly as a stale worktree does. INFRA-271
  (phase 105) owns stale-`current_story` clearing; a reader that self-healed here
  would be a second writer of build state.
- **The observability SPA/API.** `skills/observability/api/src/routes/context.ts`
  keeps reading the flat mirror and keeps working; rendering multiple active
  stories is Phase G's surface.
- **The companion sidebar's story prompt.** `skills/companion/SKILL.md` documents
  `set_current_story` and the `current_story` schema; both remain accurate under
  B2, so the skill doc is not edited. Teaching the sidebar to display several
  active stories is not this story's job.
- **Fleet rollout.** No sibling project is synced with the new state key.

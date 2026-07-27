---
id: INFRA-280
rail: INFRA
title: "Resolver in-flight claim: next-action skips stories with a live worktree, claim semantics documented (CER-095.1)"
status: draft
phase: "109"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_story.py
  - skills/pairmode/scripts/next_action.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_next_story.py
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_flex_build.py
  - docs/stories/INFRA/INFRA-280.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 109 restores **one orchestrator, parallel story builds**. The first thing
that blocks it is that the resolver has no idea a story is already being built.

`find_next_story` (`skills/pairmode/scripts/next_story.py`) walks the phase doc's
`## Stories` table in order and returns the first story with no matching git
commit and a non-`deferred`/`skipped` status. Nothing in that walk consults
`.pairmode-worktrees/`. A story's build only becomes visible to the resolver when
its `story-<ID>` commit lands on the main branch — and that commit only exists
*after* `merge-story-worktree` runs. So while story A is in flight, every
`next-action` poll keeps returning A: the loop can never be told about B, which
is exactly why parallel dispatch is impossible today.

**The claim already exists; the resolver just doesn't read it.**
`create-story-worktree` (`flex_build.py cmd_create_story_worktree`) creates
`.pairmode-worktrees/<ID>/` on branch `pairmode/<ID>` and **fails loudly (exit 1)
if either already exists — it never silently reuses one**. That is a de-facto
atomic claim, taken at the exact moment a story enters its build cycle and
released at exactly the two points a cycle can end: `merge-story-worktree` (PASS)
and `discard-story-worktree` (FAIL), both of which remove the directory and delete
the branch. This story makes the resolver read that claim and skip claimed
stories. It adds no new state, no new file, no lock — deliberately: a second
claim record would immediately be a second source of truth about which stories are
in flight, and the whole of CER-095 is a story about single-slot state disagreeing
with reality.

**The dangerous edge is not "no story" — it is "no story, therefore checkpoint".**
`resolve_next_action` treats `next_story_id is None` as *the phase is finished*
and routes into the checkpoint sequence (Row 9), whose terminal step tags the
phase and flips its index row to `complete`. If claim-filtering simply made
claimed stories vanish, a phase whose last two stories were both in flight would
present as complete and the loop would happily checkpoint a phase that is still
building. That is the CER-077 class of failure — an irreversible write derived
from an ambiguous read — and the ideology constraint *"never silently pass
contradictions"* says the resolver must stop and say so rather than pick the
interpretation that lets it proceed. Hence the two-pass design in
`## Instructions` step 3 and the `all-stories-claimed` await-user row: "every
remaining story is claimed" is a distinct, named, operator-visible state, never a
synonym for done.

**Why filtering is opt-in rather than baked into `find_next_story`.**
`flex_build.resolve_current_phase` also calls `find_next_story` — in its
no-index fallback scan, purely to answer "does this phase file still have an
unbuilt story?". If claim-filtering were unconditional, a phase whose only
remaining story was in flight would answer "no" there and the fallback would walk
on to a different phase. The claim is a fact about *dispatch*, not about
*completion*, so only the dispatch path passes `claimed`. This also keeps the
existing call signature working unchanged, per era 003's additive-until-flip
contract (`docs/eras/003-flex-orchestrator-as-harness.md` § Versioning).

**What "documented" means in the title.** The claim has never been written down as
a contract — it is an implementation detail of INFRA-224's worktree isolation that
this story promotes to a load-bearing coordination primitive. `docs/architecture.md`
must state where the claim is taken, where it is released, that the resolver reads
it, the ordering rule that makes it sound (the worktree must be created before the
next poll), and how an operator clears a stale claim left by a crashed loop.
Without that, the first agent to see `next-action` "skip" a story will assume a bug.

This story is CER-095 **item (1) only**. Items (2), (3) and (4) — story-keyed
`current_story`/`scope_guard`, the keyed attempt counter, and keyed checkpoint
state — are INFRA-281, INFRA-282 and INFRA-283. Nothing here is sufficient to
*run* two builders in parallel; it is the half that makes the resolver willing to
name a second story.

## Requires

- `skills/pairmode/scripts/next_story.py` exposes, at the line numbers current at
  spec time: `_SKIP_STATUSES` (~199), `_parse_stories_table_statuses` (~202),
  `_has_story_commit` (~139), `_git_log_oneline`, and
  `find_next_story(phase_file, project_dir)` (~170) returning a dict with keys
  `story_id`, `story_file`, `git_verified`, or `None`.
- `skills/pairmode/scripts/flex_build.py` exposes `_worktree_paths(story_id,
  project_dir)` (186) — the single definition of the
  `.pairmode-worktrees/<story-id>/` + `pairmode/<story-id>` convention —
  `_STORY_ID_RE` (105, `^[A-Z][A-Z0-9_]*-\d{3}$`), `cmd_create_story_worktree`
  (2769), `cmd_merge_story_worktree` (2840), `cmd_discard_story_worktree` (2910),
  `resolve_current_phase` (whose no-index fallback calls `find_next_story`), and
  `cmd_resolver_state` (2319), which serialises the whole `infer_position` dict.
- `skills/pairmode/scripts/next_action.py` exposes `infer_position` (~600, calling
  `find_next_story` at ~702) and `resolve_next_action` (~930), whose Row 9 branch
  (`if next_story_id is None:`) enters the checkpoint sequence.
- `docs/cer/backlog.md` contains a `CER-095` row whose `Phase` cell reads `109`.
- `docs/architecture.md` § Pairmode build loop contains the **Per-story worktree
  isolation (Phase 96, INFRA-223/INFRA-224)** and **One-iteration-per-story
  contract (CER-074)** paragraphs (~lines 168–200).
- No sibling phase-109 story is required first. INFRA-280 and INFRA-281 are the
  enabling pair and may build in either order
  (`docs/phases/phase-109.md` § Ordering); they touch different functions in
  `flex_build.py`, so a rebase conflict there is not expected. Rebase on the
  current branch tip before starting.
- Known environmental failure inside fresh story worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story.

## Ensures

**A1. A single claim-reading helper exists, next to the convention it reads.**
`flex_build.py` defines `claimed_story_ids(project_dir: Path) -> set[str]`,
declared immediately after `_worktree_paths`, returning the name of every
immediate subdirectory of `<project_dir>/.pairmode-worktrees/` that matches
`_STORY_ID_RE`. It writes nothing, spawns no subprocess, and returns an empty set
when the directory does not exist. Non-matching entries (`tmp`, `.DS_Store`, a
regular file named `INFRA-999`) are excluded.

**A2. The claim tracks the real worktree lifecycle.** For a git project on disk:
after `create-story-worktree --story-id WT-001`, `claimed_story_ids` contains
`WT-001`; after `merge-story-worktree --story-id WT-001` it does not; and in a
second project, after `create-story-worktree --story-id WT-002` followed by
`discard-story-worktree --story-id WT-002`, it does not.

**A3. `find_next_story` gains an opt-in claim filter and its default behaviour is
byte-for-byte the old behaviour.** The signature becomes
`find_next_story(phase_file, project_dir, *, claimed: set[str] | None = None)`.
Called with no `claimed` argument — as `flex_build.resolve_current_phase`'s
no-index fallback does — it returns exactly what it returns today; every existing
test in `tests/pairmode/test_next_story.py` passes **unmodified**.

**A4. Claimed stories are skipped, and the skip is reported.** With
`claimed={"A"}` over a table `A, B` where neither has a commit,
`find_next_story` returns `story_id == "B"`. The returned dict always carries a
`claimed_skipped` key: `["A"]` in that case, `[]` when nothing was skipped. The
existing `story_id` / `story_file` / `git_verified` keys are unchanged in name and
meaning.

**A5. A claim never overrides a commit or a skip status.** Ordering inside the
walk is unchanged: a story with a matching git commit is passed over as complete
before the claim is consulted, and `deferred`/`skipped` statuses still exclude a
story regardless of whether it is claimed. A claimed story ID that does not appear
in the phase's `## Stories` table has no effect on the result.

**A6. `infer_position` reports the claim set.** The Position dict gains three
keys, present on **every** call (including when `active_phase_file is None`):

- `claimed_stories: list[str]` — sorted output of `claimed_story_ids`.
- `claimed_skipped: list[str]` — claimed story IDs skipped while selecting the
  returned story, or (in the A7 case) every remaining claimed story.
- `all_stories_claimed: bool`.

All three are JSON-serialisable, so `flex_build.py resolver-state --json` emits
them under `position` with no change to `cmd_resolver_state`.

**A7. "All remaining stories are claimed" is distinguished from "phase complete".**
When the claim-filtered pass yields no story but an unfiltered pass over the same
phase file does, `infer_position` sets `all_stories_claimed = True`,
`next_story_id = None`, and `claimed_skipped` to the remaining claimed IDs. When
the phase genuinely has no unbuilt story, `all_stories_claimed` is `False`. The
second (unfiltered) pass runs **only** when the first pass returned `None` and
`claimed_stories` is non-empty.

**A8. The resolver refuses to checkpoint a phase that is still building.**
`resolve_next_action` returns
`action == "await-user"`, `scalar == ""`, `model is None`,
`reason == "all-stories-claimed"`, and `meta["claimed_stories"]` equal to the
position's `claimed_stories`, whenever `next_story_id is None` **and**
`all_stories_claimed` is true. This branch is evaluated **before** the Row 9
checkpoint branch, so for such a position `resolve_next_action` never returns
`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`, `checkpoint-tag`
or `done`, and `check_checkpoint_guards` is not called.

**A9. Consecutive polls offer different stories — the phase-109 checkpoint-proves
scenario.** A test builds a project with a two-story phase (`A`, `B`, both
uncommitted), asserts `resolve_next_action(infer_position(dir))` offers `A`, then
creates `.pairmode-worktrees/A/` and asserts the next
`resolve_next_action(infer_position(dir))` offers `B` with
`meta["claimed_skipped"] == ["A"]`. With `.pairmode-worktrees/B/` also present,
the third call returns `await-user` / `all-stories-claimed`.

**A10. Claim skips are visible on the emitted action.** When a spawn action is
emitted (`spawn-builder`, `spawn-spec-writer`, `spawn-gate-worker`,
`spawn-loop-breaker`) and the position's `claimed_skipped` is non-empty, the
action's `meta` contains `claimed_skipped` with that list. When it is empty, the
`meta` key is absent — an action for a phase with nothing in flight looks exactly
as it does today.

**A11. The worktree-path convention is not duplicated into the resolver.**
`grep -c 'pairmode-worktrees' skills/pairmode/scripts/next_story.py` prints `0`
and the same command against `skills/pairmode/scripts/next_action.py` prints `0`.
`next_story.find_next_story` never imports `flex_build`; the caller supplies
`claimed`. `next_action.infer_position` obtains it via the lazy
`from flex_build import ...` block it already uses.

**A12. Nothing in this story writes.** `next_story.py` and `next_action.py`
perform no filesystem writes, and `claimed_story_ids` neither creates
`.pairmode-worktrees/` nor prunes a stale entry. The resolver reports a stale
claim; clearing it is the operator's explicit `discard-story-worktree`.

**A13. Architecture records the claim contract.** `docs/architecture.md` §
Pairmode build loop gains a paragraph — **Worktree as in-flight claim (CER-095.1,
INFRA-280)** — placed after the existing *Per-story worktree isolation* paragraph,
stating all of:
(a) the claim is taken by `create-story-worktree` and released by
`merge-story-worktree` / `discard-story-worktree`, and is the *only* in-flight
record — there is no second claim file;
(b) `next-action` skips claimed stories, so a single orchestrator can dispatch a
second story while the first builds;
(c) the ordering rule that makes it sound: **the worktree must be created before
the next `next-action` poll**, because the poll is what selects the story and the
worktree is what claims it — a poll before the claim can hand out the same story
twice;
(d) all-remaining-claimed emits `await-user` / `all-stories-claimed` and never a
checkpoint, with the reason (an irreversible mark-complete derived from an
ambiguous read is the CER-077 failure mode);
(e) stale-claim recovery: a worktree left by a crashed loop hides its story
indefinitely; the operator clears it with `discard-story-worktree --story-id <ID>`,
and the resolver deliberately does not self-heal, because a writer that prunes
worktrees would be a second owner of build state.
The existing *One-iteration-per-story contract (CER-074)* paragraph gains one
clause noting that "one poll per story" is one poll per story **dispatch**, and
that the no-re-poll-before-merge rule is unaffected by claim filtering (a re-poll
mid-story now returns a *different* story rather than the same one, which is worse,
not better). No `##`-level heading is added or removed from `docs/architecture.md`.

**A14. CER-095 is annotated, not closed.** The `CER-095` row in
`docs/cer/backlog.md` gains a `**INFRA-280 (Phase 109) — item (1) resolved:**`
note describing the claim-reading filter and the `all-stories-claimed` await-user
state, and explicitly recording that items (2), (3) and (4) remain open under
INFRA-281/282/283. The row is not deleted, not moved, and its status is not
flipped to resolved (`docs/cer/backlog.md:6` — "Findings are not deleted —
resolved findings remain in place with a resolution note"). Its `Phase` cell
still reads `109`.

**A15. The suite is green.** `uv run pytest tests/pairmode/` passes, except the
known CER-090 worktree-environmental failure named in `## Requires`.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Do not create a git tag, do not push, and run no command against
`/mnt/work/flex-harness`.

1. **Add `claimed_story_ids` to `flex_build.py`**, immediately after
   `_worktree_paths` (line ~196) so the `.pairmode-worktrees` literal keeps a
   single home. Signature `claimed_story_ids(project_dir: Path) -> set[str]`.
   Derive the directory from the same relative path `_worktree_paths` uses —
   introduce a module-level constant if that reads better, but do not add a
   second string literal. Iterate `iterdir()`, keep entries that `is_dir()` and
   whose `.name` matches `_STORY_ID_RE`, return the set. Return an empty set if
   the directory is absent or unreadable. Docstring must state: the claim is
   established by `create-story-worktree` and released by
   `merge-story-worktree`/`discard-story-worktree`; a leftover
   `pairmode/<ID>` branch with no directory is deliberately **not** treated as a
   claim, because `create-story-worktree` already refuses to run against an
   existing branch with its own clear error — duplicating that check here would
   make the resolver hide a story for a condition the claim-taking command
   already reports.

2. **Add the opt-in filter to `next_story.find_next_story`.** New keyword-only
   parameter `claimed: set[str] | None = None`. Inside the loop, after the
   commit check and after the `_SKIP_STATUSES` check (order matters — A5),
   `if claimed and story_id in claimed: skipped.append(story_id); continue`.
   Add `"claimed_skipped": skipped` to the returned dict. Do **not** import
   `flex_build` from `next_story.py` — it would close the lazy-import cycle
   `flex_build` already works around. Update the module docstring's "Returns the
   first story that:" block to name the third condition and the new key.

3. **Wire it into `infer_position`** (`next_action.py`, § 2 "Next unbuilt
   story", ~line 692). Add `claimed_story_ids` to the existing lazy
   `from flex_build import (...)` block. Then:

   - `claimed = claimed_story_ids(project_path)` — compute it unconditionally,
     before the `if active_phase_file is not None:` guard, so the three new keys
     are present on every Position (A6).
   - First pass: `find_next_story(active_phase_file, project_path, claimed=claimed)`.
   - If that returns `None` **and** `claimed` is non-empty, run a second,
     unfiltered `find_next_story(active_phase_file, project_path)`. If *it*
     returns a story, set `all_stories_claimed = True` and `claimed_skipped` to
     the sorted claimed IDs that appear in the phase's story table. Leave
     `next_story_id` as `None` either way — the "there is a story but you may not
     have it" state is expressed by the flag, not by handing out a claimed story.
     Guard the second pass with the same `except Exception` the first pass uses.
   - Keep the second pass strictly conditional (A7): on the overwhelmingly common
     path — nothing claimed, or a story found — it never runs, so the extra
     `_git_log_oneline` subprocess is not on the hot path. Say so in a comment.
   - Add the three keys to the returned dict and document them in the "Returned
     dict keys" docstring block alongside `next_story_id`.

4. **Add the await-user row to `resolve_next_action`.** Read
   `all_stories_claimed` and `claimed_stories` from the position next to the
   other `position.get(...)` reads at the top. Insert the new branch **between**
   the Row 1 (`active_phase_file is None` → done) branch and the Row 9
   (`next_story_id is None` → checkpoint) branch:

   ```
   if next_story_id is None and all_stories_claimed:
       → make_action(AWAIT_USER, scalar="", model=None,
                     reason="all-stories-claimed",
                     meta={**meta_base, "claimed_stories": claimed_stories})
   ```

   Placement is the whole point — below Row 9 it would be dead code and the
   phase would checkpoint mid-build. Add a comment saying so, and citing
   CER-095.1. Then extend the docstring's row table (~line 937) with the new row.

5. **Attach `claimed_skipped` to spawn actions (A10).** Where `meta` is built
   for the spawn branches, add the key only when the position's `claimed_skipped`
   is non-empty. Prefer a small local helper over repeating the conditional at
   each `make_action` call site; do not change `make_action` itself or the set of
   required top-level keys — `tests/pairmode/test_next_action_schema.py`
   asserts the schema's required keys equal `make_action`'s output keys, and that
   assertion must keep passing untouched.

6. **Tests.**
   - `tests/pairmode/test_flex_build.py` — extend the existing
     `create/merge/discard-story-worktree (INFRA-224)` test class (~line 1160,
     which already has `_git`/`_commit_in` helpers and a real git tmp project):
     A1 (empty when the directory is absent; ignores a plain file and a
     non-matching directory name) and A2 (create → present; merge → absent;
     create → discard → absent).
   - `tests/pairmode/test_next_story.py` — A3 (a call with no `claimed` behaves
     as today and existing tests are not edited), A4 (skip + `claimed_skipped`
     contents, and `[]` when nothing is skipped), A5 (committed story still
     skipped as complete before the claim check; `deferred` still excluded;
     an unknown claimed ID is inert).
   - `tests/pairmode/test_next_action.py` — A6 (all three keys present, including
     for a project with no active phase), A7 (both directions: all-claimed vs
     genuinely complete), A8 (await-user, and `check_checkpoint_guards` not
     reached — assert via the returned action, or monkeypatch the guard to raise
     and assert it does not fire), A9 (the three-poll sequence), A10 (meta key
     present with claims, absent without). Follow the existing
     `TestResolveNextActionCheckpoint` pattern: build a real project dir on disk
     and assert through `infer_position` / `resolve_next_action`, not a synthetic
     position dict.
   - A11 is a grep assertion; state it in the review notes and let the reviewer
     run it.

7. **Docs** — apply A13 to `docs/architecture.md` and A14 to
   `docs/cer/backlog.md` (append to the existing CER-095 Finding cell; leave the
   row in place and its `Phase` cell at `109`).

8. **Ideology note (Step 4a — resolved inline, no conflict).** Three points
   shaped this spec. *"Never silently pass contradictions"* forced A7/A8 into
   existence: the tempting simple implementation lets claimed stories vanish, and
   a vanished story is indistinguishable from a finished one at the exact moment
   the loop decides to tag a phase complete — a contradiction passed silently, and
   the constraint's rationale is that false confidence is worse than no system.
   *"Sidebar owns all state writes"* is why A12 forbids the resolver pruning a
   stale worktree it observes: `create-story-worktree` and its two teardown
   commands are the sole writers of claim state, and a self-healing reader would
   be a second writer of build state. *"Rationale-bearing decisions over bare
   rules"* is why steps 1, 3 and 4 each require their reasoning in a docstring or
   comment — the branch-without-directory exclusion, the conditional second pass,
   and above all the ordering of the new branch above Row 9 all look like
   arbitrary fussiness to a future agent tidying the file, and each one silently
   breaks a different guarantee when "simplified".

## Tests

Run from the story worktree root. Targeted first:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_next_story.py \
  tests/pairmode/test_next_action.py \
  tests/pairmode/test_next_action_states.py \
  tests/pairmode/test_next_action_schema.py \
  tests/pairmode/test_next_action_compose.py \
  tests/pairmode/test_flex_build.py -q 2>&1 | tail -30
```

Then the full suite, **without `-x`** so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable assertions the reviewer may run directly:

```bash
grep -c 'pairmode-worktrees' skills/pairmode/scripts/next_story.py   # must print 0
grep -c 'pairmode-worktrees' skills/pairmode/scripts/next_action.py  # must print 0
grep -c 'all-stories-claimed' skills/pairmode/scripts/next_action.py # must be >= 1
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  resolver-state --project-dir . | python -c \
  "import json,sys; p=json.load(sys.stdin)['position']; \
   print(sorted(k for k in p if 'claim' in k))"
  # must print ['all_stories_claimed', 'claimed_skipped', 'claimed_stories']
```

Acceptance:

- every new test from `## Instructions` step 6 passes, in particular A9's
  three-poll sequence (offer A → claim A → offer B → claim B → await-user);
- the pre-existing `tests/pairmode/test_next_story.py` cases pass **unmodified**
  (A3), and `test_next_action_schema.py`'s
  `test_schema_top_level_required_keys_match_make_action_output` passes
  unmodified (A10/step 5);
- `test_next_action_compose.py` still passes — the resolver must keep composing
  `flex_build` helpers rather than reimplementing the worktree convention;
- the full suite is green except
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090); if
  it appears, state that it reproduces on clean `HEAD` and is unrelated.

Documentation-only assertions (A13, A14) are verified by the reviewer from the
diff.

Note for `spec-preflight`: `claimed_story_ids`, `claimed_stories`,
`claimed_skipped`, `all_stories_claimed` and the `all-stories-claimed` reason
string do not exist in the codebase yet — they are created by this story, and any
preflight finding naming them is expected.

## Out of scope

- **CER-095 items (2), (3) and (4)** — story-keyed `current_story` and
  `scope_guard` resolution (INFRA-281), the story-keyed attempt counter
  (INFRA-282), and phase-keyed checkpoint state (INFRA-283). This story makes the
  resolver *name* a second story; it does not make it safe to *build* one. Do not
  touch `.companion/attempt_counter.json`, `state.json["current_story"]`,
  `story_context.py`, `scope_guard.py`, or the checkpoint step state.
- **Rewriting the build loop for parallel dispatch.** `CLAUDE.build.md` and
  `skills/pairmode/templates/CLAUDE.build.md.j2` are untouched. The serialism
  prose they carry is rewritten in INFRA-286, deliberately last, once the whole
  enabling set exists (`docs/phases/phase-109.md` § Ordering). Editing the
  template here would also churn `tests/pairmode/test_templates.py` drift
  assertions for no delivered capability.
- **A locking or lease mechanism.** No lock file, no PID, no timestamp, no TTL on
  a claim. The worktree directory is the claim; adding a parallel record would
  create precisely the two-sources-of-truth condition CER-095 documents.
- **Auto-pruning or expiring stale worktrees.** The resolver reports; the operator
  runs `discard-story-worktree`. A reader that prunes becomes a second writer of
  build state (A12).
- **Treating a stray `pairmode/<ID>` branch with no worktree directory as a
  claim.** Argued in `## Instructions` step 1 — `create-story-worktree` already
  fails loudly on an existing branch.
- **Multi-orchestrator operation.** Out of scope for the whole phase
  (`docs/phases/phase-109.md` § Scope statement). The claim read here is not
  atomic against a second concurrent orchestrator and is not intended to be.
- **Changing `resolve_current_phase`'s no-index fallback.** It keeps calling
  `find_next_story` without `claimed`, by design — argued in `## Context`.
- **The observability SPA/API** (`ui/`, the Fastify routes). The three new
  Position keys ride through `resolver-state --json` for free; rendering them is
  Phase G's surface, not this story's.
- **Any new persistent schema object.** No table, no file, no new state key —
  `schema_introduces: false` stands and no management-surface row is owed.

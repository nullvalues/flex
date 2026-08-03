---
id: INFRA-341
rail: INFRA
title: Wire spawn-gate-worker's verdict to a real consumer, closing the INFRA-331 livelock
status: complete
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/next_action.py
touches:
  - skills/pairmode/skills/gate-worker/procedure.md
  - docs/architecture.md
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_gate_worker_isolation.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CRITICAL finding F8 of `docs/build-loop-cold-eyes-review-20260801.md` (opus): `spawn-gate-worker`
(Row 4b, added by INFRA-313/INFRA-331 this era) is a livelock. `CLAUDE.build.md`'s dispatch branch
spawns the gate-worker and re-polls `next-action`, with no instruction anywhere to route the
worker's stdout to anything. `parse_worker_verdict_json`/`route_gate_verdict` have zero non-test
callers (`route_gate_verdict`'s only caller is a test). The gate-worker's own procedure document
(`skills/pairmode/skills/gate-worker/procedure.md`) asserts "the orchestrator feeds stdout directly
to `parse_worker_verdict_json`" — it does not. Since the gate's inputs (story frontmatter, phase
manifest) don't change between polls, and nothing consumes or acts on the verdict, `spawn-gate-worker`
re-emits identically on every subsequent poll — the resolver's own docstring even frames this as a
deliberate idempotence feature, when it is in fact the livelock.

**Investigation findings this spec is built on (read before building):**

1. **`skills/pairmode/skills/gate-worker/procedure.md` is not just wrong, it is unreachable.**
   `templates/agents/gate-worker.md.j2` (the actual agent shell the orchestrator spawns) delegates
   to `skills/pairmode/gate_worker/SKILL.md` (a *different* file, singular `gate_worker/`, no
   `skills/` nesting) — never to `skills/pairmode/skills/gate-worker/procedure.md`.
   `tests/pairmode/test_gate_worker_isolation.py`'s own DP1.3 input-bound guard inspects
   `gate_worker/SKILL.md`, not `skills/gate-worker/procedure.md` either. The stale doc's false
   claim about stdout routing has therefore never been exercised by the live worker — it is
   orphaned prose left over from RESOLVER-013 (see `docs/stories/RESOLVER/RESOLVER-013.md`), not a
   description of any code path that ever ran. This story corrects its content (Ensures 8) and
   records the orphan status explicitly rather than leaving a second, unreachable procedure doc to
   mislead a future reader — full deletion is out of scope (see Out of scope) since nothing in
   this era's remit calls for removing docs wholesale.
2. **The real worker output is 2 keys, not 3 — and `parse_worker_verdict_json` requires 3 or
   fail-closes.** `gate_worker/SKILL.md` (the live judgment procedure) explicitly instructs: *"The
   `stub` key is never a valid key in your return map"* (stub is mechanical, handled entirely by
   Row 4a before `spawn-gate-worker` is ever emitted — by construction, if Row 4b fires, the stub
   gate already passed). Its own Return-format examples show `{"schema": "clean", "auth": "clean"}`
   — two keys. `gate-worker.md.j2`'s Return section matches this (two-key example). But
   `parse_worker_verdict_json` (RESOLVER-013, `next_action.py`) fail-closes (all three gates
   `block:malformed-verdict`) unless exactly `{schema, auth, stub}` are all present —
   `test_parse_worker_verdict_json.py::test_missing_stub_key` locks this in. Wiring the worker's
   real 2-key stdout straight into `parse_worker_verdict_json`, as the (unreachable) procedure doc
   claimed, would make every real gate-worker verdict fail-closed permanently — trading the
   livelock for a permanent false block, which is not a fix. This story closes that gap at the one
   new call site this story adds (Ensures 3), not by loosening `parse_worker_verdict_json`'s
   general-purpose fail-closed contract (which stays exactly as strict as RESOLVER-013 left it, for
   any other future caller).
3. **The codebase already has a proven idiom for exactly this "durable verdict, not a live pipe"
   problem: INFRA-315's `record-intent-review`.** `flex_build.py record-intent-review` parses a
   worker's verdict, writes it to `state.json`, and `next_action.py`'s `infer_position`/
   `resolve_next_action` read that durable evidence on the *next* poll to route around re-emitting
   `spawn-intent-reviewer` (see `TestPreBuildIntentReviewOnceOnlyRoundTrip` in
   `tests/pairmode/test_next_action.py`). This story applies the identical shape to
   `spawn-gate-worker`: a new `record-gate-verdict` CLI parses + persists, `infer_position` gains a
   `gate_verdict` field, and `resolve_next_action`'s Row 4b consults it before deciding whether to
   (re-)emit `spawn-gate-worker`. This keeps `resolve_next_action` pure-read (its own docstring's
   invariant) — the aggregation itself (`route_gate_verdict`, DP3.2) already exists and is reused
   unchanged, not reimplemented.

Fix direction (resolved by the investigation above, not left open for the builder): wire
`CLAUDE.build.md`'s dispatch branch (and its `.j2` template — coordinated with INFRA-340's landed
shape, see Requires) to capture the gate-worker's stdout, persist the parsed verdict via a new
`record-gate-verdict` CLI (which internally calls `parse_worker_verdict_json`), and let
`resolve_next_action`'s Row 4b apply `route_gate_verdict`'s DP3.2 aggregation to the durable verdict
on the next poll — routing to `await-user` on any `block` (surfacing the worker's reasons) or
`spawn-builder` on `clean`/`flag` (surfacing `flag` reasons as `meta.warnings[]`). This is the real
downstream effect the review's F8 finding says is missing, and it matches this era's CER-137/AG-13
shell-and-dispatch work (INFRA-331/INFRA-332) that made `spawn-gate-worker` reachable in the first
place but never closed the loop on what happens after it returns.

## Requires

1. **INFRA-340 merged** (commit `06e412c1`). Confirmed landed shape relevant to this story:
   `select_gate_worker_model` is no longer called from Row 4b (no model-selector wiring for this
   action); `spawn-gate-worker`'s emitted action still carries `model=None` and is **not** a member
   of `_SPAWN_ACTIONS`; `docs/architecture.md`'s "Gate-worker / docs-reviewer / spec-writer model
   selection" section and `gate-worker.md.j2`'s frontmatter comment already reflect this. This story
   does **not** need to touch the action grammar's `model` field or promote `spawn-gate-worker` into
   `_SPAWN_ACTIONS` — it builds the stdout-capture/parse/route wiring without assuming a model
   override exists for this action, exactly as INFRA-340's Context § Decision framed the option.
2. `parse_worker_verdict_json` and `route_gate_verdict` (`next_action.py`, RESOLVER-013/RESOLVER-005)
   as the existing pure functions this story wires to a real caller — do not rewrite their
   aggregation or fail-closed logic; call them as they exist today (Investigation finding 2 above
   is handled by pre-processing the raw text *before* it reaches `parse_worker_verdict_json`, at the
   new CLI call site only).
3. `flex_build.py record-intent-review` (`cmd_record_intent_review`) and `next_action.py`'s
   `pre_build_intent_verdict`/`infer_position` reading of `state.json["pre_build_intent_review"]`
   (INFRA-315) as the structural pattern this story's `record-gate-verdict`/`gate_verdict` mirrors —
   same durable-evidence-then-reread shape, different state key and different downstream aggregation
   (`route_gate_verdict` instead of the PASS/ALIGNED check).
4. `state_utils._atomic_write_json` (already imported in `next_action.py`; available to
   `flex_build.py`) as the write primitive for the new `state.json["gate_verdict"]` key — no new
   write mechanism is introduced.

## Ensures

1. **A new `record-gate-verdict` CLI subcommand exists in `flex_build.py`** (`--story-id` required,
   `--project-dir` default `.`), reading the gate worker's raw stdout text from stdin in full (not a
   CLI argument — avoids shell-escaping a JSON payload). `uv run python
   skills/pairmode/scripts/flex_build.py record-gate-verdict --help` exits 0 and its help text names
   both options.
2. **The command persists to `state.json["gate_verdict"][story_id]`**, a `dict[str, str]` with
   exactly the keys `schema`, `auth`, `stub` (the shape `parse_worker_verdict_json` returns),
   written via `state_utils._atomic_write_json` (temp file + `os.replace`, mirroring every other
   `state.json` writer per `docs/architecture.md`'s state-ownership table). The command exits 0 on
   any well-formed or malformed stdin (fail-closed is a *stored value*, never a CLI failure — a
   worker crash or garbage stdout must still leave durable evidence the resolver can act on, not
   silently vanish).
3. **A missing `"stub"` key in the worker's raw JSON is defaulted to `"clean"` before calling
   `parse_worker_verdict_json`, at this call site only.** If the parsed stdin is a JSON object
   without a `"stub"` key, `record-gate-verdict` injects `"stub": "clean"` before invoking
   `parse_worker_verdict_json` (Investigation finding 2: `spawn-gate-worker` is only ever emitted
   after Row 4a's mechanical stub gate has already passed, so this reflects true state, not a
   security loosening). Stdin that is not valid JSON, or is a JSON object that already contains an
   explicit non-clean `"stub"` value, is passed to `parse_worker_verdict_json` unmodified — the
   fail-closed malformed-JSON path is untouched. `parse_worker_verdict_json` itself, its docstring,
   and its existing required-keys contract are **not modified** by this story — the 3-key
   requirement stays exactly as strict as RESOLVER-013 left it for any other caller.
   Forbidden proxy: loosening `parse_worker_verdict_json`'s own `_REQUIRED_KEYS` check (in
   `next_action.py`) instead of pre-processing at the CLI boundary — that would relax the
   fail-closed guarantee for every current and future caller, not just this one call site.
4. **`infer_position` gains a `gate_verdict` field**: `dict[str, str] | None`, read from
   `state.json["gate_verdict"].get(next_story_id)` when `next_story_id` is not None, defaulting to
   `None` on any missing file, missing key, non-dict value, or parse error (fail-open, mirroring the
   `pre_build_intent_verdict` read exactly — same `try/except Exception: pass` shape,
   `isinstance` guards on both the outer dict and the per-story value). `infer_position`'s docstring
   documents the new field in the same style as `pre_build_intent_verdict`'s entry.
5. **`resolve_next_action`'s Row 4b consumes the recorded verdict instead of re-emitting
   `spawn-gate-worker` once one exists.** When `judged_tripped` is non-empty (schema and/or auth
   gate tripped) and `position["gate_verdict"]` is not `None`: build the same `meta` dict Row 4b
   already builds (`gates_tripped`, `gate_reasons`, `claimed_skipped`), then return
   `route_gate_verdict(position["gate_verdict"], next_story_id, meta_base=meta)` directly — this is
   the DP3.2 aggregation already implemented, called from a real production path for the first time.
   When `judged_tripped` is non-empty and `position["gate_verdict"]` **is** `None` (no verdict
   recorded yet for this story), Row 4b's behavior is **unchanged**: emit `spawn-gate-worker` exactly
   as it does today, `model=None`, `reason="judged-gate-tripped"`. This is what closes the livelock:
   the first poll after a judged gate trips still spawns the gate worker (unchanged), but every poll
   *after* the orchestrator records that worker's verdict resolves to `await-user` (blocked) or
   `spawn-builder` (clean/flag) instead of spawning the gate worker again.
6. **The routed action is reachable end-to-end.** A resolver-level test (new, in
   `tests/pairmode/test_next_action.py` or `test_gate_worker_isolation.py`) constructs a project
   fixture with a judged-gate-tripped story, calls `infer_position` + `resolve_next_action` once with
   no recorded verdict (asserts `SPAWN_GATE_WORKER`), then writes a `block:<reason>` verdict via
   `cmd_record_gate_verdict` (CliRunner, mirroring
   `TestPreBuildIntentReviewOnceOnlyRoundTrip::test_stateless_rerun_after_recording_verdict`'s
   pattern), then calls `infer_position` + `resolve_next_action` again on a **fresh** read (proving
   statelessness across the equivalent of a `/clear` boundary) and asserts `AWAIT_USER` with
   `reason` starting `"gate-blocked:"`. A second test does the same for an all-`clean` verdict and
   asserts `SPAWN_BUILDER`.
7. **`merge-story-worktree` and `discard-story-worktree` both clear the recorded verdict for their
   story.** `flex_build.py`'s `cmd_merge_story_worktree` and `cmd_discard_story_worktree` each pop
   `state["gate_verdict"][story_id]` (if present) as part of their existing teardown/clear sequence
   — mirroring the existing `clear_attempt_count`/`_clear_active_story`/`clear_permissions_artifact`
   calls already present in both functions (CLAUDE.build.md's own comments already promise this:
   "also clears the attempt counter... and current_story/permissions stamps" on both merge and
   discard). Forbidden proxy: clearing on merge only — a discarded story must not silently reuse a
   stale verdict on its next attempt if its frontmatter changes during a spec revision.
8. **`CLAUDE.build.md`'s dispatch branch captures, records, and re-polls — it does not
   special-case the routed action.** The `while true` loop gains an explicit `spawn-gate-worker`
   branch (alongside the existing `spawn-builder` branch and the generic `else`): spawn the
   gate-worker leaf worker, capture its returned stdout text, pipe it to
   `{{ pairmode_scripts_dir }}/flex_build.py record-gate-verdict --story-id a.scalar --project-dir .`
   via stdin, then let the loop's next iteration call `next-action` again — no new branch for
   `await-user`/`spawn-builder` results is needed here, because Row 4b (Ensures 5) already resolves
   the routed action on that next poll. This mirrors the existing pre-build intent-review prose
   pattern (`.j2`'s `intent_review=pre-build` paragraph: spawn, record via CLI, re-run `next-action`)
   rather than inventing a second dispatch idiom.
9. **`skills/pairmode/templates/CLAUDE.build.md.j2` carries the same branch**, and its
   `ACTION_SUBAGENT_TYPE` map — which currently has no `spawn-gate-worker` entry at all, unlike the
   live `CLAUDE.build.md` — gains `spawn-gate-worker: gate-worker` (matching the live file's map;
   INFRA-331/CER-137/AG-13 added this to `CLAUDE.build.md` but the `.j2` template was never brought
   into sync). This is not the full `CLAUDE.build.md`/`.j2` reconciliation (that is INFRA-342's job,
   sequenced after this story per the phase Ordering note) — only the pieces this story's own new
   branch requires are added to `.j2`.
10. **`skills/pairmode/skills/gate-worker/procedure.md` is corrected, not deleted, and its orphan
    status is recorded.** Its "the orchestrator feeds stdout directly to `parse_worker_verdict_json`"
    claim is replaced with an accurate description of the `record-gate-verdict`-mediated flow
    (Ensures 1–3), and its "all three keys ... must always be present" claim is corrected to state
    the worker emits `schema`/`auth` only (two keys — `stub` is mechanical, handled by Row 4a before
    this worker is ever spawned) and that `record-gate-verdict` supplies `"stub": "clean"` before
    parsing. A note is added stating this file has no live reader as of this story —
    `templates/agents/gate-worker.md.j2` delegates to `skills/pairmode/gate_worker/SKILL.md`
    instead — so a future reader does not mistake it for the active procedure doc.
11. **`docs/architecture.md`'s `next_action.py` Module-structure bullet gets a dated INFRA-341
    addendum** (following the file's existing convention of appending, not editing, prior entries)
    recording: `infer_position` gains `gate_verdict`; Row 4b now calls `route_gate_verdict` on a
    recorded verdict before falling back to (re-)emitting `spawn-gate-worker`; `record-gate-verdict`
    is the new CLI writer. While editing this line, the stale `parse_worker_verdict_text` name in
    the existing HARNESS002-main clause (removed by RESOLVER-016; the docstring reference was never
    updated) is corrected to `parse_worker_verdict_json`.
12. **No regression.** Full suite green without `-x` (project lesson: `-x` can mask a pre-existing
    failure): `uv run pytest tests/pairmode/ -q` (no `-x`).
13. **Grammar-unchanged.** No new action type, no `ACTIONS`/`_SPAWN_ACTIONS` membership change, no
    `SCHEMA_VERSION` bump. `spawn-gate-worker` still carries `model=None` and is still excluded from
    `_SPAWN_ACTIONS` (per INFRA-340's decision, Requires 1). `len(ACTIONS)` and `len(_SPAWN_ACTIONS)`
    are unchanged from their post-INFRA-340 values.

## Instructions

1. Read `next_action.py`'s current `infer_position` (search `pre_build_intent_verdict`) and
   `resolve_next_action` Row 4b (search `SPAWN_GATE_WORKER` inside `judged_tripped`) fresh — do not
   trust line numbers cited elsewhere in this spec. Read `flex_build.py`'s `cmd_record_intent_review`
   fully as the structural template for the new command.
2. In `flex_build.py`, add `record-gate-verdict`: `--story-id` (required), `--project-dir` (default
   `.`). Read `sys.stdin.read()` for the raw worker text. If it parses as a JSON object missing a
   `"stub"` key, inject `"stub": "clean"` before calling `next_action.parse_worker_verdict_json`
   (import lazily inside the command function, matching this module's existing lazy-import style for
   `next_action` symbols). Load `state.json` (or default `{}`), ensure `state["gate_verdict"]` is a
   dict, set `state["gate_verdict"][story_id] = verdict_map`, write via `_atomic_write_json`. Echo a
   one-line human-readable summary (verdict per gate) and exit 0 unconditionally.
3. In `next_action.py`'s `infer_position`, add the `gate_verdict` read immediately alongside the
   existing `pre_build_intent_verdict` read block (same file, same `try/except Exception: pass`
   shape), keyed by `next_story_id` instead of a phase key. Add it to the returned dict and to the
   function's docstring's "Returned dict keys" list.
4. In `resolve_next_action`'s Row 4b, after computing `judged_tripped`/`meta` exactly as today:
   if `judged_tripped` and `position.get("gate_verdict") is not None`, return
   `route_gate_verdict(position["gate_verdict"], next_story_id, meta_base=meta)` instead of
   `make_action(SPAWN_GATE_WORKER, ...)`. Otherwise (including the `not judged_tripped` case, which
   is unreachable here since Row 4b is only entered when `judged_tripped` is truthy) fall through to
   the existing `make_action(SPAWN_GATE_WORKER, ...)` call, unchanged.
5. In `flex_build.py`'s `cmd_merge_story_worktree` and `cmd_discard_story_worktree`, add a small
   shared helper (e.g. `_clear_gate_verdict(project_path, story_id)`) that loads `state.json`, pops
   `state.get("gate_verdict", {}).pop(story_id, None)` if present, and writes back via
   `_atomic_write_json` only when a key was actually removed (avoid a needless write/lock on the
   common case where no verdict was ever recorded for this story). Call it from both functions
   alongside their existing `clear_attempt_count`/`_clear_active_story` calls.
6. In `CLAUDE.build.md`, add an explicit `if a.action == "spawn-gate-worker":` branch in the `while
   true` pseudocode (before the generic `else`), per Ensures 8. Mirror the existing inline-comment
   density of the `spawn-builder` branch (name the CLI call, name what it does, name the INFRA-341
   story ID). Update `ACTION_SUBAGENT_TYPE`'s trailing comment if the new branch changes what
   `else` covers (it should no longer need to resolve `spawn-gate-worker` via the generic path).
7. Apply the same branch, in the same relative position, to
   `skills/pairmode/templates/CLAUDE.build.md.j2`, using `{{ pairmode_scripts_dir }}` in place of
   the hardcoded absolute path (matching every other `.j2` line's templating convention). Add
   `spawn-gate-worker: gate-worker` to the `.j2`'s `ACTION_SUBAGENT_TYPE` map (Ensures 9) — do not
   otherwise reconcile the two files' other divergences; that is INFRA-342's job.
8. Update `skills/pairmode/skills/gate-worker/procedure.md` per Ensures 10. Do not delete the file
   or move its content into `gate_worker/SKILL.md` — this story documents the orphan, it does not
   consolidate the two procedure trees (out of scope, see below).
9. Update `docs/architecture.md`'s `next_action.py` Module-structure bullet per Ensures 11.
10. Add the new tests named in Ensures 6, extend `test_parse_worker_verdict_json.py`-adjacent
    coverage if a new test module is more appropriate than extending an existing one (either is
    acceptable — state which in the commit), and add unit coverage for `record-gate-verdict`'s
    stub-default-injection behavior (Ensures 3) and for the merge/discard verdict-clear behavior
    (Ensures 7).
11. Run the full suite without `-x` and confirm green (Ensures 12).

**Do not:** promote `spawn-gate-worker` into `_SPAWN_ACTIONS` or otherwise change the action grammar
(Requires 1 — already decided by INFRA-340; this story's fix does not need it); modify
`parse_worker_verdict_json`'s own required-keys contract or its existing tests in
`test_parse_worker_verdict_json.py` (Ensures 3's forbidden proxy); modify `gate_worker/SKILL.md`'s
judgment scope or its two-key return-format examples — they are already correct and are the contract
this story's new CLI-side default (`"stub": "clean"`) is built to satisfy, not to change; perform the
full `CLAUDE.build.md`/`.j2` reconciliation or add a drift check between them (INFRA-342's job,
sequenced after this story); touch `model_selector.py` or re-litigate INFRA-340's option (b) decision.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -q 2>&1 | tail -40
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_gate_worker_isolation.py -q 2>&1 | tail -40
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

Acceptance: green, no `-x` (project lesson: a known pre-existing failure must not be masked).

Reviewer negative checks:
(a) `grep -n "record-gate-verdict" skills/pairmode/scripts/flex_build.py` returns at least one hit
    (the `@flex_build.command` decorator).
(b) `grep -n "route_gate_verdict" skills/pairmode/scripts/next_action.py` shows a call site inside
    `resolve_next_action` (not only the function definition and the `SPAWN_BUILDER`/`AWAIT_USER`
    branches already inside `route_gate_verdict` itself) — i.e. `route_gate_verdict` now has a
    non-test caller.
(c) `grep -n "spawn-gate-worker" CLAUDE.build.md` shows an explicit branch, not only the
    `ACTION_SUBAGENT_TYPE` map entry.
(d) `grep -n "gate_verdict\b" skills/pairmode/scripts/next_action.py` shows both a read (in
    `infer_position`) and a consuming branch (in `resolve_next_action`).
(e) A test asserts that calling `resolve_next_action` twice — once with no recorded verdict, once
    after recording a `block:` verdict via `cmd_record_gate_verdict` — transitions from
    `SPAWN_GATE_WORKER` to `AWAIT_USER` without any change to the underlying story frontmatter
    (proves the livelock is closed, not merely that the helper functions are importable).

## Out of scope

- Promoting `spawn-gate-worker` into `_SPAWN_ACTIONS` or otherwise changing the action grammar to
  let it carry a non-null `model` — already decided against by INFRA-340 (Requires 1); this story's
  fix does not require it.
- The full `CLAUDE.build.md`/`.j2` reconciliation and an automated dispatch-parity drift check
  between the two files — INFRA-342, sequenced after this story per the phase Ordering note. This
  story only adds the `spawn-gate-worker`-specific pieces its own fix needs to `.j2`.
- Deleting or merging `skills/pairmode/skills/gate-worker/procedure.md` into
  `skills/pairmode/gate_worker/SKILL.md` — this story documents the orphan and corrects its
  content so it is no longer actively misleading, but consolidating the two procedure-doc trees
  (a pattern that may also affect other roles) is a separate, broader cleanup this story does not
  scope into.
- Re-litigating INFRA-340's option (a)/(b) decision for `select_gate_worker_model` — this story's
  wiring does not need a gate-worker model override, so that decision stands unchanged.
- Any change to `gate_verdict.py`'s `VERBS`/`parse_verdict`/`validate_verdict_map` grammar, or to
  `gate_worker/SKILL.md`'s judgment logic (DP2.2 downgrade/confirm/flag rules) — this story wires
  the existing grammar and judgment procedure to a real consumer; it does not change what the
  worker judges or how.
- Docstring-currency sweeping beyond the one stale `parse_worker_verdict_text` reference this story
  happens to touch while editing the same `architecture.md` line (Ensures 11) — the broader sweep
  is INFRA-349, sequenced last in this phase on purpose.

## Evidence

Covered-contracts gate (INFRA-317): `primary_files:` names `skills/pairmode/scripts/next_action.py`,
which intersects the `covered_contracts` pair `## Module structure::skills/pairmode/scripts/next_action.py`
in `docs/architecture.md`. Read `docs/architecture.md` § Module structure's `next_action.py` bullet
and the source file in full before editing either, per `builder/procedure.md`'s covered-contracts
gate.

Divergence found (this story's own reason for existing, beyond the stub's original Context):
`skills/pairmode/skills/gate-worker/procedure.md` claims a stdout-routing mechanism that never
existed in any live code path (F8's core finding), and is itself unreachable from the live agent
shell (`gate-worker.md.j2` delegates to a different file, `gate_worker/SKILL.md`) — a second,
independent documentation-currency gap discovered during this story's investigation, corrected
alongside the functional fix rather than filed as a separate CER, since both are the same
"stdout goes nowhere real" problem described from two different angles (missing wiring, and a
doc that describes wiring which was never built). Additionally, `gate_worker/SKILL.md`'s live
2-key verdict-map contract (`stub` deliberately excluded) is incompatible with
`parse_worker_verdict_json`'s literal 3-key fail-closed requirement — wiring the two together
without the CLI-side default this story adds (Ensures 3) would have replaced the livelock with a
permanent false block on every real gate-worker invocation, which is not a fix and would not have
been caught by any existing test (none of `test_parse_worker_verdict_json.py`'s cases exercise a
2-key input, since no non-test caller existed before this story to expose the gap).

Spec-preflight note (INFRA-190/191, INFRA-320 § C): the scan flags
`skills/pairmode/gate_worker/SKILL.md` as named in this spec but outside declared scope. This is
intentional — the file is read for context (its live 2-key verdict-map contract is why Ensures 3's
CLI-side default exists) but is explicitly listed in "Do not" as unmodified by this story (its
judgment logic and return-format examples are already correct and are not touched).

Builder-time evidence (INFRA-317, quoted per `builder/procedure.md`'s covered-contracts gate):
`docs/architecture.md` § Module structure's `next_action.py` bullet, as read fresh before editing
either file, ended with: `"...spawn-loop-breaker with reason=\"\")"` — the tail of the
HARNESS009-main-through-INFRA-328 addendum chain the gate confirmed both halves cover. Also read:
the file's *own* line, "HARNESS002-main adds spawn-gate-worker to ACTIONS, ... parse_worker_verdict_text
(worker text return -> per-gate verdict map), route_gate_verdict (DP3.2 aggregation...)" — the stale
`parse_worker_verdict_text` name Ensures 11 called out as needing correction (removed from the
source file by RESOLVER-016, but the docstring reference in this doc bullet was never updated,
confirming the divergence named above). Both corrected in this build: `parse_worker_verdict_text` ->
`parse_worker_verdict_json` in place, and a dated 2026-08-01 INFRA-341 addendum appended (following
the file's own append-only convention for this bullet) recording the `gate_verdict`/Row 4b/
`record-gate-verdict` additions per Ensures 11.

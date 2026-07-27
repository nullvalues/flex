---
id: INFRA-283
rail: INFRA
title: Phase-keyed checkpoint step state on top of INFRA-265's explicit phase key (CER-095.4)
status: complete
phase: "109"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/next_action.py
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_record_checkpoint_step.py
  - tests/pairmode/test_checkpoint_step.py
  - tests/pairmode/test_next_action.py
  - docs/stories/INFRA/INFRA-283.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 109 restores single-orchestrator parallel builds. CER-095 names four
single-slot coordination structures that break under concurrency: INFRA-280
closed item (1) (resolver in-flight claim), INFRA-281 closed item (2)
(story-keyed `current_stories` + per-call `scope_guard` resolution), INFRA-282
closed item (3) (story-keyed attempt counter). **This story closes item (4):
checkpoint step state.**

`state.json["checkpoint_step"]` is **one shared list** and
`state.json["checkpoint_phase"]` is **one shared stamp**
(`skills/pairmode/scripts/flex_build.py` `_record_checkpoint_step`, ~2505–2672).
Every `record-checkpoint-step` call appends to the same list and overwrites the
same stamp, regardless of which phase is being checkpointed. With two phases
checkpointing under one orchestrator the failures are silent and destructive:

- **Interleaving.** Phase P records `checkpoint-security`; phase Q then records
  `checkpoint-security`. Q's call sees the step already present in the shared
  list and returns 0 **idempotently, without writing** — so Q's own security
  gate is recorded as done when it never ran. Worse, the stamp now names
  whichever phase wrote last, and the A4 disagreement guard (`--phase-key`
  disagrees with the stamp → exit 2) starts rejecting the *other* phase's
  perfectly correct calls.
- **Terminal reset clobbers the sibling.** The `checkpoint-tag` branch (~2639)
  sets `current = []` and `effective_key = ""` unconditionally. Tagging phase P
  therefore wipes phase Q's mid-sequence progress: Q's next `next-action` poll
  reads an empty list and re-emits `checkpoint-security`, re-running the whole
  gate sequence — the same class of duplicated-gate churn INFRA-239 and
  RESOLVER-017 each fixed for the single-phase case.
- **The resolver's stale-stamp defence turns into a weapon.**
  `next_action.infer_position` (~909–928, CER-083/INFRA-260) exposes
  `checkpoint_step` as `[]` whenever `checkpoint_phase` names a phase other than
  the active one. That rule is correct for one phase in flight; with two, the
  stamp names one of them and the *other* one's genuine progress reads as `[]`
  on every poll. The defence and the bug are the same line of code, because a
  single stamp cannot describe two checkpoints.

**INFRA-265 already put the missing fact in every call.** Closing CER-077, it
threaded an explicit `--phase-key` through `record-checkpoint-step` and made it
the head of a precedence chain (`--phase-key` → `state.json["checkpoint_phase"]`
→ sole unambiguous candidate), with a disagreement between sources treated as an
error rather than a guess. `CLAUDE.build.md` (line 48) already mandates
`--phase-key <phase-key>` on the terminal call. So by the time this story runs,
**the phase key that each call belongs to is already resolved, validated, and
in hand** — what is missing is that the resolved key is used only to *stamp* a
single global slot instead of to *key* the state. This story spends INFRA-265's
key on the storage shape it was always the prerequisite for.

The design follows INFRA-281/282's precedent exactly: a keyed record becomes the
authority, the legacy flat shape stays readable so no migration step is
required, clears are scoped to their own key, and the flat keys survive as a
**derived mirror** for readers outside this fix's scope (the observability
API's `resolverState.ts`, `client.ts`). It is also the era's load-bearing
invariant applied to the checkpoint: the harness holds nothing not
reconstructable from `next-action`, so all checkpoint progress must live in
files the resolver reads — and that store must hold one entry per in-flight
phase rather than one globally.

## Requires

- INFRA-280 is complete on `main`: `next_action.infer_position` /
  `resolve_next_action` skip claimed stories and refuse to checkpoint when every
  remaining story is claimed. (`docs/phases/phase-109.md` § Ordering:
  "INFRA-283 (keyed checkpoint state) any time after 280".) INFRA-281 and
  INFRA-282 are also complete on `main` and supply the naming/compatibility
  precedent this story mirrors; neither is a functional dependency.
- INFRA-265 is complete: `flex_build._record_checkpoint_step(step_id,
  project_dir, phase_key=None)` implements the A2 index-validation, A4
  disagreement, and A3 precedence chain described in its docstring (~2529–2544),
  and `cmd_record_checkpoint_step` (~2811) exposes `--phase-key`.
- `flex_build.py` imports `_CHECKPOINT_SEQUENCE` from `next_action` (line ~64)
  and defines `_parse_index_phases`, `_active_phase_candidates`,
  `AmbiguousActivePhaseError`, `_mark_phase_complete_in_index`, and
  `_mark_phase_complete_in_era_ledger`.
- `next_action.infer_position` reads `state.json["checkpoint_step"]` and
  `["checkpoint_phase"]` inside a single `try/except Exception: pass` block
  (~897–930) and derives the active phase key as
  `Path(active_phase_file).stem` with a leading `phase-` stripped (~922–926).
  `resolve_next_action` consumes `position["checkpoint_step"]` at ~1096–1097.
- `next_action.SCHEMA_VERSION` is `3` and `position["checkpoint_step"]` is a
  `list[str]`. Both are consumed by
  `skills/observability/api/src/readers/resolverState.ts` (~28) and
  `skills/observability/ui/src/api/client.ts` (~107).
- `docs/architecture.md` carries the checkpoint-sequence material at § Pairmode
  build loop step 10 (~605–680, including the INFRA-260 stale-stamp and
  INFRA-265 precedence paragraphs), the `checkpoint_step` / `checkpoint_phase`
  rows of the state-ownership table (~1634–1635), and the annotated `state.json`
  schema listing (~1708–1760) where INFRA-281's `current_stories` entry lives.
- `docs/cer/backlog.md` row `CER-095` carries `**INFRA-280 …**`,
  `**INFRA-281 …**` and `**INFRA-282 …**` resolution notes, and a sentence
  stating that item (4) "remains open under INFRA-283".
- Existing tests: `tests/pairmode/test_record_checkpoint_step.py` (CLI-level,
  `CliRunner`), `tests/pairmode/test_checkpoint_step.py` (`infer_position`
  field + `SCHEMA_VERSION`), `tests/pairmode/test_checkpoint_routing.py`
  (action routing). All must keep passing unmodified except where this story
  explicitly extends them.

## Ensures

Each assertion is independently checkable by reading a file or running a
command. Line numbers are orientation only; match on content.

### A — keyed storage with legacy read compatibility

1. **The on-disk shape is phase-keyed.** After
   `_record_checkpoint_step("checkpoint-security", p, phase_key="109")` followed
   by `_record_checkpoint_step("checkpoint-security", p, phase_key="105")`,
   `p/.companion/state.json` contains a dict under a single new top-level key
   (name at builder's discretion, e.g. `"checkpoint_steps"`) holding **both**
   `"109" -> ["checkpoint-security"]` and `"105" -> ["checkpoint-security"]`.
   Neither call removed or truncated the other phase's list.

2. **A keyed read helper exists and is pure.** A module-level helper in
   `flex_build.py` (e.g.
   `_read_checkpoint_steps(state: dict) -> dict[str, list[str]]`) returns the
   full phase-key → completed-step-list mapping from an already-loaded state
   dict, returns `{}` when the key is absent or malformed, drops non-string
   step entries and non-list values, and performs **no I/O and no writes on any
   path** — including when it derives the keyed view from a legacy flat file.

3. **Legacy flat state still reads correctly.** Given a `state.json` whose only
   checkpoint keys are `{"checkpoint_step": ["checkpoint-security"],
   "checkpoint_phase": "109"}` and no keyed record, the keyed view resolves to
   `{"109": ["checkpoint-security"]}`. A legacy file whose `checkpoint_phase` is
   absent or `""` resolves the list under the empty key `""`. No write occurs on
   any read path — the file's bytes are unchanged after a read-only call.

4. **Legacy state is upgraded in place on the next write.** After any successful
   `_record_checkpoint_step` call against a legacy-shape `state.json`, the file
   contains the keyed record, and the pre-existing legacy list is preserved as
   the entry for the phase its stamp named. There is no migration command and no
   bootstrap change.

5. **Idempotency is per-key.** With `{"109": ["checkpoint-security"]}` recorded,
   `_record_checkpoint_step("checkpoint-security", p, phase_key="109")` returns
   `0` and performs **no write**; the same call with `phase_key="105"` returns
   `0` and **does** append `checkpoint-security` under `"105"`. The pre-story
   code returns 0-without-write for the second case — that regression is what
   this assertion pins.

6. **Ordering: the phase key is resolved before the idempotency short-circuit.**
   The A2 (index validation), A4 (stamp disagreement) and A3 (precedence) blocks
   run **before** the "already recorded" early return, because the key is now
   required to decide idempotency. Every 2-exit path still performs **no write**
   to `state.json` and **no call** to `_mark_phase_complete_in_index` or
   `_mark_phase_complete_in_era_ledger`. The `step_id not in
   _CHECKPOINT_SEQUENCE` → exit 1 check stays first of all, ahead of any state
   read.

### B — scoped terminal reset

7. **`checkpoint-tag` clears only its own key.** With
   `{"109": ["checkpoint-security", "checkpoint-intent", "checkpoint-docs"],
   "105": ["checkpoint-security"]}` recorded,
   `_record_checkpoint_step("checkpoint-tag", p, phase_key="109")` returns `0`,
   removes the `"109"` entry entirely, and leaves `"105" ->
   ["checkpoint-security"]` intact and readable.

8. **The terminal branch's index/era writes are unchanged.** `checkpoint-tag`
   with a non-empty `effective_key` still calls
   `_mark_phase_complete_in_index(effective_key, project_dir)` and
   `_mark_phase_complete_in_era_ledger(effective_key, project_dir)` exactly once
   each, with the same key (INFRA-239 / INFRA-267), inside the same CLI call as
   the state write.

9. **Single-phase behaviour is byte-identical to today.** With only one phase
   ever recorded, the resulting `state.json` has `checkpoint_step` and
   `checkpoint_phase` values identical to the pre-story code at every step of a
   full `checkpoint-security → checkpoint-intent → checkpoint-docs →
   checkpoint-tag` sequence, ending at `[]` / `""`. Verifiable by a test that
   drives the whole sequence and asserts the flat values at each step.

10. **Writes stay atomic.** The state write remains temp-file + `os.replace`
    into `.companion/` (or `state_utils._atomic_write_json`), a single write per
    call covering the keyed record and both flat mirrors. Verifiable:
    `grep -n "write_text" skills/pairmode/scripts/flex_build.py` shows no
    `write_text` call inside `_record_checkpoint_step`.

### C — the flat keys as a derived mirror

11. **`checkpoint_step` / `checkpoint_phase` are written only as mirrors of the
    keyed record.** After every call, `state["checkpoint_phase"]` is the key
    this call resolved (or `""` on the terminal step, per assertion 12) and
    `state["checkpoint_step"]` is exactly that key's list from the keyed record.
    The mirror is never the authority: no code path reads the flat keys to
    decide what to append.

12. **The mirror's post-terminal value is deterministic.** After a
    `checkpoint-tag` that removes the last remaining keyed entry, the mirror is
    `checkpoint_step == []` and `checkpoint_phase == ""` (today's value,
    assertion 9). When other keyed entries remain, the mirror re-points to the
    single remaining entry if exactly one remains, and otherwise falls back to
    `[]` / `""`. The rule is stated in a code comment naming why: a mirror that
    names one of several live checkpoints must not be mistaken for the
    authority.

13. **The observability readers need no change.**
    `git diff main -- skills/observability/` is empty. The TypeScript readers
    consume `position["checkpoint_step"]` (a `list[str]`) and the flat state
    key; both keep their existing shape and type.

### D — resolver reads the keyed record

14. **`infer_position` prefers the keyed record.** When the keyed record is
    present, `position["checkpoint_step"]` is the list stored under the **active
    phase's own key** (the existing `Path(active_phase_file).stem` derivation
    with a leading `phase-` stripped — no second index parse, no new I/O), and
    is `[]` when the active phase has no entry.

15. **Two phases resolve independently.** With
    `{"109": ["checkpoint-security"], "105": []}` recorded and the active phase
    file `docs/phases/phase-109.md`, `position["checkpoint_step"] ==
    ["checkpoint-security"]` regardless of what `checkpoint_phase` names. Under
    the pre-story code, a `checkpoint_phase` of `"105"` forces `[]`.

16. **The CER-083 stale-stamp rule survives for legacy state.** When the keyed
    record is **absent**, the existing behaviour is unchanged: the flat list is
    honoured when `checkpoint_phase` is absent, empty, or equals the active
    phase key, and is exposed as `[]` on a mismatch. A test pins the original
    cp99→phase-100 scenario against a legacy-shape state file.

17. **`infer_position` is still pure-read and still fails open.** The keyed read
    lives inside the existing `try/except Exception: pass` block; a malformed or
    unreadable `state.json` still yields `checkpoint_step == []` and never
    raises. `next_action.py` writes neither the keyed record nor the flat keys.

18. **No schema or routing change.** `next_action.SCHEMA_VERSION` is still `3`,
    `position["checkpoint_step"]` is still a `list[str]`, `_CHECKPOINT_SEQUENCE`
    is unchanged, and `resolve_next_action`'s checkpoint rows (~1096–1097) are
    unmodified. Verifiable: the diff to `next_action.py` touches only
    `infer_position`'s checkpoint block and the module docstring.

19. **A regression test pins the interleave.**
    `tests/pairmode/test_record_checkpoint_step.py` contains a test whose name
    contains `parallel` (or `two_phase`) reproducing the CER-095.4 sequence
    end-to-end: record `checkpoint-security` for 109 and for 105; assert both
    are stored; advance 109 to `checkpoint-tag`; assert 105's list is still
    `["checkpoint-security"]`. It fails against pre-story `flex_build.py`.

### E — documentation and backlog

20. **Architecture records the keyed checkpoint state.**
    `docs/architecture.md` § Pairmode build loop step 10 gains a short
    paragraph, adjacent to the INFRA-260 stale-stamp and INFRA-265 precedence
    material, whose lead is a bolded label containing `INFRA-283` and
    `CER-095.4`, and whose body states: (a) checkpoint step state is
    phase-keyed, one entry per in-flight checkpoint; (b) the key is the one
    INFRA-265's precedence chain already resolves, so no new resolution logic
    exists; (c) the legacy flat shape is still read and is upgraded on the next
    write, so there is no migration step; (d) `checkpoint-tag` removes only its
    own key; (e) `checkpoint_step`/`checkpoint_phase` survive as a derived
    mirror for readers outside this fix's scope, and the CER-083 stale-stamp
    rule now applies only to the legacy read path.

21. **The state-ownership table stays truthful.** The `checkpoint_step` and
    `checkpoint_phase` rows (~1634–1635) are amended to name the keyed record as
    the authority and the flat keys as derived mirrors, and a row for the keyed
    record is added in the same house format (sole writer:
    `flex_build.py record-checkpoint-step`; resolver read-only). Existing row
    content is preserved and appended to, not substituted.

22. **The `state.json` schema listing documents the new key.** The annotated
    schema block (~1708–1760) gains the keyed record with the same treatment
    INFRA-281's `current_stories` entry received: marked **optional**, its shape
    given, and the flat keys explicitly marked as derived mirrors written only
    by `record-checkpoint-step`.

23. **The CER row records the closure.** The `CER-095` row in
    `docs/cer/backlog.md` gains an `**INFRA-283 (Phase 109) — item (4)
    resolved:** …` note in the same house format as the INFRA-280/281/282 notes,
    and the sentence naming item (4) as open is amended to record that all four
    items are now closed. The row is not deleted, not moved between quadrants,
    its `Source`/`Date` cells are unchanged, and its trailing phase cell still
    reads `109`.

24. **The backlog table is not corrupted.** The edited row still parses as a
    table row with the same column count as its neighbours; any literal pipe in
    the new note is escaped as `\|`, matching the existing rows' convention.

### F — suite

25. **The suite is green.** `uv run pytest tests/pairmode/ -q` (run **without**
    `-x`) shows no new failures relative to clean `HEAD` — see `## Tests`.

## Instructions

Work inside this story's worktree. All paths are relative to the repo root.

### Part A — keyed storage (`flex_build.py`, `_record_checkpoint_step`)

1. Add a module-level constant for the container key next to the
   `# record-checkpoint-step (RESOLVER-012)` banner (e.g.
   `_CHECKPOINT_STEPS_KEY = "checkpoint_steps"`) and a pure helper:

   ```
   def _read_checkpoint_steps(state: dict) -> dict[str, list[str]]:
   ```

   It takes the **already-loaded** state dict (no file I/O — the caller already
   read it) and returns the keyed view, normalising both shapes:

   - keyed: `state[_CHECKPOINT_STEPS_KEY]` is a dict → keep string keys whose
     value is a list, filtering each list to `str` members;
   - legacy: the keyed key is absent/not a dict → return
     `{stamp: [str members of state["checkpoint_step"]]}` where `stamp` is
     `state["checkpoint_phase"]` when it is a non-empty string, else `""`.
     Return `{}` when the flat list is absent, empty, or not a list.

   Never write from this helper (assertions 2–3).

2. Restructure `_record_checkpoint_step` so the **key is resolved before the
   idempotency check**. The new order is:

   1. `step_id not in _CHECKPOINT_SEQUENCE` → echo + `return 1` (unchanged, and
      still first).
   2. Read `state.json` into `state` exactly as today.
   3. A2 explicit-`--phase-key` index validation → `return 2` (unchanged).
   4. A4 stamp-disagreement check → `return 2` (unchanged). Compare
      `--phase-key` against `state["checkpoint_phase"]` as today; do **not**
      widen it to the keyed record — the stamp is the mirror of the most recent
      call and the check's purpose (catching an operator naming a different
      phase than the one mid-sequence) is unchanged.
   5. A3 precedence → `effective_key` (unchanged, including the
      `AmbiguousActivePhaseError` → 2, sole-candidate, terminal-vs-non-terminal
      warning, and `""` fallback branches).
   6. `steps = _read_checkpoint_steps(state)`;
      `current = list(steps.get(effective_key, []))`; if `step_id in current`
      → `return 0` with **no write** (assertion 5).

   Preserve every existing error message verbatim; this is a reordering, not a
   rewrite of the validation logic. Add a comment above the reorder explaining
   *why* the idempotency check moved (it is now per-key, so it cannot run before
   the key exists) — a future reader will otherwise read the move as an
   accidental behaviour change.

3. Append and store per key: `current.append(step_id)`;
   `steps[effective_key] = current`.

4. Terminal (`checkpoint-tag`) branch — keep the existing
   `_mark_phase_complete_in_index` / `_mark_phase_complete_in_era_ledger` calls
   and their guard on a non-empty `effective_key` exactly as they are
   (assertion 8). Replace the unconditional `current = []` with
   `steps.pop(effective_key, None)` (assertion 7).

5. Write the keyed record and derive the mirrors, in one atomic write:

   - `state[_CHECKPOINT_STEPS_KEY] = steps` — omit the key entirely (or store
     `{}`) when `steps` is empty; either is acceptable as long as
     `_read_checkpoint_steps` round-trips it.
   - Mirror rule (assertions 11–12): on a non-terminal step, mirror this call's
     own key — `state["checkpoint_step"] = current`,
     `state["checkpoint_phase"] = effective_key`. On the terminal step, if
     `steps` is now empty, mirror `[]` / `""` (today's exact values,
     assertion 9); if exactly one entry remains, mirror that entry's key and
     list; if two or more remain, mirror `[]` / `""`.
   - Keep the existing tempfile + `os.replace` write (assertion 10). Do not
     switch to `_atomic_write_json` — it is a behaviour-neutral refactor that
     would enlarge this diff for no assertion.

   Comment the mirror block: it exists for readers outside this fix's scope
   (`skills/observability/api/src/readers/resolverState.ts`,
   `skills/observability/ui/src/api/client.ts`) and is **derived, never
   authoritative** — mirroring the wording INFRA-281 used for the
   `current_story` mirror.

6. Update `_record_checkpoint_step`'s docstring: describe the keyed store, the
   per-key idempotency, the scoped terminal removal, the derived mirrors, and
   the legacy read/upgrade path. Keep the existing CER-077 precedence-chain
   prose intact — it is still accurate and still load-bearing.

7. Do **not** change `cmd_record_checkpoint_step`'s signature, options, or exit
   codes. No new CLI option is introduced: the phase key already comes in via
   `--phase-key` (INFRA-265), which is the whole premise of this story.

### Part B — resolver read (`next_action.py`, `infer_position`)

8. Inside the existing checkpoint block (~897–930) and inside its existing
   `try/except Exception: pass`, compute the active phase key first (the current
   `Path(active_phase_file).stem` / strip-`phase-` derivation, hoisted above the
   branch), then:

   - if `raw_state.get("checkpoint_steps")` is a dict → set `checkpoint_step` to
     that dict's entry for the active key, filtered to `str` members, defaulting
     to `[]` (assertions 14–15). The CER-083 stamp comparison is **skipped** on
     this path — keying by the active phase makes it structurally unnecessary.
   - else → run today's code path unchanged: read the flat list, then apply the
     CER-083 stamp check that clears it on mismatch (assertion 16).

   Do not import from `flex_build` (that would invert the dependency — the
   import already runs the other way, `flex_build` imports
   `_CHECKPOINT_SEQUENCE` from `next_action`). Duplicate the ~6-line keyed read
   inline rather than sharing the helper.

9. Update the `next_action.py` module docstring where it describes
   `checkpoint_step` (~42–43 and ~85–94) to state that the keyed record is the
   authority and the flat-key + stamp path is the legacy fallback, and that this
   module still never writes either. Leave `SCHEMA_VERSION` at `3` and
   `resolve_next_action` untouched (assertion 18).

### Part C — tests

10. Extend `tests/pairmode/test_record_checkpoint_step.py` with, at minimum:
    two-phase coexistence (assertion 1); per-key idempotency, both the no-write
    and the does-write case (assertion 5); scoped terminal removal
    (assertion 7); the full single-phase sequence asserting byte-identical flat
    values at each step (assertion 9); the mirror rules including the
    two-remaining fallback (assertions 11–12); legacy-state read and
    upgrade-on-write (assertions 3–4); the reorder's no-write-on-2-exit
    guarantees (assertion 6 — assert `state.json` bytes are unchanged after a
    bad `--phase-key` and after an ambiguous terminal call); and the named
    interleave regression test (assertion 19). Reuse the file's existing
    `CliRunner` / `tmp_path` helpers and its index-fixture pattern; do not add a
    new fixture framework.

11. Add unit tests for `_read_checkpoint_steps` (assertion 2) in the same file:
    absent key, malformed values (non-dict, non-list value, non-str members),
    legacy with and without a stamp, and keyed. Assert it performs no I/O by
    passing a plain dict.

12. Extend `tests/pairmode/test_checkpoint_step.py` for the resolver side
    (assertions 14–17): keyed record read for the active phase; two phases
    resolving independently; keyed record present but active phase absent → `[]`;
    the legacy CER-083 cp99→phase-100 scenario still clearing on a stamp
    mismatch; malformed `state.json` still yielding `[]`. Reuse that file's
    existing `infer_position` fixture pattern. Assert `SCHEMA_VERSION == 3` still
    holds (the file already does).

13. If `tests/pairmode/test_next_action.py` or
    `tests/pairmode/test_checkpoint_routing.py` need a keyed-state case to prove
    routing is unaffected, add it there; otherwise leave both untouched. Do not
    migrate existing fixtures to the keyed shape — leaving them on the flat shape
    is the suite's standing regression test for read compatibility, exactly as
    `resolver_fixtures.py` is for INFRA-282.

### Part D — documentation and backlog

14. Add the architecture paragraph (assertion 20), amend the two state-ownership
    rows and add the third (assertion 21), and extend the `state.json` schema
    listing (assertion 22). Follow the surrounding prose style: bolded lead
    label, ticket reference, rationale stated next to the rule. Do not
    restructure § Pairmode build loop or renumber its steps.

15. Append the `**INFRA-283 (Phase 109) — item (4) resolved:** …` note to the
    `CER-095` Finding cell and amend the "item (4) … remains open" sentence to
    record full closure of all four items (assertion 23). Copy the exact format
    of the INFRA-280/281/282 notes already in that cell. Escape literal pipes as
    `\|`. Do not reword the original finding, do not move the row, do not change
    the phase cell.

### Notes

16. **Accepted limitation — the read-modify-write window.** Two
    `record-checkpoint-step` calls that interleave between their state read and
    their `os.replace` can still lose one update, and this story's keyed record
    does not change that. Atomic replacement guarantees no reader sees a
    truncated file and no corrupt state is written; it does not serialise
    concurrent RMW. This is deliberate and deferred: file-level serialisation of
    `.companion/` writers is INFRA-285's advisory state lock (CER-097), and
    pre-empting it here would create a second, competing locking scheme. State
    the limitation in the architecture paragraph from assertion 20 — do not
    leave it implicit. (Identical treatment to INFRA-282's instruction 17.)

17. **Ideology note (Step 4a, resolved inline).** Three entries in
    `docs/ideology.md` shaped this spec. *"Never silently pass contradictions"*
    is the constraint the whole story serves: a checkpoint that records another
    phase's security gate as its own — the interleave in § Context — is a
    contradiction passing unnoticed through the one mechanism whose job is to
    catch them, and its "silent bypass is never permitted" rationale is why
    instruction 16 requires the residual RMW window to be **written down**.
    *"We prefer rationale-bearing decisions over bare rules"* is why assertions
    12 and 20 and the comments demanded in instructions 2 and 5 all require the
    *reason* beside the rule — especially the mirror block, where a bare
    "mirror, don't read" reads like redundancy to the next agent and would be
    "simplified" back into the single-slot bug. *"Sidebar owns all state
    writes"* is respected: this story adds no writer. `record-checkpoint-step`
    already owns `checkpoint_step`/`checkpoint_phase` per the state-ownership
    table, and the resolver stays pure-read on both the keyed and legacy paths
    (assertion 17), so the hook-as-thin-relay boundary is untouched. No conflict
    required routing around.

18. **Do not** touch `skills/observability/` (assertion 13),
    `_CHECKPOINT_SEQUENCE`, `SCHEMA_VERSION`, or `resolve_next_action`
    (assertion 18). If a resolver test appears to need a routing change, the
    keyed read is wrong — fix `infer_position`, not the caller.

19. **Spec-preflight note.** The identifiers `checkpoint_steps` /
    `_CHECKPOINT_STEPS_KEY` / `_read_checkpoint_steps` named above do not exist
    in the codebase yet — they are **created by this story**. A spec-preflight
    finding against them is expected and intentional.

## Tests

Targeted, then full:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_record_checkpoint_step.py \
  tests/pairmode/test_checkpoint_step.py \
  tests/pairmode/test_checkpoint_routing.py \
  tests/pairmode/test_next_action.py -q 2>&1 | tail -30
```

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Run the full suite **without `-x`**, so a known pre-existing failure cannot mask
a real one.

**Acceptance:**

- The targeted run is fully green.
- The full-suite result is unchanged from clean `HEAD`: green except any known
  pre-existing failure (e.g.
  `test_observability_ui.py::test_ui_build_emits_dist_index_html`), which must
  be shown to reproduce on clean `HEAD` if it appears.
- `git diff main -- skills/observability/` is empty (assertion 13).

Also exercise the CLI directly, as a live check that the public surface did not
move:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
  record-checkpoint-step --help ; echo "exit=$?"
```

`--phase-key` must appear in the help output, no new option may appear, and the
command must exit 0.

## Out of scope

- **The other three CER-095 items** — resolver in-flight claim (INFRA-280),
  story-keyed `current_stories` (INFRA-281), story-keyed attempt counter
  (INFRA-282). All three are complete; this story reads their precedent but
  changes none of their code.
- **effort.db concurrency** — WAL, `busy_timeout`, atomic attempt-number
  derivation and sweep ownership are INFRA-284 (CER-096).
- **A lock or advisory-lease protocol for `.companion/` writers** — INFRA-285
  (CER-097). See instruction 16: this story delivers atomic *replacement*, not
  serialised read-modify-write. It also does not touch
  `hooks/session_start.py`'s context-counter reset or `user_turn_seq.py`'s
  non-atomic whole-state rewrite, both of which are CER-097's territory and both
  of which can still clobber the keyed record this story adds.
- **Merge robustness / return-code checks** on `merge-story-worktree` —
  INFRA-286 (CER-098).
- **Changing the checkpoint sequence itself** — `_CHECKPOINT_SEQUENCE`, the four
  step IDs, the worker each maps to, the pre-checkpoint guards, and
  `checkpoint-report` are all unchanged. This story changes where step state is
  *stored*, not what the sequence *is*.
- **Making `resolve_next_action` emit checkpoint actions for more than one phase
  concurrently.** The resolver still resolves exactly one active phase per call;
  this story ensures a second phase's recorded progress *survives*, which is the
  storage prerequisite for concurrent phase checkpoints, not the routing for
  them. Multi-phase routing, if ever wanted, is a separate resolver story.
- **Migrating existing `state.json` files.** Legacy state is read as-is and
  upgraded on the next write. A one-shot migration would be a state write from a
  code path that has no business writing.
- **Surfacing per-phase checkpoint progress in observability** — the SPA and
  `resolverState.ts` keep reading the flat mirror; a per-phase view is an
  OBS-rail concern.
- **`resolve_current_phase` / `_active_phase_candidates` ambiguity semantics** —
  INFRA-265 settled these and this story consumes them unchanged.

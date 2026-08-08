---
id: INFRA-444
rail: INFRA
title: Invalidate recorded gate verdict when story spec is revised after recording
status: complete
phase: "146"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_next_action.py
  - docs/architecture.md
narrative_roles: []
---

<!-- Scope note: the scaffold deliberately omits `primary_files:` for draft
     stories (story_new.py, INFRA-370), so this story's declared write scope is
     carried entirely by `touches:` above — the two edited scripts, their two
     conventional test files, and architecture.md for the one-line behaviour
     note in Instructions step 5. -->

## Context

`state.json["gate_verdict"][story_id]` is the durable evidence Row 4b of
`resolve_next_action` uses to route a judged-gate-tripped story without
re-spawning the gate worker (INFRA-341's livelock fix). That evidence is only
ever cleared by `_clear_gate_verdict` (`flex_build.py`), which fires on
`merge-story-worktree` and `discard-story-worktree` — neither of which happens
when a story's spec is revised in place and re-attempted. A story whose
`## Ensures` were rewritten after a `clean` verdict was recorded therefore
routes straight to `spawn-builder` on a verdict that judged a spec that no
longer exists. That is exactly the "never silently pass contradictions"
constraint being violated by a stale record. CER-239 / F4 of
`docs/release-0-4-1-findings-20260807.md`.

## Requires

None — independent of INFRA-442 and INFRA-443. `_clear_gate_verdict`
(`flex_build.py`), `cmd_record_gate_verdict` (`flex_build.py`), and
`infer_position`'s section 8 gate-verdict read (`next_action.py`) all exist
and are the only touched surfaces.

## Ensures

A gate verdict recorded for a story is trusted by `infer_position` only while
the story file's content is byte-identical to what it was when the verdict was
recorded: after any edit to the story file, `infer_position(...)["gate_verdict"]`
is `None` and `resolve_next_action` re-emits `spawn-gate-worker`, while an
unedited story keeps routing through `route_gate_verdict` exactly as it does
today. Forbidden proxy: a warning or meta note about a possibly-stale verdict
while the stale verdict is still returned and routed on.

## Instructions

1. In `next_action.py`, add a small public helper `story_content_hash(path) ->
   str | None` returning the SHA-256 hexdigest of the story file's bytes, or
   `None` when it cannot be read. `flex_build.py` imports it (it already
   imports `parse_worker_verdict_json` from this module) — one definition, no
   second copy, so the recorder and the reader can never disagree about the
   hash.
2. In `cmd_record_gate_verdict`, alongside the existing
   `state["gate_verdict"][story_id]` write, record the hash of the story file
   resolved by `_story_path(story_id, project_path)` into a **sibling** map:
   `state["gate_verdict_story_hash"][story_id]`. It must be a sibling map, not
   a key inside the verdict map — `gate_verdict.validate_verdict_map` rejects
   any key outside `JUDGED_GATES`. When the story file is unreadable, write no
   hash entry (and remove any existing one for that story_id). Both writes go
   through the single existing `_atomic_write_json` call; exit code stays 0
   unconditionally.
3. In `next_action.py`'s section-8 read, after loading a candidate verdict map,
   apply this trust rule in order, inside the existing
   `try/except Exception: pass` fail-open block:
   - current hash of `next_story_file` is `None` (unreadable) → trust the
     recorded verdict (unchanged behaviour; prevents a re-gate loop on a file
     neither side can hash);
   - else no recorded hash for this story_id → distrust (`gate_verdict = None`);
   - else recorded hash != current hash → distrust;
   - else trust.
   The distrust path sets `gate_verdict` to `None` only — it does not write
   state (this module stays pure-read) and does not add an action or meta key.
   The "no recorded hash" case is fail-closed on purpose: verdicts written
   before this story shipped cost one extra gate-worker run and then self-heal.
4. Extend `_clear_gate_verdict` to pop `story_id` from
   `state["gate_verdict_story_hash"]` as well, writing back when either map
   changed, so merge/discard leave no orphan hash behind.
5. Append the new key and the trust rule to `docs/architecture.md`'s existing
   `next_action.py` entry (the INFRA-341 clause), in one sentence.
6. Tests: add the regression case in `## Tests` to
   `tests/pairmode/test_next_action.py` next to
   `TestGateVerdictOnceOnlyRoundTrip` (reuse `_write_index`/`_write_phase`/
   `_write_story`/`_patch_git_log` and the `CliRunner` invocation of
   `cmd_record_gate_verdict` that class already uses), plus a control case
   proving an *unedited* story still routes via the recorded verdict. Add a
   case to `tests/pairmode/test_flex_build.py` (beside
   `test_merge_story_worktree_clears_gate_verdict`) asserting the hash entry is
   cleared on merge.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py tests/pairmode/test_flex_build.py -q
```

The regression case must reproduce the real failure mode end to end: record a
verdict via `cmd_record_gate_verdict` for a judged-gate story, assert
`infer_position` trusts it (`resolve_next_action` does not emit
`spawn-gate-worker`), then rewrite that story file's body, then assert a fresh
`infer_position` returns `gate_verdict is None` and `resolve_next_action`
re-emits `SPAWN_GATE_WORKER`.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green.

## Out of scope

- Invalidating any other recorded per-story state on spec revision
  (`pre_build_intent_review`, attempt counters, permissions artifacts) — this
  story fixes only the gate verdict; the broader orphan-state sweep is
  INFRA-442/INFRA-443's surface.
- Any new CLI subcommand or action-grammar change: no new `ACTIONS` member, no
  `SCHEMA_VERSION` bump, no change to `route_gate_verdict`'s aggregation.
- Detecting revisions of files the story merely references (phase doc, era doc)
  — only the story file's own content is hashed.

## Evidence

Covered-contracts gate (INFRA-317): `next_action.py` is in `primary_files`/
`touches` and is covered by the `## Module structure::skills/pairmode/scripts/next_action.py`
pair. Both the doc section and the source file were read in full before any
edit. Relied-on contract lines from `docs/architecture.md` § Module structure
(the `next_action.py` bullet, pre-existing INFRA-341 clause):

> `infer_position` gains `gate_verdict` (`dict[str, str] | None`, read from
> `state.json["gate_verdict"][next_story_id]`, mirrors `pre_build_intent_verdict`'s
> fail-open read shape exactly); Row 4b now calls
> `route_gate_verdict(position["gate_verdict"], next_story_id, meta_base=meta)`
> ... whenever a verdict has been recorded, falling back to (re-)emitting
> `spawn-gate-worker` (unchanged) only when none has; `flex_build.py
> record-gate-verdict` is the new CLI writer ... then persists to
> `state.json["gate_verdict"][story_id]` via `_atomic_write_json`);
> `merge-story-worktree`/`discard-story-worktree` both clear the recorded
> verdict for their story_id, mirroring the existing attempt-counter/active-
> story/permissions clears; grammar-unchanged (no new action type, no
> `ACTIONS`/`_SPAWN_ACTIONS` membership change, no `SCHEMA_VERSION` bump)

No divergence found between the doc and the source (`next_action.py`'s
section-8 read and `flex_build.py`'s `cmd_record_gate_verdict`/
`_clear_gate_verdict` matched the documented shape exactly). This story
appends a new sentence to the same bullet, in place, rather than changing the
quoted contract — see `docs/architecture.md` § Module structure, the
sentence beginning "2026-08-08 INFRA-444:".

---
id: RESOLVER-002
rail: RESOLVER
title: Position-inference read-model (DP3, DP5)
status: complete
phase: "HARNESS001-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_next_action.py
touches:
---

## Context

The read-model half of `next-action` (agreements `HARNESS001-main.md` DP3 + DP5):
reconstruct **"where are we"** entirely from existing durable state, with **no
private persisted state** (the DP7 invariant — if this story finds it needs
authoritative private state, STOP and escalate, do not invent a marker file).

DP5 binds the implementation: `next_action.py` is a **thin read-model that composes
the existing modules as a library** — import their functions, never shell out, never
duplicate their logic, never change their signatures. Where the needed logic is
**buried in a `flex_build.py` click-command body**, extract it to a module-level
function (pure refactor, signature-preserving) and have the command call the
extraction. Recon of the current surface (already importable vs. buried):

- **Already importable** — `next_story.find_next_story(phase_file, project_dir) ->
  dict | None` (git-commit-authoritative over the table status); `story_resolver.
  resolve_story` / `list_phase_stories`; `model_selector.select_builder_model(...)`
  (and the reviewer/auditor/intent selectors).
- **Buried in CLI command bodies — extract, signature-preserving:**
  - `cmd_current_phase` (active phase file; the exit-1 = all-phases-complete branch)
    → `resolve_current_phase(project_dir) -> Path | None`.
  - `cmd_read_attempt_count` → `read_attempt_count(story_id, project_dir) -> int`
    (0 when absent/mismatched, per the current command).
  - the gate commands `check-auth-gate` / `check-schema-gate` / `check-stub` →
    module-level functions returning a structured pass/blocked result; the commands
    keep their exact exit-code behaviour by wrapping the extraction.

Extractions must not alter the CLI: same command names, same flags, same exit codes,
same stdout. The **CLI-surface freeze test (RELEASE-003) must stay green** — adding an
importable helper and calling it from the command changes no surface.

## Requires

- RESOLVER-001 complete: `next_action.py` exists with the grammar layer
  (`make_action`, `validate_action`, the action constants).

## Ensures

- `next_action.py` gains a pure-read position-inference layer that, given a project
  dir, returns a single structured **Position** (dict or dataclass) carrying at least:
  active phase file (or `None` when all phases complete), the next unbuilt story (or
  `None`), the attempt count for that story, the resolved builder model + selection
  reason (or a `prompted-upgrade` marker), the three gate signals, and the inferred
  last-attempt outcome. Name it consistently (e.g. `infer_position(project_dir)`).
- The Position is computed **purely by reading durable state** — phase docs, Stories
  tables, story frontmatter, git log (commit-authority), `.companion/attempt_counter.json`,
  `.companion/state.json`, gate exit-code helpers. No file is written by this layer;
  `grep` confirms no `write_text`/`open(...,"w")`/`json.dump` to disk in the read-model.
- Outcome inference matches DP3: **PASS** ⇒ a `story-<ID>` commit exists (reuse
  `find_next_story`'s commit-authority, do not reimplement); **FAIL** ⇒ no commit +
  status still `planned` + attempt counter advanced. The read-model never sees worker
  returns and never distinguishes "builder running vs finished" (consulted only at
  cycle-boundary seams — DP3).
- `flex_build.py` exposes new module-level functions `resolve_current_phase`,
  `read_attempt_count`, and the gate helpers; the corresponding click commands call
  these extractions and are otherwise behaviourally identical.
- `next_action.py` **imports** `next_story`, `story_resolver`, `model_selector`, and
  the `flex_build` extractions as a library; `grep` confirms no `subprocess`/`os.system`
  shelling-out to these CLIs from the read-model.
- No signature of any composed function changes (the dedicated guard lands in
  RESOLVER-004; this story must not break it).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes, including
  the CLI-surface freeze test.

## Instructions

- Add the read-model functions to `next_action.py`; do not yet add the state machine
  or the subcommand (RESOLVER-003) — `infer_position` returns facts, it does not pick
  an action.
- For each extraction in `flex_build.py`: move the decision logic out of the command
  body into a module-level function with a precise signature; replace the body with a
  thin call + the existing `click.echo`/`sys.exit` glue. Confirm the command's exit
  codes are unchanged (e.g. `current-phase` still exits 1 when all phases complete).
- Compose the model decision via `select_builder_model` — do not reimplement the
  selector table. When the selector indicates `prompted-upgrade`, record that in the
  Position (the routing to `await-user:model-upgrade` happens in RESOLVER-003).
- Read gates as **deterministic signals only** — capture blocked/ok, render no verdict
  (DP2/DP4; verdict extraction is HARNESS002).
- If any required fact cannot be derived from durable state without writing new state,
  STOP: this trips the DP7 trip-wire (escalate DP1 → fork), it is not a license to
  persist resolver-private state.

## Tests

`tests/pairmode/test_next_action.py` (new) — unit-test `infer_position` and the
`flex_build.py` extractions against **synthetic durable state** (a tmp project tree
with phase docs + Stories tables, story frontmatter, a fake/seeded git log for
commit-authority, `attempt_counter.json`, `state.json`). Cover at least:

- All-phases-complete ⇒ Position reports no active phase.
- Active phase + unbuilt story + counter 0 ⇒ Position names the story, attempt 0,
  an auto model + reason.
- A committed `story-<ID>` ⇒ outcome inferred PASS (advance).
- No commit + `planned` + counter advanced ⇒ outcome inferred FAIL at the right rung.
- A gate signalling blocked ⇒ Position carries that gate's blocked signal.
- Extraction parity: `resolve_current_phase` / `read_attempt_count` / the gate helpers
  return values consistent with their click commands' observable behaviour.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Mapping a Position to an emitted action (the state machine — RESOLVER-003).
- The `flex_build.py next-action` subcommand (RESOLVER-003).
- Any change to a composed module's signature, or any gate **verdict** (HARNESS002).
- The exhaustive one-assertion-per-DP2-state suite (RESOLVER-004).

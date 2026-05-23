# flex — Phase 39: Context budget check

← [Phase 38: Data quality and portability cleanup](phase-38.md)

## Goal

The pokus project prototyped `scripts/context_budget_check.py` — a script that sums
accumulated phase tokens from `effort.db` and blocks story advancement when a threshold
is exceeded. The intent is to surface the risk of context compaction mid-story before
it silently degrades builder coherence.

The script (and its 6 tests) exist only in pokus. Flex has no equivalent and
`CLAUDE.build.md.j2` has no context budget check step.

Two stories:

1. **Port the script to flex.** Move `context_budget_check.py` into
   `skills/pairmode/scripts/`, convert tests from `unittest` to `pytest`, and place
   them in `tests/pairmode/`.

2. **Add the check to `CLAUDE.build.md.j2`.** Insert a "Context budget check" section
   after Step 3 (Handle the result), before advancing to the next story or checkpoint
   sequence. Regenerate flex's own `CLAUDE.build.md`.

**Story dependencies:** INFRA-104 depends on INFRA-103 (script must exist before the
template references it).

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-103 | Port `context_budget_check.py` to flex pairmode scripts | complete |
| INFRA-104 | Add context budget check step to `CLAUDE.build.md.j2` | complete |

---

### Story INFRA-103 — Port `context_budget_check.py` to flex pairmode scripts

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/context_budget_check.py` does not exist.
- Prototype at `/mnt/work/pokus/scripts/context_budget_check.py` and
  `/mnt/work/pokus/tests/test_context_budget_check.py` are the reference implementation.
- `tests/pairmode/` exists and uses pytest (not unittest).

#### Ensures

`skills/pairmode/scripts/context_budget_check.py` exists with the following behaviour:

- Accepts `--project-dir`, `--phase`, and optional `--threshold` CLI args.
- Resolves `effort.db` path from `.companion/state.json["effort_db_path"]`, falling
  back to `.companion/effort.db`.
- Reads `context_budget_threshold` from `.companion/state.json` when `--threshold`
  is not passed. Threshold priority: `--threshold` > `state.json` > built-in default `120000`.
- Sums `COALESCE(tokens_total, 0)` for all rows in `attempts` where `phase = ?`.
- Prints one machine-parseable line to stdout:
  `context_budget phase=<phase> tokens=<sum> threshold=<n> status=<ok|over>`
- Exit 0 when `status=ok` (sum ≤ threshold).
- Exit 1 when `status=over` (sum > threshold); also prints a human-readable warning to stderr.
- Exit 2 on IO error (missing DB, malformed args).

`tests/pairmode/test_context_budget_check.py` exists with pytest tests covering:
1. `status=ok` when sum < default threshold
2. `status=over` when sum > default threshold
3. `--threshold` arg overrides `state.json` value
4. Missing `context_budget_threshold` key in `state.json` falls back to default 120000
5. Phase filter is exclusive (phase 1 tokens don't count toward phase 2)
6. Exit 2 when `effort.db` is missing

#### Instructions

**`skills/pairmode/scripts/context_budget_check.py`**

Copy the logic from the pokus prototype verbatim. No changes needed to the
script's logic — it has no pairmode imports and is standalone. The only
difference from the prototype is its location (`skills/pairmode/scripts/`
instead of `scripts/`).

**`tests/pairmode/test_context_budget_check.py`**

Convert the 6 unittest cases from the pokus prototype to pytest style:

- Replace `unittest.TestCase` classes with plain functions or a pytest class.
- Replace `setUp`/`tearDown` with a `tmp_path` fixture (pytest provides this).
- Replace `self.assertEqual(x, y)` with `assert x == y`.
- Import path: `sys.path.insert(0, str(Path(__file__).parent.parent.parent /
  "skills" / "pairmode" / "scripts"))` then `from context_budget_check import main`.
- Use the same `_create_db` and `_create_state` helpers from the prototype,
  adapted to take `tmp_path / ".companion"` as the companion dir.

The 6 test cases map directly to the 6 unittest cases in the prototype.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget_check.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All 6 new tests must pass. Full suite must pass.

---

### Story INFRA-104 — Add context budget check step to `CLAUDE.build.md.j2`

**Rail:** INFRA | **story_class:** methodology

#### Requires

- INFRA-103 complete: `skills/pairmode/scripts/context_budget_check.py` exists.
- `CLAUDE.build.md.j2` has a `## Step 3 — Handle the result` section.
- `CLAUDE.build.md.j2` uses `{{ pairmode_scripts_dir }}` for script paths.

#### Ensures

`CLAUDE.build.md.j2` contains a `## Context budget check (between stories)` section
inserted immediately after `## Step 3 — Handle the result` and before the
`## Checkpoint sequence` section.

The section instructs the orchestrator to run the check after every story's PASS or FAIL
handling completes — after permission cleanup and status update, before advancing to the
next story or the checkpoint sequence. The check is **blocking** on exit 1: no further
story may start without a user response.

The section content (adapt from the pokus prototype, updating `scripts/` → `{{ pairmode_scripts_dir }}/`):

```
## Context budget check (between stories)

After every story's PASS or FAIL handling completes — after permission cleanup and status
update for PASS, or after the revert for FAIL — before advancing to the next story or
entering the checkpoint sequence, run:

```bash
PATH=$HOME/.local/bin:$PATH uv run python {{ pairmode_scripts_dir }}/context_budget_check.py \
  --project-dir . \
  --phase <PHASE_ID>
```

Replace `<PHASE_ID>` with the phase identifier from the current story's frontmatter.
The script reads `.companion/effort.db` and `.companion/state.json`
(for `context_budget_threshold`). Threshold priority: `--threshold` arg →
`state.json["context_budget_threshold"]` → built-in default `120000`.

The script prints one machine-parseable line to stdout:
```
context_budget phase=<phase> tokens=<sum> threshold=<n> status=<ok|over>
```

- Exit 0 (`status=ok`): build loop continues normally.
- Exit 1 (`status=over`): **BLOCKING.** Surface the following prompt verbatim and
  wait for user response before spawning any further builder or reviewer:

```
CONTEXT BUDGET EXCEEDED — Story [RAIL-NNN] just completed.
Phase <PHASE_ID> has now accumulated <tokens> tokens of recorded subagent work
(threshold: <threshold>).

Continuing in the current session risks context compaction mid-story, which can
cause the builder to lose coherence and repeat work. Options:

1. **Proceed** — continue building in this session; budget breach acknowledged.
   Say: "Continue building"

2. **Pause for fresh session** — stop here; resume in a new session with a clean
   context window.
   Say: "Continue building" in a fresh session to resume from the next planned story.
```

- Exit 2 (IO error): report to the user and pause; do not silently continue.
```

After editing the template, regenerate flex's own `CLAUDE.build.md`:

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-build --project-dir . --apply --yes
```

#### Instructions

**`skills/pairmode/templates/CLAUDE.build.md.j2`**

Locate the section `## Step 3 — Handle the result` and find where it ends (before the
next `## ` heading, which should be `## Checkpoint sequence`). Insert the full
"Context budget check" section between Step 3 and Checkpoint sequence.

**`CLAUDE.build.md`** (flex's own)

Regenerate via `pairmode_sync sync-build --apply --yes` as shown above.

#### Tests

This story modifies only `CLAUDE.build.md.j2` and the regenerated `CLAUDE.build.md`.
No test file expected.

The reviewer verifies:
1. `CLAUDE.build.md.j2` contains `## Context budget check (between stories)`.
2. `CLAUDE.build.md.j2` references `{{ pairmode_scripts_dir }}/context_budget_check.py`.
3. `CLAUDE.build.md` contains the rendered absolute path (e.g. `/mnt/work/flex/skills/pairmode/scripts/context_budget_check.py`).
4. The section appears after `## Step 3` and before `## Checkpoint sequence`.
5. Full test suite passes.

`TEST RUN: methodology story — no test file expected`

---

Tag: `cp39-context-budget-check` ✓

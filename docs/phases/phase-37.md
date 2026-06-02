---
era: "001"
---

# flex — Phase 37: Builder model-selection tuning + token-direction recording

← [Phase 36: `/flex:pairmode migrate-from-anchor`](phase-36.md)

## Goal

Usage data across seven pairmode projects (343 build attempts, ~10M tokens) shows that
Opus builders retry at the same rate as Sonnet builders (~20% each) while costing 73%
more per story. The current `prompted-upgrade` trigger — any `code` story with ≥ 3
`primary_files` — fires too broadly: stories with 3–4 files get Opus at story-start
despite producing no retry benefit over Sonnet.

Two separate fixes:

1. **Raise the file-count threshold from 3 → 5.** The existing protected-file trigger
   remains unchanged (one protected-file touch still escalates to Opus unconditionally).
2. **Add dynamic builder escalation.** `select_builder_model` currently ignores
   `attempt_number`; the model is fixed at story-start. Matching the reviewer's existing
   retry-upgrade pattern, builders should start on Sonnet and escalate to Opus only when
   a Sonnet attempt fails, not by predicting failure from file-count alone.

A third story fixes effort-DB data quality: the orchestrator only passes `--tokens-total`
to `record_attempt.py`, leaving `tokens_in`, `tokens_out`, `cache_read_tokens`, and
`cache_write_tokens` null for every builder and reviewer row. CLAUDE.build.md is updated
to extract and pass all directional token fields the runtime provides.

**Story dependencies:**

```
INFRA-097 (raise threshold)           — independent
INFRA-098 (builder retry escalation)  — depends on INFRA-097 (touches same files)
INFRA-099 (token-direction recording) — depends on INFRA-098 (final CLAUDE.build.md edit)
```

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-097 | Raise `_CODE_UPGRADE_FILE_COUNT` from 3 → 5 | complete |
| INFRA-098 | Add `attempt_number` to `select_builder_model` (dynamic builder escalation) | complete |
| INFRA-099 | Extend CLAUDE.build.md token recording to capture per-direction counts | complete |

---

### Story INFRA-097 — Raise `_CODE_UPGRADE_FILE_COUNT` from 3 → 5

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/model_selector.py` — `_CODE_UPGRADE_FILE_COUNT = 3` at line 126.
- `tests/pairmode/test_model_selector.py` — `TestSelectBuilderModel` class with tests for
  the 3-file boundary.
- `CLAUDE.build.md` — decision table at § Model evaluation lists `< 3 primary_files`.

#### Ensures

`_CODE_UPGRADE_FILE_COUNT` is raised to 5.  The decision table in `CLAUDE.build.md` is
updated to reflect the new boundary.  Tests are updated so that:

- 1, 2, 3, 4 `primary_files` with no protected file → `sonnet` / `auto-baseline`
- 5+ `primary_files` → `opus` / `prompted-upgrade`
- Protected-file trigger behaviour is unchanged (one protected touch → `opus` regardless of count)

#### Instructions

**`skills/pairmode/scripts/model_selector.py`**

Change:
```python
_CODE_UPGRADE_FILE_COUNT = 3
```
to:
```python
_CODE_UPGRADE_FILE_COUNT = 5
```

No other logic changes.  The docstring decision table in `select_builder_model` already uses
`_CODE_UPGRADE_FILE_COUNT` by reference in the code comment; update the inline comment if
it hardcodes the number `3`.

**`tests/pairmode/test_model_selector.py`** — `TestSelectBuilderModel`

Replace the 3-file and 4-file upgrade tests with sonnet/auto-baseline assertions:

```python
def test_code_three_files_no_protected_returns_sonnet(self) -> None:
    files = ["a.py", "b.py", "c.py"]
    model, reason = select_builder_model("code", files, _NO_PROTECTED)
    assert model == MODEL_SONNET
    assert reason == REASON_AUTO_BASELINE

def test_code_four_files_no_protected_returns_sonnet(self) -> None:
    files = ["a.py", "b.py", "c.py", "d.py"]
    model, reason = select_builder_model("code", files, _NO_PROTECTED)
    assert model == MODEL_SONNET
    assert reason == REASON_AUTO_BASELINE

def test_code_five_files_no_protected_returns_opus_prompted(self) -> None:
    files = ["a.py", "b.py", "c.py", "d.py", "e.py"]
    model, reason = select_builder_model("code", files, _NO_PROTECTED)
    assert model == MODEL_OPUS
    assert reason == REASON_PROMPTED_UPGRADE

def test_code_six_files_returns_opus_prompted(self) -> None:
    files = ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"]
    model, reason = select_builder_model("code", files, _NO_PROTECTED)
    assert model == MODEL_OPUS
    assert reason == REASON_PROMPTED_UPGRADE
```

The existing `test_code_three_files_no_protected_returns_opus_prompted` and
`test_code_four_files_returns_opus_prompted` tests must be renamed/replaced as shown
above — do not leave both the old and new versions.

The `unknown_class_three_files_returns_opus` test must also be updated to return
`sonnet` (since unknown defaults to code, and 3 < 5).

**`CLAUDE.build.md`** — § Model evaluation decision table

Update the `code` row:

| Before | After |
|--------|-------|
| `code \| < 3 primary_files AND no protected file \| sonnet \| auto-baseline` | `code \| < 5 primary_files AND no protected file \| sonnet \| auto-baseline` |
| `code \| ≥ 3 primary_files OR protected file in touches \| opus \| prompted-upgrade` | `code \| ≥ 5 primary_files OR protected file in touches \| opus \| prompted-upgrade` |

Also update the example snippet in the same section if it hardcodes the number `3`.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_model_selector.py -x -q
```

All `TestSelectBuilderModel` tests must pass.  The four new boundary tests
(3-file sonnet, 4-file sonnet, 5-file opus, 6-file opus) must all be present and green.

---

### Story INFRA-098 — Add `attempt_number` to `select_builder_model`

**Rail:** INFRA | **story_class:** code

#### Requires

- INFRA-097 complete: `_CODE_UPGRADE_FILE_COUNT = 5` in `model_selector.py`.
- `select_builder_model` signature has no `attempt_number` parameter.
- `CLAUDE.build.md` § Model evaluation calls `select_builder_model` with 3 positional args.

#### Ensures

`select_builder_model` accepts an optional `attempt_number: int = 1` parameter.  For
`attempt_number >= 2` on `code` (and unknown-defaulting-to-code) stories, it returns
`(MODEL_OPUS, "retry-upgrade")`.  Doc/lesson/methodology classes are unaffected by
`attempt_number`.

A new exported constant `REASON_RETRY_UPGRADE = "retry-upgrade"` is added to
`model_selector.py` alongside the other `REASON_*` constants.

`CLAUDE.build.md` is updated in two places:
1. The model evaluation `python -c` snippet passes `attempt_number` to
   `select_builder_model`.
2. The **Attempt 1 FAIL — auto-retry** section instructs the orchestrator to
   re-call `select_builder_model(attempt_number=2)` before spawning the retry
   builder, and to record the resulting model and reason.

The decision table in § Model evaluation gains a new row for the retry path:

| story_class | complexity signal | attempt | builder model | reason |
|---|---|---|---|---|
| `code` | any | ≥ 2 | opus | `retry-upgrade` |

#### Instructions

**`skills/pairmode/scripts/model_selector.py`**

1. Add the constant after `REASON_USER_OVERRIDE`:
```python
REASON_RETRY_UPGRADE = "retry-upgrade"
```

2. Update `select_builder_model` signature and body:

```python
def select_builder_model(
    story_class: str,
    primary_files: list[str],
    protected_files: list[str],
    attempt_number: int = 1,
) -> tuple[str, str]:
```

After the existing normalisation block and before the `_HAIKU_CLASSES` check,
add the retry-escalation path for code stories:

```python
    # Retry escalation: code stories on attempt >= 2 always use opus.
    # doc/lesson/methodology classes never escalate (mirrors reviewer behaviour).
    if attempt_number >= 2 and story_class == "code":
        return (MODEL_OPUS, REASON_RETRY_UPGRADE)
```

Place this block AFTER the `story_class` normalisation (so unknown classes default
to "code" and inherit the escalation) but BEFORE the `_HAIKU_CLASSES` check.

Update the docstring decision table inside `select_builder_model` to include the
`attempt_number` column:

```
  story_class   attempt   complexity signal                         model   reason
  -----------   -------   -----------------                         -----   ------
  doc           any       any                                       haiku   auto-downgrade
  lesson        any       any                                       haiku   auto-downgrade
  methodology   any       any                                       sonnet  auto-baseline
  code          1         <5 primary_files AND no protected file    sonnet  auto-baseline
  code          1         ≥5 primary_files OR protected file        opus    prompted-upgrade
  code          ≥2        any                                       opus    retry-upgrade
```

**`tests/pairmode/test_model_selector.py`**

Add `REASON_RETRY_UPGRADE` to the import block.

Add a new inner class `TestSelectBuilderModelRetry` (or equivalent) with cases:

```python
class TestSelectBuilderModelRetry:
    def test_code_attempt2_escalates_to_opus(self) -> None:
        model, reason = select_builder_model("code", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_code_attempt3_escalates_to_opus(self) -> None:
        model, reason = select_builder_model("code", [], _NO_PROTECTED, attempt_number=3)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_code_attempt2_overrides_file_count_signal(self) -> None:
        # Even a 1-file story escalates on retry — attempt_number beats file count.
        model, reason = select_builder_model("code", ["a.py"], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_doc_attempt2_stays_haiku(self) -> None:
        model, reason = select_builder_model("doc", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_HAIKU
        assert reason == REASON_AUTO_DOWNGRADE

    def test_methodology_attempt2_stays_sonnet(self) -> None:
        model, reason = select_builder_model("methodology", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_unknown_class_attempt2_escalates(self) -> None:
        # Unknown defaults to code — should escalate.
        model, reason = select_builder_model("unknown", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_attempt1_default_unchanged(self) -> None:
        # attempt_number=1 is the default; existing behaviour must not change.
        model, reason = select_builder_model("code", [], _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE
```

**`CLAUDE.build.md`** — two edits:

*Edit 1: § Model evaluation — python snippet*

Add `attempt_number=1` (or the current value) to the `select_builder_model` call:

```python
model, reason = select_builder_model(story_class, primary_files, protected_files,
                                     attempt_number=1)
```

Extend the decision table with a new row for the retry path (above the `user-override` row):

| story_class | complexity signal | attempt | builder model | reason | action |
|---|---|---|---|---|---|
| `code` | any | ≥ 2 | opus | `retry-upgrade` | auto (no prompt) |

*Edit 2: § Handle the result — Attempt 1 FAIL — auto-retry*

After the sentence "Re-spawn the builder (attempt 2) immediately — no user pause",
add:

> Before spawning the retry builder, re-call `select_builder_model` with
> `attempt_number=2`.  For `code` stories this returns `opus` / `retry-upgrade`.
> Pass the escalated model to the builder Agent tool and record
> `--model-selection-reason retry-upgrade` in the attempt row.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_model_selector.py -x -q
```

All existing and new `TestSelectBuilderModel*` tests must pass.

---

### Story INFRA-099 — Extend CLAUDE.build.md token recording to capture per-direction counts

**Rail:** INFRA | **story_class:** methodology

#### Requires

- INFRA-098 complete: `CLAUDE.build.md` updated with retry-escalation instructions.
- `record_attempt.py` already accepts `--tokens-in`, `--tokens-out`,
  `--cache-read-tokens`, `--cache-write-tokens` (verified at spec time — CLI flags exist).
- Current CLAUDE.build.md `<usage>` block extraction uses only `total_tokens`,
  `tool_uses`, `duration_ms`.

#### Ensures

`CLAUDE.build.md` instructs the orchestrator to extract all available token fields
from the Agent tool `<usage>` block and pass them to `record_attempt.py`.

The `<usage>` block description is updated to document the full set of fields the
Claude Code runtime may emit (the orchestrator must treat absent fields as optional):

```
<usage>total_tokens: N
input_tokens: I
output_tokens: O
cache_read_tokens: CR
cache_write_tokens: CW
tool_uses: M
duration_ms: K</usage>
```

Both `record_attempt.py` invocation examples (builder and reviewer) are updated to
include the four directional flags, with inline comments noting they are passed only
when the runtime provides them:

```bash
PATH=$HOME/.local/bin:$PATH uv run python .../record_attempt.py \
  --story-file docs/stories/RAIL/RAIL-NNN.md \
  --agent-role builder \
  --model claude-sonnet-4-6 \
  --attempt-number 1 \
  --tokens-total 38000 \
  --tokens-in 30000 \       # omit flag if runtime did not emit input_tokens
  --tokens-out 8000 \       # omit flag if runtime did not emit output_tokens
  --cache-read-tokens 0 \   # omit flag if runtime did not emit cache_read_tokens
  --cache-write-tokens 0 \  # omit flag if runtime did not emit cache_write_tokens
  --tool-uses 11 \
  --duration-ms 187000 \
  --model-selection-reason auto-baseline \
  --project-dir .
```

The prose introduction before the `<usage>` block gains a sentence:

> If the runtime provides `input_tokens`, `output_tokens`, `cache_read_tokens`, or
> `cache_write_tokens` in the `<usage>` block, extract them and pass the corresponding
> flags to `record_attempt.py`.  Omit any flag whose value is absent from the block —
> the CLI treats missing flags as NULL, which is correct for runtimes that do not yet
> emit the full breakdown.

#### Instructions

Locate the `<usage>` block description in § Build loop — Step 1 and § Build loop —
Step 2 of `CLAUDE.build.md`.  Make the following edits:

1. Replace the `<usage>` block format example (appears once, referenced by both steps)
   with the extended version showing all six fields as optional beyond `total_tokens`.

2. Update the prose sentence "Extract `total_tokens`, `tool_uses`, and `duration_ms`
   from those three fields" to read:
   "Extract `total_tokens`, `tool_uses`, and `duration_ms` from the block.  If the
   runtime also emits `input_tokens`, `output_tokens`, `cache_read_tokens`, or
   `cache_write_tokens`, extract those as well."

3. Update both `record_attempt.py` example invocations (builder in Step 1, reviewer
   in Step 2) to include the four directional flags with the inline comments shown
   above.

Do not change any other part of CLAUDE.build.md.  This story does not touch Python
files or tests.

#### Tests

This story modifies only `CLAUDE.build.md` (a methodology file).  No test file is
expected.  The reviewer verifies:

1. The `<usage>` block format example is present and includes all six fields.
2. Both `record_attempt.py` invocations include `--tokens-in`, `--tokens-out`,
   `--cache-read-tokens`, `--cache-write-tokens`.
3. The prose update (omit-if-absent note) is present.
4. No Python logic was modified.

`TEST RUN: methodology story — no test file expected`

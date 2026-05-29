# flex — Phase 46: Local model infrastructure

← [Phase 45: Deterministic orchestrator offload](phase-45.md)

## Goal

The companion sidebar makes LLM calls after every assistant response to extract
decisions from the live transcript, check conflicts against the spec, and validate
file writes against non-negotiables. These narrow, repetitive tasks — structured
JSON extraction against a fixed schema — are candidates for local model routing via
Ollama, reducing per-session API cost when an operator opts in.

**Architecture clarification:** The existing `call_claude` in `sidebar.py` uses
`claude_agent_sdk` (OAuth / Claude CLI subprocess) — not `anthropic.Anthropic()`.
There is no `ANTHROPIC_API_KEY` in this system. The "anthropic" backend is the
`claude_agent_sdk` path; it remains the default and is preserved exactly. Ollama
is added as an additive new path via `FLEX_MODEL_BACKEND=ollama`.

**Design constraints:**
- `sidebar.py` is a protected file. Modifications are declared in each story that
  touches it.
- Local model routing must be opt-in via environment variable. The default backend
  is `anthropic` (claude_agent_sdk path) and nothing changes for users who do not
  set `FLEX_MODEL_BACKEND`.
- Plan-impact analysis is complex and high-stakes; it is hardcoded to the
  `_call_anthropic` path regardless of `FLEX_MODEL_BACKEND`.
- Tests must not require Ollama to be running.

**Four stories:**

| ID | Title | Status |
|----|-------|--------|
| INFRA-120 | `call_model.py` — Ollama HTTP client | planned |
| INFRA-121 | Wire `sidebar.py` to Ollama backend | planned |
| INFRA-122 | Fallback for extraction / conflict / spec call sites + plan-impact hardening | planned |
| INFRA-123 | `backend` column in effort DB | planned |

**Story dependencies:** INFRA-121 depends on INFRA-120. INFRA-122 depends on
INFRA-121. INFRA-123 is independent (touches `effort_db.py` and
`effort_recorder.py`, not `sidebar.py`) and can be built in any order relative
to the others.

---

## Stories

### Story INFRA-120 — `call_model.py`: Ollama HTTP client

**Rail:** INFRA | **story_class:** code

#### Requires

- No local model infrastructure exists in the codebase.
- `sidebar.py:364` contains `call_claude(...)` which uses `claude_agent_sdk`
  (OAuth / Claude CLI subprocess). There is no `anthropic.Anthropic()` call
  anywhere in `sidebar.py`; the "anthropic" backend IS `claude_agent_sdk`.
- No `call_model.py` exists.

#### Ensures

**`skills/pairmode/scripts/call_model.py`** (new file)

1. Defines a single public function:
   ```python
   def call_ollama(
       prompt: str,
       system: str,
       model: str,
       *,
       base_url: str = "http://localhost:11434",
       timeout: int = 10,
   ) -> str | None:
   ```
   Returns the response text, or `None` on failure.

2. POSTs to `{base_url}/api/chat` with body:
   ```json
   {
     "model": "<model>",
     "messages": [
       {"role": "system", "content": "<system>"},
       {"role": "user", "content": "<prompt>"}
     ],
     "stream": false
   }
   ```

3. Parses and returns `response.json()["message"]["content"]` on HTTP 200.

4. Returns `None` and prints a warning to stderr on:
   - `requests.RequestException` (connection refused, timeout, etc.)
   - Non-200 HTTP status code

5. No side effects, no global state, no file I/O. No anthropic SDK.

**`requirements.txt`** (companion skill — `skills/companion/requirements.txt`)

6. `requests` is added if not already present. Check before adding.

**`tests/pairmode/test_call_model.py`** (new file)

7. `test_ollama_posts_correct_json_body` — mock `requests.post`; call
   `call_ollama("hello", "sys", "llama3.1:8b")`; assert POST body has
   `model`, `messages` (system + user), and `stream=false`.

8. `test_ollama_returns_message_content` — mock `requests.post` returning
   `{"message": {"content": "ok"}}`; assert return value is `"ok"`.

9. `test_ollama_custom_base_url` — pass `base_url="http://gpu-box:11434"`;
   assert the POST URL uses the custom base.

10. `test_ollama_returns_none_on_connection_error` — mock `requests.post` to
    raise `requests.exceptions.ConnectionError`; assert return value is `None`.

11. `test_ollama_returns_none_on_non_200` — mock `requests.post` returning
    status 503; assert return value is `None`.

#### Instructions

1. Create `skills/pairmode/scripts/call_model.py` with `call_ollama` above.
2. Check `skills/companion/requirements.txt` for `requests`; add if absent.
3. Create `tests/pairmode/test_call_model.py` with tests 7–11 using
   `unittest.mock.patch`.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_call_model.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-121 — Wire `sidebar.py` to Ollama backend

**Rail:** INFRA | **story_class:** code

**Protected file justification:** `sidebar.py` is modified to add an optional
Ollama routing layer. The existing `call_claude` function (which uses
`claude_agent_sdk` via OAuth) is renamed to `_call_anthropic` and preserved
exactly — all internals, closures, and error handling are unchanged. A new
public `call_claude` dispatches to either `_call_anthropic` (default) or
`call_ollama` (opt-in). This reduces per-session API cost when
`FLEX_MODEL_BACKEND=ollama` is set; default behavior is identical for all
users who do not set it.

#### Requires

- INFRA-120 complete: `skills/pairmode/scripts/call_model.py` exists with
  `call_ollama(prompt, system, model, *, base_url, timeout)`.
- `sidebar.py:364` has `call_claude(prompt, system, model, timeout)` using
  `claude_agent_sdk.query()` with `ClaudeAgentOptions`.
- `sidebar.py:117–123` adds `_REPO_ROOT` to `sys.path` and imports from
  `skills.pairmode.scripts.*`.
- `sidebar.py:1472` has startup diagnostics checking `CLAUDE_CODE_OAUTH_TOKEN`
  and `shutil.which("claude")`.

#### Ensures

**`skills/companion/scripts/sidebar.py`**

1. Three new module-level constants, placed after the existing import block:
   ```python
   _MODEL_BACKEND = os.environ.get("FLEX_MODEL_BACKEND", "anthropic")
   _OLLAMA_BASE_URL = os.environ.get("FLEX_OLLAMA_BASE_URL", "http://localhost:11434")
   _OLLAMA_MODEL = os.environ.get("FLEX_OLLAMA_MODEL", "llama3.1:8b")
   ```

2. `call_ollama` is imported from `skills.pairmode.scripts.call_model` using
   the same `sys.path` pattern already in use for `effort_recorder`:
   ```python
   try:
       from skills.pairmode.scripts.call_model import call_ollama as _call_ollama
   except ImportError:
       _call_ollama = None
   ```
   (guarded import — if pairmode scripts are absent, Ollama routing silently
   degrades to anthropic)

3. The existing `call_claude` function is renamed to `_call_anthropic`. **All
   internals are preserved exactly:** the `claude_agent_sdk` import, the
   `collected` dict, the `_run` coroutine, the `_finalize` helper, the
   `_record_sidebar_effort` closure, the asyncio event loop, and all
   error-handling branches.

4. A new public function replaces `call_claude`:
   ```python
   def call_claude(
       prompt: str,
       system: str,
       model: str = "claude-haiku-4-5-20251001",
       timeout: int = 60,
   ) -> str | None:
       if _MODEL_BACKEND == "ollama" and _call_ollama is not None:
           return _call_ollama(prompt, system, _OLLAMA_MODEL,
                               base_url=_OLLAMA_BASE_URL, timeout=10)
       return _call_anthropic(prompt, system, model, timeout)
   ```
   The signature and return type are unchanged. All existing call sites within
   `sidebar.py` continue to work without modification.

5. Startup diagnostics (near line 1472): when `_MODEL_BACKEND == "ollama"`,
   attempt a `requests.get(f"{_OLLAMA_BASE_URL}/api/tags", timeout=2)`. If it
   raises or returns non-200, print a yellow warning:
   `"[yellow]  Ollama not reachable at {_OLLAMA_BASE_URL} — calls will fail[/yellow]"`.
   If it succeeds, print a dim confirmation:
   `"[dim]  Ollama backend: {_OLLAMA_BASE_URL} model={_OLLAMA_MODEL}[/dim]"`.
   If `_MODEL_BACKEND != "ollama"`, no health check is performed.

**`tests/pairmode/test_sidebar_call_model.py`** (new file)

6. `test_call_claude_defaults_to_anthropic` — with no `FLEX_MODEL_BACKEND`
   env var set, mock `_call_anthropic`; call `call_claude(...)` and assert
   `_call_anthropic` was called.

7. `test_call_claude_routes_to_ollama` — set `FLEX_MODEL_BACKEND=ollama`
   in the environment; mock `_call_ollama`; call `call_claude(...)` and assert
   `_call_ollama` was called with `model=_OLLAMA_MODEL` and `timeout=10`.

8. `test_call_claude_returns_none_on_backend_failure` — mock `_call_ollama`
   to return `None`; assert `call_claude` also returns `None` without raising.

#### Instructions

1. Add the three `_MODEL_BACKEND`, `_OLLAMA_BASE_URL`, `_OLLAMA_MODEL`
   constants after the existing imports in `sidebar.py`.
2. Add the guarded import of `_call_ollama`.
3. Rename `call_claude` → `_call_anthropic` (find/replace the `def` line only;
   internal `call_claude` self-references if any should be preserved — check
   there are none).
4. Add the new `call_claude` dispatcher immediately after `_call_anthropic`.
5. Add the Ollama health-check block in the startup diagnostics section.
6. Create `tests/pairmode/test_sidebar_call_model.py` with tests 6–8. Use
   `unittest.mock.patch` to control module-level references; use
   `monkeypatch.setenv` or `unittest.mock.patch.dict(os.environ, ...)` to
   control the env var without polluting other tests.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_sidebar_call_model.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-122 — Fallback for extraction / conflict / spec call sites + plan-impact hardening

**Rail:** INFRA | **story_class:** code

**Protected file justification:** `sidebar.py` is modified to add JSON-shape
fallback for the three call sites that route LLM calls to the local model. An
explicit Anthropic retry is added when the local model returns unparseable
output. Plan-impact analysis is hardcoded to `_call_anthropic` because it
performs complex multi-item classification that requires full model capability.
The change is additive; no existing logic is removed.

#### Requires

- INFRA-121 complete: `_call_anthropic` and `_MODEL_BACKEND` exist in
  `sidebar.py`.
- `sidebar.py:578` `extract_incremental` calls `call_claude(...)`, parses
  result as a JSON array, returns `[]` on failure.
- `sidebar.py:605` `check_conflicts` calls `call_claude(...)`, parses result
  as a JSON array, returns `[]` on failure.
- `sidebar.py:655` `check_file_against_spec` calls `call_claude(...)`, parses
  result as a JSON object, returns `None` on failure.
- `sidebar.py:1157` and `sidebar.py:1541` plan-impact blocks call
  `call_claude(...)`.

#### Ensures

**`skills/companion/scripts/sidebar.py`**

1. **Plan-impact hardening:** At both plan-impact call sites (approximately
   lines 1157 and 1541), replace `call_claude(prompt, ...)` with
   `_call_anthropic(prompt, ...)`. These calls bypass the `FLEX_MODEL_BACKEND`
   dispatch unconditionally. No other changes to the plan-impact logic.

2. **`extract_incremental` fallback:** Wrap the `call_claude(...)` call and
   subsequent `json.loads(raw)` in a helper pattern:
   - Call `call_claude(prompt, EXTRACTION_SYSTEM)` as today.
   - If `raw` is `None` or `json.loads(raw)` raises, AND `_MODEL_BACKEND !=
     "anthropic"`: retry once by calling `_call_anthropic(prompt,
     EXTRACTION_SYSTEM)` directly.
   - Parse the retry result; on failure, return `[]`.
   - If `_MODEL_BACKEND == "anthropic"` and parsing fails: return `[]` (same
     as today — no retry).

3. **`check_conflicts` fallback:** Same fallback pattern as `extract_incremental`.
   If local result is `None` or unparseable and `_MODEL_BACKEND != "anthropic"`:
   retry once with `_call_anthropic(...)`; on retry failure, return `[]`.

4. **`check_file_against_spec` fallback:** The `call_claude(prompt, system)`
   call inside the non-negotiables check block gets the same fallback. If local
   result is `None` or `json.loads(raw)` raises and `_MODEL_BACKEND !=
   "anthropic"`: retry once with `_call_anthropic(prompt, system)`; on retry
   failure, return `None` (existing behavior on failure).

5. Prompts, system strings, and all other parsing logic are untouched.

**`tests/pairmode/test_sidebar_call_model.py`** (extend)

6. `test_extraction_falls_back_to_anthropic_on_bad_json` — mock `call_claude`
   to return `"not json"`; mock `_call_anthropic` to return a valid JSON array
   string; set `FLEX_MODEL_BACKEND=ollama`; call `extract_incremental(...)`;
   assert `_call_anthropic` was called and the result is the parsed array.

7. `test_extraction_returns_empty_on_double_failure` — mock both `call_claude`
   and `_call_anthropic` to return `None`; set `FLEX_MODEL_BACKEND=ollama`;
   assert `extract_incremental` returns `[]` without raising.

8. `test_extraction_no_fallback_when_anthropic_backend` — set
   `FLEX_MODEL_BACKEND=anthropic`; mock `call_claude` to return bad JSON; assert
   `_call_anthropic` is never called (exactly 0 calls) and result is `[]`.

#### Instructions

1. In `sidebar.py`, replace the two plan-impact `call_claude(...)` calls with
   `_call_anthropic(...)`.
2. In `extract_incremental`, after the existing `if not raw: return []` block,
   wrap `json.loads(raw)` in try/except; add the retry branch guarded by
   `_MODEL_BACKEND != "anthropic"`.
3. Apply the same pattern to `check_conflicts` and the non-negotiables block in
   `check_file_against_spec`.
4. Extend `tests/pairmode/test_sidebar_call_model.py` with tests 6–8.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_sidebar_call_model.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-123 — `backend` column in effort DB

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/effort_db.py` has:
  - `_SCHEMA_TABLE` (CREATE TABLE string)
  - `_MIGRATIONS` tuple of ALTER TABLE strings
  - `_INSERT_COLUMNS` tuple of column names used by `insert_attempt`
- `skills/pairmode/scripts/effort_recorder.py` has `record_effort(*, ...)` at
  line ~125. It calls `_effort_db.insert_attempt(db_path, ...)`.
- `sidebar.py:_record_sidebar_effort` (nested in `_call_anthropic` after
  INFRA-121) calls `record_effort(...)` for the anthropic path.
- No `backend` column exists in the `attempts` table.

#### Ensures

**`skills/pairmode/scripts/effort_db.py`**

1. `_SCHEMA_TABLE`: add `backend TEXT` as a column in the `CREATE TABLE IF NOT
   EXISTS attempts (...)` statement.

2. `_MIGRATIONS`: append:
   ```python
   "ALTER TABLE attempts ADD COLUMN backend TEXT",
   ```

3. `_INSERT_COLUMNS`: add `"backend"` to the tuple.

**`skills/pairmode/scripts/effort_recorder.py`**

4. `record_effort(...)` gains `backend: str | None = None` keyword argument.

5. Passes `backend=backend` to `_effort_db.insert_attempt(db_path, ...)`.

**`skills/companion/scripts/sidebar.py`** (protected — justification: adding
`backend="anthropic"` to effort recording for the existing anthropic call path,
and adding effort recording for the new Ollama call path)

6. `_record_sidebar_effort(outcome)` inside `_call_anthropic`: add
   `backend="anthropic"` to the `record_effort(...)` call.

7. The public `call_claude` dispatcher (from INFRA-121): when the Ollama path
   is taken (i.e., `_MODEL_BACKEND == "ollama" and _call_ollama is not None`),
   after `_call_ollama` returns, call:
   ```python
   try:
       story = _current_story or {}
       sid = story.get("id") if isinstance(story, dict) else None
       story_id = f"sidebar:{sid}" if sid else "sidebar:no-story"
       record_effort(
           project_dir=Path.cwd(),
           story_id=story_id,
           agent_role="sidebar-extractor",
           model=_OLLAMA_MODEL,
           usage=None,
           attempt_number=1,
           outcome="PASS" if result else "FAIL",
           backend="ollama",
           notes="sidebar pipe-message LLM extraction (ollama)",
       )
   except Exception:
       pass
   ```

**`tests/pairmode/test_effort_db.py`** (extend)

8. `test_backend_column_stored` — insert an attempt row with `backend="ollama"`;
   query the row from the DB; assert `backend == "ollama"`.

9. `test_backend_column_nullable` — insert an attempt row with no `backend`
   argument (or `backend=None`); assert no error and the row is stored.

#### Instructions

1. Edit `_SCHEMA_TABLE` in `effort_db.py` to include `backend TEXT`.
2. Append the migration string to `_MIGRATIONS`.
3. Add `"backend"` to `_INSERT_COLUMNS`.
4. Add `backend: str | None = None` to `record_effort`'s signature and pass it
   through to `insert_attempt`.
5. In `sidebar.py`, add `backend="anthropic"` to the `record_effort(...)` call
   inside `_record_sidebar_effort`.
6. In `sidebar.py`, add the Ollama effort-recording block to the `call_claude`
   dispatcher (see Ensures 7).
7. Add tests 8–9 to `tests/pairmode/test_effort_db.py`.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_effort_db.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

## Follow-on scope (not in this phase)

- Per-call-type model env vars (e.g. `FLEX_OLLAMA_EXTRACTION_MODEL`,
  `FLEX_OLLAMA_CONFLICT_MODEL`) for finer-grained local routing.
- Batch seed transcript mining with local model — `mine_sessions.py`.
- RAG corpus for few-shot grounding of extraction prompts using the existing
  `extraction.json` corpus.
- Routing `check_conflicts` and `check_file_against_spec` to separate, smaller
  local models once extraction is proven stable.

Tag: `cp46-local-model-infrastructure`

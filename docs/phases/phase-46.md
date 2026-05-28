# flex — Phase 46: Local model infrastructure

← [Phase 45: Deterministic orchestrator offload](phase-45.md)

## Goal

The companion sidebar calls the Anthropic API after every assistant response to
extract decisions from the live transcript. This is the highest-frequency paid
API call in the system and the task — structured JSON extraction from a short
transcript window against a fixed schema — is narrow enough for a local 7B
model to handle. The seed transcript miner (`mine_sessions.py`) has the same
extraction task in batch/offline form.

This phase builds the plumbing to route these calls to a local model running
via Ollama, with Anthropic as fallback. No behavior changes on the default path:
Anthropic remains the default and the existing extraction quality is preserved
unless the operator explicitly opts in to the local backend.

**Design constraints:**
- `sidebar.py` is a protected file. The change is declared here as the stated
  reason required by CLAUDE.md: reduce per-session API cost for the highest-
  frequency sidebar call (decision extraction) by enabling an optional local
  model backend.
- Local model routing must be opt-in via environment variable. The default
  backend is `anthropic` and nothing changes for users who do not set it.
- Tests must not require Ollama to be running. The Ollama HTTP client is
  injectable/mockable at the module boundary.

**Three stories:**

| ID | Title | Status |
|----|-------|--------|
| INFRA-120 | `call_model.py` — pluggable model client module | planned |
| INFRA-121 | Wire `sidebar.py` `call_claude` to pluggable backend | planned |
| INFRA-122 | Route decision extraction to local model with fallback | planned |

**Story dependencies:** INFRA-121 depends on INFRA-120. INFRA-122 depends on
INFRA-121. Build in order.

---

## Stories

### Story INFRA-120 — `call_model.py`: pluggable model client module

**Rail:** INFRA | **story_class:** code

#### Requires

- No local model infrastructure exists in the codebase (confirmed: no Ollama,
  embedding, or vector references anywhere).
- `skills/companion/scripts/sidebar.py:364` contains `call_claude(prompt, system,
  model, timeout)` which calls the Anthropic SDK directly.

#### Ensures

**`skills/pairmode/scripts/call_model.py`** (new file)

1. Defines a single public function:
   ```python
   def call_model(
       prompt: str,
       system: str,
       model: str,
       backend: str = "anthropic",
       timeout: int = 60,
       base_url: str | None = None,
   ) -> str | None:
   ```
   Returns the response text, or `None` on failure (matching `call_claude`'s
   contract).

2. When `backend == "anthropic"`: calls the Anthropic SDK
   (`anthropic.Anthropic().messages.create(...)`) with the same parameters and
   error handling as the current `call_claude` in `sidebar.py`. The Anthropic
   client is instantiated lazily (import inside the function body) so the
   module can be imported without `ANTHROPIC_API_KEY` set.

3. When `backend == "ollama"`: sends an HTTP POST to
   `{base_url}/api/chat` (default `base_url`: `http://localhost:11434`).
   Request body:
   ```json
   {
     "model": "<model>",
     "messages": [{"role": "system", "content": "<system>"}, {"role": "user", "content": "<prompt>"}],
     "stream": false
   }
   ```
   Parses `response.json()["message"]["content"]` as the return value.
   Uses `requests` with the given `timeout`. Returns `None` on `requests`
   exception or non-200 status (logs a warning to stderr).

4. Raises `ValueError` for unknown `backend` values.

5. No side effects, no global state, no file I/O.

**`requirements.txt`** (companion or pairmode — whichever owns `sidebar.py`'s deps)

6. `requests` is added if not already present (check before adding).

**`tests/pairmode/test_call_model.py`** (new file)

7. `test_anthropic_backend_calls_sdk` — mock the Anthropic client; assert
   `call_model(..., backend="anthropic")` calls `messages.create` with the
   correct model/messages and returns the message text.

8. `test_ollama_backend_posts_to_endpoint` — mock `requests.post`; assert
   `call_model(..., backend="ollama")` POSTs to `http://localhost:11434/api/chat`
   with the correct JSON body and returns `response.json()["message"]["content"]`.

9. `test_ollama_backend_custom_base_url` — mock `requests.post` and pass
   `base_url="http://gpu-box:11434"`; assert the POST URL uses the custom base.

10. `test_ollama_returns_none_on_http_error` — mock `requests.post` to raise
    `requests.exceptions.ConnectionError`; assert return value is `None`.

11. `test_unknown_backend_raises` — assert `ValueError` raised for
    `backend="unknown"`.

#### Instructions

1. Create `skills/pairmode/scripts/call_model.py` with the function above.
2. Use `requests` for the Ollama HTTP call; check `requirements.txt` for the
   companion skill and add `requests` if absent.
3. Create `tests/pairmode/test_call_model.py` with tests 7–11 using
   `unittest.mock.patch`.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_call_model.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-121 — Wire `sidebar.py` `call_claude` to pluggable backend

**Rail:** INFRA | **story_class:** code

**Protected file justification:** `sidebar.py` is modified to delegate its
`call_claude` function to the new `call_model` module. The change is
backward-compatible (Anthropic remains the default backend), enables per-session
cost reduction for users who opt into a local backend, and introduces no new
external dependencies into `sidebar.py` beyond the import of `call_model`.

#### Requires

- INFRA-120 complete: `skills/pairmode/scripts/call_model.py` exists with
  `call_model(prompt, system, model, backend, timeout, base_url)`.
- `skills/companion/scripts/sidebar.py:364` has `call_claude(prompt, system,
  model, timeout)` that calls the Anthropic SDK inline.
- `sidebar.py` is a protected file (CLAUDE.md §7).

#### Ensures

**`skills/companion/scripts/sidebar.py`**

1. At module load, reads two environment variables:
   - `FLEX_MODEL_BACKEND` — `"anthropic"` (default) or `"ollama"`.
   - `FLEX_OLLAMA_BASE_URL` — base URL for Ollama (default `"http://localhost:11434"`).
   Stored as module-level constants `_MODEL_BACKEND` and `_OLLAMA_BASE_URL`.

2. `call_claude(prompt, system, model, timeout)` is rewritten to delegate to
   `call_model` imported from `call_model.py`:
   ```python
   from skills.pairmode.scripts.call_model import call_model as _call_model
   # or relative import depending on how sidebar.py resolves its imports
   ```
   The function signature and return type (`str | None`) are unchanged.
   All existing call sites within `sidebar.py` continue to work without
   modification.

3. When `_MODEL_BACKEND == "anthropic"`: behavior is identical to the current
   implementation (same model, same timeout, same error handling).

4. When `_MODEL_BACKEND == "ollama"`: `call_model` is called with
   `backend="ollama"` and `base_url=_OLLAMA_BASE_URL`.

5. The previous inline Anthropic SDK code inside `call_claude` is removed and
   replaced with the delegation. The Anthropic import at the top of `sidebar.py`
   (if any) is retained only if used elsewhere in the file; otherwise it can be
   removed.

**No other changes to `sidebar.py`.** Extraction prompts, conflict checks,
plan-impact logic, rendering functions, and event handlers are untouched.

**`tests/pairmode/test_sidebar_call_model.py`** (new file — tests only the
`call_claude` delegation; do not attempt to unit-test the full sidebar)

6. `test_call_claude_delegates_to_anthropic_by_default` — mock `call_model`
   in the sidebar module; assert that invoking `call_claude(...)` with no
   `FLEX_MODEL_BACKEND` env var calls `call_model` with `backend="anthropic"`.

7. `test_call_claude_delegates_to_ollama_when_env_set` — set
   `FLEX_MODEL_BACKEND=ollama` in the environment; mock `call_model`; assert
   `call_claude` calls `call_model` with `backend="ollama"`.

8. `test_call_claude_returns_none_on_backend_failure` — mock `call_model` to
   return `None`; assert `call_claude` also returns `None` without raising.

#### Instructions

1. In `sidebar.py`, add the two `os.environ.get(...)` reads near the top of
   the file (after existing imports).
2. Rewrite `call_claude` to call `_call_model` from `call_model.py`. Resolve
   the import path by checking how `sidebar.py` currently imports other
   pairmode scripts — use the same pattern.
3. Create `tests/pairmode/test_sidebar_call_model.py` with tests 6–8. Use
   `importlib.reload` or `monkeypatch` (if using pytest fixtures) to control
   the env var at test time without polluting other tests.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_sidebar_call_model.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

### Story INFRA-122 — Route decision extraction to local model with fallback

**Rail:** INFRA | **story_class:** code

#### Requires

- INFRA-121 complete: `sidebar.py` `call_claude` delegates to `call_model` and
  reads `FLEX_MODEL_BACKEND` from the environment.
- `sidebar.py:578` has `extract_incremental(transcript_path, loaded_modules)`
  which calls `call_claude(prompt, EXTRACTION_SYSTEM, model="claude-haiku-...")`.
- `sidebar.py:605` has `check_conflicts(new_items, specs)` which calls
  `call_claude(prompt, system)`.

#### Ensures

**`skills/companion/scripts/sidebar.py`**

1. `extract_incremental` gains JSON-parse validation after `call_claude` returns:
   - If the response is `None` or cannot be parsed as a JSON array, and
     `_MODEL_BACKEND != "anthropic"`, retry the call once with `backend`
     explicitly forced to `"anthropic"` (Anthropic fallback).
   - If the Anthropic retry also fails or returns unparseable JSON, log a
     warning to stderr and return an empty list (existing silent-failure
     behavior is preserved, but the fallback is now explicit).
   - If `_MODEL_BACKEND == "anthropic"` and parsing fails, behavior is
     unchanged from today (return empty list, no retry).

2. The fallback path is the only change to `extract_incremental`. The prompt,
   system, and parsing logic are untouched.

3. `check_conflicts` does **not** get a fallback in this story — its lower
   frequency means it can be addressed in a follow-on phase once extraction
   is proven stable.

**`tests/pairmode/test_sidebar_call_model.py`** (extend)

4. `test_extraction_falls_back_to_anthropic_on_bad_json` — mock `call_model`
   to return `"not json"` on the first call and a valid JSON array on the
   second call; set `FLEX_MODEL_BACKEND=ollama`; invoke `extract_incremental`;
   assert the second call used `backend="anthropic"` and the result is the
   parsed array from the second call.

5. `test_extraction_returns_empty_on_double_failure` — mock `call_model` to
   return `None` both times; assert `extract_incremental` returns `[]` without
   raising.

6. `test_extraction_no_fallback_when_anthropic_backend` — set
   `FLEX_MODEL_BACKEND=anthropic`; mock `call_model` to return bad JSON once;
   assert `call_model` is called exactly once (no retry).

#### Instructions

1. In `extract_incremental`, wrap the `json.loads` call in a try/except;
   implement the retry logic from Ensures 1.
2. Pass `backend="anthropic"` explicitly on the retry call — do not use
   `_MODEL_BACKEND` for the fallback call.
3. Extend `tests/pairmode/test_sidebar_call_model.py` with tests 4–6.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_sidebar_call_model.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

All new tests must pass. Full suite must pass.

---

## Follow-on scope (not in this phase)

- Routing `check_conflicts` and `check_file_against_spec` to local model (2.2 from audit).
- Routing plan-impact analysis to local model (2.3 from audit).
- Batch seed transcript mining with local model — `mine_sessions.py` (2.4 from audit).
- RAG corpus for few-shot grounding of extraction prompts.
- Model selection per call type (e.g. use a larger local model for conflict
  checking than for extraction).

Tag: `cp46-local-model-infrastructure`

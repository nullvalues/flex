"""Tests for skills/pairmode/scripts/user_turn_seq.py — INFRA-248.

Module-level coverage of the idempotent UserPromptSubmit turn-counter
increment (``record_user_turn``) and its fingerprint helper
(``compute_fingerprint``). Hook-level (subprocess) coverage lives in
``tests/pairmode/test_user_prompt_submit_hook.py``.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "pairmode" / "scripts"))

import user_turn_seq  # noqa: E402


def _write_state(cwd: Path, state: dict) -> Path:
    companion_dir = cwd / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _read_state(state_path: Path) -> dict:
    return json.loads(state_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# compute_fingerprint
# ---------------------------------------------------------------------------


def test_compute_fingerprint_is_deterministic():
    data = {"session_id": "sess-1", "prompt": "hello"}
    assert user_turn_seq.compute_fingerprint(data) == user_turn_seq.compute_fingerprint(data)


def test_compute_fingerprint_differs_for_different_prompt():
    a = user_turn_seq.compute_fingerprint({"session_id": "sess-1", "prompt": "hello"})
    b = user_turn_seq.compute_fingerprint({"session_id": "sess-1", "prompt": "goodbye"})
    assert a != b


def test_compute_fingerprint_differs_for_different_session():
    a = user_turn_seq.compute_fingerprint({"session_id": "sess-1", "prompt": "hello"})
    b = user_turn_seq.compute_fingerprint({"session_id": "sess-2", "prompt": "hello"})
    assert a != b


def test_compute_fingerprint_handles_none():
    # Must not raise; falls back to a stable digest of the empty payload.
    fp = user_turn_seq.compute_fingerprint(None)
    assert isinstance(fp, str) and len(fp) == 64


def test_compute_fingerprint_handles_non_dict():
    fp = user_turn_seq.compute_fingerprint("not a dict")  # type: ignore[arg-type]
    assert isinstance(fp, str) and len(fp) == 64


def test_compute_fingerprint_falls_back_to_full_payload_when_no_identifying_fields():
    a = user_turn_seq.compute_fingerprint({"cwd": "/a"})
    b = user_turn_seq.compute_fingerprint({"cwd": "/b"})
    assert a != b


# ---------------------------------------------------------------------------
# record_user_turn — normal increment behaviour
# ---------------------------------------------------------------------------


def test_record_user_turn_increments_from_absent_key(tmp_path):
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 1
    assert state["context_budget_user_turn_seq_fingerprint"] == user_turn_seq.compute_fingerprint(
        {"session_id": "s1", "prompt": "p1"}
    )


def test_record_user_turn_increments_monotonically_for_distinct_prompts(tmp_path):
    state_path = _write_state(
        tmp_path, {"pairmode_version": "0.1.0", "context_budget_user_turn_seq": 5}
    )
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 6

    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p2"})
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 7


# ---------------------------------------------------------------------------
# record_user_turn — idempotency guard (INFRA-248)
# ---------------------------------------------------------------------------


def test_record_user_turn_duplicate_invocation_increments_once(tmp_path):
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    payload = {"session_id": "s1", "prompt": "same"}
    user_turn_seq.record_user_turn(tmp_path, payload)
    user_turn_seq.record_user_turn(tmp_path, payload)
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 1


def test_record_user_turn_distinct_payload_after_duplicate_still_increments(tmp_path):
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    payload = {"session_id": "s1", "prompt": "same"}
    user_turn_seq.record_user_turn(tmp_path, payload)
    user_turn_seq.record_user_turn(tmp_path, payload)  # duplicate — skipped
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "different"})
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 2


def test_record_user_turn_stores_fingerprint_for_future_dedup(tmp_path):
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    payload = {"session_id": "s1", "prompt": "same"}
    user_turn_seq.record_user_turn(tmp_path, payload)
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq_fingerprint"] == user_turn_seq.compute_fingerprint(
        payload
    )


# ---------------------------------------------------------------------------
# record_user_turn — fail-open behaviour
# ---------------------------------------------------------------------------


def test_record_user_turn_no_state_file_is_noop(tmp_path):
    # Must not raise, must not create the file.
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    assert not (tmp_path / ".companion" / "state.json").exists()


def test_record_user_turn_malformed_state_json_is_noop(tmp_path):
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state_path = companion_dir / "state.json"
    state_path.write_text("{not valid json", encoding="utf-8")
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    assert state_path.read_text(encoding="utf-8") == "{not valid json"


def test_record_user_turn_non_dict_state_root_is_noop(tmp_path):
    state_path = _write_state(tmp_path, [])  # type: ignore[arg-type]
    # _write_state json.dumps a list here — overwrite directly to be explicit.
    state_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    assert json.loads(state_path.read_text(encoding="utf-8")) == [1, 2, 3]


def test_record_user_turn_non_dict_data_does_not_crash(tmp_path):
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    user_turn_seq.record_user_turn(tmp_path, "not a dict")  # type: ignore[arg-type]
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 1


def test_record_user_turn_string_path_accepted(tmp_path):
    """project_dir may be a plain string, not just a Path."""
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    user_turn_seq.record_user_turn(str(tmp_path), {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 1


def test_record_user_turn_non_numeric_counter_treated_as_zero(tmp_path):
    state_path = _write_state(
        tmp_path,
        {"pairmode_version": "0.1.0", "context_budget_user_turn_seq": "not-a-number"},
    )
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 1


# ---------------------------------------------------------------------------
# INFRA-285 (CER-097, item E4) — locked, atomic conversion
# ---------------------------------------------------------------------------


def test_record_user_turn_no_longer_uses_a_bare_write_text():
    """E4: the non-atomic whole-file write is gone."""
    source = (
        REPO_ROOT / "skills" / "pairmode" / "scripts" / "user_turn_seq.py"
    ).read_text(encoding="utf-8")
    assert "state_path.write_text" not in source
    assert "update_state_json(" in source


def test_record_user_turn_writes_under_the_advisory_lock(tmp_path, monkeypatch):
    """E4: the read-check-write happens inside one update_state_json call."""
    import state_utils

    calls = []
    real = state_utils.update_state_json

    def _spy(path, mutate):
        calls.append(str(path))
        return real(path, mutate)

    monkeypatch.setattr(user_turn_seq, "update_state_json", _spy)
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    assert len(calls) == 1
    assert calls[0].endswith(".companion/state.json")


def test_record_user_turn_persists_atomically_leaving_no_tmp_files(tmp_path):
    """E4: the atomic-replace contract — no .tmp sibling survives the write."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    assert list((tmp_path / ".companion").glob("*.tmp")) == []


def test_record_user_turn_duplicate_leaves_the_file_byte_identical(tmp_path):
    """E4: the `return False` skip path performs no write at all."""
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    payload = {"session_id": "s1", "prompt": "same"}
    user_turn_seq.record_user_turn(tmp_path, payload)
    before = state_path.read_bytes()
    user_turn_seq.record_user_turn(tmp_path, payload)
    assert state_path.read_bytes() == before


# ---------------------------------------------------------------------------
# INFRA-321 § C1/C3/C4/C5/C6 — orchestrator-track refresh from record_user_turn
# ---------------------------------------------------------------------------


def test_record_user_turn_refreshes_orchestrator_tokens_from_measurement(tmp_path, monkeypatch):
    """test_record_user_turn_refreshes_orchestrator_tokens_from_measurement."""
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    monkeypatch.setattr(user_turn_seq.context_budget, "read_current_tokens", lambda **kw: 42000)
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_current_tokens"] == 42000
    assert "context_current_tokens_recorded_at" in state
    assert state["context_current_tokens_source"] == "user-prompt-submit"


def test_record_user_turn_leaves_tokens_untouched_when_measurement_is_none(tmp_path, monkeypatch):
    """test_record_user_turn_leaves_tokens_untouched_when_measurement_is_none."""
    state_path = _write_state(
        tmp_path, {"pairmode_version": "0.1.0", "context_current_tokens": 99999}
    )
    monkeypatch.setattr(user_turn_seq.context_budget, "read_current_tokens", lambda **kw: None)
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_current_tokens"] == 99999
    assert "context_current_tokens_source" not in state


def test_record_user_turn_increments_counter_when_measurement_raises(tmp_path, monkeypatch):
    """test_record_user_turn_increments_counter_when_measurement_raises."""
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})

    def _raise(**kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(user_turn_seq.context_budget, "read_current_tokens", _raise)
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 1
    assert "context_current_tokens" not in state


def test_record_user_turn_does_not_append_step_growth_sample(tmp_path, monkeypatch):
    """test_record_user_turn_does_not_append_step_growth_sample (§ C4)."""
    state_path = _write_state(
        tmp_path,
        {"pairmode_version": "0.1.0", "context_step_growth_samples": [1000, 2000]},
    )
    monkeypatch.setattr(user_turn_seq.context_budget, "read_current_tokens", lambda **kw: 5000)
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_step_growth_samples"] == [1000, 2000]


def test_duplicate_user_prompt_increments_once_and_refreshes_tokens(tmp_path, monkeypatch):
    """test_duplicate_user_prompt_increments_once_and_refreshes_tokens (§ C5)."""
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    monkeypatch.setattr(user_turn_seq.context_budget, "read_current_tokens", lambda **kw: 7000)
    payload = {"session_id": "s1", "prompt": "same"}
    user_turn_seq.record_user_turn(tmp_path, payload)
    user_turn_seq.record_user_turn(tmp_path, payload)  # duplicate — skipped entirely
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 1
    assert state["context_current_tokens"] == 7000


def test_user_prompt_submit_hook_still_only_delegates():
    """test_user_prompt_submit_hook_still_only_delegates — § C2, byte content
    of the protected hook file is unchanged by this story.
    """
    hook_path = REPO_ROOT / "hooks" / "user_prompt_submit.py"
    src = hook_path.read_text(encoding="utf-8")
    assert "record_user_turn(" in src
    # No new state.json I/O was added to the hook itself.
    assert "import context_budget" not in src
    assert "import session_state" not in src


def test_context_current_tokens_source_stamped_by_each_writer(tmp_path, monkeypatch):
    """test_context_current_tokens_source_stamped_by_each_writer — the
    user-prompt-submit writer stamps "user-prompt-submit"; the "manual"
    writer (flex_build.py set-context-tokens / bump-context-tokens) is
    covered by tests/pairmode/test_flex_build.py. This module owns the
    user-prompt-submit half only.
    """
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    monkeypatch.setattr(user_turn_seq.context_budget, "read_current_tokens", lambda **kw: 1000)
    user_turn_seq.record_user_turn(tmp_path, {"session_id": "s1", "prompt": "p1"})
    state = _read_state(state_path)
    assert state["context_current_tokens_source"] == "user-prompt-submit"


def test_hooks_directory_has_no_uncommitted_changes_from_this_story():
    """§ C2 (INFRA-248): guarded this story's own scope against an
    accidental edit slipping into hooks/.

    Retired as a blanket "hooks/ is always clean" assertion (INFRA-323):
    ``hooks/**`` is a *protected* path, not a *frozen* one —
    ``scope_guard.PROTECTED_GLOBS`` fails closed by default but is
    explicitly satisfiable by a story that declares the file in its
    frontmatter ``touches:`` and carries a valid permissions artifact
    (see ``docs/architecture.md`` § Protected files). A generic
    ``git status --porcelain hooks/`` check has no way to distinguish an
    accidental edit from one a later story's own declared, reviewed scope
    deliberately makes — it fails for every future story legitimately
    authorized to touch a hook. The real guard against accidental hook
    drift is scope_guard's fail-closed default plus per-story code review,
    not a point-in-time git-status snapshot baked into an unrelated
    module's test file.
    """

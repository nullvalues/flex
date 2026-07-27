"""Tests for state_utils (CER-050 / INFRA-200; locking added INFRA-285/CER-097)."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import sys

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import state_utils  # noqa: E402
from state_utils import (  # noqa: E402
    STATE_LOCK_TIMEOUT_SECONDS,
    _atomic_write_json,
    _atomic_write_text,
    state_lock,
    update_state_json,
)

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover — non-POSIX
    _fcntl = None


def test_atomic_write_json_writes_expected_content(tmp_path: Path) -> None:
    """_atomic_write_json writes the expected JSON content to the target path."""
    target = tmp_path / "state.json"
    data = {"key": "value", "number": 42}

    _atomic_write_json(target, data)

    assert target.exists()
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written == data


def test_atomic_write_json_overwrites_existing(tmp_path: Path) -> None:
    """_atomic_write_json overwrites an existing file correctly."""
    target = tmp_path / "state.json"
    target.write_text(json.dumps({"old": "data"}), encoding="utf-8")

    new_data = {"new": "data", "x": 1}
    _atomic_write_json(target, new_data)

    written = json.loads(target.read_text(encoding="utf-8"))
    assert written == new_data


def test_atomic_write_json_cleans_up_tmp_on_exception(tmp_path: Path) -> None:
    """_atomic_write_json deletes the .tmp file when os.replace raises."""
    target = tmp_path / "state.json"
    data = {"foo": "bar"}

    tmp_files_created: list[str] = []

    original_named_temp = __import__("tempfile").NamedTemporaryFile

    class _CapturingNTF:
        """Thin wrapper that records the tmp path before os.replace is patched."""

        def __init__(self, *args, **kwargs):
            self._ntf = original_named_temp(*args, **kwargs)
            tmp_files_created.append(self._ntf.name)

        def __enter__(self):
            return self._ntf.__enter__()

        def __exit__(self, *a):
            return self._ntf.__exit__(*a)

    with patch("state_utils.os.replace", side_effect=OSError("simulated replace failure")):
        with pytest.raises(OSError, match="simulated replace failure"):
            _atomic_write_json(target, data)

    # Target must not have been created
    assert not target.exists()

    # All .tmp siblings must have been cleaned up
    for p in tmp_files_created:
        assert not Path(p).exists(), f"tmp file not cleaned up: {p}"

    # Verify by scanning the directory directly
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"leftover .tmp files: {leftovers}"


def test_atomic_write_json_no_tmp_left_after_success(tmp_path: Path) -> None:
    """No .tmp files remain in the directory after a successful write."""
    target = tmp_path / "state.json"
    _atomic_write_json(target, {"a": 1})

    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"unexpected .tmp files: {leftovers}"


# ---------------------------------------------------------------------------
# E1 — _atomic_write_text
# ---------------------------------------------------------------------------


class TestAtomicWriteText:
    def test_writes_expected_text(self, tmp_path: Path) -> None:
        target = tmp_path / "phase.md"
        _atomic_write_text(target, "# heading\n\n| a | b |\n")
        assert target.read_text(encoding="utf-8") == "# heading\n\n| a | b |\n"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "phase.md"
        target.write_text("old", encoding="utf-8")
        _atomic_write_text(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_cleans_up_tmp_and_reraises_on_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "phase.md"
        with patch("state_utils.os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError, match="boom"):
                _atomic_write_text(target, "x")
        assert not target.exists()
        assert list(tmp_path.glob("*.tmp")) == []


# ---------------------------------------------------------------------------
# E1 / E2 — state_lock
# ---------------------------------------------------------------------------


class TestStateLock:
    def test_timeout_constant(self) -> None:
        assert STATE_LOCK_TIMEOUT_SECONDS == 2.0

    def test_acquires_and_releases(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        with state_lock(target) as acquired:
            assert acquired is True
        # Releasing means a second acquisition succeeds immediately.
        with state_lock(target) as acquired_again:
            assert acquired_again is True

    def test_creates_a_sibling_lock_file(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        with state_lock(target):
            pass
        assert (tmp_path / "state.json.lock").exists()

    def test_missing_directory_fails_open(self, tmp_path: Path) -> None:
        """E2: no directory → yields anyway, never raises, creates nothing."""
        target = tmp_path / "nope" / "state.json"
        with state_lock(target) as acquired:
            assert acquired is False
        assert not (tmp_path / "nope").exists()

    def test_failed_acquisition_still_runs_the_wrapped_write(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """E2: with acquisition always failing, the write still happens."""
        target = tmp_path / "state.json"
        target.write_text(json.dumps({"n": 0}), encoding="utf-8")

        monkeypatch.setattr(
            state_utils, "_acquire_state_lock", lambda path, timeout: (None, False)
        )

        def _bump(state: dict) -> None:
            state["n"] = state["n"] + 1

        assert update_state_json(target, _bump) == {"n": 1}
        assert json.loads(target.read_text(encoding="utf-8")) == {"n": 1}

    def test_raising_acquisition_never_escapes(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        target = tmp_path / "state.json"
        target.write_text(json.dumps({"n": 0}), encoding="utf-8")

        def _boom(path, timeout):
            raise RuntimeError("acquisition exploded")

        monkeypatch.setattr(state_utils, "_acquire_state_lock", _boom)
        assert update_state_json(target, lambda s: s.__setitem__("n", 1)) == {"n": 1}

    def test_no_fcntl_fails_open(self, tmp_path: Path, monkeypatch) -> None:
        """E2: a platform with no fcntl degrades to atomic-replace only."""
        monkeypatch.setattr(state_utils, "_load_fcntl", lambda: None)
        target = tmp_path / "state.json"
        with state_lock(target) as acquired:
            assert acquired is False
        assert not (tmp_path / "state.json.lock").exists()

    @pytest.mark.skipif(_fcntl is None, reason="fcntl unavailable on this platform")
    def test_contended_lock_gives_up_within_the_bound(self, tmp_path: Path) -> None:
        """E2: a lock held by a live second descriptor must not stall a hook."""
        target = tmp_path / "state.json"
        lock_path = tmp_path / "state.json.lock"
        holder = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        _fcntl.flock(holder, _fcntl.LOCK_EX)
        try:
            started = time.monotonic()
            with state_lock(target, timeout_seconds=0.3) as acquired:
                assert acquired is False
            elapsed = time.monotonic() - started
        finally:
            _fcntl.flock(holder, _fcntl.LOCK_UN)
            os.close(holder)
        assert elapsed < 0.3 + 0.5


# ---------------------------------------------------------------------------
# E3 — update_state_json
# ---------------------------------------------------------------------------


class TestUpdateStateJson:
    def test_mutates_and_returns_written_dict(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        target.write_text(json.dumps({"a": 1}), encoding="utf-8")
        result = update_state_json(target, lambda s: s.__setitem__("b", 2))
        assert result == {"a": 1, "b": 2}
        assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1, "b": 2}

    def test_mutate_returning_false_skips_the_write(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        original = json.dumps({"a": 1})
        target.write_text(original, encoding="utf-8")

        def _skip(state: dict) -> bool:
            state["a"] = 999  # must be discarded
            return False

        assert update_state_json(target, _skip) is None
        assert target.read_text(encoding="utf-8") == original

    def test_missing_file_is_no_update(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        assert update_state_json(target, lambda s: None) is None
        assert not target.exists()

    def test_malformed_file_is_no_update(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        target.write_text("{not json", encoding="utf-8")
        assert update_state_json(target, lambda s: None) is None
        assert target.read_text(encoding="utf-8") == "{not json"

    def test_non_dict_root_is_no_update(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        target.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        assert update_state_json(target, lambda s: None) is None
        assert json.loads(target.read_text(encoding="utf-8")) == [1, 2, 3]

    def test_raising_mutate_leaves_the_file_untouched(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        original = json.dumps({"a": 1})
        target.write_text(original, encoding="utf-8")

        def _boom(state: dict) -> None:
            raise RuntimeError("mutate exploded")

        assert update_state_json(target, _boom) is None
        assert target.read_text(encoding="utf-8") == original

    def test_accepts_a_string_path(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        target.write_text(json.dumps({}), encoding="utf-8")
        assert update_state_json(str(target), lambda s: s.__setitem__("x", 1)) == {"x": 1}


# ---------------------------------------------------------------------------
# E5 — concurrency regression
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    _fcntl is None, reason="fcntl unavailable — the advisory lock cannot be exercised"
)
def test_concurrent_update_state_json_writers_do_not_lose_updates(
    tmp_path: Path,
) -> None:
    """E5: two writers, distinct keys, 50 increments each — both reach 50.

    Without the lock this is the classic lost-update race: both threads read
    the same state, mutate different keys, and the second write discards the
    first's mutation.
    """
    target = tmp_path / "state.json"
    target.write_text(json.dumps({"a": 0, "b": 0}), encoding="utf-8")

    def _worker(key: str) -> None:
        for _ in range(50):
            update_state_json(
                target, lambda state: state.__setitem__(key, state.get(key, 0) + 1)
            )

    threads = [
        threading.Thread(target=_worker, args=("a",)),
        threading.Thread(target=_worker, args=("b",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    final = json.loads(target.read_text(encoding="utf-8"))
    assert final["a"] == 50
    assert final["b"] == 50

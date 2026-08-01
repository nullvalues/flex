"""Tests for ``flex_build.py`` attempt-counter subcommands (Story BUILD-022).

Subcommands under test:
  write-attempt-count  — persist {story_id, attempt_count} to .companion/attempt_counter.json
  read-attempt-count   — print persisted count (0 on absent/mismatch/malformed)
  clear-attempt-count  — delete the counter file; silent no-op when absent

Tests follow the pattern in ``tests/pairmode/test_flex_build_current_phase.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"

_STORY_ID = "BUILD-022"
_OTHER_STORY_ID = "INFRA-135"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess:
    """Invoke flex_build.py with *args*; return the completed process."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(_REPO_ROOT),
        },
    )


def _counter_path(project_dir: Path) -> Path:
    return project_dir / ".companion" / "attempt_counter.json"


# ---------------------------------------------------------------------------
# Tests — write-attempt-count
# ---------------------------------------------------------------------------


def test_write_attempt_count_creates_file_with_expected_shape(tmp_path: Path) -> None:
    """write-attempt-count creates the file with the correct JSON shape."""
    # Create .companion/ so the depth guard (3+ path parts) passes.
    companion = tmp_path / ".companion"
    companion.mkdir()

    result = _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "2",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    counter_file = _counter_path(tmp_path)
    assert counter_file.exists()
    data = json.loads(counter_file.read_text(encoding="utf-8"))
    assert data == {"stories": {_STORY_ID: 2}}


def test_write_attempt_count_creates_companion_dir(tmp_path: Path) -> None:
    """write-attempt-count creates .companion/ when it does not exist."""
    assert not (tmp_path / ".companion").exists()

    result = _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "1",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert _counter_path(tmp_path).exists()


def test_write_attempt_count_overwrites_existing_file(tmp_path: Path) -> None:
    """write-attempt-count with count=3 overwrites an earlier count=1 file."""
    _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "1",
        "--project-dir", str(tmp_path),
    )

    result = _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "3",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    data = json.loads(_counter_path(tmp_path).read_text(encoding="utf-8"))
    assert data["stories"][_STORY_ID] == 3


# ---------------------------------------------------------------------------
# Tests — read-attempt-count
# ---------------------------------------------------------------------------


def test_read_attempt_count_returns_persisted_value(tmp_path: Path) -> None:
    """read-attempt-count prints the stored integer when story_id matches."""
    _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "2",
        "--project-dir", str(tmp_path),
    )

    result = _run(
        "read-attempt-count",
        "--story-id", _STORY_ID,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "2"


def test_read_attempt_count_missing_file_returns_zero(tmp_path: Path) -> None:
    """read-attempt-count prints 0 and exits 0 when no counter file exists."""
    result = _run(
        "read-attempt-count",
        "--story-id", _STORY_ID,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "0"


def test_read_attempt_count_mismatched_story_returns_zero(tmp_path: Path) -> None:
    """read-attempt-count prints 0 when story_id in file differs from requested."""
    _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "2",
        "--project-dir", str(tmp_path),
    )

    result = _run(
        "read-attempt-count",
        "--story-id", _OTHER_STORY_ID,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "0"


def test_read_attempt_count_malformed_file_returns_zero(tmp_path: Path) -> None:
    """read-attempt-count prints 0 when counter file contains non-JSON garbage."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    _counter_path(tmp_path).write_text("this is not json {{{{", encoding="utf-8")

    result = _run(
        "read-attempt-count",
        "--story-id", _STORY_ID,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "0"


# ---------------------------------------------------------------------------
# Tests — clear-attempt-count
# ---------------------------------------------------------------------------


def test_clear_attempt_count_removes_file(tmp_path: Path) -> None:
    """clear-attempt-count deletes the counter file when it exists."""
    _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "2",
        "--project-dir", str(tmp_path),
    )
    assert _counter_path(tmp_path).exists()

    result = _run("clear-attempt-count", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not _counter_path(tmp_path).exists()


def test_clear_attempt_count_missing_file_noop(tmp_path: Path) -> None:
    """clear-attempt-count exits 0 silently when no counter file exists."""
    assert not _counter_path(tmp_path).exists()

    result = _run("clear-attempt-count", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout == ""
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# Tests — gitignore coverage
# ---------------------------------------------------------------------------


def test_attempt_counter_path_is_gitignored(tmp_path: Path) -> None:
    """The counter file path is covered by the .companion/ rule in .gitignore."""
    # Use the actual repo directory where git is initialized, so
    # `git check-ignore` can resolve the .gitignore rules properly.
    proc = subprocess.run(
        ["git", "check-ignore", "-q", ".companion/attempt_counter.json"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
    )
    assert proc.returncode == 0, (
        ".companion/attempt_counter.json is NOT covered by .gitignore"
    )


# ---------------------------------------------------------------------------
# Tests — depth guard
# ---------------------------------------------------------------------------


def test_write_attempt_count_depth_guard(tmp_path: Path) -> None:
    """A --project-dir that resolves to fewer than 3 path components is rejected."""
    result = _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "1",
        "--project-dir", "/",
    )
    assert result.returncode == 1
    assert "depth guard" in result.stderr.lower() or "too shallow" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Tests — story-keyed storage (INFRA-282, CER-095.3)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(_REPO_ROOT / "skills" / "pairmode" / "scripts"))
from flex_build import (  # noqa: E402
    _read_attempt_counters,
    bump_attempt_count,
    clear_attempt_count,
    read_attempt_count,
    write_attempt_count,
)

_STORY_A = "INFRA-282"
_STORY_B = "INFRA-283"


def test_two_stories_coexist_in_the_same_file(tmp_path: Path) -> None:
    """Writing A then B leaves both entries present (assertion 1)."""
    write_attempt_count(_STORY_A, 2, tmp_path)
    write_attempt_count(_STORY_B, 1, tmp_path)

    data = json.loads(_counter_path(tmp_path).read_text(encoding="utf-8"))
    assert data["stories"][_STORY_A] == 2
    assert data["stories"][_STORY_B] == 1


def test_read_attempt_counters_absent_file_returns_empty_dict(tmp_path: Path) -> None:
    """_read_attempt_counters returns {} when the file does not exist (assertion 2)."""
    assert _read_attempt_counters(tmp_path) == {}


def test_read_attempt_counters_malformed_file_returns_empty_dict(tmp_path: Path) -> None:
    """_read_attempt_counters returns {} on malformed JSON (assertion 2)."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    _counter_path(tmp_path).write_text("not json {{{", encoding="utf-8")
    assert _read_attempt_counters(tmp_path) == {}


def test_read_attempt_counters_legacy_shape(tmp_path: Path) -> None:
    """_read_attempt_counters normalises the legacy flat shape (assertion 3)."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    _counter_path(tmp_path).write_text(
        json.dumps({"story_id": _STORY_A, "attempt_count": 3}), encoding="utf-8"
    )
    assert _read_attempt_counters(tmp_path) == {_STORY_A: 3}


def test_read_attempt_counters_keyed_shape(tmp_path: Path) -> None:
    """_read_attempt_counters returns the keyed shape unchanged."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    _counter_path(tmp_path).write_text(
        json.dumps({"stories": {_STORY_A: 2, _STORY_B: 1}}), encoding="utf-8"
    )
    assert _read_attempt_counters(tmp_path) == {_STORY_A: 2, _STORY_B: 1}


def test_legacy_file_read_does_not_mutate_bytes(tmp_path: Path) -> None:
    """Reading a legacy-shape file via read_attempt_count performs no migration
    write — the file's bytes are unchanged after the read (assertion 3)."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    path = _counter_path(tmp_path)
    path.write_text(
        json.dumps({"story_id": _STORY_A, "attempt_count": 3}), encoding="utf-8"
    )
    before = path.read_bytes()

    assert read_attempt_count(_STORY_A, tmp_path) == 3
    assert read_attempt_count("INFRA-999", tmp_path) == 0

    assert path.read_bytes() == before


def test_legacy_file_upgraded_in_place_on_next_write(tmp_path: Path) -> None:
    """A write against a legacy-shape file upgrades it to the keyed shape and
    preserves the pre-existing legacy entry (assertion 4)."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    _counter_path(tmp_path).write_text(
        json.dumps({"story_id": _STORY_A, "attempt_count": 3}), encoding="utf-8"
    )

    write_attempt_count(_STORY_B, 1, tmp_path)

    data = json.loads(_counter_path(tmp_path).read_text(encoding="utf-8"))
    assert "stories" in data
    assert data["stories"][_STORY_A] == 3
    assert data["stories"][_STORY_B] == 1


def test_reads_are_per_key_and_never_cross_attribute(tmp_path: Path) -> None:
    """A count stored under one story is never returned for another, and is
    still returned for its own story even with siblings present (assertion 5)."""
    write_attempt_count(_STORY_A, 2, tmp_path)
    write_attempt_count(_STORY_B, 5, tmp_path)

    assert read_attempt_count(_STORY_A, tmp_path) == 2
    assert read_attempt_count(_STORY_B, tmp_path) == 5
    assert read_attempt_count("INFRA-999", tmp_path) == 0


def test_malformed_per_key_value_yields_zero_without_affecting_others(
    tmp_path: Path,
) -> None:
    """A non-coercible per-key value yields 0 for that key only (assertion 5)."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    _counter_path(tmp_path).write_text(
        json.dumps({"stories": {_STORY_A: "not-an-int", _STORY_B: 2}}),
        encoding="utf-8",
    )

    assert read_attempt_count(_STORY_A, tmp_path) == 0
    assert read_attempt_count(_STORY_B, tmp_path) == 2


def test_bumps_are_independent(tmp_path: Path) -> None:
    """Independent bumps across stories (assertion 6)."""
    write_attempt_count(_STORY_A, 2, tmp_path)
    write_attempt_count(_STORY_B, 1, tmp_path)

    assert bump_attempt_count(_STORY_B, tmp_path) == 2
    assert read_attempt_count(_STORY_A, tmp_path) == 2

    assert bump_attempt_count(_STORY_A, tmp_path) == 3


def test_bump_for_absent_story_starts_at_one_and_leaves_others_untouched(
    tmp_path: Path,
) -> None:
    """A bump for a story with no entry returns 1 and does not disturb siblings
    (assertion 6)."""
    write_attempt_count(_STORY_A, 4, tmp_path)

    assert bump_attempt_count(_STORY_B, tmp_path) == 1
    assert read_attempt_count(_STORY_A, tmp_path) == 4


def test_writes_are_atomic_not_write_text() -> None:
    """No write_text call inside the attempt-counter block (assertion 7)."""
    script_text = _SCRIPT.read_text(encoding="utf-8")
    start = script_text.index("# Per-story attempt counter")
    end = script_text.index("# Story cost estimate")
    block = script_text[start:end]
    assert "write_text" not in block


def test_scoped_clear_leaves_sibling_intact(tmp_path: Path) -> None:
    """clear_attempt_count(p, story_id) removes only that story's entry
    (assertion 8)."""
    write_attempt_count(_STORY_A, 2, tmp_path)
    write_attempt_count(_STORY_B, 1, tmp_path)

    clear_attempt_count(tmp_path, _STORY_A)

    assert read_attempt_count(_STORY_A, tmp_path) == 0
    assert read_attempt_count(_STORY_B, tmp_path) == 1
    assert _counter_path(tmp_path).exists()


def test_scoped_clear_of_last_entry_removes_file(tmp_path: Path) -> None:
    """Removing the last entry via a scoped clear deletes the file
    (assertion 8)."""
    write_attempt_count(_STORY_A, 2, tmp_path)

    clear_attempt_count(tmp_path, _STORY_A)

    assert not _counter_path(tmp_path).exists()


def test_unscoped_clear_still_removes_whole_file(tmp_path: Path) -> None:
    """clear_attempt_count(p) with no story_id keeps today's behaviour: whole
    file removed (assertion 8/9)."""
    write_attempt_count(_STORY_A, 2, tmp_path)
    write_attempt_count(_STORY_B, 1, tmp_path)

    clear_attempt_count(tmp_path)

    assert not _counter_path(tmp_path).exists()


def test_clear_attempt_count_cli_scoped_by_story_id(tmp_path: Path) -> None:
    """clear-attempt-count --story-id exits 0 and scopes the clear to that
    story (assertion 9)."""
    write_attempt_count(_STORY_A, 2, tmp_path)
    write_attempt_count(_STORY_B, 1, tmp_path)

    result = _run(
        "clear-attempt-count",
        "--story-id", _STORY_A,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert read_attempt_count(_STORY_A, tmp_path) == 0
    assert read_attempt_count(_STORY_B, tmp_path) == 1


def test_clear_attempt_count_cli_no_story_id_still_removes_file(
    tmp_path: Path,
) -> None:
    """clear-attempt-count with no --story-id still exits 0 and removes the
    file (assertion 9)."""
    write_attempt_count(_STORY_A, 2, tmp_path)

    result = _run("clear-attempt-count", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not _counter_path(tmp_path).exists()


def test_parallel_cross_story_clobber_regression(tmp_path: Path) -> None:
    """Reproduces the CER-095 cross-clobber sequence end-to-end: bump A twice,
    bump B once, A must still be 2; then merge-clear A, B must still be 1
    (assertion 13). Fails against pre-story flex_build.py, where B's bump —
    reading 0 because of the story-ID mismatch — would rewrite the whole file
    and silently reset A's count."""
    bump_attempt_count(_STORY_A, tmp_path)
    bump_attempt_count(_STORY_A, tmp_path)
    bump_attempt_count(_STORY_B, tmp_path)

    assert read_attempt_count(_STORY_A, tmp_path) == 2
    assert read_attempt_count(_STORY_B, tmp_path) == 1

    clear_attempt_count(tmp_path, _STORY_A)

    assert read_attempt_count(_STORY_A, tmp_path) == 0
    assert read_attempt_count(_STORY_B, tmp_path) == 1


# ---------------------------------------------------------------------------
# Tests — CER-147: attempt_counter.json writers are lock-protected (INFRA-336)
# ---------------------------------------------------------------------------


def test_bump_attempt_count_wraps_state_lock() -> None:
    """CER-147, Ensures 4: bump_attempt_count's read-modify-write body is
    wrapped in ``state_utils.state_lock`` — inline source inspection (not a
    behavioural proxy) so the test fails if a future edit removes the lock
    even when timing makes the concurrency test below flaky-pass."""
    import inspect

    from flex_build import bump_attempt_count as _bac

    src = inspect.getsource(_bac)
    assert "state_lock(" in src


def test_write_and_clear_attempt_count_wrap_state_lock() -> None:
    """CER-147, Ensures 4: write_attempt_count and clear_attempt_count also
    wrap their critical sections in state_lock (not just bump_attempt_count —
    the forbidden proxy named by Ensures 4 is wrapping only one of the
    three)."""
    import inspect

    from flex_build import clear_attempt_count as _cac
    from flex_build import write_attempt_count as _wac

    assert "state_lock(" in inspect.getsource(_wac)
    assert "state_lock(" in inspect.getsource(_cac)


def test_attempt_counter_lock_file_is_scoped_not_shared_with_state_json(
    tmp_path: Path,
) -> None:
    """CER-147, Instructions 3: the lock file used is
    ``attempt_counter.json.lock``, a sibling of ``attempt_counter.json`` —
    never ``state.json.lock``."""
    write_attempt_count(_STORY_A, 1, tmp_path)
    bump_attempt_count(_STORY_A, tmp_path)

    lock_path = tmp_path / ".companion" / "attempt_counter.json.lock"
    assert lock_path.exists()
    assert not (tmp_path / ".companion" / "state.json.lock").exists()


def test_concurrent_bumps_for_same_story_do_not_lose_an_update(
    tmp_path: Path,
) -> None:
    """CER-147, Ensures 5: two near-simultaneous bump_attempt_count calls for
    the *same* story_id, run as real threads (not a mock of the lock), both
    land — the final count is the starting count + 2, not +1.

    Uses real OS threads (not multiprocessing) so both calls share this
    process's ``fcntl.flock`` — POSIX advisory locks are per (file, process),
    so real inter-process contention needs subprocesses; the thread-level
    contention here still exercises the same read-modify-write window this
    story's fix narrows (the lock plus the atomic replace), and is the
    concurrency shape the story's Ensures 5 text names ("real threads or
    subprocesses, not a mock of the lock").
    """
    import threading

    write_attempt_count(_STORY_A, 5, tmp_path)

    barrier = threading.Barrier(2)

    def _bump() -> None:
        barrier.wait(timeout=5)
        bump_attempt_count(_STORY_A, tmp_path)

    threads = [threading.Thread(target=_bump) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert read_attempt_count(_STORY_A, tmp_path) == 7


def test_concurrent_writers_for_different_stories_do_not_clobber(
    tmp_path: Path,
) -> None:
    """CER-147, Ensures 5 (second test): simultaneous
    bump_attempt_count/write_attempt_count/clear_attempt_count calls for two
    *different* story_ids both land correctly and neither clobbers the
    other's final entry."""
    import threading

    write_attempt_count(_STORY_A, 1, tmp_path)
    write_attempt_count(_STORY_B, 10, tmp_path)

    _STORY_C = "INFRA-284"
    write_attempt_count(_STORY_C, 1, tmp_path)

    barrier = threading.Barrier(3)

    def _bump_a() -> None:
        barrier.wait(timeout=5)
        for _ in range(3):
            bump_attempt_count(_STORY_A, tmp_path)

    def _write_b() -> None:
        barrier.wait(timeout=5)
        write_attempt_count(_STORY_B, 20, tmp_path)

    def _clear_c() -> None:
        barrier.wait(timeout=5)
        clear_attempt_count(tmp_path, _STORY_C)

    threads = [
        threading.Thread(target=_bump_a),
        threading.Thread(target=_write_b),
        threading.Thread(target=_clear_c),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert read_attempt_count(_STORY_A, tmp_path) == 4
    assert read_attempt_count(_STORY_B, tmp_path) == 20
    assert read_attempt_count(_STORY_C, tmp_path) == 0

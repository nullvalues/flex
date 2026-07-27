"""Concurrency tests for skills/pairmode/scripts/effort_db.py (CER-096).

These exercise the genuinely-concurrent cases (A5, A6, C2) that need real
threads and a shared database file, so they do not fit either
test_effort_db.py's or test_subagent_transcript.py's fixtures.

Deterministic by construction: every thread is joined, assertions are made
on the final row set (never on timing), and a threading.Barrier is used
where workers must be made to contend on purpose — no sleep-as-a-
synchronisation-primitive anywhere in this file.
"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from skills.pairmode.scripts import effort_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / ".companion" / "effort.db"


def _required_fields(**overrides) -> dict:
    base = {
        "story_id": "INFRA-900",
        "agent_role": "builder",
        "attempt_number": 1,
        "ts": "2026-07-26T00:00:00+00:00",
    }
    base.update(overrides)
    return base


class TestConcurrentReaderWriter:
    def test_insert_succeeds_while_a_read_cursor_is_open(self, db_path: Path) -> None:
        """A5: a long-lived read connection with an open cursor over
        `attempts` must not block a concurrent insert_attempt call. Under
        the pre-CER-096 rollback-journal configuration, this is the shape
        that produced `database is locked`."""
        effort_db.init_db(db_path)
        effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-901"))

        reader_conn = sqlite3.connect(str(db_path))
        reader_cur = reader_conn.cursor()
        reader_cur.execute("SELECT * FROM attempts")
        # Cursor stays open (not fully consumed) across the write below.
        _first_row = reader_cur.fetchone()

        try:
            row_id = effort_db.insert_attempt(
                db_path, **_required_fields(story_id="INFRA-902")
            )
            assert row_id is not None

            rows = effort_db.query_by_story(db_path, "INFRA-902")
            assert len(rows) == 1
        finally:
            reader_cur.close()
            reader_conn.close()


class TestContentionIsRetriedNotLost:
    def test_eight_threads_five_inserts_each_all_land(self, db_path: Path) -> None:
        """A6: N=8 threads x 5 inserts each against the same database file
        must all succeed — no exception, no lost row. This test must fail
        if _connect's busy_timeout is removed."""
        effort_db.init_db(db_path)

        n_threads = 8
        inserts_per_thread = 5
        barrier = threading.Barrier(n_threads)
        errors: list[BaseException] = []
        lock = threading.Lock()

        def _worker(idx: int) -> None:
            try:
                barrier.wait()
                for i in range(inserts_per_thread):
                    effort_db.insert_attempt(
                        db_path,
                        **_required_fields(
                            story_id=f"INFRA-{1000 + idx}",
                            ts=f"2026-07-26T00:{idx:02d}:{i:02d}+00:00",
                        ),
                    )
            except BaseException as exc:  # noqa: BLE001
                with lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=_worker, args=(idx,)) for idx in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"worker exceptions: {errors!r}"
        assert len(effort_db.query_all(db_path)) == n_threads * inserts_per_thread


class TestAtomicAttemptNumberDerivation:
    def test_ten_threads_same_pair_no_duplicates_no_gaps(self, db_path: Path) -> None:
        """C2: this is the acceptance criterion for CER-096's atomic
        write-side attempt-number derivation — it must fail if the
        implementation reverts to a read-then-write pair (e.g. a
        next_attempt_number() COUNT(*) followed by a separate
        insert_attempt() call)."""
        effort_db.init_db(db_path)

        n_threads = 10
        barrier = threading.Barrier(n_threads)
        results: list[int] = []
        lock = threading.Lock()
        errors: list[BaseException] = []

        def _worker(idx: int) -> None:
            try:
                barrier.wait()
                _row_id, attempt_number = effort_db.insert_attempt_derived(
                    db_path,
                    story_id="INFRA-1100",
                    agent_role="builder",
                    ts=f"2026-07-26T01:{idx:02d}:00+00:00",
                )
                with lock:
                    results.append(attempt_number)
            except BaseException as exc:  # noqa: BLE001
                with lock:
                    errors.append(exc)

        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(_worker, idx) for idx in range(n_threads)]
            for fut in futures:
                fut.result()

        assert errors == [], f"worker exceptions: {errors!r}"
        assert sorted(results) == list(range(1, n_threads + 1))

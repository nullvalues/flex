"""state_utils.py — shared helpers for atomic state.json writes and locking.

CER-050 / INFRA-200: All state.json writers must use atomic write
(temp file + os.replace()) to avoid partial-write corruption.

INFRA-285 (CER-097): atomic replace makes a write all-or-nothing, but it does
nothing about the *read-modify-write window*. Two sessions that both read
state.json, mutate different keys and both write back produce a perfectly
well-formed file with one session's mutation silently dropped. Phase 109 makes
parallel builds and side sessions real, so this module also provides a bounded,
advisory, fail-open :func:`state_lock` and the single locked read-modify-write
helper :func:`update_state_json` that every state.json writer routes through.

This module is stdlib-only so it can be safely imported by hooks/
via the PYTHONPATH sys.path injection they already use. ``fcntl`` is imported
lazily inside :func:`state_lock` (never at module scope) so the module keeps
importing on non-POSIX platforms.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

#: How long :func:`state_lock` will wait for the advisory lock before giving up
#: and proceeding anyway. Deliberately short — see :func:`state_lock`'s
#: docstring for why "make the lock reliable" is a regression here.
STATE_LOCK_TIMEOUT_SECONDS = 2.0

#: Sleep between non-blocking acquisition attempts, in seconds.
_STATE_LOCK_POLL_SECONDS = 0.02


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write *data* as JSON to *path* atomically.

    1. Writes ``json.dumps(data, indent=2)`` to a ``.tmp`` sibling of *path*
       (same directory, so the rename crosses no filesystem boundary).
    2. Calls ``os.replace(tmp_path, path)`` — atomic on POSIX.
    3. On any exception: deletes the ``.tmp`` file if it exists, then re-raises.

    The directory of *path* must already exist; this function does not create it.
    """
    dir_ = path.parent
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=dir_,
            delete=False,
            suffix=".tmp",
        ) as tf:
            tf.write(json.dumps(data, indent=2))
            tmp_path = tf.name
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def _atomic_write_text(path: Path, text: str) -> None:
    """Write *text* to *path* atomically.

    Mirrors :func:`_atomic_write_json`'s contract exactly — temp-file sibling,
    ``os.replace``, cleanup-and-re-raise on failure — for ``str`` payloads. It
    exists because the markdown writers CER-097 named (``phase_new.py``'s phase
    manifest and index rows, ``story_update.py``'s story/phase status rewrites)
    are whole-file rewrites of *derived* content: a torn write there does not
    lose one row, it truncates the phase index.

    The directory of *path* must already exist; this function does not create it.
    """
    dir_ = path.parent
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=dir_,
            delete=False,
            suffix=".tmp",
        ) as tf:
            tf.write(text)
            tmp_path = tf.name
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# Advisory locking (INFRA-285 / CER-097)
# ---------------------------------------------------------------------------


def _load_fcntl():
    """Return the ``fcntl`` module, or ``None`` on a platform without it.

    Imported lazily (never at module scope) so ``state_utils`` keeps importing
    on non-POSIX platforms and the hooks' bare ``sys.path`` injection keeps
    working unchanged.
    """
    try:
        import fcntl  # noqa: PLC0415 — deliberate lazy import, see docstring
    except ImportError:
        return None
    return fcntl


def _acquire_state_lock(
    path: Path, timeout_seconds: float
) -> "tuple[int | None, bool]":
    """Try to take an exclusive advisory lock on ``<path>.lock``.

    Returns ``(fd, acquired)``. ``fd`` is ``None`` when the lock file could not
    even be opened (missing directory, read-only filesystem, no ``fcntl``);
    ``acquired`` is ``False`` when the descriptor exists but the lock was not
    obtained within *timeout_seconds*. Never raises — every failure is reported
    through the return value so :func:`state_lock` can yield anyway.

    Uses non-blocking ``flock(LOCK_EX | LOCK_NB)`` in a poll loop rather than a
    blocking ``flock``: a blocking call has no upper bound, and this runs on the
    hook path.
    """
    fcntl = _load_fcntl()
    if fcntl is None:
        return None, False

    lock_path = str(path) + ".lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return None, False

    try:
        deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd, True
            except OSError:
                if time.monotonic() >= deadline:
                    return fd, False
                time.sleep(_STATE_LOCK_POLL_SECONDS)
    except Exception:
        return fd, False


@contextmanager
def state_lock(
    path: "Path | str",
    timeout_seconds: float = STATE_LOCK_TIMEOUT_SECONDS,
) -> "Iterator[bool]":
    """Bounded, advisory, fail-open exclusive lock around a state-file update.

    Takes an exclusive ``fcntl.flock`` on a sibling lock file ``<path>.lock``,
    yields ``True`` when the lock was obtained (``False`` when it was not), and
    **always** releases and closes the descriptor in a ``finally``.

    Why it is deliberately weak — read before "fixing" it
    ----------------------------------------------------
    ``docs/ideology.md`` § Accepted constraints holds "hooks are thin relays
    only" with **no override permitted**. A lock *is* blocking logic, so the
    constraint's rationale — protect session performance, never stall the
    operator's session — rather than its letter, decides this design:

    - the wait is bounded at :data:`STATE_LOCK_TIMEOUT_SECONDS` (2 s);
    - acquisition is non-blocking-with-poll, never a blocking ``flock``;
    - **every** failure path yields anyway — timeout, no ``fcntl`` (non-POSIX),
      a missing or read-only directory, any ``OSError`` — degrading to exactly
      today's atomic-replace-only behaviour rather than raising.

    So the worst case for a hook is an unchanged-from-today racy write, never a
    stalled session. A future reviewer's instinct to "make the lock reliable" —
    retry until success, a lock daemon, contention logging — is a regression,
    not an improvement: it trades a rare lost update for a common stall. This
    lock **narrows** the read-modify-write window; it does not close it, and it
    does not make the system safe for two competing build loops (that remains
    out of scope, see ``docs/phases/phase-109.md`` § Scope statement).

    Never raises.
    """
    try:
        path = path if isinstance(path, Path) else Path(path)
    except Exception:
        yield False
        return

    fd: "int | None" = None
    acquired = False
    try:
        fd, acquired = _acquire_state_lock(path, timeout_seconds)
    except Exception:
        fd, acquired = None, False

    try:
        yield acquired
    finally:
        if fd is not None:
            if acquired:
                fcntl = _load_fcntl()
                if fcntl is not None:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
            try:
                os.close(fd)
            except Exception:
                pass


def update_state_json(
    path: "Path | str",
    mutate: "Callable[[dict], object]",
) -> "dict | None":
    """Perform one locked read-modify-write of the JSON file at *path*.

    Acquires :func:`state_lock`, reads and parses *path*, calls ``mutate(state)``
    and persists the (mutated) dict via :func:`_atomic_write_json`, returning the
    written dict.

    Returns ``None`` — leaving the file untouched — when:

    - the file is missing, unreadable, malformed, or its root is not a dict
      ("no update", matching every existing reader's fail-open contract);
    - ``mutate`` returns ``False`` (the explicit skip signal — the idempotency
      case in ``user_turn_seq.record_user_turn``, where the decision to write is
      itself part of the critical section and cannot be hoisted out of the lock);
    - any exception occurs anywhere in the call.

    Never raises. This is the single conversion target for every state.json
    read-modify-write in the codebase; a caller that reads, decides, and writes
    as three separate steps has re-opened the window this exists to narrow.
    """
    try:
        state_path = path if isinstance(path, Path) else Path(path)
        with state_lock(state_path):
            if not state_path.exists():
                return None
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, ValueError):
                return None
            if not isinstance(state, dict):
                return None
            if mutate(state) is False:
                return None
            _atomic_write_json(state_path, state)
            return state
    except Exception:
        return None

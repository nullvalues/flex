"""state_utils.py — shared helpers for atomic state.json writes.

CER-050 / INFRA-200: All state.json writers must use atomic write
(temp file + os.replace()) to avoid partial-write corruption.

This module is stdlib-only so it can be safely imported by hooks/
via the PYTHONPATH sys.path injection they already use.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


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

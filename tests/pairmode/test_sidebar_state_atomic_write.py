"""Tests for INFRA-202: sidebar.py's state.json writes route through
state_utils._atomic_write_json instead of raw write_text(json.dumps(...)).

The three sites (pipe_path write, mode-update, session_end) live inline inside
main()'s event loop and aren't independently callable without driving the
full interactive loop, so this asserts the source-level contract directly:
_atomic_write_json is imported and used for every state.json write site, and
no raw write_text(json.dumps(...)) call remains for STATE_PATH.
"""

from __future__ import annotations

import re
from pathlib import Path

SIDEBAR_PATH = (
    Path(__file__).parent.parent.parent
    / "skills"
    / "companion"
    / "scripts"
    / "sidebar.py"
)


def _source() -> str:
    return SIDEBAR_PATH.read_text(encoding="utf-8")


def test_sidebar_imports_atomic_write_json():
    source = _source()
    assert "from skills.pairmode.scripts.state_utils import _atomic_write_json" in source


def test_sidebar_state_json_writes_use_atomic_write_json():
    source = _source()

    state_write_vars = {"_state_path", "_sp"}
    for var in state_write_vars:
        pattern = re.compile(rf"\b{re.escape(var)}\.write_text\(json\.dumps\(")
        assert not pattern.search(source), (
            f"{var}.write_text(json.dumps(...)) still present — "
            "should route through _atomic_write_json"
        )

    # All three known call sites route through the shared helper.
    assert source.count("_atomic_write_json(_state_path, ") == 2
    assert source.count("_atomic_write_json(_sp, ") == 1


def test_sidebar_non_state_writers_untouched():
    """inc_path (capture log) and spec_path writes are out of scope — must remain raw."""
    source = _source()
    assert "inc_path.write_text(json.dumps(" in source
    assert "spec_path.write_text(json.dumps(" in source

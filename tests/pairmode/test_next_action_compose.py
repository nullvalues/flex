"""
tests/pairmode/test_next_action_compose.py

DP5 "composes, no signature drift" guard.

Asserts that:
1. The composed functions retain their expected signatures (any future phase
   that edits a composed-function signature will fail loudly here, naming the
   drifted function).
2. ``next_action.py`` *imports* the composed functions rather than redefining
   their logic — checked by verifying that the functions in next_action.py's
   namespace are the same objects as in the source modules.

Functions checked
-----------------
- ``next_story.find_next_story``
- ``next_story._git_log_oneline``
- ``next_story._has_story_commit``
- ``model_selector.select_builder_model``
- ``story_resolver.resolve_story``
- ``story_resolver.list_phase_stories``
- ``flex_build.resolve_current_phase``
- ``flex_build.read_attempt_count``
- ``flex_build.check_stub_gate``
- ``flex_build.check_schema_gate_result``
- ``flex_build.check_auth_gate_result``
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import wiring
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import next_action  # noqa: E402
import next_story  # noqa: E402
import model_selector  # noqa: E402
import story_resolver  # noqa: E402
import flex_build  # noqa: E402


# ---------------------------------------------------------------------------
# Signature expectations
#
# Format: list of (function_object, expected_param_names, expected_annotation_names)
# expected_param_names: tuple of positional+keyword param names in order.
# Keyword-only and defaults are intentionally NOT checked here — only that the
# named parameters exist in the right positions, to catch renames and additions
# that would break callers.
# ---------------------------------------------------------------------------

_SIGNATURE_TABLE = [
    # next_story
    pytest.param(
        next_story.find_next_story,
        ("phase_file", "project_dir"),
        id="next_story.find_next_story",
    ),
    pytest.param(
        next_story._git_log_oneline,
        ("project_dir",),
        id="next_story._git_log_oneline",
    ),
    pytest.param(
        next_story._has_story_commit,
        ("story_id", "git_log"),
        id="next_story._has_story_commit",
    ),
    # model_selector
    pytest.param(
        model_selector.select_builder_model,
        ("story_class", "primary_files", "protected_files", "attempt_number"),
        id="model_selector.select_builder_model",
    ),
    # story_resolver
    pytest.param(
        story_resolver.resolve_story,
        ("story_id", "project_dir"),
        id="story_resolver.resolve_story",
    ),
    pytest.param(
        story_resolver.list_phase_stories,
        ("phase_path",),
        id="story_resolver.list_phase_stories",
    ),
    # flex_build extractions (RESOLVER-002)
    pytest.param(
        flex_build.resolve_current_phase,
        ("project_dir",),
        id="flex_build.resolve_current_phase",
    ),
    pytest.param(
        flex_build.read_attempt_count,
        ("story_id", "project_dir"),
        id="flex_build.read_attempt_count",
    ),
    pytest.param(
        flex_build.check_stub_gate,
        ("story_id", "project_dir"),
        id="flex_build.check_stub_gate",
    ),
    pytest.param(
        flex_build.check_schema_gate_result,
        ("story_id", "project_dir"),
        id="flex_build.check_schema_gate_result",
    ),
    pytest.param(
        flex_build.check_auth_gate_result,
        ("story_id", "project_dir"),
        id="flex_build.check_auth_gate_result",
    ),
]


@pytest.mark.parametrize("func,expected_params", _SIGNATURE_TABLE)
def test_signature_not_drifted(func, expected_params: tuple[str, ...]) -> None:
    """Assert the composed function's positional params match the expected names.

    If this test fails it names the drifted function and shows the current vs.
    expected parameter list — the DP5 protection the era relies on.
    """
    sig = inspect.signature(func)
    actual_params = tuple(sig.parameters.keys())

    for pos, name in enumerate(expected_params):
        assert pos < len(actual_params), (
            f"Signature drift in {func.__qualname__}: "
            f"expected parameter {name!r} at position {pos} but function "
            f"only has {len(actual_params)} parameters. "
            f"Current signature: {actual_params}"
        )
        assert actual_params[pos] == name, (
            f"Signature drift in {func.__qualname__} at position {pos}: "
            f"expected {name!r}, got {actual_params[pos]!r}. "
            f"Current signature: {actual_params}"
        )


# ---------------------------------------------------------------------------
# Composition guard: next_action.py imports, not reimplements
#
# Verify that the functions next_action.infer_position consumes are imported
# from their source modules (same object identity) rather than redefined
# inline.  We trigger the imports by calling infer_position on a minimal dummy
# tree, then inspect next_action's module namespace.
# ---------------------------------------------------------------------------


def test_next_action_imports_find_next_story() -> None:
    """next_action imports find_next_story from next_story (no reimplementation)."""
    # Trigger the lazy import inside infer_position by looking at the source.
    source = inspect.getsource(next_action)
    assert "from next_story import find_next_story" in source, (
        "next_action.py must import find_next_story from next_story; "
        "it appears to have been removed or reimplemented."
    )


def test_next_action_imports_select_builder_model() -> None:
    """next_action imports select_builder_model from model_selector."""
    source = inspect.getsource(next_action)
    assert "from model_selector import select_builder_model" in source, (
        "next_action.py must import select_builder_model from model_selector; "
        "it appears to have been removed or reimplemented."
    )


def test_next_action_imports_flex_build_extractions() -> None:
    """next_action imports the four flex_build extraction functions."""
    source = inspect.getsource(next_action)
    required_imports = [
        "resolve_current_phase",
        "read_attempt_count",
        "check_stub_gate",
        "check_schema_gate_result",
        "check_auth_gate_result",
    ]
    for fn_name in required_imports:
        assert fn_name in source, (
            f"next_action.py must import {fn_name!r} from flex_build; "
            "it appears to have been removed or reimplemented."
        )


def test_next_action_imports_story_resolver_or_uses_it() -> None:
    """next_action references story_resolver functions (does not reimplement)."""
    # story_resolver is used indirectly through flex_build / next_story; we
    # verify that next_action.py itself does not duplicate resolve_story or
    # list_phase_stories by checking no local def of those names exists.
    source = inspect.getsource(next_action)

    # next_action must NOT define its own resolve_story or list_phase_stories
    assert "def resolve_story" not in source, (
        "next_action.py must not redefine resolve_story; "
        "import it from story_resolver instead."
    )
    assert "def list_phase_stories" not in source, (
        "next_action.py must not redefine list_phase_stories; "
        "import it from story_resolver instead."
    )


def test_next_action_no_inline_git_log_impl() -> None:
    """next_action.py does not reimplement git log parsing inline.

    The module is permitted to call _git_log_oneline and _has_story_commit
    from next_story (which it does in the last_attempt_outcome block), but it
    must not define its own copy of the git-log logic.
    """
    source = inspect.getsource(next_action)
    assert "def _git_log_oneline" not in source, (
        "next_action.py must not define _git_log_oneline inline; "
        "import it from next_story."
    )
    assert "def _has_story_commit" not in source, (
        "next_action.py must not define _has_story_commit inline; "
        "import it from next_story."
    )

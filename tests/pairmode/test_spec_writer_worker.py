"""
tests/pairmode/test_spec_writer_worker.py — tests for the spec-writer worker
procedure and SPEC-RESULT contract (WORKER-013).

Coverage:
- procedure.md exists at the expected path.
- Bounded inputs: procedure references only the four declared inputs (no
  forbidden file paths).
- Single write target: procedure contains no paths outside docs/stories/.
- Injected SPEC-RESULT{status: "done"} parses via worker_result.parse_worker_result.
- Injected SPEC-RESULT{status: "revised"} parses via worker_result.parse_worker_result.
- No live API call: procedure.md contains no API endpoint strings.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
_PROCEDURE_PATH = (
    _REPO_ROOT / "skills" / "pairmode" / "skills" / "spec-writer" / "procedure.md"
)

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import worker_result  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_procedure() -> str:
    return _PROCEDURE_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Existence check
# ---------------------------------------------------------------------------


def test_procedure_file_exists() -> None:
    """The spec-writer procedure.md must exist at the declared path."""
    assert _PROCEDURE_PATH.exists(), (
        f"Procedure file not found at {_PROCEDURE_PATH}"
    )


# ---------------------------------------------------------------------------
# Bounded inputs (DP1.3 negative assertion)
# ---------------------------------------------------------------------------

# Files and directories that are NOT among the four declared bounded inputs
# and must not appear as targets to read in the procedure.
_FORBIDDEN_READ_PATTERNS: list[str] = [
    # orchestrator state
    ".companion/state.json",
    "effort.db",
    "attempt_counter.json",
    # build orchestrator
    "CLAUDE.build.md",
    # scripts or skills beyond the procedure itself
    "skills/pairmode/scripts/",
    # raw template files
    "skills/pairmode/templates/",
    # phase-level permissions
    "docs/phases/permissions/",
]


@pytest.mark.parametrize("forbidden", _FORBIDDEN_READ_PATTERNS)
def test_bounded_inputs_no_forbidden_reads(forbidden: str) -> None:
    """Procedure must not reference file paths outside the four declared inputs."""
    text = _read_procedure()
    assert forbidden not in text, (
        f"Procedure references forbidden path {forbidden!r} "
        "(violates DP1.3 input-bound property)"
    )


# ---------------------------------------------------------------------------
# Single write target — no out-of-scope paths
# ---------------------------------------------------------------------------

# Paths that a write instruction must NOT target (outside docs/stories/).
# These are checked only in lines that carry an affirmative write instruction
# (contain "write" but not a prohibition word).
_FORBIDDEN_WRITE_PATHS: list[str] = [
    "docs/phases/phase-",
    "docs/architecture.md",
    "CLAUDE.md",
    ".companion/",
    "lessons/",
    "hooks/",
]

# Words that indicate a prohibition context — the path is being named as
# something to AVOID, not to write to.
_PROHIBITION_WORDS: tuple[str, ...] = (
    "not",
    "never",
    "no other",
    "do not",
    "only",
    "must not",
    "avoid",
    "except",
)


@pytest.mark.parametrize("forbidden_write", _FORBIDDEN_WRITE_PATHS)
def test_single_write_target_no_out_of_scope_paths(forbidden_write: str) -> None:
    """Procedure must not instruct writing to any path outside docs/stories/.

    Checks only lines that carry an affirmative write instruction (contain the
    word 'write' without a prohibition qualifier). Read-context references
    (e.g. listing the phase doc as a bounded input to READ) are acceptable.
    """
    text = _read_procedure()
    for line in text.splitlines():
        stripped = line.strip().lower()
        # Only examine lines that contain both "write" and the forbidden path.
        if "write" not in stripped:
            continue
        if forbidden_write.lower() not in stripped:
            continue
        # Line contains both "write" and the forbidden path — check that it is
        # a prohibition (telling the agent NOT to write there).
        is_prohibition = any(word in stripped for word in _PROHIBITION_WORDS)
        assert is_prohibition, (
            f"Procedure appears to instruct writing to {forbidden_write!r} "
            f"in a non-prohibition write-context line: {line!r}"
        )


def test_procedure_write_target_is_docs_stories() -> None:
    """Procedure's write step must target docs/stories/ only."""
    text = _read_procedure()
    # Verify that the write section explicitly names docs/stories/
    assert "docs/stories/" in text, (
        "Procedure must explicitly name docs/stories/ as the write target"
    )


# ---------------------------------------------------------------------------
# SPEC-RESULT schema — injected result parsing (no live API call)
# ---------------------------------------------------------------------------


def test_spec_result_done_parses() -> None:
    """SPEC-RESULT with status 'done' must parse via parse_worker_result."""
    payload = json.dumps(
        {"type": "SPEC-RESULT", "story_id": "BUILD-099", "status": "done"}
    )
    result = worker_result.parse_worker_result(payload)
    assert result["type"] == worker_result.SPEC_RESULT
    assert result["story_id"] == "BUILD-099"
    assert result["status"] == "done"


def test_spec_result_revised_parses() -> None:
    """SPEC-RESULT with status 'revised' must parse via parse_worker_result."""
    payload = json.dumps(
        {"type": "SPEC-RESULT", "story_id": "BUILD-099", "status": "revised"}
    )
    result = worker_result.parse_worker_result(payload)
    assert result["type"] == worker_result.SPEC_RESULT
    assert result["story_id"] == "BUILD-099"
    assert result["status"] == "revised"


def test_spec_result_invalid_status_rejected() -> None:
    """SPEC-RESULT with an invalid status must be rejected."""
    payload = json.dumps(
        {"type": "SPEC-RESULT", "story_id": "BUILD-099", "status": "unknown"}
    )
    with pytest.raises(ValueError, match="status"):
        worker_result.parse_worker_result(payload)


def test_spec_result_missing_story_id_rejected() -> None:
    """SPEC-RESULT missing story_id must be rejected."""
    payload = json.dumps({"type": "SPEC-RESULT", "status": "done"})
    with pytest.raises(ValueError, match="story_id"):
        worker_result.parse_worker_result(payload)


# ---------------------------------------------------------------------------
# No live API call
# ---------------------------------------------------------------------------

# Patterns that would indicate an API call embedded in the procedure text.
_API_CALL_PATTERNS: list[str] = [
    "anthropic.com",
    "api.anthropic",
    "openai.com",
    "requests.get",
    "requests.post",
    "httpx",
    "urllib.request",
]


@pytest.mark.parametrize("pattern", _API_CALL_PATTERNS)
def test_no_live_api_call_in_procedure(pattern: str) -> None:
    """Procedure must not contain API endpoint strings or HTTP client calls."""
    text = _read_procedure()
    assert pattern not in text, (
        f"Procedure contains API call pattern {pattern!r} — "
        "spec-writer must not make live API calls"
    )

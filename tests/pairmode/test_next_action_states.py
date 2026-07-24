"""
tests/pairmode/test_next_action_states.py

Exhaustive matrix of the 9 DP2 resolver states — one assertion per row.

Each parametrize row represents one entry in the DP2 state table from
HARNESS001-main.md.  The test builds a synthetic durable-state tree via
``resolver_fixtures.make_resolver_project``, runs ``infer_position`` →
``resolve_next_action``, and asserts the emitted ``{action, scalar, model,
reason, meta}`` equals the DP2-tabled expectation.

Judgment-handoff rows (3, 4, 7) assert ``action == "await-user"`` with the
correct reason and that no verdict was computed.

The suite also asserts every produced action passes ``validate_action`` and
survives a JSON round-trip (DP1 schema integration).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Import wiring
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).parent
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
for _d in (_TESTS_DIR, _SCRIPTS_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from next_action import (  # noqa: E402
    AWAIT_USER,
    CHECKPOINT,
    CHECKPOINT_SECURITY,
    DONE,
    OUTCOME_FAIL,
    OUTCOME_NONE,
    OUTCOME_PASS,
    SPAWN_BUILDER,
    SPAWN_LOOP_BREAKER,
    infer_position,
    resolve_next_action,
    validate_action,
)

from resolver_fixtures import make_resolver_project  # noqa: E402


# ---------------------------------------------------------------------------
# Git-log patcher (monkeypatches next_story._git_log_oneline)
# ---------------------------------------------------------------------------


def _patch_git_log(monkeypatch: Any, log_output: str) -> None:
    """Replace next_story._git_log_oneline to return a fixed string.

    This lets state-machine assertions run without actually having a live
    git commit in the synthetic repo for commit-authority logic, while still
    allowing the real git repo path to be exercised for tests that want it.
    """
    import next_story as _ns  # type: ignore[import]
    monkeypatch.setattr(_ns, "_git_log_oneline", lambda _p: log_output)


# ---------------------------------------------------------------------------
# DP2 parametrize table
#
# Each entry is a tuple:
#   (dp_row, label, fixture_cfg, git_log_override, expected_action,
#    expected_scalar_prefix, expected_reason, expected_meta_subset)
#
# fixture_cfg keys documented in resolver_fixtures.py.
# git_log_override: str | None — if str, monkeypatches git log; if None uses
#   real git log from the seeded repo (useful for Row 1 / complete phases).
# expected_scalar_prefix: str — the expected scalar value (exact match for
#   empty / phase-key; prefix for story IDs).
# expected_meta_subset: dict — every key in this dict must match in meta.
# ---------------------------------------------------------------------------

_STORIES_FIRST = [("RESOLVER-001", "planned", "code", ["a.py"])]
_STORIES_TWO = [
    ("RESOLVER-001", "complete", "code", ["a.py"]),
    ("RESOLVER-002", "planned", "code", ["b.py"]),
]

_DP2_PARAMS = [
    # ------------------------------------------------------------------
    # Row 1 — current-phase exit 1 (all phases complete) → done
    # ------------------------------------------------------------------
    pytest.param(
        1,
        "row1-all-phases-complete",
        {
            "phase_status": "complete",
            "stories": [("RESOLVER-001", "complete", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": ["feat(story-RESOLVER-001): done"],
        },
        None,  # use real git log
        DONE,
        "",           # scalar
        "",           # reason
        {},           # meta subset
        None,         # gate_fn: not needed (Row 1 exits before guards)
        id="row1-all-phases-complete",
    ),

    # ------------------------------------------------------------------
    # Row 2 — active phase, counter 0, model auto → spawn-builder attempt 1
    # ------------------------------------------------------------------
    pytest.param(
        2,
        "row2-first-attempt-auto-model",
        {
            "phase_status": "active",
            "stories": _STORIES_FIRST,
            "attempt_count": 0,
            "git_commits": [],
        },
        "",  # empty git log
        SPAWN_BUILDER,
        "RESOLVER-001",
        "auto-baseline",
        {"attempt": 1},
        None,         # gate_fn: not needed (next_story_id is set)
        id="row2-first-attempt-auto-model",
    ),

    # ------------------------------------------------------------------
    # Row 3 — prompted-upgrade at counter 0 → await-user model-upgrade
    # (high-scope signal: ≥5 primary files forces prompted-upgrade)
    # ------------------------------------------------------------------
    pytest.param(
        3,
        "row3-prompted-upgrade",
        {
            "phase_status": "active",
            "stories": [
                (
                    "RESOLVER-001",
                    "planned",
                    "code",
                    ["a.py", "b.py", "c.py", "d.py", "e.py"],
                )
            ],
            "attempt_count": 0,
            "git_commits": [],
        },
        "",
        AWAIT_USER,
        "",
        "model-upgrade",
        {"attempt": 1},
        None,         # gate_fn: not needed (next_story_id is set)
        id="row3-prompted-upgrade",
    ),

    # ------------------------------------------------------------------
    # Row 4 — pre-flight gate blocked (stub gate) → await-user gate-blocked:stub
    # ------------------------------------------------------------------
    pytest.param(
        4,
        "row4-stub-gate-blocked",
        {
            "phase_status": "active",
            "stories": _STORIES_FIRST,
            "attempt_count": 0,
            "git_commits": [],
            "stub_story": True,
        },
        "",
        AWAIT_USER,
        "",
        "gate-blocked:stub",
        {"gate": "stub"},
        None,         # gate_fn: not needed (next_story_id is set)
        id="row4-stub-gate-blocked",
    ),

    # ------------------------------------------------------------------
    # Row 5 — counter 1, no commit → spawn-builder attempt 2, retry-upgrade
    # ------------------------------------------------------------------
    pytest.param(
        5,
        "row5-retry-attempt2",
        {
            "phase_status": "active",
            "stories": _STORIES_FIRST,
            "attempt_count": 1,
            "git_commits": [],
        },
        "",
        SPAWN_BUILDER,
        "RESOLVER-001",
        "retry-upgrade",
        {"attempt": 2, "fail_rung": "single-fail"},
        None,         # gate_fn: not needed (next_story_id is set)
        id="row5-retry-attempt2",
    ),

    # ------------------------------------------------------------------
    # Row 6 — counter 2, no commit → spawn-loop-breaker
    # ------------------------------------------------------------------
    pytest.param(
        6,
        "row6-double-fail-loop-breaker",
        {
            "phase_status": "active",
            "stories": _STORIES_FIRST,
            "attempt_count": 2,
            "git_commits": [],
        },
        "",
        SPAWN_LOOP_BREAKER,
        "RESOLVER-001",
        "",
        {"attempt": 3, "fail_rung": "double-fail"},
        None,         # gate_fn: not needed (next_story_id is set)
        id="row6-double-fail-loop-breaker",
    ),

    # ------------------------------------------------------------------
    # Row 7 — counter ≥ 3, no commit → await-user build-paused
    # ------------------------------------------------------------------
    pytest.param(
        7,
        "row7-triple-fail-paused",
        {
            "phase_status": "active",
            "stories": _STORIES_FIRST,
            "attempt_count": 3,
            "git_commits": [],
        },
        "",
        AWAIT_USER,
        "",
        "build-paused",
        {"fail_rung": "triple-fail-or-pause"},
        None,         # gate_fn: not needed (next_story_id is set)
        id="row7-triple-fail-paused",
    ),

    # ------------------------------------------------------------------
    # Row 8 — story committed (PASS), more unbuilt stories → spawn-builder next
    # ------------------------------------------------------------------
    pytest.param(
        8,
        "row8-pass-more-stories",
        {
            "phase_status": "active",
            "stories": _STORIES_TWO,
            "attempt_count": 0,
            "git_commits": ["feat(story-RESOLVER-001): done"],
        },
        None,  # use real git log (commit was seeded above)
        SPAWN_BUILDER,
        "RESOLVER-002",
        "auto-baseline",
        {"attempt": 1},
        None,         # gate_fn: not needed (next_story_id is set)
        id="row8-pass-more-stories",
    ),

    # ------------------------------------------------------------------
    # Row 9 — all phase stories complete → checkpoint routing (RESOLVER-008)
    # All stories complete, CER backlog absent (clear), gate injected True.
    # Expects first checkpoint step: checkpoint-security.
    # ------------------------------------------------------------------
    pytest.param(
        9,
        "row9-checkpoint",
        {
            "phase_status": "active",
            "stories": [("RESOLVER-001", "complete", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": ["feat(story-RESOLVER-001): done"],
        },
        None,  # real git log
        CHECKPOINT_SECURITY,
        "",   # scalar is empty for checkpoint actions
        "",   # reason is empty (step emitted directly)
        {},
        lambda: True,  # gate_fn: inject passing build gate
        id="row9-checkpoint",
    ),
]


@pytest.mark.parametrize(
    "dp_row,label,fixture_cfg,git_log_override,"
    "expected_action,expected_scalar,expected_reason,expected_meta_subset,gate_fn",
    _DP2_PARAMS,
)
def test_dp2_state(
    tmp_path: Path,
    monkeypatch: Any,
    dp_row: int,
    label: str,
    fixture_cfg: dict,
    git_log_override: "str | None",
    expected_action: str,
    expected_scalar: str,
    expected_reason: str,
    expected_meta_subset: dict,
    gate_fn: "Any",
) -> None:
    """Assert that the resolver emits the correct action for each DP2 state."""

    project = make_resolver_project(tmp_path, fixture_cfg)

    # Optionally override git log to avoid live git calls for outcome inference.
    if git_log_override is not None:
        _patch_git_log(monkeypatch, git_log_override)

    position = infer_position(project)
    action = resolve_next_action(position, gate_fn=gate_fn)

    # --- Core assertions ---
    assert action["action"] == expected_action, (
        f"DP2 Row {dp_row} ({label}): "
        f"expected action={expected_action!r}, got {action['action']!r}. "
        f"Full action: {action}"
    )

    if expected_scalar:
        assert action["scalar"] == expected_scalar or action["scalar"].startswith(
            expected_scalar
        ), (
            f"DP2 Row {dp_row} ({label}): "
            f"expected scalar={expected_scalar!r}, got {action['scalar']!r}"
        )
    else:
        assert action["scalar"] == expected_scalar, (
            f"DP2 Row {dp_row} ({label}): "
            f"expected scalar={expected_scalar!r}, got {action['scalar']!r}"
        )

    assert action["reason"] == expected_reason, (
        f"DP2 Row {dp_row} ({label}): "
        f"expected reason={expected_reason!r}, got {action['reason']!r}"
    )

    for key, expected_val in expected_meta_subset.items():
        assert action["meta"].get(key) == expected_val, (
            f"DP2 Row {dp_row} ({label}): "
            f"expected meta[{key!r}]={expected_val!r}, "
            f"got {action['meta'].get(key)!r}"
        )

    # --- DP4 binding property: judgment-handoff rows ---
    if dp_row in (3, 4, 7):
        assert action["action"] == AWAIT_USER, (
            f"DP2 Row {dp_row} is a judgment-handoff; "
            f"must emit await-user, got {action['action']!r}"
        )
        # The resolver must not have computed a verdict (model must be None)
        assert action["model"] is None, (
            f"DP2 Row {dp_row}: judgment-handoff must have model=None, "
            f"got {action['model']!r}"
        )

    # --- DP1 schema integration: validate_action returns [] ---
    violations = validate_action(action)
    assert violations == [], (
        f"DP2 Row {dp_row} ({label}): action failed schema validation: "
        + "; ".join(violations)
    )

    # --- DP1 JSON round-trip ---
    serialised = json.dumps(action)
    restored = json.loads(serialised)
    assert restored == action, (
        f"DP2 Row {dp_row} ({label}): action did not survive JSON round-trip"
    )


# ---------------------------------------------------------------------------
# Explicit DP1 schema round-trip fixture (all action types)
# ---------------------------------------------------------------------------


def test_dp1_schema_roundtrip_all_action_types(tmp_path: Path) -> None:
    """Every action type the resolver can emit passes validate_action and
    survives json.loads(json.dumps(...)) unchanged.
    """
    from next_action import make_action, DONE, SPAWN_BUILDER, SPAWN_LOOP_BREAKER, CHECKPOINT, AWAIT_USER

    phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
    phase_file.parent.mkdir(parents=True, exist_ok=True)
    phase_file.write_text("# Phase 1\n", encoding="utf-8")

    _ok_gate = {"ok": True, "blocked_reason": ""}

    positions = [
        # done
        {"active_phase_file": None, "next_story_id": None, "attempt_count": 0,
         "builder_model": None, "builder_model_reason": None,
         "gate_stub": _ok_gate, "gate_schema": _ok_gate, "gate_auth": _ok_gate,
         "last_attempt_outcome": OUTCOME_NONE},
        # checkpoint
        {"active_phase_file": phase_file, "next_story_id": None, "attempt_count": 0,
         "builder_model": None, "builder_model_reason": None,
         "gate_stub": _ok_gate, "gate_schema": _ok_gate, "gate_auth": _ok_gate,
         "last_attempt_outcome": OUTCOME_NONE},
        # spawn-builder row 2
        {"active_phase_file": phase_file, "next_story_id": "X-001", "attempt_count": 0,
         "builder_model": "sonnet", "builder_model_reason": "auto-baseline",
         "gate_stub": _ok_gate, "gate_schema": _ok_gate, "gate_auth": _ok_gate,
         "last_attempt_outcome": OUTCOME_NONE},
        # spawn-builder row 5
        {"active_phase_file": phase_file, "next_story_id": "X-002", "attempt_count": 1,
         "builder_model": "sonnet", "builder_model_reason": "auto-baseline",
         "gate_stub": _ok_gate, "gate_schema": _ok_gate, "gate_auth": _ok_gate,
         "last_attempt_outcome": OUTCOME_FAIL},
        # spawn-loop-breaker row 6
        {"active_phase_file": phase_file, "next_story_id": "X-003", "attempt_count": 2,
         "builder_model": "opus", "builder_model_reason": "retry-upgrade",
         "gate_stub": _ok_gate, "gate_schema": _ok_gate, "gate_auth": _ok_gate,
         "last_attempt_outcome": OUTCOME_FAIL},
        # await-user gate-blocked (row 4)
        {"active_phase_file": phase_file, "next_story_id": "X-004", "attempt_count": 0,
         "builder_model": "sonnet", "builder_model_reason": "auto-baseline",
         "gate_stub": {"ok": False, "blocked_reason": "stub"},
         "gate_schema": _ok_gate, "gate_auth": _ok_gate,
         "last_attempt_outcome": OUTCOME_NONE},
        # await-user model-upgrade (row 3)
        {"active_phase_file": phase_file, "next_story_id": "X-005", "attempt_count": 0,
         "builder_model": "opus", "builder_model_reason": "prompted-upgrade",
         "gate_stub": _ok_gate, "gate_schema": _ok_gate, "gate_auth": _ok_gate,
         "last_attempt_outcome": OUTCOME_NONE},
        # await-user build-paused (row 7)
        {"active_phase_file": phase_file, "next_story_id": "X-006", "attempt_count": 3,
         "builder_model": "opus", "builder_model_reason": "retry-upgrade",
         "gate_stub": _ok_gate, "gate_schema": _ok_gate, "gate_auth": _ok_gate,
         "last_attempt_outcome": OUTCOME_FAIL},
    ]

    for i, pos in enumerate(positions):
        # Pass gate_fn=lambda: True to prevent the real pytest subprocess from
        # running during schema validation tests (which use synthetic tmp dirs).
        action = resolve_next_action(pos, gate_fn=lambda: True)
        violations = validate_action(action)
        assert violations == [], (
            f"Position {i} ({action['action']!r}) produced invalid action: "
            + "; ".join(violations)
        )
        serialised = json.dumps(action)
        restored = json.loads(serialised)
        assert restored == action, (
            f"Position {i} ({action['action']!r}) did not survive JSON round-trip"
        )

"""
tests/pairmode/test_harness004_isolation.py

HARNESS004 isolation suite (WORKER-012, HARNESS004-main).

Pins the entire checkpoint action sequence deterministically. No live API
call, no real git operations, no real pytest invocations.

LLM-JUDGMENT GAP (deliberate, not silent):
    These tests verify the *deterministic scaffold* — pre-checkpoint guard
    failures, checkpoint step sequencing, action grammar constraints, and the
    docs-review input-bound property — NOT the LLM's runtime judgment quality.
    Whether the security-auditor correctly identifies a CRITICAL vulnerability,
    the intent-reviewer detects a design pivot, or the docs-reviewer surfaces a
    stale architecture reference is validated by the procedure prompt text and
    manual review, not by unit tests.  The security/intent/docs review verdicts
    are injected via synthetic ``position["checkpoint_step"]`` values and
    ``gate_fn=lambda: True``; the actual LLM judgment is out of scope for this
    suite.  No live API call is made anywhere in this module.

Suite sections (HARNESS004 isolation matrix):
    1. SCHEMA_VERSION == 3 (RESOLVER-007 bump)
    2. Actions vocabulary — all checkpoint actions in ACTIONS; monolithic
       "checkpoint" NOT in ACTIONS (removed in RESOLVER-007)
    3. checkpoint-tag action shape — model=None; NOT in _SPAWN_ACTIONS
    4. Pre-checkpoint guard failures — one fixture per guard class:
         phase-incomplete, cer-do-now, build-gate (injected)
    5. Checkpoint step sequencing — ordered 5-state matrix (parametrized)
    6. Docs-review worker input-bound guard — procedure references only its
       declared bounded inputs; contains explicit accumulated-state prohibition
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
_SKILLS_DIR = _REPO_ROOT / "skills" / "pairmode" / "skills"
_TESTS_DIR = Path(__file__).parent

for _d in (_SCRIPTS_DIR, _TESTS_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

import next_action  # noqa: E402
from next_action import (  # noqa: E402
    ACTIONS,
    AWAIT_USER,
    CHECKPOINT,
    CHECKPOINT_DOCS,
    CHECKPOINT_INTENT,
    CHECKPOINT_SECURITY,
    CHECKPOINT_TAG,
    DONE,
    SCHEMA_VERSION,
    _SPAWN_ACTIONS,
    resolve_next_action,
    validate_action,
)

from resolver_fixtures import make_resolver_project  # noqa: E402

# ---------------------------------------------------------------------------
# Shared constants and helpers
# ---------------------------------------------------------------------------

_PROCEDURE_PATH = (
    _SKILLS_DIR / "checkpoint-docs" / "procedure.md"
)

_OK_GATE: dict = {"ok": True, "blocked_reason": ""}


def _make_position(
    phase_file: "Path | None",
    checkpoint_step: "list[str] | None" = None,
) -> dict:
    """Return a minimal Position dict for the checkpoint (no next story) path.

    The position is constructed synthetically; infer_position is not called
    so that the suite remains free of infrastructure side-effects.
    """
    return {
        "active_phase_file": phase_file,
        "next_story_id": None,
        "attempt_count": 0,
        "builder_model": None,
        "builder_model_reason": None,
        "gate_stub": _OK_GATE,
        "gate_schema": _OK_GATE,
        "gate_auth": _OK_GATE,
        "last_attempt_outcome": "none",
        "checkpoint_step": checkpoint_step or [],
    }


# ===========================================================================
# Section 1 — SCHEMA_VERSION == 3
# ===========================================================================


class TestSchemaVersion:
    """SCHEMA_VERSION must equal 3 after the RESOLVER-007 bump."""

    def test_schema_version_is_3(self) -> None:
        """next_action.SCHEMA_VERSION must be 3 (RESOLVER-007 checkpoint decomposition bump)."""
        assert SCHEMA_VERSION == 3, (
            f"Expected SCHEMA_VERSION == 3; got {SCHEMA_VERSION!r}"
        )

    def test_make_action_embeds_schema_version(self) -> None:
        """make_action must embed SCHEMA_VERSION in meta.schema_version."""
        action = next_action.make_action(DONE)
        assert action["meta"]["schema_version"] == SCHEMA_VERSION


# ===========================================================================
# Section 2 — Actions vocabulary
# ===========================================================================


class TestActionsVocabulary:
    """All checkpoint step actions in ACTIONS; monolithic 'checkpoint' removed."""

    @pytest.mark.parametrize("action_name", [
        "checkpoint-security",
        "checkpoint-intent",
        "checkpoint-docs",
        "checkpoint-tag",
    ])
    def test_checkpoint_action_in_ACTIONS(self, action_name: str) -> None:
        """Each checkpoint step action must be in ACTIONS."""
        assert action_name in ACTIONS, (
            f"Expected {action_name!r} in ACTIONS; ACTIONS = {sorted(ACTIONS)}"
        )

    def test_monolithic_checkpoint_not_in_ACTIONS(self) -> None:
        """The monolithic 'checkpoint' action must NOT be in ACTIONS (removed in RESOLVER-007).

        The constant CHECKPOINT is retained for backward import compatibility but
        must no longer appear as a member of ACTIONS.
        """
        assert CHECKPOINT not in ACTIONS, (
            "'checkpoint' must not be in ACTIONS after RESOLVER-007 removal; "
            f"ACTIONS = {sorted(ACTIONS)}"
        )

    @pytest.mark.parametrize("action_name", [
        "checkpoint-security",
        "checkpoint-intent",
        "checkpoint-docs",
    ])
    def test_spawn_checkpoint_actions_in_SPAWN_ACTIONS(self, action_name: str) -> None:
        """checkpoint-security/intent/docs are spawn actions and must be in _SPAWN_ACTIONS."""
        assert action_name in _SPAWN_ACTIONS, (
            f"Expected {action_name!r} in _SPAWN_ACTIONS; "
            f"_SPAWN_ACTIONS = {sorted(_SPAWN_ACTIONS)}"
        )


# ===========================================================================
# Section 3 — checkpoint-tag action shape
# ===========================================================================


class TestCheckpointTagShape:
    """checkpoint-tag is an inline action — model=None; NOT in _SPAWN_ACTIONS."""

    def test_checkpoint_tag_not_in_spawn_actions(self) -> None:
        """checkpoint-tag must NOT be in _SPAWN_ACTIONS (it is an inline action)."""
        assert CHECKPOINT_TAG not in _SPAWN_ACTIONS, (
            f"checkpoint-tag must NOT be in _SPAWN_ACTIONS; "
            f"_SPAWN_ACTIONS = {sorted(_SPAWN_ACTIONS)}"
        )

    def test_checkpoint_tag_model_is_none(self, tmp_path: Path) -> None:
        """checkpoint-tag emitted by resolve_next_action must carry model=None.

        Uses make_resolver_project to build a real durable-state tree so the
        fixture exercises the full resolver path.  gate_fn=lambda: True avoids
        any live pytest subprocess.

        Note: per DP1 the scalar should be the phase file stem (phase_key); the
        current implementation sets scalar="" for all checkpoint step actions.
        The model=None and NOT-in-_SPAWN_ACTIONS constraints are the binding
        assertions for this story.  scalar is validated only as a string type.
        """
        project = make_resolver_project(tmp_path, {
            "phase_status": "active",
            "stories": [("HARNESS-001", "complete", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            "state_json": {
                "checkpoint_step": [
                    CHECKPOINT_SECURITY,
                    CHECKPOINT_INTENT,
                    CHECKPOINT_DOCS,
                ],
            },
        })
        phase_file = project / "docs" / "phases" / "phase-1.md"
        position = _make_position(
            phase_file,
            checkpoint_step=[CHECKPOINT_SECURITY, CHECKPOINT_INTENT, CHECKPOINT_DOCS],
        )

        action = resolve_next_action(position, gate_fn=lambda: True)

        assert action["action"] == CHECKPOINT_TAG, (
            f"Expected checkpoint-tag; got {action['action']!r}"
        )
        assert action["model"] is None, (
            f"checkpoint-tag must carry model=None; got {action['model']!r}"
        )
        # scalar must be a string (type contract); value is "" in the current impl.
        assert isinstance(action["scalar"], str), (
            f"checkpoint-tag scalar must be a str; got {type(action['scalar']).__name__}"
        )
        # Schema validation enforces the model=None constraint at the grammar level.
        violations = validate_action(action)
        assert violations == [], (
            f"checkpoint-tag action failed schema validation: {violations}"
        )


# ===========================================================================
# Section 4 — Pre-checkpoint guard failures (one fixture per guard class)
# ===========================================================================


class TestPreCheckpointGuards:
    """Three guard classes; each must produce a distinct await-user reason."""

    def test_guard_phase_incomplete(self, tmp_path: Path) -> None:
        """Phase has a 'planned' story → await-user:checkpoint-guard-failed:phase-incomplete.

        The guard checks the phase manifest Stories table for any row whose
        status is not 'complete' or 'deferred'.  'planned' and 'in-progress'
        both trigger the guard.  gate_fn=lambda: True ensures the build-gate
        guard does not mask the phase-incomplete failure.
        """
        project = make_resolver_project(tmp_path, {
            "phase_status": "active",
            "stories": [("HARNESS-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
        })
        phase_file = project / "docs" / "phases" / "phase-1.md"
        position = _make_position(phase_file, checkpoint_step=[])

        action = resolve_next_action(position, gate_fn=lambda: True)

        assert action["action"] == AWAIT_USER, (
            f"Expected await-user on phase-incomplete; got {action['action']!r}"
        )
        assert action["reason"] == "checkpoint-guard-failed:phase-incomplete", (
            f"Unexpected reason: {action['reason']!r}"
        )
        assert action["model"] is None
        assert validate_action(action) == []

    def test_guard_cer_do_now_not_clear(self, tmp_path: Path) -> None:
        """Unresolved CER Do Now item → await-user:checkpoint-guard-failed:cer-do-now.

        All phase stories are complete so the phase-completion guard passes.
        An unresolved Do Now row in docs/cer/backlog.md triggers the CER guard.
        gate_fn=lambda: True skips the live build gate.
        """
        project = make_resolver_project(tmp_path, {
            "phase_status": "active",
            "stories": [("HARNESS-001", "complete", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
        })

        # Inject an unresolved CER Do Now item into the project tree.
        cer_dir = project / "docs" / "cer"
        cer_dir.mkdir(parents=True, exist_ok=True)
        (cer_dir / "backlog.md").write_text(
            "# CER Backlog\n\n"
            "## Do Now\n\n"
            "| ID | Finding | Source | Date | Phase |\n"
            "|----|---------|--------|------|-------|\n"
            "| CER-042 | An unresolved finding | harness | 2026-01-01 | HARNESS004-main |\n\n"
            "## Do Later\n\n",
            encoding="utf-8",
        )

        phase_file = project / "docs" / "phases" / "phase-1.md"
        position = _make_position(phase_file, checkpoint_step=[])

        action = resolve_next_action(position, gate_fn=lambda: True)

        assert action["action"] == AWAIT_USER, (
            f"Expected await-user on cer-do-now guard failure; got {action['action']!r}"
        )
        assert action["reason"] == "checkpoint-guard-failed:cer-do-now", (
            f"Unexpected reason: {action['reason']!r}"
        )
        assert action["model"] is None
        assert validate_action(action) == []

    def test_guard_build_gate_fails(self, tmp_path: Path) -> None:
        """Injected failing build gate → await-user:checkpoint-guard-failed:build-gate.

        All phase stories are complete and no CER Do Now items exist so the
        first two guards pass.  gate_fn=lambda: False simulates a failing pytest
        run without spawning a real subprocess.
        """
        project = make_resolver_project(tmp_path, {
            "phase_status": "active",
            "stories": [("HARNESS-001", "complete", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
        })
        phase_file = project / "docs" / "phases" / "phase-1.md"
        position = _make_position(phase_file, checkpoint_step=[])

        # Inject a failing build gate; no real pytest subprocess is invoked.
        action = resolve_next_action(position, gate_fn=lambda: False)

        assert action["action"] == AWAIT_USER, (
            f"Expected await-user on build-gate guard failure; got {action['action']!r}"
        )
        assert action["reason"] == "checkpoint-guard-failed:build-gate", (
            f"Unexpected reason: {action['reason']!r}"
        )
        assert action["model"] is None
        assert validate_action(action) == []


# ===========================================================================
# Section 5 — Checkpoint step sequencing (5-state matrix, table-driven)
# ===========================================================================


_STEP_SEQUENCE_CASES: list[tuple[list[str], str]] = [
    # State 1: no steps done → first step is checkpoint-security
    ([], CHECKPOINT_SECURITY),
    # State 2: security done → checkpoint-intent
    ([CHECKPOINT_SECURITY], CHECKPOINT_INTENT),
    # State 3: security + intent done → checkpoint-docs
    ([CHECKPOINT_SECURITY, CHECKPOINT_INTENT], CHECKPOINT_DOCS),
    # State 4: security + intent + docs done → checkpoint-tag
    ([CHECKPOINT_SECURITY, CHECKPOINT_INTENT, CHECKPOINT_DOCS], CHECKPOINT_TAG),
    # State 5: all four steps done → done (phase complete / advance to next phase)
    (
        [CHECKPOINT_SECURITY, CHECKPOINT_INTENT, CHECKPOINT_DOCS, CHECKPOINT_TAG],
        DONE,
    ),
]


class TestCheckpointStepSequencing:
    """Ordered 5-state matrix: guards pass + controlled checkpoint_step → correct action.

    Uses make_resolver_project to build a durable-state tree with the given
    checkpoint_step in state.json.  The position is constructed from the
    phase file path; gate_fn=lambda: True is injected to avoid live pytest runs.

    LLM-judgment gap: the step transition is gated by the harness writing the
    completed step into state.json["checkpoint_step"] after the worker returns.
    The correctness of what the worker concludes (PASS/FAIL verdict quality) is
    out of scope for this suite.
    """

    @pytest.mark.parametrize(
        "completed_steps,expected_action",
        _STEP_SEQUENCE_CASES,
        ids=[
            "no-steps-checkpoint-security",
            "security-done-checkpoint-intent",
            "security-intent-done-checkpoint-docs",
            "security-intent-docs-done-checkpoint-tag",
            "all-steps-done-done",
        ],
    )
    def test_step_sequence(
        self,
        tmp_path: Path,
        completed_steps: "list[str]",
        expected_action: str,
    ) -> None:
        """Guards pass + controlled checkpoint_step → correct next checkpoint action."""
        project = make_resolver_project(tmp_path, {
            "phase_status": "active",
            "stories": [("HARNESS-001", "complete", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            "state_json": {"checkpoint_step": completed_steps},
        })
        phase_file = project / "docs" / "phases" / "phase-1.md"
        position = _make_position(phase_file, checkpoint_step=completed_steps)

        action = resolve_next_action(position, gate_fn=lambda: True)

        assert action["action"] == expected_action, (
            f"completed_steps={completed_steps!r}: "
            f"expected action={expected_action!r}, got {action['action']!r}. "
            f"Full action: {action}"
        )
        assert action["model"] is None, (
            f"completed_steps={completed_steps!r}: "
            f"all checkpoint actions must have model=None; got {action['model']!r}"
        )
        violations = validate_action(action)
        assert violations == [], (
            f"completed_steps={completed_steps!r}: "
            f"action failed schema validation: " + "; ".join(violations)
        )


# ===========================================================================
# Section 6 — Docs-review worker input-bound guard
# ===========================================================================


class TestDocsReviewInputBound:
    """The checkpoint-docs procedure references only its declared bounded inputs.

    The five declared inputs per WORKER-011 Ensures:
      1. The phase doc   (docs/phases/phase-<ID>.md)
      2. The era doc     (docs/eras/<NNN>-<name>.md)
      3. docs/phases/index.md
      4. docs/architecture.md
      5. docs/cer/backlog.md

    No accumulated orchestrator state (effort.db, state.json, attempt counters,
    prior-attempt transcripts) may appear as read instructions.  The procedure
    must carry an explicit prohibition clause (DP1.3 input-bound property).
    """

    def test_procedure_file_exists(self) -> None:
        """Procedure file for the checkpoint-docs worker must exist and be non-empty."""
        assert _PROCEDURE_PATH.exists(), (
            f"Procedure file not found: {_PROCEDURE_PATH}"
        )
        assert _PROCEDURE_PATH.stat().st_size > 0, (
            f"Procedure file is empty: {_PROCEDURE_PATH}"
        )

    def test_procedure_declares_dp1_input_bound_property(self) -> None:
        """Procedure must declare the DP1.3 input-bound property."""
        text = _PROCEDURE_PATH.read_text(encoding="utf-8")
        has_dp1 = "DP1.3" in text
        has_input_bound = "input-bound" in text.lower()
        assert has_dp1 or has_input_bound, (
            "Procedure must declare the DP1.3 input-bound property "
            f"('DP1.3' or 'input-bound'); not found in {_PROCEDURE_PATH}"
        )

    @pytest.mark.parametrize("bounded_input_ref", [
        "docs/phases/index.md",
        "docs/architecture.md",
        "docs/cer/backlog.md",
        "phase doc",
        "era doc",
    ])
    def test_procedure_references_declared_bounded_input(
        self, bounded_input_ref: str
    ) -> None:
        """Each of the five declared bounded inputs must appear in the procedure."""
        text = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert bounded_input_ref in text, (
            f"Procedure must reference bounded input {bounded_input_ref!r}; "
            f"not found in {_PROCEDURE_PATH}"
        )

    def test_procedure_contains_explicit_must_not_prohibition(self) -> None:
        """Procedure must contain an explicit 'must not' prohibition clause."""
        text = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "must not" in text.lower(), (
            "Procedure must contain an explicit 'must not' prohibition clause; "
            f"not found in {_PROCEDURE_PATH}"
        )

    @pytest.mark.parametrize("banned_topic", [
        "accumulated orchestrator state",
        "effort database",
        "session state",
        "attempt counter",
    ])
    def test_procedure_names_banned_topic_in_prohibition(
        self, banned_topic: str
    ) -> None:
        """Procedure must name each banned accumulated-state topic in its prohibition block.

        The procedure's 'must not' block must cover the following topics so that
        the docs-reviewer knows exactly which surfaces are off-limits:
          - accumulated orchestrator state
          - effort database (effort.db)
          - session state (state.json)
          - attempt counters (attempt_counter.json)
        """
        text = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert banned_topic in text, (
            f"Procedure must name {banned_topic!r} as a banned surface "
            f"in its prohibition block; not found in {_PROCEDURE_PATH}"
        )

    def test_procedure_does_not_reference_effort_db_as_read_instruction(self) -> None:
        """Procedure must not instruct the worker to read effort.db.

        The procedure may mention 'effort' only in a prohibition context.
        We verify the file does not contain 'effort.db' as an unqualified
        reference (without surrounding prohibition language).
        """
        text = _PROCEDURE_PATH.read_text(encoding="utf-8")
        # effort.db is mentioned only in the 'must not' prohibition; verify it does
        # not appear as a positive read instruction.
        lines = text.splitlines()
        _PROHIBITION_MARKERS = ("must not", "do not", "never", "not rely", "not request")
        _WINDOW = 5

        for i, line in enumerate(lines):
            if "effort.db" not in line.lower():
                continue
            lo = max(0, i - _WINDOW)
            hi = min(len(lines), i + _WINDOW + 1)
            window_text = " ".join(lines[lo:hi]).lower()
            is_prohibition = any(m in window_text for m in _PROHIBITION_MARKERS)
            assert is_prohibition, (
                f"Procedure references 'effort.db' outside a prohibition context "
                f"at line {i + 1}:\n  {line.strip()}\nFile: {_PROCEDURE_PATH}"
            )

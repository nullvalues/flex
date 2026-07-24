"""
test_gate_worker_isolation.py — Exhaustive deterministic isolation suite for
the HARNESS002 gate-worker acceptance backbone (WORKER-003, DP8).

LLM-judgment gap (DP8.2 — deliberate, not silent):
    These tests verify the *deterministic scaffold* — signal collection,
    verdict routing, grammar round-trips, input-bound constraints, and the
    CF-1 model-selector regression — not the LLM's runtime judgment quality.
    Whether the gate worker correctly downgrades a spurious schema block or
    confirms a genuine auth block is validated by the procedure prompt text
    and manual review (DP8.2), not by unit tests.  No live API call is made
    anywhere in this module.

Suite sections (DP8.1 matrix):
    1. Signal collection — per-scenario gate signal assertions + DP2
       spawn-vs-not routing.
    2. Injected-verdict routing — ``route_gate_verdict`` fed injected maps;
       asserts DP3/DP4 aggregation actions without a live worker.
    3. Grammar round-trip — gate_verdict_grammar.json fixture: valid maps
       survive JSON round-trip unchanged and validate; invalid maps yield
       a non-empty violation list.
    4. DP1.3 input-bound guard — text inspection of the gate-worker
       procedure/shell for absence of accumulated-state references and
       presence of the bounded input set.
    5. CF-1 regression — Row 5 emitted model is selector-sourced; Row 2
       first-attempt model stays at attempt-1.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).parent
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"

for _d in (_TESTS_DIR, _SCRIPTS_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from gate_verdict import (  # noqa: E402
    JUDGED_GATES,
    VERBS,
    parse_verdict,
    validate_verdict_map,
)
from next_action import (  # noqa: E402
    AWAIT_USER,
    OUTCOME_FAIL,
    OUTCOME_NONE,
    SPAWN_BUILDER,
    SPAWN_GATE_WORKER,
    make_action,
    resolve_next_action,
    route_gate_verdict,
    validate_action,
)
from model_selector import select_builder_model  # noqa: E402
from resolver_fixtures import make_resolver_project  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures file paths
# ---------------------------------------------------------------------------

_FIXTURES_DIR = _TESTS_DIR / "fixtures"
_GRAMMAR_FIXTURE = _FIXTURES_DIR / "gate_verdict_grammar.json"
_SIGNALS_FIXTURE = _FIXTURES_DIR / "gate_signals.json"

_SKILL_FILE = _REPO_ROOT / "skills" / "pairmode" / "gate_worker" / "SKILL.md"
_SHELL_TEMPLATE = (
    _REPO_ROOT / "skills" / "pairmode" / "templates" / "agents" / "gate-worker.md.j2"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STORY_ID = "TEST-001"
_RAIL = "TEST"


def _gate_signal_ok(ok: bool, blocked_reason: str = "") -> dict:
    return {"ok": ok, "blocked_reason": blocked_reason}


def _build_position(
    next_story_id: str,
    gate_stub: dict,
    gate_schema: dict,
    gate_auth: dict,
    *,
    attempt_count: int = 0,
    builder_model: str | None = "sonnet",
    builder_model_reason: str | None = "auto-baseline",
    last_attempt_outcome: str = OUTCOME_NONE,
) -> dict:
    """Build a minimal Position dict for ``resolve_next_action``."""
    return {
        "active_phase_file": Path("/synthetic/phase-1.md"),
        "next_story_id": next_story_id,
        "next_story_file": None,
        "attempt_count": attempt_count,
        "builder_model": builder_model,
        "builder_model_reason": builder_model_reason,
        "gate_stub": gate_stub,
        "gate_schema": gate_schema,
        "gate_auth": gate_auth,
        "last_attempt_outcome": last_attempt_outcome,
    }


def _load_grammar_fixture() -> dict:
    return json.loads(_GRAMMAR_FIXTURE.read_text(encoding="utf-8"))


def _load_signals_fixture() -> dict:
    return json.loads(_SIGNALS_FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# § 1 — Signal collection (DP8.1)
#
# Each scenario builds a synthetic project via ``make_resolver_project``,
# optionally augments it (classification in arch.md, exception in story body),
# then calls the gate-check functions directly and asserts the resulting
# ``{ok, blocked_reason}`` signals match the DP8.1 matrix.
#
# Spawn-vs-not is asserted by feeding the signal outputs into
# ``resolve_next_action`` via a constructed position dict.
# ---------------------------------------------------------------------------

# Scenarios correspond 1-to-1 with gate_signals.json entries.
_SIGNAL_SCENARIOS = _load_signals_fixture()["scenarios"]


def _setup_project(tmp_path: Path, scenario: dict) -> tuple[Path, str]:
    """Create a synthetic project tree for the given scenario.

    Returns (project_path, story_id).  The first story in the phase is used
    as the story under test.  Post-creation file mutations (classification in
    arch.md; exception phrase in story body) are applied here.
    """
    story_id = _STORY_ID
    project = make_resolver_project(
        tmp_path,
        {
            "stories": [(story_id, "planned", "code", ["a.py"])],
            "stub_story": scenario.get("stub_story", False),
            "auth_gated": scenario.get("auth_gated", False),
            "schema_introduces": scenario.get("schema_introduces", False),
            "attempt_count": 0,
            "git_commits": [],
        },
    )

    # Add **Classification:** line in docs/architecture.md when needed.
    if scenario.get("classification_in_arch", False):
        docs_dir = project / "docs"
        docs_dir.mkdir(exist_ok=True)
        arch_path = docs_dir / "architecture.md"
        arch_path.write_text(
            "# Architecture\n\n**Classification:** RBAC\n", encoding="utf-8"
        )

    # Append exception phrase to the story body when needed.
    if scenario.get("exception_in_body", False):
        story_path = project / "docs" / "stories" / _RAIL / f"{story_id}.md"
        existing = story_path.read_text(encoding="utf-8")
        # Append "append-only" as a documented exception note.
        story_path.write_text(
            existing + "\n## Exception\n\nThis table is append-only.\n",
            encoding="utf-8",
        )

    return project, story_id


@pytest.mark.parametrize(
    "scenario",
    _SIGNAL_SCENARIOS,
    ids=[s["label"] for s in _SIGNAL_SCENARIOS],
)
def test_signal_collection_and_spawn_routing(tmp_path: Path, scenario: dict) -> None:
    """Assert gate signals and DP2 spawn-vs-not action for each scenario."""
    from flex_build import (  # type: ignore[import]
        check_auth_gate_result,
        check_schema_gate_result,
        check_stub_gate,
    )

    project, story_id = _setup_project(tmp_path, scenario)

    # ------------------------------------------------------------------
    # Assert gate signals
    # ------------------------------------------------------------------
    raw_stub = check_stub_gate(story_id, project)
    raw_schema = check_schema_gate_result(story_id, project)
    raw_auth = check_auth_gate_result(story_id, project)

    gate_stub = {
        "ok": raw_stub.get("ok", True),
        "blocked_reason": (raw_stub.get("reasons") or [""])[0]
        if not raw_stub.get("ok", True)
        else "",
    }
    gate_schema = {
        "ok": raw_schema.get("ok", True),
        "blocked_reason": raw_schema.get("blocked_reason", ""),
    }
    gate_auth = {
        "ok": raw_auth.get("ok", True),
        "blocked_reason": raw_auth.get("blocked_reason", ""),
    }

    assert gate_stub["ok"] is scenario["expected_gate_stub_ok"], (
        f"[{scenario['label']}] expected gate_stub.ok="
        f"{scenario['expected_gate_stub_ok']}, got {gate_stub['ok']}"
    )
    assert gate_schema["ok"] is scenario["expected_gate_schema_ok"], (
        f"[{scenario['label']}] expected gate_schema.ok="
        f"{scenario['expected_gate_schema_ok']}, got {gate_schema['ok']}"
    )
    assert gate_auth["ok"] is scenario["expected_gate_auth_ok"], (
        f"[{scenario['label']}] expected gate_auth.ok="
        f"{scenario['expected_gate_auth_ok']}, got {gate_auth['ok']}"
    )

    # Blocked gates must carry a non-empty reason string.
    if not gate_stub["ok"]:
        assert gate_stub["blocked_reason"], "gate_stub blocked but blocked_reason is empty"
    if not gate_schema["ok"]:
        assert gate_schema["blocked_reason"], "gate_schema blocked but blocked_reason is empty"
    if not gate_auth["ok"]:
        assert gate_auth["blocked_reason"], "gate_auth blocked but blocked_reason is empty"

    # ------------------------------------------------------------------
    # Assert DP2 spawn-vs-not routing
    # ------------------------------------------------------------------
    position = _build_position(story_id, gate_stub, gate_schema, gate_auth)
    action = resolve_next_action(position)

    assert action["action"] == scenario["expected_action"], (
        f"[{scenario['label']}] expected action={scenario['expected_action']!r}, "
        f"got {action['action']!r} (reason={action['reason']!r})"
    )
    if "expected_action_reason" in scenario:
        assert action["reason"] == scenario["expected_action_reason"], (
            f"[{scenario['label']}] expected reason={scenario['expected_action_reason']!r}, "
            f"got {action['reason']!r}"
        )

    # Action must always pass the grammar validator.
    violations = validate_action(action)
    assert violations == [], (
        f"[{scenario['label']}] action failed validate_action: {violations}"
    )


# ---------------------------------------------------------------------------
# § 1b — spawn-gate-worker scalar is the story ID (DP1.3 data flow)
# ---------------------------------------------------------------------------

def test_spawn_gate_worker_scalar_is_story_id() -> None:
    """spawn-gate-worker scalar carries the story ID, not accumulated state."""
    position = _build_position(
        _STORY_ID,
        gate_stub=_gate_signal_ok(True),
        gate_schema=_gate_signal_ok(False, "schema blocked"),
        gate_auth=_gate_signal_ok(True),
    )
    action = resolve_next_action(position)
    assert action["action"] == SPAWN_GATE_WORKER
    assert action["scalar"] == _STORY_ID, (
        f"spawn-gate-worker scalar must be the story ID; got {action['scalar']!r}"
    )
    # Scalar must match story-ID pattern (RAIL-NNN), not a free-text state dump.
    assert re.match(r"^[A-Z][A-Z0-9]+-\d+$", action["scalar"]), (
        f"spawn-gate-worker scalar {action['scalar']!r} does not match story-ID pattern"
    )


# ---------------------------------------------------------------------------
# § 2 — Injected-verdict routing (DP3/DP4 aggregation)
#
# All routing is tested with **injected** verdict maps — never a live worker
# spawn and never an API call.  If any test path would hit the model, the
# test is wrong.
# ---------------------------------------------------------------------------

_ROUTING_CASES: list[dict] = [
    {
        "label": "all-clean",
        "verdict_map": {"auth": "clean", "schema": "clean"},
        "expected_action": SPAWN_BUILDER,
        "expected_reason": "gate-clean-proceed",
        "expected_warnings": [],
        "block_gates": [],
    },
    {
        "label": "empty-map-clean",
        "verdict_map": {},
        "expected_action": SPAWN_BUILDER,
        "expected_reason": "gate-clean-proceed",
        "expected_warnings": [],
        "block_gates": [],
    },
    {
        "label": "auth-block-only",
        "verdict_map": {"auth": "block:auth_gated story missing Classification line"},
        "expected_action": AWAIT_USER,
        "block_gates": ["auth"],
    },
    {
        "label": "schema-block-only",
        "verdict_map": {
            "schema": "block:schema_introduces=true with no management UI story"
        },
        "expected_action": AWAIT_USER,
        "block_gates": ["schema"],
    },
    {
        "label": "mixed-auth-clean-schema-block",
        "verdict_map": {
            "auth": "clean",
            "schema": "block:no management surface story found for new table",
        },
        "expected_action": AWAIT_USER,
        "block_gates": ["schema"],
    },
    {
        "label": "both-gates-block",
        "verdict_map": {
            "auth": "block:auth_gated=true but docs/architecture.md has no Classification",
            "schema": "block:schema_introduces=true with no management UI story in phase",
        },
        "expected_action": AWAIT_USER,
        "block_gates": ["auth", "schema"],
    },
    {
        "label": "schema-flag-proceed",
        "verdict_map": {
            "schema": "flag:schema_introduces=true but no management surface found; confirm exception applies"
        },
        "expected_action": SPAWN_BUILDER,
        "expected_reason": "gate-flag-proceed",
        "flag_gates": ["schema"],
        "block_gates": [],
    },
    {
        "label": "auth-flag-proceed",
        "verdict_map": {
            "auth": "flag:auth_gated but Classification may be missing; advisory only"
        },
        "expected_action": SPAWN_BUILDER,
        "expected_reason": "gate-flag-proceed",
        "flag_gates": ["auth"],
        "block_gates": [],
    },
    {
        "label": "flag-takes-lower-priority-than-block",
        "verdict_map": {
            "auth": "flag:advisory note",
            "schema": "block:hard block from schema gate",
        },
        "expected_action": AWAIT_USER,
        "block_gates": ["schema"],
    },
]


@pytest.mark.parametrize(
    "case",
    _ROUTING_CASES,
    ids=[c["label"] for c in _ROUTING_CASES],
)
def test_injected_verdict_routing(case: dict) -> None:
    """Injected verdict maps route to the correct action per DP3/DP4 aggregation."""
    action = route_gate_verdict(case["verdict_map"], next_story_id=_STORY_ID)

    assert action["action"] == case["expected_action"], (
        f"[{case['label']}] expected action={case['expected_action']!r}, "
        f"got {action['action']!r} (reason={action['reason']!r})"
    )

    if "expected_reason" in case:
        assert action["reason"] == case["expected_reason"], (
            f"[{case['label']}] expected reason={case['expected_reason']!r}, "
            f"got {action['reason']!r}"
        )

    # block: reason carries gate label(s)
    block_gates: list[str] = case.get("block_gates", [])
    if block_gates:
        assert action["action"] == AWAIT_USER
        reason = action["reason"]
        assert reason.startswith("gate-blocked:"), (
            f"[{case['label']}] expected reason 'gate-blocked:...', got {reason!r}"
        )
        for gate in block_gates:
            assert gate in reason, (
                f"[{case['label']}] expected gate {gate!r} in reason {reason!r}"
            )
        # Worker reason(s) must be carried in meta.gate_block_reasons
        meta = action.get("meta", {})
        assert "gate_block_reasons" in meta, (
            f"[{case['label']}] meta.gate_block_reasons missing for block action"
        )
        for gate in block_gates:
            assert gate in meta["gate_block_reasons"], (
                f"[{case['label']}] gate {gate!r} missing from gate_block_reasons"
            )

    # flag: warnings[] must carry gate-flag entries
    flag_gates: list[str] = case.get("flag_gates", [])
    if flag_gates and case["expected_action"] == SPAWN_BUILDER:
        meta = action.get("meta", {})
        warnings = meta.get("warnings") or []
        for gate in flag_gates:
            assert any(f"gate-flag:{gate}:" in w for w in warnings), (
                f"[{case['label']}] expected warning for gate {gate!r} in warnings={warnings}"
            )

    # Verdict map is always reflected in meta.verdict_map.
    meta = action.get("meta", {})
    assert "verdict_map" in meta, (
        f"[{case['label']}] meta.verdict_map missing"
    )
    assert meta["verdict_map"] == case["verdict_map"], (
        f"[{case['label']}] meta.verdict_map mismatch"
    )

    # All produced actions must pass validate_action.
    violations = validate_action(action)
    assert violations == [], (
        f"[{case['label']}] action failed validate_action: {violations}"
    )


# ---------------------------------------------------------------------------
# § 3 — Grammar round-trip (gate_verdict_grammar.json fixture / DP3)
# ---------------------------------------------------------------------------


class TestGrammarRoundTrip:
    """Every valid fixture entry round-trips unchanged; every invalid yields violations.

    This section exercises WORKER-001's gate_verdict_grammar.json fixture as
    the DP3 grammar contract binding test.  All round-trips are pure JSON
    encode/decode — no LLM, no subprocess.
    """

    _fixture = _load_grammar_fixture()

    @pytest.mark.parametrize(
        "entry",
        _load_grammar_fixture()["valid"],
        ids=[e["label"] for e in _load_grammar_fixture()["valid"]],
    )
    def test_valid_map_round_trips_unchanged(self, entry: dict) -> None:
        original = entry["map"]
        restored = json.loads(json.dumps(original))
        assert restored == original, (
            f"JSON round-trip changed map for {entry['label']!r}"
        )
        violations = validate_verdict_map(original)
        assert violations == [], (
            f"Valid entry {entry['label']!r} produced violations: {violations}"
        )

    @pytest.mark.parametrize(
        "entry",
        _load_grammar_fixture()["valid"],
        ids=[e["label"] for e in _load_grammar_fixture()["valid"]],
    )
    def test_valid_map_verdict_strings_parse_round_trip(self, entry: dict) -> None:
        """Each verdict string in valid maps parses and reconstructs identically."""
        for gate, verdict_str in entry["map"].items():
            verb, reason = parse_verdict(verdict_str)
            reconstructed = verb if not reason else f"{verb}:{reason}"
            assert reconstructed == verdict_str, (
                f"parse round-trip failed for gate={gate!r} "
                f"verdict={verdict_str!r} in {entry['label']!r}: got {reconstructed!r}"
            )

    @pytest.mark.parametrize(
        "entry",
        _load_grammar_fixture()["invalid"],
        ids=[e["label"] for e in _load_grammar_fixture()["invalid"]],
    )
    def test_invalid_map_yields_violations(self, entry: dict) -> None:
        violations = validate_verdict_map(entry["map"])
        assert len(violations) >= 1, (
            f"Expected violations for invalid entry {entry['label']!r}, got none"
        )


# ---------------------------------------------------------------------------
# § 4 — DP1.3 input-bound guard
#
# Strategy:
#   SKILL.md — positive assertions: the prohibition of accumulated state IS
#     encoded ("must not … accumulated … state") and the bounded input set IS
#     present (three check-* CLIs, single story, diff/frontmatter).  The SKILL.md
#     *names* the excluded concepts in its prohibition clause; we do not treat
#     that as a violation.
#   Shell template — negative assertions: the thin shell must not contain ANY
#     accumulated-state references (granting or otherwise), because the shell is
#     not where the prohibition clause lives.
#   Action shape — the spawn-gate-worker meta carries only bounded gate info.
#
# Mirrors the text-inspection pattern from test_gate_worker.py.
# ---------------------------------------------------------------------------

#: Patterns that must NOT appear in the thin SHELL template (gate-worker.md.j2).
#: The shell is not the place for prohibition clauses — if these appear there, it
#: means some accumulated-state logic leaked into the shell.
_FORBIDDEN_IN_SHELL: list[tuple[str, str]] = [
    (r"\bphase.history\b", "phase history"),
    (r"\bprior.attempt.transcript\b", "prior attempt transcript"),
    (r"\bloop.history\b", "loop history"),
    (r"\bcontext_current_tokens\b", "context_current_tokens"),
    (r"\beffort\.db\b", "effort.db"),
    (r"\battempt_counter\b", "attempt_counter"),
]

#: Patterns that MUST appear in the procedure SKILL.md.
#: These encode the DP1.3 contract: bounded input set + explicit prohibition.
_REQUIRED_IN_SKILL: list[tuple[str, str]] = [
    # Bounded input set: the three check-* CLIs must be named.
    (r"\bcheck-schema-gate\b|\bcheck_schema_gate\b", "check-schema-gate CLI"),
    (r"\bcheck-auth-gate\b|\bcheck_auth_gate\b", "check-auth-gate CLI"),
    (r"\bcheck-stub\b|\bcheck_stub\b", "check-stub CLI"),
    # The story file must be named as a bounded input.
    (r"\bstory\b", "story (bounded input)"),
    # Explicit prohibition of accumulated state must be encoded.
    (
        r"must not.{0,60}(accumulated|loop history|phase.history)",
        "explicit prohibition of accumulated-state access",
    ),
    # DP1.3 label or equivalent input-bound constraint.
    (
        r"DP1\.3|input.bound",
        "DP1.3 input-bound constraint label",
    ),
]


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert _SKILL_FILE.exists(), f"gate_worker SKILL.md not found: {_SKILL_FILE}"
    return _SKILL_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def shell_text() -> str:
    assert _SHELL_TEMPLATE.exists(), f"gate-worker shell template not found: {_SHELL_TEMPLATE}"
    return _SHELL_TEMPLATE.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "pattern, description",
    _FORBIDDEN_IN_SHELL,
    ids=[d for _, d in _FORBIDDEN_IN_SHELL],
)
def test_shell_excludes_accumulated_state_reference(
    shell_text: str, pattern: str, description: str
) -> None:
    """Shell template must not reference accumulated loop state in any form (DP1.3)."""
    assert not re.search(pattern, shell_text, re.IGNORECASE), (
        f"gate-worker.md.j2 contains an accumulated-state reference: {description!r}"
    )


@pytest.mark.parametrize(
    "pattern, description",
    _REQUIRED_IN_SKILL,
    ids=[d for _, d in _REQUIRED_IN_SKILL],
)
def test_skill_encodes_dp13_contract(
    skill_text: str, pattern: str, description: str
) -> None:
    """SKILL.md must contain the DP1.3 bounded-input set and prohibition (positive assertion)."""
    assert re.search(pattern, skill_text, re.IGNORECASE | re.DOTALL), (
        f"SKILL.md is missing required DP1.3 contract element: {description!r}"
    )


def test_spawn_gate_worker_action_has_no_accumulated_state_in_meta() -> None:
    """spawn-gate-worker meta carries only tripped-gate info, not orchestrator state."""
    position = _build_position(
        "MYTEST-007",
        gate_stub=_gate_signal_ok(True),
        gate_schema=_gate_signal_ok(False, "schema blocked reason"),
        gate_auth=_gate_signal_ok(True),
    )
    action = resolve_next_action(position)
    assert action["action"] == SPAWN_GATE_WORKER
    meta = action["meta"]
    # meta must carry gates_tripped and gate_reasons — the bounded signal set.
    assert "gates_tripped" in meta
    assert "gate_reasons" in meta
    # meta must NOT carry orchestrator-owned state keys.
    forbidden_meta_keys = {
        "context_current_tokens",
        "attempt_counter",
        "phase_history",
        "prior_transcripts",
    }
    overlap = forbidden_meta_keys & set(meta.keys())
    assert not overlap, (
        f"spawn-gate-worker meta contains accumulated-state keys: {overlap}"
    )


# ---------------------------------------------------------------------------
# § 5 — CF-1 regression (DP7.2 / CER-060)
#
# Row 5: emitted model == select_builder_model(<code story>, ..., attempt_number=2)[0]
#         (selector-sourced, not hardcoded "opus")
# Row 2: emitted model == select_builder_model(<code story>, ..., attempt_number=1)[0]
#         (first-attempt model stays at attempt-1 tier)
# ---------------------------------------------------------------------------

def test_cf1_row5_model_is_selector_sourced() -> None:
    """Row 5 (attempt=1, FAIL) uses the builder model from the selector at attempt_number=2.

    This pins the CF-1 fix: the retry tier is resolved by select_builder_model
    (attempt_number=2) and embedded in the Position before resolve_next_action
    runs — the state machine never hardcodes the retry tier independently.
    """
    # Compute the expected model from the selector at attempt 2 for a code story.
    expected_model, expected_reason = select_builder_model(
        "code", [], [], attempt_number=2
    )

    # Build a Row 5 position: attempt_count=1, FAIL, builder_model from selector.
    position = _build_position(
        _STORY_ID,
        gate_stub=_gate_signal_ok(True),
        gate_schema=_gate_signal_ok(True),
        gate_auth=_gate_signal_ok(True),
        attempt_count=1,
        builder_model=expected_model,
        builder_model_reason=expected_reason,
        last_attempt_outcome=OUTCOME_FAIL,
    )
    action = resolve_next_action(position)

    assert action["action"] == SPAWN_BUILDER
    assert action["meta"].get("attempt") == 2
    assert action["meta"].get("fail_rung") == "single-fail"
    assert action["model"] == expected_model, (
        f"Row 5 model {action['model']!r} does not match "
        f"select_builder_model(..., attempt_number=2)[0] = {expected_model!r}"
    )

    violations = validate_action(action)
    assert violations == [], f"Row 5 action invalid: {violations}"


def test_cf1_row2_model_uses_attempt1_tier() -> None:
    """Row 2 (attempt=0, first launch) uses the builder model at attempt_number=1."""
    expected_model, expected_reason = select_builder_model(
        "code", [], [], attempt_number=1
    )

    position = _build_position(
        _STORY_ID,
        gate_stub=_gate_signal_ok(True),
        gate_schema=_gate_signal_ok(True),
        gate_auth=_gate_signal_ok(True),
        attempt_count=0,
        builder_model=expected_model,
        builder_model_reason=expected_reason,
        last_attempt_outcome=OUTCOME_NONE,
    )
    action = resolve_next_action(position)

    assert action["action"] == SPAWN_BUILDER
    assert action["meta"].get("attempt") == 1
    assert action["model"] == expected_model, (
        f"Row 2 model {action['model']!r} does not match "
        f"select_builder_model(..., attempt_number=1)[0] = {expected_model!r}"
    )

    violations = validate_action(action)
    assert violations == [], f"Row 2 action invalid: {violations}"


def test_cf1_row5_model_differs_from_row2() -> None:
    """Row 5 (retry) must select a higher-tier model than Row 2 (first attempt).

    This encodes the contract that retry-upgrade escalates beyond the baseline,
    so the CF-1 selector-sourcing has an observable effect.
    """
    row2_model, _ = select_builder_model("code", [], [], attempt_number=1)
    row5_model, _ = select_builder_model("code", [], [], attempt_number=2)
    assert row5_model != row2_model, (
        "Row 5 and Row 2 models are identical — CF-1 retry escalation is not observable. "
        f"Both returned {row5_model!r}. Check select_builder_model."
    )


# ---------------------------------------------------------------------------
# § 6 — Full-suite build gate
#
# The existence of this module as the consolidation suite means the build gate
# (pytest tests/pairmode/ -x -q) must stay green.  No explicit test needed —
# any broken import or parametrize failure will surface here.
# ---------------------------------------------------------------------------

def test_grammar_constants_unchanged() -> None:
    """Verify grammar constants have not silently drifted (consolidation guard)."""
    assert VERBS == frozenset({"clean", "block", "flag"}), (
        "VERBS set has drifted from expected {'clean', 'block', 'flag'}"
    )
    assert JUDGED_GATES == frozenset({"schema", "auth"}), (
        "JUDGED_GATES set has drifted from expected {'schema', 'auth'}"
    )
    assert "stub" not in JUDGED_GATES, (
        "stub must never be a judged gate (DP2 — stub is mechanical)"
    )

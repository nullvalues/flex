"""
tests/pairmode/test_next_action_schema.py

Tests for the next_action action grammar module (RESOLVER-001).

Coverage:
- Round-trip: every sample in next_action_samples.json validates and survives json round-trip.
- Constructor: make_action(DONE) shape; meta mutation safety.
- Enum closure: ACTIONS contains exactly the documented values (RESOLVER-007 adds four
  checkpoint-* actions and removes monolithic checkpoint).
- Negative cases: unknown action, missing key, model on non-spawn, bad/missing schema_version.
- Schema/validator agreement: enum and key set in next_action.schema.json match Python module.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — make the skills scripts importable without an install.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = (
    Path(__file__).parent.parent.parent
    / "skills"
    / "pairmode"
    / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

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
    SPAWN_BUILDER,
    SPAWN_LOOP_BREAKER,
    make_action,
    validate_action,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_SAMPLES_FILE = _FIXTURES_DIR / "next_action_samples.json"
_SCHEMA_FILE = _FIXTURES_DIR / "next_action.schema.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_samples() -> list[dict]:
    return json.loads(_SAMPLES_FILE.read_text())


def _load_schema() -> dict:
    return json.loads(_SCHEMA_FILE.read_text())


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Every sample in next_action_samples.json must validate and survive json round-trip."""

    def test_all_samples_valid(self):
        samples = _load_samples()
        assert len(samples) >= 5, "Need at least 5 samples (one per action)"
        for i, sample in enumerate(samples):
            violations = validate_action(sample)
            assert violations == [], (
                f"Sample {i} ({sample.get('action', '?')!r}) failed validation: "
                + "; ".join(violations)
            )

    def test_all_samples_json_round_trip(self):
        samples = _load_samples()
        for i, sample in enumerate(samples):
            serialised = json.dumps(sample)
            restored = json.loads(serialised)
            assert restored == sample, (
                f"Sample {i} changed after json round-trip: {sample!r} → {restored!r}"
            )

    def test_samples_cover_all_actions(self):
        """At least one sample per action value."""
        samples = _load_samples()
        covered = {s["action"] for s in samples}
        missing = ACTIONS - covered
        assert not missing, f"No sample for actions: {missing}"


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_make_action_done_minimal(self):
        result = make_action(DONE)
        assert result == {
            "action": "done",
            "scalar": "",
            "model": None,
            "reason": "",
            "meta": {"schema_version": SCHEMA_VERSION},
        }

    def test_make_action_spawn_builder_with_model(self):
        result = make_action(SPAWN_BUILDER, scalar="RESOLVER-002", model="sonnet", reason="baseline")
        assert result["action"] == SPAWN_BUILDER
        assert result["scalar"] == "RESOLVER-002"
        assert result["model"] == "sonnet"
        assert result["meta"]["schema_version"] == SCHEMA_VERSION

    def test_make_action_does_not_mutate_caller_meta(self):
        caller_meta = {"attempt": 1}
        original_meta = copy.deepcopy(caller_meta)
        make_action(SPAWN_BUILDER, meta=caller_meta)
        assert caller_meta == original_meta, "make_action must not mutate the caller's meta dict"

    def test_make_action_stamps_schema_version_even_if_caller_omits(self):
        # Use CHECKPOINT_TAG (a valid action) to test that schema_version is stamped.
        result = make_action(CHECKPOINT_TAG, meta={"gate": "context-budget"})
        assert result["meta"]["schema_version"] == SCHEMA_VERSION

    def test_make_action_stamps_schema_version_overrides_caller_value(self):
        """schema_version in caller meta is overwritten to SCHEMA_VERSION."""
        result = make_action(DONE, meta={"schema_version": 99})
        assert result["meta"]["schema_version"] == SCHEMA_VERSION

    def test_make_action_no_meta_arg_produces_clean_meta(self):
        result = make_action(AWAIT_USER)
        assert result["meta"] == {"schema_version": SCHEMA_VERSION}

    def test_make_action_preserves_extra_meta_fields(self):
        result = make_action(SPAWN_LOOP_BREAKER, meta={"attempt": 3, "fail_rung": "double-fail"})
        assert result["meta"]["attempt"] == 3
        assert result["meta"]["fail_rung"] == "double-fail"

    def test_make_action_output_keys(self):
        result = make_action(DONE)
        assert set(result.keys()) == {"action", "scalar", "model", "reason", "meta"}


# ---------------------------------------------------------------------------
# Enum closure tests
# ---------------------------------------------------------------------------


class TestEnumClosure:
    def test_actions_contains_exactly_thirteen_values(self):
        # RESOLVER-005 added spawn-gate-worker (was five before HARNESS002-main).
        # WORKER-004 added spawn-reviewer, spawn-security-auditor, spawn-intent-reviewer (was six).
        # RESOLVER-007 removed monolithic checkpoint and added four checkpoint-* actions (net +3).
        # RESOLVER-009 added spawn-spec-writer (was twelve).
        assert len(ACTIONS) == 13

    def test_actions_contains_all_documented_values(self):
        expected = {
            "spawn-builder",
            "spawn-loop-breaker",
            "spawn-gate-worker",
            "spawn-reviewer",
            "spawn-security-auditor",
            "spawn-intent-reviewer",
            "spawn-spec-writer",
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
            "checkpoint-tag",
            "await-user",
            "done",
        }
        assert ACTIONS == expected

    def test_named_constants_match_actions(self):
        """Each named constant must be in ACTIONS and the set must equal constants."""
        from next_action import (  # noqa: PLC0415
            SPAWN_GATE_WORKER,
            SPAWN_REVIEWER,
            SPAWN_SECURITY_AUDITOR,
            SPAWN_INTENT_REVIEWER,
            SPAWN_SPEC_WRITER,
        )
        named = {
            SPAWN_BUILDER,
            SPAWN_LOOP_BREAKER,
            SPAWN_GATE_WORKER,
            SPAWN_REVIEWER,
            SPAWN_SECURITY_AUDITOR,
            SPAWN_INTENT_REVIEWER,
            SPAWN_SPEC_WRITER,
            CHECKPOINT_SECURITY,
            CHECKPOINT_INTENT,
            CHECKPOINT_DOCS,
            CHECKPOINT_TAG,
            AWAIT_USER,
            DONE,
        }
        assert named == ACTIONS

    def test_checkpoint_constant_not_in_actions(self):
        """CHECKPOINT constant is retained for backward compatibility but removed from ACTIONS."""
        assert CHECKPOINT == "checkpoint"
        assert CHECKPOINT not in ACTIONS


# ---------------------------------------------------------------------------
# Negative-case tests
# ---------------------------------------------------------------------------


class TestValidateActionNegative:
    def _valid_done(self) -> dict:
        return make_action(DONE)

    def test_unknown_action_rejected(self):
        obj = make_action("fly-to-moon")  # not in ACTIONS
        # make_action stamps schema_version, so meta is fine; only action is wrong
        violations = validate_action(obj)
        assert violations, "Expected violation for unknown action"
        assert any("unknown action" in v for v in violations)

    def test_missing_required_key_action(self):
        obj = self._valid_done()
        del obj["action"]
        violations = validate_action(obj)
        assert violations
        assert any("action" in v for v in violations)

    def test_missing_required_key_scalar(self):
        obj = self._valid_done()
        del obj["scalar"]
        violations = validate_action(obj)
        assert violations
        assert any("scalar" in v for v in violations)

    def test_missing_required_key_model(self):
        obj = self._valid_done()
        del obj["model"]
        violations = validate_action(obj)
        assert violations
        assert any("model" in v for v in violations)

    def test_missing_required_key_reason(self):
        obj = self._valid_done()
        del obj["reason"]
        violations = validate_action(obj)
        assert violations
        assert any("reason" in v for v in violations)

    def test_missing_required_key_meta(self):
        obj = self._valid_done()
        del obj["meta"]
        violations = validate_action(obj)
        assert violations
        assert any("meta" in v for v in violations)

    def test_model_set_on_await_user_rejected(self):
        obj = make_action(AWAIT_USER, model="sonnet")
        violations = validate_action(obj)
        assert violations
        assert any("await-user" in v for v in violations)

    def test_model_set_on_checkpoint_tag_rejected(self):
        # checkpoint-tag is an inline action (not in _SPAWN_ACTIONS); model must be null.
        obj = make_action(CHECKPOINT_TAG, model="sonnet")
        violations = validate_action(obj)
        assert violations
        assert any("checkpoint-tag" in v for v in violations)

    def test_model_set_on_done_rejected(self):
        obj = make_action(DONE, model="haiku")
        violations = validate_action(obj)
        assert violations
        assert any("done" in v for v in violations)

    def test_meta_missing_schema_version(self):
        obj = self._valid_done()
        del obj["meta"]["schema_version"]
        violations = validate_action(obj)
        assert violations
        assert any("schema_version" in v for v in violations)

    def test_meta_wrong_schema_version(self):
        obj = self._valid_done()
        obj["meta"]["schema_version"] = 999
        violations = validate_action(obj)
        assert violations
        assert any("schema_version" in v for v in violations)

    def test_non_dict_object_rejected(self):
        violations = validate_action("not a dict")
        assert violations
        assert any("dict" in v for v in violations)

    def test_valid_done_accepted(self):
        obj = make_action(DONE)
        assert validate_action(obj) == []

    def test_valid_spawn_builder_with_model_accepted(self):
        obj = make_action(SPAWN_BUILDER, scalar="X-001", model="opus", reason="retry")
        assert validate_action(obj) == []

    def test_valid_spawn_loop_breaker_with_model_accepted(self):
        obj = make_action(SPAWN_LOOP_BREAKER, scalar="X-001", model="opus")
        assert validate_action(obj) == []

    def test_valid_spawn_builder_null_model_accepted(self):
        """model=null is also legal on spawn-builder (resolver may not know model yet)."""
        obj = make_action(SPAWN_BUILDER, scalar="X-001", model=None)
        assert validate_action(obj) == []


# ---------------------------------------------------------------------------
# Schema / validator agreement tests
# ---------------------------------------------------------------------------


class TestSchemaValidatorAgreement:
    def test_schema_file_is_valid_json(self):
        schema = _load_schema()
        assert isinstance(schema, dict)

    def test_schema_action_enum_matches_actions(self):
        schema = _load_schema()
        schema_enum = set(schema["properties"]["action"]["enum"])
        assert schema_enum == ACTIONS, (
            f"Schema action enum {schema_enum} does not match ACTIONS {ACTIONS}"
        )

    def test_schema_top_level_required_keys_match_make_action_output(self):
        schema = _load_schema()
        schema_required = set(schema["required"])
        make_action_keys = set(make_action(DONE).keys())
        assert schema_required == make_action_keys, (
            f"Schema required keys {schema_required} != make_action output keys {make_action_keys}"
        )

    def test_schema_version_in_schema_matches_constant(self):
        schema = _load_schema()
        schema_version = schema["properties"]["meta"]["properties"]["schema_version"]["const"]
        assert schema_version == SCHEMA_VERSION

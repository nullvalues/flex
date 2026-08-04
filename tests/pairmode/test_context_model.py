"""Tests for skills/pairmode/scripts/context_model.py — INFRA-321 § A1/A2.

Track vocabulary: TRACK_ORCHESTRATOR / TRACK_STORY_SPEND constants,
ORCHESTRATOR_TRACK_KEYS / STORY_SPEND_SOURCES boundary tuples, and the
track_label() captioning helper.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))

import context_model  # noqa: E402


def test_track_constants_and_label_are_total():
    """test_track_constants_and_label_are_total."""
    assert context_model.TRACK_ORCHESTRATOR == "orchestrator-window"
    assert context_model.TRACK_STORY_SPEND == "story-spend"
    assert context_model.track_label(context_model.TRACK_ORCHESTRATOR)
    assert context_model.track_label(context_model.TRACK_STORY_SPEND)
    # Total: unknown values return "unlabelled" rather than raising.
    assert context_model.track_label("bogus-track") == "unlabelled"
    assert context_model.track_label("") == "unlabelled"
    assert context_model.track_label(None) == "unlabelled"  # type: ignore[arg-type]


def test_orchestrator_track_keys_cover_the_known_gate_state():
    expected_subset = {
        "context_current_tokens",
        "context_current_tokens_recorded_at",
        "context_step_growth_samples",
        "expected_step_tokens",
        "context_budget_threshold",
        "context_budget_overrun_pct",
        "context_budget_reprompt_margin",
        "context_budget_acknowledged_at",
        "context_budget_user_turn_seq",
        "context_budget_acknowledged_user_turn_seq",
        "context_session_reset_at",
    }
    assert set(context_model.ORCHESTRATOR_TRACK_KEYS) == expected_subset
    # story_spend_threshold is deliberately NOT an orchestrator-track key —
    # it is the dedicated story-spend threshold (§ A3).
    assert "story_spend_threshold" not in context_model.ORCHESTRATOR_TRACK_KEYS


def test_story_spend_sources_are_effort_db_columns_only():
    assert context_model.STORY_SPEND_SOURCES == (
        "attempts.tokens_total",
        "attempts.tokens_out",
        "attempts.tokens_in",
    )


def test_boundary_rule_documented_in_module_source():
    src = Path(context_model.__file__).read_text(encoding="utf-8")
    stripped_lines = [line.lstrip("#").strip() for line in src.splitlines()]
    normalized = " ".join(" ".join(stripped_lines).split())
    assert "may NEVER be compared against an orchestrator-track threshold" in normalized
    assert "may NEVER be summed into an orchestrator-track" in normalized


def test_context_current_tokens_sources_names_all_three_and_all_three_are_live():
    assert context_model.CONTEXT_CURRENT_TOKENS_SOURCES == (
        "post-tool-use",
        "user-prompt-submit",
        "manual",
    )

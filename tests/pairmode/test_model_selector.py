"""Tests for skills/pairmode/scripts/model_selector.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from skills.pairmode.scripts.model_selector import (
    MODEL_FABLE,
    MODEL_HAIKU,
    MODEL_OPUS,
    MODEL_SONNET,
    REASON_AUTO_BASELINE,
    REASON_AUTO_DOWNGRADE,
    REASON_ESCALATION_UPGRADE,
    REASON_PROMPTED_UPGRADE,
    REASON_RETRY_UPGRADE,
    REASON_STORY_DECLARED,
    apply_declared_model_floor,
    select_builder_model,
    select_docs_reviewer_model,
    select_gate_worker_model,
    select_intent_reviewer_model,
    select_loop_breaker_model,
    select_reviewer_model,
    select_security_auditor_model,
    select_shadow_reviewer_model,
    select_spec_writer_model,
)

# ---------------------------------------------------------------------------
# Helpers for building fixture story and phase files
# ---------------------------------------------------------------------------


def _write_story(
    tmp_path: Path,
    story_id: str,
    story_class: str | None = None,
    phase: str = "24",
    status: str = "planned",
) -> Path:
    """Write a minimal story file under tmp_path/docs/stories/RAIL/."""
    rail = story_id.split("-")[0]
    story_dir = tmp_path / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"

    sc_line = f"story_class: {story_class}\n" if story_class is not None else ""

    story_path.write_text(
        f"---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"title: Test Story {story_id}\n"
        f"status: {status}\n"
        f"phase: \"{phase}\"\n"
        f"{sc_line}"
        f"primary_files:\n"
        f"  - some/file.py\n"
        f"---\n\nBody text.\n",
        encoding="utf-8",
    )
    return story_path


def _write_phase(
    tmp_path: Path,
    phase_id: str,
    story_ids: list[str],
    phase_class: str | None = None,
) -> Path:
    """Write a minimal phase manifest under tmp_path/docs/phases/."""
    phases_dir = tmp_path / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_path = phases_dir / f"phase-{phase_id}.md"

    pc_line = f"phase_class: {phase_class}\n" if phase_class is not None else ""

    rows = "\n".join(f"| {sid} | Title | planned |" for sid in story_ids)
    phase_path.write_text(
        f"---\n"
        f"era: 003-test\n"
        f"{pc_line}"
        f"---\n\n"
        f"## Stories\n\n"
        f"| ID | Title | Status |\n"
        f"|----|-------|--------|\n"
        f"{rows}\n",
        encoding="utf-8",
    )
    return phase_path


# ---------------------------------------------------------------------------
# Selection table — attempt_number = 1 (all classes return "sonnet")
# ---------------------------------------------------------------------------


class TestAttemptOne:
    def test_code_attempt1(self) -> None:
        model, reason = select_reviewer_model("code", 1)
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"

    def test_doc_attempt1(self) -> None:
        model, reason = select_reviewer_model("doc", 1)
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"

    def test_lesson_attempt1(self) -> None:
        model, reason = select_reviewer_model("lesson", 1)
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"

    def test_methodology_attempt1(self) -> None:
        model, reason = select_reviewer_model("methodology", 1)
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"


# ---------------------------------------------------------------------------
# Selection table — attempt_number >= 2
# ---------------------------------------------------------------------------


class TestAttemptTwoPlus:
    def test_code_attempt2_upgrades_to_opus(self) -> None:
        model, reason = select_reviewer_model("code", 2)
        assert model == MODEL_OPUS
        assert reason == "retry-upgrade"

    def test_code_attempt3_upgrades_to_opus(self) -> None:
        model, reason = select_reviewer_model("code", 3)
        assert model == MODEL_OPUS
        assert reason == "retry-upgrade"

    def test_doc_attempt2_stays_sonnet(self) -> None:
        model, reason = select_reviewer_model("doc", 2)
        assert model == MODEL_SONNET
        assert reason == "doc-class-baseline"

    def test_doc_attempt5_stays_sonnet(self) -> None:
        model, reason = select_reviewer_model("doc", 5)
        assert model == MODEL_SONNET
        assert reason == "doc-class-baseline"

    def test_lesson_attempt2_stays_sonnet(self) -> None:
        model, reason = select_reviewer_model("lesson", 2)
        assert model == MODEL_SONNET
        assert reason == "doc-class-baseline"

    def test_lesson_attempt3_stays_sonnet(self) -> None:
        model, reason = select_reviewer_model("lesson", 3)
        assert model == MODEL_SONNET
        assert reason == "doc-class-baseline"

    def test_methodology_attempt2_no_phase_upgrades_to_opus(self) -> None:
        """INFRA-334: methodology escalates unconditionally on retry, even
        without phase_id/project_dir supplied."""
        model, reason = select_reviewer_model("methodology", 2)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_methodology_attempt2_with_phase_id_but_no_project_dir_upgrades(
        self,
    ) -> None:
        """INFRA-334: phase_id no longer influences the outcome — the
        same-phase-code-story conditional escalation was removed."""
        model, reason = select_reviewer_model("methodology", 2, phase_id="24")
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE


# ---------------------------------------------------------------------------
# INFRA-334: methodology no longer depends on a same-phase code story — the
# conditional escalation is removed, methodology escalates unconditionally
# on retry (like code). These tests confirm phase_id/project_dir no longer
# affect the outcome in any direction (present, absent, or unreadable).
# ---------------------------------------------------------------------------


class TestMethodologyUnconditionalEscalation:
    def test_upgrades_regardless_of_same_phase_code_story(
        self, tmp_path: Path
    ) -> None:
        """A same-phase code story is no longer required for the upgrade."""
        _write_story(tmp_path, "INFRA-001", story_class="code")
        _write_story(tmp_path, "INFRA-002", story_class="methodology")
        _write_phase(tmp_path, "24", ["INFRA-001", "INFRA-002"])

        model, reason = select_reviewer_model(
            "methodology", 2, phase_id="24", project_dir=tmp_path
        )
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_upgrades_when_phase_has_only_non_code_stories(
        self, tmp_path: Path
    ) -> None:
        """No code story in phase → methodology still upgrades (INFRA-334)."""
        _write_story(tmp_path, "INFRA-001", story_class="doc")
        _write_story(tmp_path, "LESSON-001", story_class="lesson")
        _write_story(tmp_path, "INFRA-002", story_class="methodology")
        _write_phase(tmp_path, "24", ["INFRA-001", "LESSON-001", "INFRA-002"])

        model, reason = select_reviewer_model(
            "methodology", 2, phase_id="24", project_dir=tmp_path
        )
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_upgrades_when_phase_file_missing(self, tmp_path: Path) -> None:
        """Missing phase manifest no longer matters — upgrade is unconditional."""
        # No phase file written; project_dir is empty
        (tmp_path / "docs" / "phases").mkdir(parents=True, exist_ok=True)

        model, reason = select_reviewer_model(
            "methodology", 2, phase_id="99", project_dir=tmp_path
        )
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_upgrades_when_phase_has_empty_story_table(
        self, tmp_path: Path
    ) -> None:
        """Empty story list in phase no longer matters — upgrade is unconditional."""
        _write_phase(tmp_path, "24", [])

        model, reason = select_reviewer_model(
            "methodology", 2, phase_id="24", project_dir=tmp_path
        )
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_attempt1_methodology_stays_sonnet_even_with_code_story(
        self, tmp_path: Path
    ) -> None:
        """Attempt 1 is always sonnet regardless of same-phase code story."""
        _write_story(tmp_path, "INFRA-001", story_class="code")
        _write_story(tmp_path, "INFRA-002", story_class="methodology")
        _write_phase(tmp_path, "24", ["INFRA-001", "INFRA-002"])

        model, reason = select_reviewer_model(
            "methodology", 1, phase_id="24", project_dir=tmp_path
        )
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"


# ---------------------------------------------------------------------------
# Unknown / missing story_class defaults to "code" rules
# ---------------------------------------------------------------------------


class TestUnknownStoryClass:
    def test_unknown_class_attempt1_returns_sonnet(self) -> None:
        model, reason = select_reviewer_model("unknown", 1)
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"

    def test_unknown_class_attempt2_returns_opus(self) -> None:
        """Unknown defaults to 'code' — upgrades on retry."""
        model, reason = select_reviewer_model("unknown", 2)
        assert model == MODEL_OPUS
        assert reason == "retry-upgrade"

    def test_empty_string_class_attempt2_returns_opus(self) -> None:
        model, reason = select_reviewer_model("", 2)
        assert model == MODEL_OPUS
        assert reason == "retry-upgrade"

    def test_none_like_class_treated_as_code(self) -> None:
        # None would be a type error in typed code but we guard anyway
        # This tests the falsy branch: story_class = ""
        model, reason = select_reviewer_model("", 1)
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"


# ---------------------------------------------------------------------------
# select_intent_reviewer_model
# ---------------------------------------------------------------------------


class TestSelectIntentReviewerModel:
    def test_production_returns_sonnet(self) -> None:
        model, reason = select_intent_reviewer_model("production")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"

    def test_docs_only_returns_sonnet(self) -> None:
        model, reason = select_intent_reviewer_model("docs-only")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"

    def test_pre_pr_returns_opus(self) -> None:
        model, reason = select_intent_reviewer_model("pre-pr")
        assert model == MODEL_OPUS
        assert reason == "production-class"

    def test_unknown_defaults_to_production_sonnet(self) -> None:
        """Unknown phase_class defaults to 'production' → sonnet."""
        model, reason = select_intent_reviewer_model("unknown")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"

    def test_empty_string_defaults_to_production_sonnet(self) -> None:
        model, reason = select_intent_reviewer_model("")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"


# ---------------------------------------------------------------------------
# select_security_auditor_model
# ---------------------------------------------------------------------------


class TestSelectSecurityAuditorModel:
    def test_production_returns_opus(self) -> None:
        model, reason = select_security_auditor_model("production")
        assert model == MODEL_OPUS
        assert reason == "production-class"

    def test_docs_only_returns_sonnet(self) -> None:
        model, reason = select_security_auditor_model("docs-only")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"

    def test_pre_pr_returns_opus(self) -> None:
        model, reason = select_security_auditor_model("pre-pr")
        assert model == MODEL_OPUS
        assert reason == "production-class"

    def test_unknown_defaults_to_production_opus(self) -> None:
        """Unknown phase_class defaults to 'production' → opus."""
        model, reason = select_security_auditor_model("unknown")
        assert model == MODEL_OPUS
        assert reason == "production-class"

    def test_empty_string_defaults_to_production_opus(self) -> None:
        model, reason = select_security_auditor_model("")
        assert model == MODEL_OPUS
        assert reason == "production-class"


# ---------------------------------------------------------------------------
# select_loop_breaker_model
# ---------------------------------------------------------------------------


class TestSelectLoopBreakerModel:
    def test_returns_fable_escalation_upgrade(self) -> None:
        """The loop-breaker rung escalates unconditionally to the fable tier."""
        model, reason = select_loop_breaker_model()
        assert model == "fable"
        assert reason == "escalation-upgrade"

    def test_returns_named_constants(self) -> None:
        model, reason = select_loop_breaker_model()
        assert model == MODEL_FABLE
        assert reason == REASON_ESCALATION_UPGRADE


# ---------------------------------------------------------------------------
# select_gate_worker_model (INFRA-333)
# ---------------------------------------------------------------------------


class TestSelectGateWorkerModel:
    def test_production_returns_opus(self) -> None:
        model, reason = select_gate_worker_model("production")
        assert model == MODEL_OPUS
        assert reason == "production-class"

    def test_docs_only_returns_sonnet(self) -> None:
        model, reason = select_gate_worker_model("docs-only")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"

    def test_pre_pr_returns_opus(self) -> None:
        model, reason = select_gate_worker_model("pre-pr")
        assert model == MODEL_OPUS
        assert reason == "production-class"

    def test_unknown_defaults_to_production_opus(self) -> None:
        model, reason = select_gate_worker_model("unknown")
        assert model == MODEL_OPUS
        assert reason == "production-class"

    def test_empty_string_defaults_to_production_opus(self) -> None:
        model, reason = select_gate_worker_model("")
        assert model == MODEL_OPUS
        assert reason == "production-class"


# ---------------------------------------------------------------------------
# select_docs_reviewer_model (INFRA-333)
# ---------------------------------------------------------------------------


class TestSelectDocsReviewerModel:
    def test_production_returns_sonnet(self) -> None:
        model, reason = select_docs_reviewer_model("production")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"

    def test_docs_only_returns_sonnet(self) -> None:
        model, reason = select_docs_reviewer_model("docs-only")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"

    def test_pre_pr_returns_opus(self) -> None:
        model, reason = select_docs_reviewer_model("pre-pr")
        assert model == MODEL_OPUS
        assert reason == "production-class"

    def test_unknown_defaults_to_production_sonnet(self) -> None:
        model, reason = select_docs_reviewer_model("unknown")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"

    def test_empty_string_defaults_to_production_sonnet(self) -> None:
        model, reason = select_docs_reviewer_model("")
        assert model == MODEL_SONNET
        assert reason == "non-production-class"


# ---------------------------------------------------------------------------
# select_spec_writer_model (INFRA-333)
# ---------------------------------------------------------------------------


class TestSelectSpecWriterModel:
    @pytest.mark.parametrize(
        "story_class", ["code", "doc", "lesson", "methodology"]
    )
    def test_every_known_class_returns_opus(self, story_class: str) -> None:
        model, reason = select_spec_writer_model(story_class)
        assert model == MODEL_OPUS
        assert reason == "spec-elaboration-baseline"

    def test_unknown_defaults_to_code_still_opus(self) -> None:
        model, reason = select_spec_writer_model("unknown")
        assert model == MODEL_OPUS
        assert reason == "spec-elaboration-baseline"

    def test_empty_string_defaults_to_code_still_opus(self) -> None:
        model, reason = select_spec_writer_model("")
        assert model == MODEL_OPUS
        assert reason == "spec-elaboration-baseline"


# ---------------------------------------------------------------------------
# select_shadow_reviewer_model (INFRA-358/359)
# ---------------------------------------------------------------------------


class TestSelectShadowReviewerModel:
    @pytest.mark.parametrize(
        "story_class", ["code", "doc", "lesson", "methodology"]
    )
    def test_every_known_class_returns_sonnet_auto_baseline(
        self, story_class: str
    ) -> None:
        model, reason = select_shadow_reviewer_model(story_class)
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"

    def test_unknown_defaults_to_code_still_sonnet(self) -> None:
        model, reason = select_shadow_reviewer_model("unknown")
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"

    def test_empty_string_defaults_to_code_still_sonnet(self) -> None:
        model, reason = select_shadow_reviewer_model("")
        assert model == MODEL_SONNET
        assert reason == "auto-baseline"


# ---------------------------------------------------------------------------
# select_builder_model — decision table coverage
# ---------------------------------------------------------------------------

_NO_PROTECTED: list[str] = []
_PROTECTED = ["hooks/stop.py", "hooks/exit_plan_mode.py"]


class TestSelectBuilderModel:
    # --- doc stories ---

    def test_doc_any_files_returns_haiku_auto_downgrade(self) -> None:
        model, reason = select_builder_model("doc", [], _NO_PROTECTED)
        assert model == MODEL_HAIKU
        assert reason == REASON_AUTO_DOWNGRADE

    def test_doc_many_files_still_haiku(self) -> None:
        files = ["a.md", "b.md", "c.md", "d.md"]
        model, reason = select_builder_model("doc", files, _NO_PROTECTED)
        assert model == MODEL_HAIKU
        assert reason == REASON_AUTO_DOWNGRADE

    def test_doc_with_protected_file_still_haiku(self) -> None:
        """Protected file signal does NOT override doc class downgrade."""
        model, reason = select_builder_model(
            "doc", ["hooks/stop.py"], ["hooks/stop.py"]
        )
        assert model == MODEL_HAIKU
        assert reason == REASON_AUTO_DOWNGRADE

    # --- lesson stories ---

    def test_lesson_returns_haiku_auto_downgrade(self) -> None:
        model, reason = select_builder_model("lesson", ["lessons/lessons.json"], _NO_PROTECTED)
        assert model == MODEL_HAIKU
        assert reason == REASON_AUTO_DOWNGRADE

    def test_lesson_empty_files_returns_haiku(self) -> None:
        model, reason = select_builder_model("lesson", [], _NO_PROTECTED)
        assert model == MODEL_HAIKU
        assert reason == REASON_AUTO_DOWNGRADE

    # --- methodology stories ---

    def test_methodology_returns_sonnet_auto_baseline(self) -> None:
        model, reason = select_builder_model("methodology", [], _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_methodology_many_files_still_sonnet(self) -> None:
        files = ["a.py", "b.py", "c.py", "d.py"]
        model, reason = select_builder_model("methodology", files, _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_methodology_with_protected_still_sonnet(self) -> None:
        model, reason = select_builder_model(
            "methodology", ["hooks/stop.py"], ["hooks/stop.py"]
        )
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    # --- code stories: auto-baseline (< 5 files, no protected) ---

    def test_code_zero_files_returns_sonnet_auto_baseline(self) -> None:
        model, reason = select_builder_model("code", [], _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_code_one_file_no_protected_returns_sonnet(self) -> None:
        model, reason = select_builder_model("code", ["skills/foo.py"], _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_code_two_files_no_protected_returns_sonnet(self) -> None:
        model, reason = select_builder_model(
            "code", ["skills/a.py", "skills/b.py"], _NO_PROTECTED
        )
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_code_three_files_no_protected_returns_sonnet(self) -> None:
        files = ["a.py", "b.py", "c.py"]
        model, reason = select_builder_model("code", files, _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_code_four_files_no_protected_returns_sonnet(self) -> None:
        files = ["a.py", "b.py", "c.py", "d.py"]
        model, reason = select_builder_model("code", files, _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    # --- code stories: prompted-upgrade (≥ 5 files) ---

    def test_code_five_files_no_protected_returns_opus_prompted(self) -> None:
        files = ["a.py", "b.py", "c.py", "d.py", "e.py"]
        model, reason = select_builder_model("code", files, _NO_PROTECTED)
        assert model == MODEL_OPUS
        assert reason == REASON_PROMPTED_UPGRADE

    def test_code_six_files_returns_opus_prompted(self) -> None:
        files = ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"]
        model, reason = select_builder_model("code", files, _NO_PROTECTED)
        assert model == MODEL_OPUS
        assert reason == REASON_PROMPTED_UPGRADE

    # --- code stories: prompted-upgrade (protected file in primary_files) ---

    def test_code_one_file_protected_returns_opus_prompted(self) -> None:
        model, reason = select_builder_model(
            "code", ["hooks/stop.py"], ["hooks/stop.py"]
        )
        assert model == MODEL_OPUS
        assert reason == REASON_PROMPTED_UPGRADE

    def test_code_two_files_one_protected_returns_opus(self) -> None:
        model, reason = select_builder_model(
            "code",
            ["skills/foo.py", "hooks/stop.py"],
            _PROTECTED,
        )
        assert model == MODEL_OPUS
        assert reason == REASON_PROMPTED_UPGRADE

    def test_code_file_not_in_protected_set_stays_sonnet(self) -> None:
        """primary_file not in protected_files → no upgrade signal."""
        model, reason = select_builder_model(
            "code",
            ["skills/foo.py"],
            ["hooks/stop.py"],  # protected list exists but foo.py is not in it
        )
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    # --- unknown / missing story_class defaults to code ---

    def test_unknown_class_two_files_returns_sonnet(self) -> None:
        model, reason = select_builder_model("unknown", ["a.py", "b.py"], _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_unknown_class_three_files_returns_sonnet(self) -> None:
        model, reason = select_builder_model("unknown", ["a.py", "b.py", "c.py"], _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    def test_empty_class_treated_as_code(self) -> None:
        model, reason = select_builder_model("", [], _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

    # --- user-override reason is a constant (not returned by helper) ---

    def test_user_override_reason_constant_exists(self) -> None:
        """REASON_USER_OVERRIDE is exported for orchestrators to record."""
        from skills.pairmode.scripts.model_selector import REASON_USER_OVERRIDE

        assert REASON_USER_OVERRIDE == "user-override"

    def test_return_type_is_tuple_of_two_strings(self) -> None:
        result = select_builder_model("code", [], _NO_PROTECTED)
        assert isinstance(result, tuple)
        assert len(result) == 2
        model, reason = result
        assert isinstance(model, str)
        assert isinstance(reason, str)


# ---------------------------------------------------------------------------
# select_builder_model — attempt_number escalation (retry path)
# ---------------------------------------------------------------------------


class TestSelectBuilderModelRetry:
    def test_code_attempt2_escalates_to_opus(self) -> None:
        model, reason = select_builder_model("code", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_code_attempt3_escalates_to_opus(self) -> None:
        model, reason = select_builder_model("code", [], _NO_PROTECTED, attempt_number=3)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_code_attempt2_overrides_file_count_signal(self) -> None:
        # Even a 1-file story escalates on retry — attempt_number beats file count.
        model, reason = select_builder_model("code", ["a.py"], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_doc_attempt2_escalates_to_sonnet(self) -> None:
        """INFRA-334: doc no longer stays haiku forever — escalates on retry."""
        model, reason = select_builder_model("doc", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_SONNET
        assert reason == REASON_RETRY_UPGRADE

    def test_doc_attempt5_stays_sonnet(self) -> None:
        """Once escalated, doc does not escalate further past sonnet."""
        model, reason = select_builder_model("doc", [], _NO_PROTECTED, attempt_number=5)
        assert model == MODEL_SONNET
        assert reason == REASON_RETRY_UPGRADE

    def test_lesson_attempt2_escalates_to_sonnet(self) -> None:
        """INFRA-334: lesson no longer stays haiku forever — escalates on retry."""
        model, reason = select_builder_model("lesson", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_SONNET
        assert reason == REASON_RETRY_UPGRADE

    def test_methodology_attempt2_escalates_to_opus(self) -> None:
        """INFRA-334: methodology no longer stays sonnet forever — escalates
        to opus on retry, unconditionally (no same-phase code story needed)."""
        model, reason = select_builder_model("methodology", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_methodology_attempt3_stays_opus(self) -> None:
        model, reason = select_builder_model("methodology", [], _NO_PROTECTED, attempt_number=3)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_unknown_class_attempt2_escalates(self) -> None:
        # Unknown defaults to code — should escalate.
        model, reason = select_builder_model("unknown", [], _NO_PROTECTED, attempt_number=2)
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_attempt1_default_unchanged(self) -> None:
        # attempt_number=1 is the default; existing behaviour must not change.
        model, reason = select_builder_model("code", [], _NO_PROTECTED)
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE


# ---------------------------------------------------------------------------
# CLI tests — __main__ entry point (INFRA-117)
# ---------------------------------------------------------------------------

import subprocess  # noqa: E402


# Valid model identifiers returned by model_selector.
_VALID_MODELS = frozenset({MODEL_HAIKU, MODEL_SONNET, MODEL_OPUS})


def _write_cli_story(tmp_path: Path, story_class: str = "code", phase: str = "45") -> Path:
    """Write a minimal story file for CLI tests."""
    story_dir = tmp_path / "docs" / "stories" / "INFRA"
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / "INFRA-999.md"
    story_path.write_text(
        f"---\n"
        f"id: INFRA-999\n"
        f"rail: INFRA\n"
        f"title: CLI test story\n"
        f"status: planned\n"
        f"phase: \"{phase}\"\n"
        f"story_class: {story_class}\n"
        f"primary_files: []\n"
        f"---\n\nBody text.\n",
        encoding="utf-8",
    )
    return story_path


def _run_cli(story_file: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Invoke model_selector.py as a subprocess using uv run."""
    scripts_dir = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
    cmd = [
        "uv",
        "run",
        "python",
        str(scripts_dir / "model_selector.py"),
        "--story-file",
        str(story_file),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


class TestCLI:
    def test_cli_builder_defaults(self, tmp_path: Path) -> None:
        """Builder role (default) with a code story returns a valid model identifier."""
        story_path = _write_cli_story(tmp_path, story_class="code", phase="45")
        result = _run_cli(story_path, ["--project-dir", str(tmp_path)])

        assert result.returncode == 0, f"stderr: {result.stderr}"
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 2, f"Expected 2 output lines, got: {lines!r}"
        model = lines[0].strip()
        assert model in _VALID_MODELS, f"Unknown model: {model!r}"

    def test_cli_reviewer_role(self, tmp_path: Path) -> None:
        """Reviewer role with a code story returns a valid model string."""
        story_path = _write_cli_story(tmp_path, story_class="code", phase="45")
        result = _run_cli(story_path, ["--role", "reviewer", "--project-dir", str(tmp_path)])

        assert result.returncode == 0, f"stderr: {result.stderr}"
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 2, f"Expected 2 output lines, got: {lines!r}"
        model = lines[0].strip()
        assert model in _VALID_MODELS, f"Unknown model: {model!r}"

    def test_cli_missing_story_file_exits_1(self, tmp_path: Path) -> None:
        """A non-existent story file path must cause exit code 1."""
        nonexistent = tmp_path / "does_not_exist.md"
        result = _run_cli(nonexistent, ["--project-dir", str(tmp_path)])
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# apply_declared_model_floor (INFRA-318)
# ---------------------------------------------------------------------------


class TestApplyDeclaredModelFloor:
    def test_undeclared_is_noop(self) -> None:
        """declared_model=None returns (model, reason) unchanged (Ensures 2/5)."""
        model, reason = apply_declared_model_floor(
            MODEL_SONNET, REASON_AUTO_BASELINE, None, 1
        )
        assert (model, reason) == (MODEL_SONNET, REASON_AUTO_BASELINE)

        model, reason = apply_declared_model_floor(
            MODEL_OPUS, REASON_RETRY_UPGRADE, None, 2
        )
        assert (model, reason) == (MODEL_OPUS, REASON_RETRY_UPGRADE)

    def test_attempt_1_declared_raise_is_override(self) -> None:
        """Attempt 1: declared model above the auto-baseline is an outright
        override, reason becomes story-declared."""
        model, reason = apply_declared_model_floor(
            MODEL_SONNET, REASON_AUTO_BASELINE, MODEL_OPUS, 1
        )
        assert model == MODEL_OPUS
        assert reason == REASON_STORY_DECLARED

    def test_attempt_1_declared_lower_is_override(self) -> None:
        """Attempt 1: declared model below the auto-baseline is also an
        outright override (lowering is unilateral, per spec-writer procedure)."""
        model, reason = apply_declared_model_floor(
            MODEL_OPUS, REASON_PROMPTED_UPGRADE, MODEL_SONNET, 1
        )
        assert model == MODEL_SONNET
        assert reason == REASON_STORY_DECLARED

    def test_attempt_2_never_downgrades_below_declared_floor(self) -> None:
        """Attempt >= 2: the auto-selected retry tier is floored at the
        declared value's rank, never lowered below it."""
        # Auto-selected haiku (hypothetical) with a declared opus floor must
        # rise to opus.
        model, reason = apply_declared_model_floor(
            MODEL_HAIKU, REASON_AUTO_DOWNGRADE, MODEL_OPUS, 2
        )
        assert model == MODEL_OPUS
        # Reason is preserved (still describes what the auto-selector
        # decided) — this is a floor, not a declared override.
        assert reason == REASON_AUTO_DOWNGRADE

    def test_attempt_2_retry_upgrade_already_above_floor_is_unchanged(self) -> None:
        """Attempt >= 2: retry-upgrade already at/above the declared floor is
        left completely alone (no downgrade ever applied by this helper)."""
        model, reason = apply_declared_model_floor(
            MODEL_OPUS, REASON_RETRY_UPGRADE, MODEL_SONNET, 2
        )
        assert model == MODEL_OPUS
        assert reason == REASON_RETRY_UPGRADE

    def test_attempt_2_equal_rank_is_unchanged(self) -> None:
        model, reason = apply_declared_model_floor(
            MODEL_SONNET, REASON_AUTO_BASELINE, MODEL_SONNET, 2
        )
        assert model == MODEL_SONNET
        assert reason == REASON_AUTO_BASELINE

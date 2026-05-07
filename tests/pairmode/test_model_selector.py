"""Tests for skills/pairmode/scripts/model_selector.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from skills.pairmode.scripts.model_selector import (
    MODEL_HAIKU,
    MODEL_OPUS,
    MODEL_SONNET,
    REASON_AUTO_BASELINE,
    REASON_AUTO_DOWNGRADE,
    REASON_PROMPTED_UPGRADE,
    _phase_has_code_story,
    select_builder_model,
    select_intent_reviewer_model,
    select_reviewer_model,
    select_security_auditor_model,
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
        assert select_reviewer_model("code", 1) == MODEL_SONNET

    def test_doc_attempt1(self) -> None:
        assert select_reviewer_model("doc", 1) == MODEL_SONNET

    def test_lesson_attempt1(self) -> None:
        assert select_reviewer_model("lesson", 1) == MODEL_SONNET

    def test_methodology_attempt1(self) -> None:
        assert select_reviewer_model("methodology", 1) == MODEL_SONNET


# ---------------------------------------------------------------------------
# Selection table — attempt_number >= 2
# ---------------------------------------------------------------------------


class TestAttemptTwoPlus:
    def test_code_attempt2_upgrades_to_opus(self) -> None:
        assert select_reviewer_model("code", 2) == MODEL_OPUS

    def test_code_attempt3_upgrades_to_opus(self) -> None:
        assert select_reviewer_model("code", 3) == MODEL_OPUS

    def test_doc_attempt2_stays_sonnet(self) -> None:
        assert select_reviewer_model("doc", 2) == MODEL_SONNET

    def test_doc_attempt5_stays_sonnet(self) -> None:
        assert select_reviewer_model("doc", 5) == MODEL_SONNET

    def test_lesson_attempt2_stays_sonnet(self) -> None:
        assert select_reviewer_model("lesson", 2) == MODEL_SONNET

    def test_lesson_attempt3_stays_sonnet(self) -> None:
        assert select_reviewer_model("lesson", 3) == MODEL_SONNET

    def test_methodology_attempt2_no_phase_stays_sonnet(self) -> None:
        """Methodology without phase_id always stays sonnet."""
        assert select_reviewer_model("methodology", 2) == MODEL_SONNET

    def test_methodology_attempt2_with_phase_id_but_no_project_dir_stays_sonnet(
        self,
    ) -> None:
        """phase_id alone (no project_dir) cannot resolve stories — stays sonnet."""
        assert select_reviewer_model("methodology", 2, phase_id="24") == MODEL_SONNET


# ---------------------------------------------------------------------------
# Same-phase code story rule for methodology
# ---------------------------------------------------------------------------


class TestMethodologySamePhaseCodeStory:
    def test_upgrades_when_phase_has_explicit_code_story(
        self, tmp_path: Path
    ) -> None:
        """Methodology story on retry upgrades if a code story exists in phase."""
        _write_story(tmp_path, "INFRA-001", story_class="code")
        _write_story(tmp_path, "INFRA-002", story_class="methodology")
        _write_phase(tmp_path, "24", ["INFRA-001", "INFRA-002"])

        result = select_reviewer_model(
            "methodology", 2, phase_id="24", project_dir=tmp_path
        )
        assert result == MODEL_OPUS

    def test_upgrades_when_phase_has_story_with_no_class(
        self, tmp_path: Path
    ) -> None:
        """story_class absent defaults to 'code', triggering upgrade."""
        _write_story(tmp_path, "INFRA-001", story_class=None)  # no story_class
        _write_story(tmp_path, "INFRA-002", story_class="methodology")
        _write_phase(tmp_path, "24", ["INFRA-001", "INFRA-002"])

        result = select_reviewer_model(
            "methodology", 2, phase_id="24", project_dir=tmp_path
        )
        assert result == MODEL_OPUS

    def test_stays_sonnet_when_phase_has_only_non_code_stories(
        self, tmp_path: Path
    ) -> None:
        """No code story in phase → methodology stays sonnet even on retry."""
        _write_story(tmp_path, "INFRA-001", story_class="doc")
        _write_story(tmp_path, "LESSON-001", story_class="lesson")
        _write_story(tmp_path, "INFRA-002", story_class="methodology")
        _write_phase(tmp_path, "24", ["INFRA-001", "LESSON-001", "INFRA-002"])

        result = select_reviewer_model(
            "methodology", 2, phase_id="24", project_dir=tmp_path
        )
        assert result == MODEL_SONNET

    def test_stays_sonnet_when_phase_file_missing(self, tmp_path: Path) -> None:
        """Missing phase manifest → fail-safe, stay sonnet."""
        # No phase file written; project_dir is empty
        (tmp_path / "docs" / "phases").mkdir(parents=True, exist_ok=True)

        result = select_reviewer_model(
            "methodology", 2, phase_id="99", project_dir=tmp_path
        )
        assert result == MODEL_SONNET

    def test_stays_sonnet_when_phase_has_empty_story_table(
        self, tmp_path: Path
    ) -> None:
        """Empty story list in phase → no code story → stay sonnet."""
        _write_phase(tmp_path, "24", [])

        result = select_reviewer_model(
            "methodology", 2, phase_id="24", project_dir=tmp_path
        )
        assert result == MODEL_SONNET

    def test_attempt1_methodology_never_upgrades_even_with_code_story(
        self, tmp_path: Path
    ) -> None:
        """Attempt 1 is always sonnet regardless of same-phase code story."""
        _write_story(tmp_path, "INFRA-001", story_class="code")
        _write_story(tmp_path, "INFRA-002", story_class="methodology")
        _write_phase(tmp_path, "24", ["INFRA-001", "INFRA-002"])

        result = select_reviewer_model(
            "methodology", 1, phase_id="24", project_dir=tmp_path
        )
        assert result == MODEL_SONNET


# ---------------------------------------------------------------------------
# Unknown / missing story_class defaults to "code" rules
# ---------------------------------------------------------------------------


class TestUnknownStoryClass:
    def test_unknown_class_attempt1_returns_sonnet(self) -> None:
        assert select_reviewer_model("unknown", 1) == MODEL_SONNET

    def test_unknown_class_attempt2_returns_opus(self) -> None:
        """Unknown defaults to 'code' — upgrades on retry."""
        assert select_reviewer_model("unknown", 2) == MODEL_OPUS

    def test_empty_string_class_attempt2_returns_opus(self) -> None:
        assert select_reviewer_model("", 2) == MODEL_OPUS

    def test_none_like_class_treated_as_code(self) -> None:
        # None would be a type error in typed code but we guard anyway
        # This tests the falsy branch: story_class = ""
        assert select_reviewer_model("", 1) == MODEL_SONNET


# ---------------------------------------------------------------------------
# _phase_has_code_story internal helper
# ---------------------------------------------------------------------------


class TestPhaseHasCodeStory:
    def test_returns_true_for_code_story(self, tmp_path: Path) -> None:
        _write_story(tmp_path, "INFRA-001", story_class="code")
        _write_phase(tmp_path, "24", ["INFRA-001"])
        assert _phase_has_code_story("24", tmp_path) is True

    def test_returns_true_for_missing_story_class(self, tmp_path: Path) -> None:
        """Absent story_class defaults to 'code'."""
        _write_story(tmp_path, "INFRA-001", story_class=None)
        _write_phase(tmp_path, "24", ["INFRA-001"])
        assert _phase_has_code_story("24", tmp_path) is True

    def test_returns_false_for_doc_story(self, tmp_path: Path) -> None:
        _write_story(tmp_path, "INFRA-001", story_class="doc")
        _write_phase(tmp_path, "24", ["INFRA-001"])
        assert _phase_has_code_story("24", tmp_path) is False

    def test_returns_false_for_lesson_story(self, tmp_path: Path) -> None:
        _write_story(tmp_path, "LESSON-001", story_class="lesson")
        _write_phase(tmp_path, "24", ["LESSON-001"])
        assert _phase_has_code_story("24", tmp_path) is False

    def test_returns_false_for_methodology_story(self, tmp_path: Path) -> None:
        _write_story(tmp_path, "INFRA-001", story_class="methodology")
        _write_phase(tmp_path, "24", ["INFRA-001"])
        assert _phase_has_code_story("24", tmp_path) is False

    def test_returns_false_for_missing_phase(self, tmp_path: Path) -> None:
        (tmp_path / "docs" / "phases").mkdir(parents=True, exist_ok=True)
        assert _phase_has_code_story("99", tmp_path) is False

    def test_mixed_phase_returns_true(self, tmp_path: Path) -> None:
        """A mix of doc and code → True (one code story is enough)."""
        _write_story(tmp_path, "INFRA-001", story_class="doc")
        _write_story(tmp_path, "INFRA-002", story_class="code")
        _write_phase(tmp_path, "24", ["INFRA-001", "INFRA-002"])
        assert _phase_has_code_story("24", tmp_path) is True


# ---------------------------------------------------------------------------
# select_intent_reviewer_model
# ---------------------------------------------------------------------------


class TestSelectIntentReviewerModel:
    def test_production_returns_sonnet(self) -> None:
        assert select_intent_reviewer_model("production") == MODEL_SONNET

    def test_docs_only_returns_sonnet(self) -> None:
        assert select_intent_reviewer_model("docs-only") == MODEL_SONNET

    def test_pre_pr_returns_opus(self) -> None:
        assert select_intent_reviewer_model("pre-pr") == MODEL_OPUS

    def test_unknown_defaults_to_production_sonnet(self) -> None:
        """Unknown phase_class defaults to 'production' → sonnet."""
        assert select_intent_reviewer_model("unknown") == MODEL_SONNET

    def test_empty_string_defaults_to_production_sonnet(self) -> None:
        assert select_intent_reviewer_model("") == MODEL_SONNET


# ---------------------------------------------------------------------------
# select_security_auditor_model
# ---------------------------------------------------------------------------


class TestSelectSecurityAuditorModel:
    def test_production_returns_opus(self) -> None:
        assert select_security_auditor_model("production") == MODEL_OPUS

    def test_docs_only_returns_sonnet(self) -> None:
        assert select_security_auditor_model("docs-only") == MODEL_SONNET

    def test_pre_pr_returns_opus(self) -> None:
        assert select_security_auditor_model("pre-pr") == MODEL_OPUS

    def test_unknown_defaults_to_production_opus(self) -> None:
        """Unknown phase_class defaults to 'production' → opus."""
        assert select_security_auditor_model("unknown") == MODEL_OPUS

    def test_empty_string_defaults_to_production_opus(self) -> None:
        assert select_security_auditor_model("") == MODEL_OPUS


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

    # --- code stories: auto-baseline (< 3 files, no protected) ---

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

    # --- code stories: prompted-upgrade (≥ 3 files) ---

    def test_code_three_files_no_protected_returns_opus_prompted(self) -> None:
        files = ["a.py", "b.py", "c.py"]
        model, reason = select_builder_model("code", files, _NO_PROTECTED)
        assert model == MODEL_OPUS
        assert reason == REASON_PROMPTED_UPGRADE

    def test_code_four_files_returns_opus_prompted(self) -> None:
        files = ["a.py", "b.py", "c.py", "d.py"]
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

    def test_unknown_class_three_files_returns_opus(self) -> None:
        model, reason = select_builder_model("unknown", ["a.py", "b.py", "c.py"], _NO_PROTECTED)
        assert model == MODEL_OPUS
        assert reason == REASON_PROMPTED_UPGRADE

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

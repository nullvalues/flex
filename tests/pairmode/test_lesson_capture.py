"""Tests for lesson.py — capture_lesson() function."""

import json
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def patched_lesson(tmp_path, monkeypatch):
    """Redirect LESSONS_FILE (in lesson_utils) and _LESSONS_MD (in lesson) to tmp_path.

    Returns (lesson_module, lessons_json_path, lessons_md_path).
    """
    import skills.pairmode.scripts.lesson_utils as lu
    import skills.pairmode.scripts.lesson as lm

    lessons_json = tmp_path / "lessons.json"
    lessons_md = tmp_path / "LESSONS.md"

    lessons_json.write_text(
        json.dumps({"version": "1.0.0", "lessons": []}) + "\n"
    )

    monkeypatch.setattr(lu, "LESSONS_FILE", lessons_json)
    monkeypatch.setattr(lm, "_LESSONS_MD", lessons_md)

    return lm, lessons_json, lessons_md


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCaptureLessonBasic:
    def test_writes_valid_entry(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lm.capture_lesson(
            trigger="Builder skipped tests",
            problem="Tests failed after story was closed.",
            learning="Always run tests before marking a story done.",
            methodology_change_description="Add test gate to builder checklist.",
            affects=["builder_agent"],
            applies_to=["all"],
        )
        data = json.loads(lessons_json.read_text())
        assert len(data["lessons"]) == 1
        lesson = data["lessons"][0]
        assert lesson["trigger"] == "Builder skipped tests"
        assert lesson["problem"] == "Tests failed after story was closed."
        assert lesson["learning"] == "Always run tests before marking a story done."

    def test_first_lesson_id_is_l001(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="First trigger",
            problem="First problem",
            learning="First learning",
            methodology_change_description="First change",
            affects=["all"],
            applies_to=["all"],
        )
        assert lesson["id"] == "L001"

    def test_second_lesson_id_is_l002(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lm.capture_lesson(
            trigger="First trigger",
            problem="First problem",
            learning="First learning",
            methodology_change_description="First change",
            affects=["all"],
            applies_to=["all"],
        )
        lesson2 = lm.capture_lesson(
            trigger="Second trigger",
            problem="Second problem",
            learning="Second learning",
            methodology_change_description="Second change",
            affects=["reviewer_checklist"],
            applies_to=["python"],
        )
        assert lesson2["id"] == "L002"

    def test_status_is_captured(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="Trigger",
            problem="Problem",
            learning="Learning",
            methodology_change_description="Change",
            affects=["all"],
            applies_to=["all"],
        )
        assert lesson["status"] == "captured"

    def test_affects_stored_in_methodology_change(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="Trigger",
            problem="Problem",
            learning="Learning",
            methodology_change_description="Change description",
            affects=["reviewer_checklist", "builder_agent"],
            applies_to=["all"],
        )
        assert lesson["methodology_change"]["affects"] == ["reviewer_checklist", "builder_agent"]
        assert lesson["methodology_change"]["description"] == "Change description"

    def test_applies_to_stored_correctly(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="Trigger",
            problem="Problem",
            learning="Learning",
            methodology_change_description="Change",
            affects=["all"],
            applies_to=["python", "typescript"],
        )
        assert lesson["applies_to"] == ["python", "typescript"]

    def test_lessons_md_regenerated(self, patched_lesson):
        lm, lessons_json, lessons_md = patched_lesson
        lm.capture_lesson(
            trigger="Some trigger",
            problem="Some problem",
            learning="Some learning",
            methodology_change_description="Some change",
            affects=["all"],
            applies_to=["all"],
        )
        assert lessons_md.exists()
        md_text = lessons_md.read_text()
        assert "# Flex Methodology Lessons" in md_text
        assert "Some trigger" in md_text

    def test_append_only_no_overwrite(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lm.capture_lesson(
            trigger="First",
            problem="P1",
            learning="L1",
            methodology_change_description="C1",
            affects=["all"],
            applies_to=["all"],
        )
        lm.capture_lesson(
            trigger="Second",
            problem="P2",
            learning="L2",
            methodology_change_description="C2",
            affects=["all"],
            applies_to=["all"],
        )
        data = json.loads(lessons_json.read_text())
        assert len(data["lessons"]) == 2
        ids = [e["id"] for e in data["lessons"]]
        assert ids == ["L001", "L002"]

    def test_source_project_default_unknown(self, patched_lesson):
        lm, _, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
        )
        assert lesson["source_project"] == "unknown"

    def test_source_project_custom(self, patched_lesson):
        lm, _, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
            source_project="my-project",
        )
        assert lesson["source_project"] == "my-project"

    def test_date_is_set(self, patched_lesson):
        lm, _, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
        )
        # Should be a valid date string YYYY-MM-DD
        from datetime import date
        parsed = date.fromisoformat(lesson["date"])
        assert parsed is not None


class TestCaptureLessonOptionalFields:
    """Tests for value_framing and validation_phase optional fields (CER-018)."""

    def test_value_framing_written_when_provided(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
            value_framing="efficiency_ratio = pass_rate / avg_cost",
        )
        assert lesson["value_framing"] == "efficiency_ratio = pass_rate / avg_cost"
        data = json.loads(lessons_json.read_text())
        assert data["lessons"][0]["value_framing"] == "efficiency_ratio = pass_rate / avg_cost"

    def test_validation_phase_written_when_provided(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
            validation_phase="phase-28",
        )
        assert lesson["validation_phase"] == "phase-28"
        data = json.loads(lessons_json.read_text())
        assert data["lessons"][0]["validation_phase"] == "phase-28"

    def test_both_optional_fields_written_together(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
            value_framing="ratio_formula",
            validation_phase="phase-24",
        )
        assert lesson["value_framing"] == "ratio_formula"
        assert lesson["validation_phase"] == "phase-24"

    def test_value_framing_absent_when_not_provided(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
        )
        assert "value_framing" not in lesson
        data = json.loads(lessons_json.read_text())
        assert "value_framing" not in data["lessons"][0]

    def test_validation_phase_absent_when_not_provided(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
        )
        assert "validation_phase" not in lesson
        data = json.loads(lessons_json.read_text())
        assert "validation_phase" not in data["lessons"][0]

    def test_optional_fields_not_null_when_absent(self, patched_lesson):
        """Fields must be completely absent (not written as null) when not provided."""
        lm, lessons_json, _ = patched_lesson
        lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
        )
        data = json.loads(lessons_json.read_text())
        lesson = data["lessons"][0]
        # Must not be present at all, not even as null
        assert "value_framing" not in lesson
        assert "validation_phase" not in lesson
        assert lesson.get("value_framing") is None  # confirms absence, not explicit null
        assert lesson.get("validation_phase") is None


class TestCaptureLessonEnforcedBy:
    def test_default_is_none(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
        )
        assert lesson["enforced_by"] == "none"
        data = json.loads(lessons_json.read_text())
        assert data["lessons"][0]["enforced_by"] == "none"

    def test_explicit_value_stored(self, patched_lesson):
        lm, lessons_json, _ = patched_lesson
        lesson = lm.capture_lesson(
            trigger="T",
            problem="P",
            learning="L",
            methodology_change_description="C",
            affects=["all"],
            applies_to=["all"],
            enforced_by="hook",
        )
        assert lesson["enforced_by"] == "hook"
        data = json.loads(lessons_json.read_text())
        assert data["lessons"][0]["enforced_by"] == "hook"

    def test_cli_default_is_none(self, patched_lesson):
        from click.testing import CliRunner
        lm, lessons_json, _ = patched_lesson

        runner = CliRunner()
        result = runner.invoke(lm.cli, [
            "--trigger", "T",
            "--problem", "P",
            "--learning", "L",
            "--methodology-change", "C",
            "--affects", "all",
            "--applies-to", "all",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(lessons_json.read_text())
        assert data["lessons"][0]["enforced_by"] == "none"

    def test_cli_explicit_value_stored(self, patched_lesson):
        from click.testing import CliRunner
        lm, lessons_json, _ = patched_lesson

        runner = CliRunner()
        result = runner.invoke(lm.cli, [
            "--trigger", "T",
            "--problem", "P",
            "--learning", "L",
            "--methodology-change", "C",
            "--affects", "all",
            "--applies-to", "all",
            "--enforced-by", "hook",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(lessons_json.read_text())
        assert data["lessons"][0]["enforced_by"] == "hook"

    def test_cli_invalid_value_rejected(self, patched_lesson):
        from click.testing import CliRunner
        lm, _, _ = patched_lesson

        runner = CliRunner()
        result = runner.invoke(lm.cli, [
            "--trigger", "T",
            "--problem", "P",
            "--learning", "L",
            "--methodology-change", "C",
            "--affects", "all",
            "--applies-to", "all",
            "--enforced-by", "bogus",
        ])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid choice" in result.output.lower()

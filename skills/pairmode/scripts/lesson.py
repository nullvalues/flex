"""Lesson capture script for flex pairmode.

Captures a methodology lesson, appends it to lessons.json, and regenerates LESSONS.md.

Can be used as a library (via capture_lesson()) or as a CLI tool.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Path constants (relative to this file — no hardcoded absolute paths)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent
_PAIRMODE_DIR = _SCRIPTS_DIR.parent
_REPO_ROOT = _PAIRMODE_DIR.parent.parent
_LESSONS_MD = _REPO_ROOT / "lessons" / "LESSONS.md"

# lesson_utils is in the same scripts/ directory
from skills.pairmode.scripts import lesson_utils  # noqa: E402


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def capture_lesson(
    trigger: str,
    problem: str,
    learning: str,
    methodology_change_description: str,
    affects: list[str],
    applies_to: list[str],
    source_project: str = "unknown",
    value_framing: str | None = None,
    validation_phase: str | None = None,
    enforced_by: str = "none",
) -> dict:
    """Capture a lesson and persist it.

    Writes the lesson to lessons.json (via lesson_utils), regenerates LESSONS.md,
    and returns the lesson dict that was written.

    Optional fields:
    - value_framing: durable metric framing for efficiency-based lessons.
    - validation_phase: phase ID that confirmed or revised the lesson.
    When None, these fields are omitted from the lesson entry entirely.

    enforced_by: one of "lint" | "hook" | "skill" | "none" — how (if at all)
    this lesson is mechanically enforced. Defaults to "none".
    """
    data = lesson_utils.load_lessons()

    lesson_id = lesson_utils.next_lesson_id(data.get("lessons", []))
    today = date.today().isoformat()

    lesson = {
        "id": lesson_id,
        "date": today,
        "source_project": source_project,
        "trigger": trigger,
        "problem": problem,
        "learning": learning,
        "methodology_change": {
            "affects": affects,
            "description": methodology_change_description,
        },
        "applies_to": applies_to,
        "status": "captured",
        "enforced_by": enforced_by,
    }

    if value_framing is not None:
        lesson["value_framing"] = value_framing
    if validation_phase is not None:
        lesson["validation_phase"] = validation_phase

    data["lessons"].append(lesson)
    lesson_utils.save_lessons(data)

    md_content = lesson_utils.generate_lessons_md(data)
    _LESSONS_MD.write_text(md_content, encoding="utf-8")

    return lesson


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option("--trigger", required=True, help="What situation prompted this lesson.")
@click.option("--problem", required=True, help="What went wrong or was inefficient.")
@click.option("--learning", required=True, help="The insight or corrective pattern.")
@click.option(
    "--methodology-change",
    "methodology_change",
    required=True,
    help="How the methodology should change as a result.",
)
@click.option(
    "--affects",
    multiple=True,
    default=["all"],
    show_default=True,
    help="Which components are affected (repeat for multiple).",
)
@click.option(
    "--applies-to",
    "applies_to",
    multiple=True,
    default=["all"],
    show_default=True,
    help="Which project types this lesson applies to (repeat for multiple).",
)
@click.option(
    "--source-project",
    "source_project",
    default="unknown",
    show_default=True,
    help="Name of the project that produced this lesson.",
)
@click.option(
    "--value-framing",
    "value_framing",
    default=None,
    help="Durable metric framing for efficiency-based lessons (optional).",
)
@click.option(
    "--validation-phase",
    "validation_phase",
    default=None,
    help="Phase ID that confirmed or revised this lesson (optional).",
)
@click.option(
    "--enforced-by",
    "enforced_by",
    type=click.Choice(["lint", "hook", "skill", "none"]),
    default="none",
    show_default=True,
    help="How this lesson is mechanically enforced, if at all.",
)
def cli(
    trigger: str,
    problem: str,
    learning: str,
    methodology_change: str,
    affects: tuple[str, ...],
    applies_to: tuple[str, ...],
    source_project: str,
    value_framing: str | None,
    validation_phase: str | None,
    enforced_by: str,
) -> None:
    """Capture a methodology lesson and append it to lessons.json."""
    lesson = capture_lesson(
        trigger=trigger,
        problem=problem,
        learning=learning,
        methodology_change_description=methodology_change,
        affects=list(affects),
        applies_to=list(applies_to),
        source_project=source_project,
        value_framing=value_framing,
        validation_phase=validation_phase,
        enforced_by=enforced_by,
    )
    click.echo(f"Lesson captured: {lesson['id']}")
    click.echo(json.dumps(lesson, indent=2))


if __name__ == "__main__":
    cli()

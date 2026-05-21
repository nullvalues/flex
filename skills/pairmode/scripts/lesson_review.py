"""Lesson review script for anchor pairmode.

Surfaces captured lessons grouped by affects, proposes template edits,
and writes approved updates to the templates.  After the lesson review
step, runs drift promotion if registered_projects are present in state.json.

Can be used as a library or as a CLI tool:
    uv run python lesson_review.py --approve L001 --approve L002 --reject L003
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Path constants (relative to this file — no hardcoded absolute paths)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent
_PAIRMODE_DIR = _SCRIPTS_DIR.parent
_TEMPLATES_DIR = _PAIRMODE_DIR / "templates"
_REPO_ROOT = _PAIRMODE_DIR.parent.parent
_LESSONS_MD = _REPO_ROOT / "lessons" / "LESSONS.md"

# Insert repo root so sibling imports work when run as CLI
sys.path.insert(0, str(_REPO_ROOT))

from skills.pairmode.scripts import lesson_utils  # noqa: E402

# ---------------------------------------------------------------------------
# Affects → template file mapping
# ---------------------------------------------------------------------------

_AFFECTS_TO_TEMPLATE: dict[str, str] = {
    "reviewer_checklist": "skills/pairmode/templates/CLAUDE.md.j2",
    "builder_agent": "skills/pairmode/templates/agents/builder.md.j2",
    "orchestrator": "skills/pairmode/templates/CLAUDE.build.md.j2",
    "checkpoint_sequence": "skills/pairmode/templates/CLAUDE.build.md.j2",
}

_ALL_TEMPLATE_FILES: list[str] = [
    "skills/pairmode/templates/CLAUDE.md.j2",
    "skills/pairmode/templates/agents/builder.md.j2",
    "skills/pairmode/templates/CLAUDE.build.md.j2",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_reviewable_lessons() -> list[dict]:
    """Return all lessons with status 'captured' or 'reviewed'."""
    data = lesson_utils.load_lessons()
    return [
        lesson
        for lesson in data.get("lessons", [])
        if lesson.get("status") in ("captured", "reviewed")
    ]


def group_lessons_by_affects(lessons: list[dict]) -> dict[str, list[dict]]:
    """Group lesson list by methodology_change.affects values.

    A lesson with affects=["all"] appears under each known affects key.
    A lesson with affects=["reviewer_checklist"] appears only under
    "reviewer_checklist".
    """
    known_affects = list(_AFFECTS_TO_TEMPLATE.keys()) + ["all"]

    groups: dict[str, list[dict]] = {}

    for lesson in lessons:
        affects_list = lesson.get("methodology_change", {}).get("affects", [])
        for affects_value in affects_list:
            if affects_value == "all":
                # Add this lesson to every known group
                for key in _AFFECTS_TO_TEMPLATE:
                    groups.setdefault(key, []).append(lesson)
            else:
                groups.setdefault(affects_value, []).append(lesson)

    return groups


def propose_template_change(lesson: dict) -> list[dict]:
    """Return a list of proposal dicts for the given lesson.

    For affects values other than "all", returns a single-element list.
    For "all", returns one proposal per known template file.

    Each proposal dict:
    {
        "lesson_id": str,
        "affects": str,
        "template_file": str,
        "description": str,
        "lesson_trigger": str,
        "lesson_learning": str,
    }
    """
    lesson_id = lesson.get("id", "")
    trigger = lesson.get("trigger", "")
    learning = lesson.get("learning", "")
    methodology_change = lesson.get("methodology_change", {})
    affects_list = methodology_change.get("affects", [])
    description = methodology_change.get("description", "")

    proposals: list[dict] = []

    for affects_value in affects_list:
        if affects_value == "all":
            for template_file in _ALL_TEMPLATE_FILES:
                proposals.append({
                    "lesson_id": lesson_id,
                    "affects": affects_value,
                    "template_file": template_file,
                    "description": description,
                    "lesson_trigger": trigger,
                    "lesson_learning": learning,
                })
        else:
            template_file = _AFFECTS_TO_TEMPLATE.get(affects_value, "")
            proposals.append({
                "lesson_id": lesson_id,
                "affects": affects_value,
                "template_file": template_file,
                "description": description,
                "lesson_trigger": trigger,
                "lesson_learning": learning,
            })

    return proposals


def apply_template_change(proposal: dict, change_text: str, templates_root: Path | None = None) -> None:
    """Append change_text as a comment block to the template file.

    Format: {# LESSON <lesson_id>: <change_text> #}

    The comment marks the location for the developer to implement manually.

    Args:
        proposal: A proposal dict from propose_template_change().
        change_text: The text describing the change to embed.
        templates_root: Optional override for the repo root (used in tests).
    """
    root = templates_root if templates_root is not None else _REPO_ROOT
    template_path = (root / proposal["template_file"]).resolve()
    templates_boundary = (root / "skills" / "pairmode" / "templates").resolve()
    try:
        template_path.resolve().relative_to(templates_boundary.resolve())
    except ValueError:
        raise ValueError(
            f"Template path {template_path} is outside templates directory"
        )
    lesson_id = proposal["lesson_id"]

    comment_block = f"\n{{# LESSON {lesson_id}: {change_text} #}}\n"
    with open(template_path, "a", encoding="utf-8") as f:
        f.write(comment_block)


def mark_lesson_status(lesson_id: str, new_status: str) -> None:
    """Update the status field on a lesson.

    Uses save_lessons() which enforces the append-only invariant
    (only the status field may be changed on existing entries).
    """
    data = lesson_utils.load_lessons()
    lessons = data.get("lessons", [])
    for lesson in lessons:
        if lesson.get("id") == lesson_id:
            lesson["status"] = new_status
            break
    lesson_utils.save_lessons(data)


def regenerate_lessons_md() -> None:
    """Reload lessons.json and write LESSONS.md."""
    data = lesson_utils.load_lessons()
    md_content = lesson_utils.generate_lessons_md(data)
    _LESSONS_MD.write_text(md_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Drift promotion
# ---------------------------------------------------------------------------

_DRIFT_REJECTED_FILENAME = ".pairmode-drift-rejected"


def _read_rejected_patterns(project_dir: Path) -> set[str]:
    """Return the set of rejected pattern identifiers from .pairmode-drift-rejected."""
    rejected_path = project_dir / _DRIFT_REJECTED_FILENAME
    if not rejected_path.exists():
        return set()
    try:
        lines = rejected_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {line.strip() for line in lines if line.strip()}


def _append_rejected_pattern(project_dir: Path, pattern_id: str) -> None:
    """Append *pattern_id* to .pairmode-drift-rejected, creating the file if needed."""
    rejected_path = project_dir / _DRIFT_REJECTED_FILENAME
    with open(rejected_path, "a", encoding="utf-8") as f:
        f.write(pattern_id + "\n")


def _candidate_pattern_id(candidate: dict) -> str:
    """Return a stable string identifier for a convergence candidate."""
    return f"{candidate['file']}::{candidate['section']}"


def _safe_registered_project(raw: str) -> Path | None:
    """Validate a registered project path with depth guard.

    Returns the resolved Path on success, None on failure.
    """
    from skills.pairmode.scripts.pairmode_drift_report import _depth_guard

    try:
        resolved = _depth_guard(Path(raw))
    except ValueError as exc:
        click.echo(f"  warning: registered_projects entry skipped — {exc}", err=True)
        return None
    if not resolved.is_dir():
        click.echo(
            f"  warning: registered_projects entry not a directory: {resolved} — skipping",
            err=True,
        )
        return None
    return resolved


def run_drift_promotion(
    project_dirs: list[str | Path],
    project_dir: Path,
    *,
    drift_report_fn=None,
    create_story_fn=None,
    input_fn=None,
) -> None:
    """Run the drift-promotion step for a list of registered project directories.

    Args:
        project_dirs: Validated project directories to analyse.
        project_dir: The anchor project root (where .pairmode-drift-rejected lives).
        drift_report_fn: Callable matching ``drift_report(project_dirs, convergent, output_format)``.
            Defaults to the real ``pairmode_drift_report.drift_report``.
        create_story_fn: Callable matching ``create_story(rail, title, project_dir, ...)``.
            Defaults to the real ``story_new.create_story``.
        input_fn: Callable used to read user input (defaults to ``click.prompt``).
    """
    if drift_report_fn is None:
        from skills.pairmode.scripts.pairmode_drift_report import drift_report as _drift_report
        drift_report_fn = _drift_report

    if create_story_fn is None:
        from skills.pairmode.scripts.story_new import create_story as _create_story
        create_story_fn = _create_story

    if input_fn is None:
        def input_fn(prompt: str) -> str:  # type: ignore[misc]
            return click.prompt(prompt)

    data = drift_report_fn(
        project_dirs=project_dirs,
        convergent=True,
        output_format="json",
    )

    candidates = data.get("convergence_candidates", [])
    if not candidates:
        click.echo("  No convergence candidates found.")
        return

    rejected = _read_rejected_patterns(project_dir)

    promoted_count = 0
    rejected_count = 0

    for candidate in candidates:
        pattern_id = _candidate_pattern_id(candidate)

        # Skip previously rejected patterns
        if pattern_id in rejected:
            continue

        # Surface the candidate
        file_val = candidate.get("file", "")
        section_val = candidate.get("section", "")
        projects_list = candidate.get("projects", [])
        drift_excerpt = candidate.get("project_body", "")[:200]
        score = candidate.get("score")
        justification = candidate.get("justification", "insufficient data")

        click.echo(f"\nCONVERGENCE CANDIDATE — {file_val}/{section_val}")
        click.echo(f"Appears in: {', '.join(projects_list)}")
        # Show token-evidence score before the diff excerpt (INFRA-067)
        if score is None:
            click.echo(f"Token evidence: insufficient data")
        else:
            click.echo(f"Token evidence score: {score:.2f} — {justification}")
        click.echo("Drift:")
        click.echo(f"  {drift_excerpt}")
        click.echo("Promote to canonical? [y/n/skip]")

        answer = input_fn("Choice").strip().lower()

        if answer == "y":
            # Derive a title from the section/file name
            title = f"Promote drift: {section_val} in {file_val}"
            # Use the first project in the list as origin
            origin_project = projects_list[0] if projects_list else "unknown"

            # Create the story file
            story_path = create_story_fn(
                rail="INFRA",
                title=title,
                project_dir=project_dir,
                story_class="code",
                source=origin_project,
            )
            click.echo(f"  Story created: {story_path}")
            promoted_count += 1
        elif answer in ("n", "skip", ""):
            _append_rejected_pattern(project_dir, pattern_id)
            rejected_count += 1
        # Any other value: treat like skip
        else:
            _append_rejected_pattern(project_dir, pattern_id)
            rejected_count += 1

    click.echo(
        f"\nDRIFT PROMOTION COMPLETE — {promoted_count} promoted, {rejected_count} rejected."
    )


def drift_promotion_step(project_dir: Path, **kwargs) -> None:
    """Read registered_projects from state.json and run drift promotion.

    If ``registered_projects`` is absent or empty in ``.companion/state.json``,
    prints a note and returns without error.

    Args:
        project_dir: The anchor project root.
        **kwargs: Forwarded to ``run_drift_promotion`` (for testing overrides).
    """
    from skills.pairmode.scripts.story_context import read_state

    companion_dir = project_dir / ".companion"
    if not companion_dir.is_dir():
        click.echo("  No registered projects — drift detection skipped.")
        return

    state = read_state(companion_dir)
    raw_projects = state.get("registered_projects", [])

    if not raw_projects:
        click.echo("  No registered projects — drift detection skipped.")
        return

    # Validate each path with the depth guard
    valid_dirs: list[Path] = []
    for raw in raw_projects:
        resolved = _safe_registered_project(str(raw))
        if resolved is not None:
            valid_dirs.append(resolved)

    if not valid_dirs:
        click.echo("  No valid registered project paths — drift detection skipped.")
        return

    click.echo(f"  Running drift detection across {len(valid_dirs)} registered project(s)...")
    run_drift_promotion(valid_dirs, project_dir, **kwargs)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--approve",
    "approve_ids",
    multiple=True,
    metavar="LESSON_ID",
    help="Lesson IDs to approve (may be repeated).",
)
@click.option(
    "--reject",
    "reject_ids",
    multiple=True,
    metavar="LESSON_ID",
    help="Lesson IDs to reject (may be repeated).",
)
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Root directory of the anchor project (used for drift detection).",
)
@click.option(
    "--skip-drift",
    is_flag=True,
    default=False,
    help="Skip the drift promotion step.",
)
def cli(
    approve_ids: tuple[str, ...],
    reject_ids: tuple[str, ...],
    project_dir: str,
    skip_drift: bool,
) -> None:
    """Process lesson approvals and rejections, then regenerate LESSONS.md.

    After processing lessons, runs drift promotion if registered_projects are
    present in .companion/state.json (unless --skip-drift is passed).

    Approved lessons: apply_template_change() is called with the lesson's
    own description as change_text, then status is set to 'applied'.

    Rejected lessons: status is set to 'reviewed'.
    """
    if not approve_ids and not reject_ids:
        click.echo("No lessons specified. Use --approve or --reject.")
        return

    all_lessons = load_reviewable_lessons()
    lessons_by_id = {l["id"]: l for l in all_lessons}

    approved_count = 0
    rejected_count = 0

    for lesson_id in approve_ids:
        lesson = lessons_by_id.get(lesson_id)
        if lesson is None:
            click.echo(f"WARNING: lesson {lesson_id} not found or not reviewable — skipping.")
            continue
        proposals = propose_template_change(lesson)
        for proposal in proposals:
            description = proposal["description"]
            apply_template_change(proposal, description)
            click.echo(
                f"  Annotated {proposal['template_file']} with lesson {lesson_id}.\n"
                f"  ACTION REQUIRED: Open the template and implement the change:\n"
                f"    {{# LESSON {lesson_id}: {proposal['description']} #}}"
            )
        mark_lesson_status(lesson_id, "applied")
        approved_count += 1

    for lesson_id in reject_ids:
        if lesson_id not in lessons_by_id:
            click.echo(f"WARNING: lesson {lesson_id} not found or not reviewable — skipping.")
            continue
        mark_lesson_status(lesson_id, "reviewed")
        rejected_count += 1

    regenerate_lessons_md()
    click.echo(
        f"REVIEW COMPLETE\n"
        f"  {approved_count} lesson(s) annotated — open affected templates to implement the changes.\n"
        f"  {rejected_count} lesson(s) deferred for next review cycle.\n"
        f"LESSONS.md regenerated."
    )

    # Drift promotion step — runs after lesson review
    if not skip_drift:
        click.echo("\n--- Drift Promotion ---")
        drift_promotion_step(Path(project_dir).resolve())


if __name__ == "__main__":
    cli()

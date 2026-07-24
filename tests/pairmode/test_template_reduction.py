"""
Tests for HARNESS-001: CLAUDE.build.md.j2 thin dispatch loop reduction.

Asserts:
- Template renders without Jinja2 errors given minimal context vars.
- Rendered output is <=40 non-blank lines.
- Rendered output contains required keywords ("next-action", "leaf-worker").
- Rendered output does NOT contain old procedure-section headings or prose.
"""
from pathlib import Path

import jinja2
import pytest


TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent
    / "skills"
    / "pairmode"
    / "templates"
    / "CLAUDE.build.md.j2"
)

MINIMAL_CONTEXT = {
    "project_name": "test-project",
    "build_command": "uv run pytest tests/ -x -q",
    "test_command": "uv run pytest tests/ -x -q",
    "migration_command": "",
    "pairmode_scripts_dir": "/path/to/scripts",
}

# Old headings / prose that must NOT appear in the reduced template.
BANNED_PHRASES = [
    "## Gate checks",
    "await-user",
    "## Model evaluation",
    "## Step 1",
    "## Step 2",
    "## Step 3",
    "## Spec workflow",
    "## Session modes",
    "## Pre-story gates",
]


@pytest.fixture(scope="module")
def rendered() -> str:
    loader = jinja2.FileSystemLoader(str(TEMPLATE_PATH.parent))
    env = jinja2.Environment(loader=loader, undefined=jinja2.Undefined)
    template = env.get_template(TEMPLATE_PATH.name)
    return template.render(**MINIMAL_CONTEXT)


def test_renders_without_error(rendered: str) -> None:
    """Template must render to a non-empty string without raising."""
    assert rendered.strip(), "Rendered template is empty"


def test_non_blank_line_count(rendered: str) -> None:
    """Rendered template must be <=40 non-blank lines."""
    non_blank = [line for line in rendered.splitlines() if line.strip()]
    assert len(non_blank) <= 40, (
        f"Rendered template has {len(non_blank)} non-blank lines (limit: 40).\n"
        + "\n".join(f"  {i+1}: {l}" for i, l in enumerate(non_blank))
    )


def test_contains_next_action(rendered: str) -> None:
    """Rendered template must mention next-action (the resolver CLI)."""
    assert "next-action" in rendered


def test_contains_leaf_worker(rendered: str) -> None:
    """Rendered template must mention leaf-worker (the dispatch concept)."""
    assert "leaf-worker" in rendered


@pytest.mark.parametrize("phrase", BANNED_PHRASES)
def test_old_prose_absent(rendered: str, phrase: str) -> None:
    """Old procedure headings and prose must not appear in the reduced template."""
    assert phrase not in rendered, (
        f"Old procedure phrase found in reduced template: {phrase!r}"
    )

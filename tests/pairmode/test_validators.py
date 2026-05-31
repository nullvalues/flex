"""Tests for _validate_test_command in bootstrap.py.

Covers:
- Python stack + Python test_command → no warnings
- Python stack + Node test_command → no warnings (inverse not gated)
- Node stack + Python test_command (AAB case) → one warning
- Node stack + Node test_command → no warnings
"""

from __future__ import annotations

from skills.pairmode.scripts.bootstrap import _validate_test_command


def test_python_stack_python_test_command_no_warnings() -> None:
    """Python stack with pytest command should produce no warnings."""
    warnings = _validate_test_command(
        "uv run pytest tests/ -x -q",
        "Python / FastAPI / SQLAlchemy / pytest",
    )
    assert warnings == []


def test_python_stack_node_test_command_no_warnings() -> None:
    """Python stack with a Node test command should produce no warnings.

    The inverse direction (Python stack + Node command) is not a defect
    we have evidence for; the validator does not gate it.
    """
    warnings = _validate_test_command(
        "pnpm test",
        "Python / Django / pytest",
    )
    assert warnings == []


def test_node_stack_python_test_command_one_warning() -> None:
    """Node stack with pytest command should produce exactly one warning (the AAB case)."""
    warnings = _validate_test_command(
        "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q",
        "TypeScript / pnpm workspaces / Fastify v5 / Drizzle ORM / Postgres / Vite / React 19 / Tailwind v4 / better-auth / zod / vitest",
    )
    assert len(warnings) == 1
    assert "pytest" in warnings[0] or "uv run" in warnings[0]
    assert "Python" in warnings[0]


def test_node_stack_node_test_command_no_warnings() -> None:
    """Node stack with a pnpm test command should produce no warnings."""
    warnings = _validate_test_command(
        "pnpm test",
        "TypeScript / pnpm workspaces / Fastify v5 / vitest",
    )
    assert warnings == []

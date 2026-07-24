"""Invariant tests for CER-053 state half (HARNESS-003).

Asserts that expected_step_tokens (the context-budget window-growth constant) is
sourced from THIN_HARNESS_STEP_TOKENS, not from effort.db / by_role.builder.median.
"""
from __future__ import annotations

import ast
import pathlib

SCRIPTS = pathlib.Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"


def _source(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def _function_body_source(source: str, func_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return ast.unparse(node)
    return ""


class TestExpectedStepTokensSource:
    """(a) bootstrap.py seed function does not read effort.db / by_role."""

    def test_load_seed_does_not_reference_effort_baseline(self) -> None:
        body = _function_body_source(_source("bootstrap.py"), "_load_seed_expected_step_tokens")
        assert body, "Function _load_seed_expected_step_tokens not found in bootstrap.py"
        assert "by_role" not in body, "Seed function still reads by_role (effort.db comingling)"
        assert "effort_baseline" not in body, "Seed function still references effort_baseline"
        assert "builder" not in body.lower() or "THIN_HARNESS_STEP_TOKENS" in body, (
            "Seed function may still reference builder effort data"
        )

    def test_load_seed_returns_thin_harness_constant(self) -> None:
        body = _function_body_source(_source("bootstrap.py"), "_load_seed_expected_step_tokens")
        assert "THIN_HARNESS_STEP_TOKENS" in body, (
            "Seed function should return THIN_HARNESS_STEP_TOKENS, not effort.db value"
        )

    def test_bootstrap_default_not_53000(self) -> None:
        src = _source("bootstrap.py")
        assert "_DEFAULT_EXPECTED_STEP_TOKENS = 53000" not in src, (
            "Effort-derived literal 53000 still in bootstrap.py _DEFAULT_EXPECTED_STEP_TOKENS"
        )

    def test_sync_default_not_53000(self) -> None:
        src = _source("sync.py")
        assert '"expected_step_tokens", 53000' not in src, (
            "Effort-derived literal 53000 still in sync.py expected_step_tokens default"
        )

    def test_context_budget_fallback_not_53000(self) -> None:
        src = _source("context_budget.py")
        assert "53000" not in src, (
            "Effort-derived literal 53000 still in context_budget.py"
        )

    def test_context_budget_does_not_read_effort_db_for_window_growth(self) -> None:
        """(b) context_budget.py decide() does not pass db_path to estimate_next_step_tokens."""
        body = _function_body_source(_source("context_budget.py"), "decide")
        assert "estimate_next_step_tokens(None" in body, (
            "decide() should pass db_path=None to estimate_next_step_tokens to exclude effort.db"
        )

    def test_seeded_value_matches_thin_harness_constant(self) -> None:
        """(c) The seeded value matches THIN_HARNESS_STEP_TOKENS."""
        from skills.pairmode.scripts.bootstrap import _load_seed_expected_step_tokens
        from skills.pairmode.scripts.context_model import THIN_HARNESS_STEP_TOKENS
        assert _load_seed_expected_step_tokens() == THIN_HARNESS_STEP_TOKENS

    def test_context_model_constant_defined(self) -> None:
        from skills.pairmode.scripts.context_model import THIN_HARNESS_STEP_TOKENS
        assert isinstance(THIN_HARNESS_STEP_TOKENS, int)
        assert THIN_HARNESS_STEP_TOKENS > 0
        assert THIN_HARNESS_STEP_TOKENS < 53000, (
            "Thin-harness step constant should be smaller than the old effort-derived 53000"
        )

    def test_derive_expected_step_tokens_never_opens_effort_db(self) -> None:
        """(d) INFRA-254: the new live-derivation path
        (derive_expected_step_tokens) never opens effort.db — it reads only
        the ring-buffer/seed already present in the state dict it is passed."""
        body = _function_body_source(
            _source("context_budget.py"), "derive_expected_step_tokens"
        )
        assert body, "Function derive_expected_step_tokens not found in context_budget.py"
        assert "sqlite3" not in body
        assert "connect(" not in body
        assert "db_path" not in body

    def test_record_step_growth_never_opens_effort_db(self) -> None:
        """(d) INFRA-254: the ring-buffer recording path is also DP7-clean."""
        body = _function_body_source(_source("context_budget.py"), "record_step_growth")
        assert body, "Function record_step_growth not found in context_budget.py"
        assert "sqlite3" not in body
        assert "connect(" not in body

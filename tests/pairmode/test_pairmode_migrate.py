# Full test coverage in INFRA-093. This stub satisfies the per-story test-coverage gate.
"""
Minimal smoke tests for pairmode_migrate.py.

These tests verify:
1. Module imports successfully (no syntax errors or broken imports)
2. Depth guard rejects shallow paths
3. MigrationReport and MigrationRule dataclasses can be instantiated
4. MIGRATION_RULES is a non-empty list with expected structure

The full 12-test suite lives in INFRA-093 and will extend this skeleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import setup
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import pairmode_migrate as _mod  # noqa: E402


# ---------------------------------------------------------------------------
# Test 1: Module imports successfully
# ---------------------------------------------------------------------------


class TestImport:
    """The module must import without errors."""

    def test_module_attributes_present(self) -> None:
        """Key public symbols must be present after import."""
        assert hasattr(_mod, "migrate"), "migrate() function not found"
        assert hasattr(_mod, "MigrationReport"), "MigrationReport dataclass not found"
        assert hasattr(_mod, "MigrationRule"), "MigrationRule dataclass not found"
        assert hasattr(_mod, "MIGRATION_RULES"), "MIGRATION_RULES constant not found"


# ---------------------------------------------------------------------------
# Test 2: Depth guard
# ---------------------------------------------------------------------------


class TestDepthGuard:
    """_depth_guard() must reject paths with fewer than 3 components."""

    def test_depth_guard_rejects_shallow_path(self) -> None:
        """A path like /tmp should be rejected with SystemExit(1)."""
        shallow = Path("/tmp")
        with pytest.raises(SystemExit) as exc_info:
            _mod._depth_guard(shallow)
        assert exc_info.value.code == 1

    def test_depth_guard_rejects_root(self) -> None:
        """The filesystem root / must be rejected."""
        with pytest.raises(SystemExit) as exc_info:
            _mod._depth_guard(Path("/"))
        assert exc_info.value.code == 1

    def test_depth_guard_accepts_deep_path(self, tmp_path: Path) -> None:
        """A path with 3+ components must not raise."""
        # tmp_path is typically /tmp/pytest-xxx/test_xxx/... (>=3 parts)
        # Ensure we have at least 3 parts
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True, exist_ok=True)
        # Should not raise
        _mod._depth_guard(deep)


# ---------------------------------------------------------------------------
# Test 3: MigrationReport and MigrationRule dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:
    """Dataclasses must be instantiable with default values."""

    def test_migration_report_default_instantiation(self) -> None:
        """MigrationReport() with no args must work."""
        r = _mod.MigrationReport()
        assert r.changed == []
        assert r.skipped == []
        assert r.missing == []
        assert r.backups == []
        assert r.gate_results == []
        assert r.already_migrated is False
        assert r.pairmode_version_old is None
        assert r.pairmode_version_new is None

    def test_migration_report_with_values(self) -> None:
        """MigrationReport can be constructed with explicit field values."""
        r = _mod.MigrationReport(
            changed=["a.py", "b.py"],
            skipped=["c.py"],
            missing=["d.py"],
            backups=["a.py.bak"],
            gate_results=[("gate 1", True)],
            already_migrated=False,
            pairmode_version_old="anchor-1.0",
            pairmode_version_new="0.2.0",
        )
        assert len(r.changed) == 2
        assert r.pairmode_version_old == "anchor-1.0"
        assert r.pairmode_version_new == "0.2.0"

    def test_migration_rule_default_instantiation(self) -> None:
        """MigrationRule() must work with required fields only."""
        rule = _mod.MigrationRule(
            rule_id=99,
            description="test rule",
            strategy="regex",
        )
        assert rule.rule_id == 99
        assert rule.description == "test rule"
        assert rule.strategy == "regex"
        assert rule.patterns == []
        assert rule.handler == ""
        assert rule.lessons_gated is False

    def test_migration_rule_with_patterns(self) -> None:
        """MigrationRule with patterns must store them correctly."""
        rule = _mod.MigrationRule(
            rule_id=1,
            description="test",
            strategy="regex",
            patterns=[("old", "new"), ("foo", "bar")],
        )
        assert len(rule.patterns) == 2
        assert rule.patterns[0] == ("old", "new")


# ---------------------------------------------------------------------------
# Test 4: MIGRATION_RULES structure
# ---------------------------------------------------------------------------


class TestMigrationRules:
    """MIGRATION_RULES must be a non-empty list with valid structure."""

    def test_migration_rules_is_list(self) -> None:
        """MIGRATION_RULES must be a list."""
        assert isinstance(_mod.MIGRATION_RULES, list)

    def test_migration_rules_is_non_empty(self) -> None:
        """MIGRATION_RULES must contain at least one rule."""
        assert len(_mod.MIGRATION_RULES) > 0, "MIGRATION_RULES must not be empty"

    def test_migration_rules_has_15_entries(self) -> None:
        """MIGRATION_RULES must contain all 15 rules as specified."""
        assert len(_mod.MIGRATION_RULES) == 15, (
            f"Expected 15 rules, got {len(_mod.MIGRATION_RULES)}"
        )

    def test_migration_rules_all_are_migration_rule_instances(self) -> None:
        """Every entry in MIGRATION_RULES must be a MigrationRule instance."""
        for rule in _mod.MIGRATION_RULES:
            assert isinstance(rule, _mod.MigrationRule), (
                f"Rule {rule!r} is not a MigrationRule instance"
            )

    def test_migration_rules_have_unique_ids(self) -> None:
        """Each rule must have a unique rule_id."""
        ids = [r.rule_id for r in _mod.MIGRATION_RULES]
        assert len(ids) == len(set(ids)), "MIGRATION_RULES contains duplicate rule_ids"

    def test_migration_rules_ids_are_sequential_1_to_15(self) -> None:
        """Rule IDs must run from 1 to 15 inclusive."""
        ids = sorted(r.rule_id for r in _mod.MIGRATION_RULES)
        assert ids == list(range(1, 16)), f"Rule IDs are not 1–15: {ids}"

    def test_migration_rules_strategies_are_valid(self) -> None:
        """Every rule strategy must be one of the recognised values."""
        valid = {"subprocess", "regex", "conditional", "bypass", "regenerate"}
        for rule in _mod.MIGRATION_RULES:
            assert rule.strategy in valid, (
                f"Rule {rule.rule_id} has unknown strategy: {rule.strategy!r}"
            )

    def test_lessons_gated_rules_are_14_and_15(self) -> None:
        """Rules 14 and 15 must be lessons_gated=True; all others False."""
        for rule in _mod.MIGRATION_RULES:
            if rule.rule_id in (14, 15):
                assert rule.lessons_gated is True, (
                    f"Rule {rule.rule_id} should be lessons_gated=True"
                )
            else:
                assert rule.lessons_gated is False, (
                    f"Rule {rule.rule_id} should be lessons_gated=False"
                )

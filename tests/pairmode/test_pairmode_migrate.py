"""
Comprehensive tests for pairmode_migrate.py — INFRA-093 and RELEASE-011.

Tests run against a synthetic anchor-bootstrapped project fixture.
Rules 1 and 2 (subprocess-based sync-build and sync-agents) are mocked
to avoid real subprocess calls on synthetic fixtures.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import setup
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import pairmode_migrate as _mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _build_anchor_project(tmp_path: Path) -> Path:
    """Create a minimal but representative anchor-bootstrapped project under tmp_path.

    Populates files with anchor references at every substitution site the rule
    table covers. Returns tmp_path (the project root).
    """
    root = tmp_path

    # CLAUDE.build.md — has /anchor: refs and /mnt/work/anchor path
    (root / "CLAUDE.build.md").write_text(
        "# Build guide\n"
        "PYTHONPATH=/mnt/work/anchor/skills/pairmode/scripts\n"
        "Run /anchor:pairmode to bootstrap.\n",
        encoding="utf-8",
    )

    # .claude/agents/ — builder.md and reviewer.md
    agents_dir = root / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    (agents_dir / "builder.md").write_text(
        "---\nmodel: sonnet\n---\nYou are the builder for the anchor project.\n",
        encoding="utf-8",
    )
    (agents_dir / "reviewer.md").write_text(
        "---\nmodel: sonnet\n---\nYou are the reviewer for the anchor project.\n",
        encoding="utf-8",
    )
    (agents_dir / "security-auditor.md").write_text(
        "---\nmodel: sonnet\n---\n"
        "Auth config: $HOME/.anchor/auth.json\n",
        encoding="utf-8",
    )

    # .claude/settings.deny-rationale.json
    deny_rationale = root / ".claude" / "settings.deny-rationale.json"
    deny_rationale.write_text(
        json.dumps({"generated_by": "anchor:pairmode", "rules": []}),
        encoding="utf-8",
    )

    # hooks/
    hooks_dir = root / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "session_start.py").write_text(
        "# Hook\n"
        "import os\n"
        "ANCHOR_PROJECT_DIR = os.environ.get('ANCHOR_PROJECT_DIR', '')\n"
        "# /tmp/anchor_project_dir_xyz\n",
        encoding="utf-8",
    )
    (hooks_dir / "session_end.py").write_text(
        "# Anchor companion terminal.\n"
        "print('Session ended')\n",
        encoding="utf-8",
    )

    # skills/companion/
    companion_scripts = root / "skills" / "companion" / "scripts"
    companion_scripts.mkdir(parents=True)

    (root / "skills" / "companion" / "SKILL.md").write_text(
        "---\n"
        "name: anchor:companion\n"
        "---\n"
        "# Companion skill\nUse /anchor:companion to start.\n",
        encoding="utf-8",
    )
    (companion_scripts / "launch_sidebar.sh").write_text(
        "#!/bin/bash\n"
        "export ANCHOR_PROJECT_DIR=$1\n"
        "source ~/.anchor/auth.json\n",
        encoding="utf-8",
    )
    (companion_scripts / "start_sidebar.sh").write_text(
        "#!/bin/bash\n"
        "echo $ANCHOR_PROJECT_DIR\n",
        encoding="utf-8",
    )
    (companion_scripts / "sidebar.py").write_text(
        '# Sidebar\ntitle="[bold]anchor[/bold]"\n',
        encoding="utf-8",
    )

    # skills/seed/
    seed_skill = root / "skills" / "seed"
    seed_skill.mkdir(parents=True)
    (seed_skill / "SKILL.md").write_text(
        "name: anchor:seed\nUse /anchor:seed to run.\n",
        encoding="utf-8",
    )

    # skills/pairmode/
    pairmode_skill = root / "skills" / "pairmode"
    pairmode_skill.mkdir(parents=True)
    (pairmode_skill / "SKILL.md").write_text(
        "---\n"
        "name: anchor:pairmode\n"
        "---\n"
        "Use /anchor:pairmode to bootstrap a project.\n",
        encoding="utf-8",
    )

    # .companion/state.json — skipped by gate scan but processed by rule 13
    companion_dir = root / ".companion"
    companion_dir.mkdir()
    (companion_dir / "state.json").write_text(
        json.dumps({
            "pairmode_version": "anchor-0.1.0",
            "project_name": "anchor",
        }),
        encoding="utf-8",
    )

    # lessons/
    lessons_dir = root / "lessons"
    lessons_dir.mkdir()
    (lessons_dir / "lessons.json").write_text(
        json.dumps({
            "lessons": [
                {
                    "id": "L001",
                    "source_project": "anchor",
                    "trigger": "anchor fails",
                    "problem": "anchor issue",
                    "learning": "use flex not anchor",
                    "status": "active",
                }
            ]
        }),
        encoding="utf-8",
    )
    (lessons_dir / "LESSONS.md").write_text(
        "# Anchor Methodology Lessons\n\nSome lessons here.\n",
        encoding="utf-8",
    )

    # docs/ — NOT touched by migration
    docs_dir = root / "docs"
    docs_dir.mkdir()
    phases_dir = docs_dir / "phases"
    phases_dir.mkdir()
    (phases_dir / "phase-1.md").write_text(
        "# Phase 1\nThis is project history about anchor.\n",
        encoding="utf-8",
    )
    (docs_dir / "architecture.md").write_text(
        "# Architecture\nThis project was originally called anchor.\n",
        encoding="utf-8",
    )

    return root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_subprocess_side_effect(project: Path, backup_suffix: str) -> object:
    """Return a side_effect function for subprocess.run that simulates sync-build/sync-agents.

    When the mock is called for sync-build, it rewrites CLAUDE.build.md to remove
    common anchor refs (simulating what pairmode_sync sync-build would do).
    When called for sync-agents, it rewrites agent frontmatter lines.
    All calls return a MagicMock with returncode=0.
    """
    import re

    def _side_effect(cmd, **kwargs):  # type: ignore[no-untyped-def]
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""

        # Detect which subcommand is being called by inspecting cmd list
        cmd_str = " ".join(str(c) for c in cmd)
        if "sync-build" in cmd_str:
            target = project / "CLAUDE.build.md"
            if target.exists():
                original = target.read_text(encoding="utf-8")
                modified = re.sub(r"/anchor:", "/flex:", original)
                modified = re.sub(r"/mnt/work/anchor\b", "/mnt/work/flex", modified)
                modified = re.sub(r"\banchor\b", "flex", modified, flags=re.IGNORECASE)
                if modified != original:
                    backup = Path(str(target) + backup_suffix)
                    if not backup.exists():
                        backup.write_text(original, encoding="utf-8")
                    target.write_text(modified, encoding="utf-8")
        elif "sync-agents" in cmd_str:
            agents_dir = project / ".claude" / "agents"
            if agents_dir.is_dir():
                for md_file in agents_dir.glob("*.md"):
                    original = md_file.read_text(encoding="utf-8")
                    modified = re.sub(r"\banchor\b", "flex", original, flags=re.IGNORECASE)
                    if modified != original:
                        backup = Path(str(md_file) + backup_suffix)
                        if not backup.exists():
                            backup.write_text(original, encoding="utf-8")
                        md_file.write_text(modified, encoding="utf-8")

        return result

    return _side_effect


def _run_migrate_no_subprocess(
    project: Path,
    *,
    apply: bool = False,
    yes: bool = True,
    migrate_lessons: bool = False,
    backup_suffix: str = ".pre-flex-migration",
) -> "_mod.MigrationReport":
    """Run migrate() with subprocess calls (rules 1 and 2) mocked.

    When apply=True, the mock side_effect simulates what sync-build and sync-agents
    would do so that the project is fully migrated and idempotency checks pass.
    When apply=False (dry-run), the mock returns returncode=0 without writing.
    """
    if apply:
        side_effect = _make_subprocess_side_effect(project, backup_suffix)
    else:
        mock_result = MagicMock(returncode=0, stderr="", stdout="")
        side_effect = lambda cmd, **kw: mock_result  # noqa: E731

    with patch("pairmode_migrate.subprocess.run", side_effect=side_effect):
        return _mod.migrate(
            project,
            apply=apply,
            yes=yes,
            migrate_lessons=migrate_lessons,
            backup_suffix=backup_suffix,
        )


# ---------------------------------------------------------------------------
# Test 1 — dry-run does not write
# ---------------------------------------------------------------------------


def test_migrate_dry_run_does_not_write(tmp_path: Path) -> None:
    """Dry-run mode must not modify any files and must not create backups."""
    project = _build_anchor_project(tmp_path)

    # Snapshot all file contents before the run
    before: dict[str, bytes] = {
        str(p): p.read_bytes()
        for p in sorted(project.rglob("*"))
        if p.is_file()
    }

    report = _run_migrate_no_subprocess(project, apply=False)

    # No backups
    backups = list(project.rglob("*.pre-flex-migration"))
    assert backups == [], f"Dry-run created backups: {backups}"

    # File contents unchanged
    for path_str, original_bytes in before.items():
        p = Path(path_str)
        if p.exists():
            assert p.read_bytes() == original_bytes, (
                f"Dry-run modified file: {path_str}"
            )

    # Report has non-empty changed list (proposals)
    assert len(report.changed) > 0, "Dry-run report.changed should be non-empty"


# ---------------------------------------------------------------------------
# Test 2 — apply writes changes and backups
# ---------------------------------------------------------------------------


def test_migrate_apply_writes_changes_and_backups(tmp_path: Path) -> None:
    """apply=True must write new content and create .pre-flex-migration backups."""
    project = _build_anchor_project(tmp_path)

    report = _run_migrate_no_subprocess(project, apply=True, yes=True)

    assert not report.already_migrated, "Project should not be considered already-migrated"

    # Every file in report.changed must exist; every backup file must exist
    for changed_path in report.changed:
        # Strip dry-run suffix if present (shouldn't be, but be safe)
        clean_path = changed_path.replace(" (subprocess dry-run)", "")
        p = Path(clean_path)
        assert p.exists(), f"Changed file does not exist: {clean_path}"

    for backup_path in report.backups:
        assert Path(backup_path).exists(), f"Backup file does not exist: {backup_path}"


def test_migrate_rule_8_rewrites_seed_name_bare_not_flex_prefixed(
    tmp_path: Path,
) -> None:
    """Rule 8's frontmatter rewrite must produce bare `name: seed`, not
    `name: flex:seed` — a doubled `flex:` prefix on top of the plugin
    namespace Claude Code already applies (INFRA-292)."""
    project = _build_anchor_project(tmp_path)

    _run_migrate_no_subprocess(project, apply=True, yes=True)

    seed_skill_md = (project / "skills" / "seed" / "SKILL.md").read_text()
    assert "name: seed" in seed_skill_md
    assert "name: flex:seed" not in seed_skill_md


def test_migrate_rules_9_10_rewrite_pairmode_companion_names_bare_not_flex_prefixed(
    tmp_path: Path,
) -> None:
    """CER-108: rules 9 and 10 must reach frontmatter parity with rule 8.

    Runs the real migrate-from-anchor apply path (not a unit test over the
    `patterns` tuples — F1) against a fixture whose skills/pairmode/SKILL.md
    and skills/companion/SKILL.md carry `anchor:`-prefixed frontmatter
    `name:` values, alongside the existing `/anchor:` prose. After apply,
    both SKILL.md files must carry the bare name (INFRA-292's rationale:
    Claude Code already applies the plugin namespace, so a `flex:` prefix
    in frontmatter would double it), and the `anchor:` name must be gone
    entirely.
    """
    project = _build_anchor_project(tmp_path)

    _run_migrate_no_subprocess(project, apply=True, yes=True)

    pairmode_skill_md = (project / "skills" / "pairmode" / "SKILL.md").read_text()
    assert "name: pairmode" in pairmode_skill_md
    assert "name: flex:pairmode" not in pairmode_skill_md
    assert "anchor:pairmode" not in pairmode_skill_md

    companion_skill_md = (project / "skills" / "companion" / "SKILL.md").read_text()
    assert "name: companion" in companion_skill_md
    assert "name: flex:companion" not in companion_skill_md
    assert "anchor:companion" not in companion_skill_md


# ---------------------------------------------------------------------------
# Test 3 — state.json pairmode_version bumped
# ---------------------------------------------------------------------------


def test_migrate_state_json_version_bumped(tmp_path: Path) -> None:
    """After apply, state.json pairmode_version must not start with 'anchor-'."""
    project = _build_anchor_project(tmp_path)

    _run_migrate_no_subprocess(project, apply=True, yes=True)

    state = json.loads((project / ".companion" / "state.json").read_text())
    assert not state["pairmode_version"].startswith("anchor-"), (
        f"pairmode_version still starts with 'anchor-': {state['pairmode_version']!r}"
    )


def test_migrate_state_json_version_matches_current_pairmode_version(
    tmp_path: Path,
) -> None:
    """After apply, state.json pairmode_version must equal _version.PAIRMODE_VERSION.

    Drift canary (INFRA-250): the default on
    ``_apply_conditional_rule``'s ``new_pairmode_version`` keyword must derive
    from ``_version.PAIRMODE_VERSION``, not duplicate it as a hardcoded
    string. Bumping ``_version.py`` alone must never again leave migrate
    stamping projects with a stale version.
    """
    project = _build_anchor_project(tmp_path)

    _run_migrate_no_subprocess(project, apply=True, yes=True)

    state = json.loads((project / ".companion" / "state.json").read_text())
    assert state["pairmode_version"] == _mod.PAIRMODE_VERSION


def test_apply_conditional_rule_default_matches_version_module() -> None:
    """The handler's keyword default must equal _version.PAIRMODE_VERSION directly."""
    import inspect

    sig = inspect.signature(_mod._apply_conditional_rule)
    default = sig.parameters["new_pairmode_version"].default
    assert default == _mod.PAIRMODE_VERSION


# ---------------------------------------------------------------------------
# Test 4 — custom project_name preserved (not "anchor")
# ---------------------------------------------------------------------------


def test_migrate_state_json_custom_project_name_preserved(tmp_path: Path) -> None:
    """A project_name other than 'anchor' must survive migration unchanged."""
    project = _build_anchor_project(tmp_path)

    # Overwrite state.json with a non-anchor project name
    state_file = project / ".companion" / "state.json"
    state_file.write_text(
        json.dumps({"pairmode_version": "anchor-0.1.0", "project_name": "cora"}),
        encoding="utf-8",
    )

    _run_migrate_no_subprocess(project, apply=True, yes=True)

    state = json.loads(state_file.read_text())
    assert state["project_name"] == "cora", (
        f"project_name was changed from 'cora' to {state['project_name']!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 — authored content not touched
# ---------------------------------------------------------------------------


def test_migrate_does_not_touch_authored_content(tmp_path: Path) -> None:
    """docs/phases/phase-1.md and docs/architecture.md must be unchanged after migration."""
    project = _build_anchor_project(tmp_path)

    phase1 = project / "docs" / "phases" / "phase-1.md"
    arch = project / "docs" / "architecture.md"

    phase1_before = phase1.read_bytes()
    arch_before = arch.read_bytes()

    _run_migrate_no_subprocess(project, apply=True, yes=True)

    assert phase1.read_bytes() == phase1_before, "docs/phases/phase-1.md was modified"
    assert arch.read_bytes() == arch_before, "docs/architecture.md was modified"


# ---------------------------------------------------------------------------
# Test 6 — lessons default skip (no --migrate-lessons)
# ---------------------------------------------------------------------------


def test_migrate_lessons_default_skip(tmp_path: Path) -> None:
    """Without migrate_lessons=True, lessons/lessons.json must be unchanged."""
    project = _build_anchor_project(tmp_path)
    lessons_file = project / "lessons" / "lessons.json"
    before = lessons_file.read_bytes()

    _run_migrate_no_subprocess(project, apply=True, yes=True, migrate_lessons=False)

    assert lessons_file.read_bytes() == before, (
        "lessons/lessons.json was modified without migrate_lessons=True"
    )


# ---------------------------------------------------------------------------
# Test 8 — idempotent
# ---------------------------------------------------------------------------


def _build_minimal_anchor_project(tmp_path: Path) -> Path:
    """Build a minimal anchor project for the idempotency test.

    Contains only files with anchor refs that are fully cleaned by the migration
    engine (no lessons files that partially survive migration). This ensures
    all gate checks pass after the first apply run.
    """
    root = tmp_path

    # CLAUDE.build.md — cleaned by rule 1 (subprocess mock)
    (root / "CLAUDE.build.md").write_text(
        "PYTHONPATH=/mnt/work/anchor/skills\n"
        "Run /anchor:pairmode to bootstrap.\n",
        encoding="utf-8",
    )

    # .claude/agents/
    agents_dir = root / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "builder.md").write_text(
        "---\nmodel: sonnet\n---\nYou are the builder for the anchor project.\n",
        encoding="utf-8",
    )

    # .claude/settings.deny-rationale.json
    (root / ".claude" / "settings.deny-rationale.json").write_text(
        json.dumps({"generated_by": "anchor:pairmode"}),
        encoding="utf-8",
    )

    # hooks/
    hooks_dir = root / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "session.py").write_text(
        "ANCHOR_PROJECT_DIR = ''\nANCHOR_PROJECT_HASH = ''\n",
        encoding="utf-8",
    )

    # skills/seed/
    (root / "skills" / "seed").mkdir(parents=True)
    (root / "skills" / "seed" / "SKILL.md").write_text(
        "name: anchor:seed\nUse /anchor:seed\n",
        encoding="utf-8",
    )

    # skills/pairmode/
    (root / "skills" / "pairmode").mkdir(parents=True)
    (root / "skills" / "pairmode" / "SKILL.md").write_text(
        "---\n"
        "name: anchor:pairmode\n"
        "---\n"
        "Use /anchor:pairmode\n",
        encoding="utf-8",
    )

    # skills/companion/
    companion_scripts = root / "skills" / "companion" / "scripts"
    companion_scripts.mkdir(parents=True)
    (root / "skills" / "companion" / "SKILL.md").write_text(
        "---\n"
        "name: anchor:companion\n"
        "---\n"
        "/anchor:companion\n",
        encoding="utf-8",
    )
    (companion_scripts / "launch_sidebar.sh").write_text(
        "#!/bin/bash\nexport ANCHOR_PROJECT_DIR=$1\n",
        encoding="utf-8",
    )
    (companion_scripts / "start_sidebar.sh").write_text(
        "#!/bin/bash\necho $ANCHOR_PROJECT_DIR\n",
        encoding="utf-8",
    )
    (companion_scripts / "sidebar.py").write_text(
        'title="[bold]anchor[/bold]"\n',
        encoding="utf-8",
    )

    # .companion/state.json
    (root / ".companion").mkdir()
    (root / ".companion" / "state.json").write_text(
        json.dumps({"pairmode_version": "anchor-0.1.0", "project_name": "anchor"}),
        encoding="utf-8",
    )

    return root


def test_migrate_idempotent(tmp_path: Path) -> None:
    """Running apply twice: second run reports already_migrated=True; no new backups.

    Note: The gate scan (which determines already_migrated) scans all text files
    including backup files (.pre-flex-migration). To test true idempotency, we
    remove the backup files after the first run — backup files from the first run
    are themselves expected to contain the original (anchor) content and must not
    be confused with live project files on the second run.
    """
    project = _build_minimal_anchor_project(tmp_path)

    # First run — apply the migration
    report1 = _run_migrate_no_subprocess(project, apply=True, yes=True)
    assert not report1.already_migrated, (
        "First run should NOT be already_migrated"
    )

    # Remove backup files so the second run doesn't see anchor refs in backups
    for backup in list(project.rglob("*.pre-flex-migration")):
        backup.unlink()

    # Second run — the project is now fully migrated; should detect it and skip
    report2 = _run_migrate_no_subprocess(project, apply=True, yes=True)

    assert report2.already_migrated, (
        "Second apply run (after backup cleanup) should report already_migrated=True.\n"
        f"Gate results: {report2.gate_results}"
    )

    # No new backups created on second run (engine exits early via already_migrated)
    new_backups = list(project.rglob("*.pre-flex-migration"))
    assert new_backups == [], f"New backups created on second run: {new_backups}"


# ---------------------------------------------------------------------------
# Test 9 — partial project (missing files) completes on the rest
# ---------------------------------------------------------------------------


def test_migrate_partial_project_missing_files(tmp_path: Path) -> None:
    """A fixture without CLAUDE.build.md must list it in missing but still complete.

    Rule 1 (subprocess sync-build) explicitly checks for CLAUDE.build.md existence
    and adds it to report.missing when absent. The engine must continue processing
    remaining rules rather than aborting.
    """
    project = _build_anchor_project(tmp_path)

    # Remove CLAUDE.build.md — rule 1 checks this explicitly and marks it missing
    (project / "CLAUDE.build.md").unlink()

    report = _run_migrate_no_subprocess(project, apply=False)

    # CLAUDE.build.md should appear in missing
    build_md_path = str(project / "CLAUDE.build.md")
    assert build_md_path in report.missing, (
        f"Expected {build_md_path} in report.missing.\n"
        f"Actual missing: {report.missing}"
    )

    # Engine should have completed and processed other rules (report returned, not crashed)
    assert report is not None

    # Other files without CLAUDE.build.md still get processed — should have changed entries
    assert len(report.changed) > 0, (
        "Expected other files to be proposed as changed even though CLAUDE.build.md is missing"
    )


# ---------------------------------------------------------------------------
# Test 10 — gate residuals reported for uncovered anchor refs
# ---------------------------------------------------------------------------


def test_migrate_gate_residuals_reported(tmp_path: Path) -> None:
    """An extra file with an uncovered anchor ref must show up in gate results as dirty."""
    project = _build_anchor_project(tmp_path)

    # Add an extra file with a raw anchor ref not covered by any rule
    extra = project / "docs" / "foo.md"
    extra.write_text(
        "This document references /anchor:pairmode — an uncovered ref.\n",
        encoding="utf-8",
    )

    # Run migration (apply to clear the known refs, but the extra file is not in any rule)
    report = _run_migrate_no_subprocess(project, apply=True, yes=True)

    # After migration, the extra file still has anchor refs.
    # Running gates again on the post-migration state should detect the residual.
    gate_results = _mod._run_gates(project)

    # At least one gate should be dirty (the broad-sweep gate or /anchor: gate)
    dirty = [(name, clean) for name, clean in gate_results if not clean]
    assert len(dirty) >= 1, (
        "Expected at least one dirty gate due to residual in docs/foo.md, "
        f"but all gates passed. Gate results: {gate_results}"
    )


# ---------------------------------------------------------------------------
# Test 11 — depth guard rejects shallow paths
# ---------------------------------------------------------------------------


def test_migrate_depth_guard_rejects_shallow_path() -> None:
    """Calling migrate() with /tmp (2 components) raises SystemExit."""
    with pytest.raises(SystemExit) as exc_info:
        _mod.migrate(
            Path("/tmp"),
            apply=False,
            yes=True,
            migrate_lessons=False,
        )
    # Exit code must be 1 (or any non-zero)
    assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# Test 12 — dry-run then apply: changed file sets match
# ---------------------------------------------------------------------------


def test_migrate_dry_run_then_apply(tmp_path: Path) -> None:
    """Files proposed by dry-run and files changed by apply must be the same set."""
    project = _build_anchor_project(tmp_path)

    # Dry-run pass — capture changed proposals
    dry_report = _run_migrate_no_subprocess(project, apply=False)
    # Strip subprocess dry-run annotation for comparison
    dry_changed = {
        c.replace(" (subprocess dry-run)", "")
        for c in dry_report.changed
    }

    # Apply pass
    apply_report = _run_migrate_no_subprocess(project, apply=True, yes=True)
    apply_changed = set(apply_report.changed)

    # The sets must match (order-independent)
    assert dry_changed == apply_changed, (
        f"Dry-run proposed: {sorted(dry_changed)}\n"
        f"Apply changed:    {sorted(apply_changed)}"
    )


# ---------------------------------------------------------------------------
# Retained skeleton tests (still valid, complement the 12 above)
# ---------------------------------------------------------------------------


class TestImport:
    """The module must import without errors."""

    def test_module_attributes_present(self) -> None:
        assert hasattr(_mod, "migrate")
        assert hasattr(_mod, "MigrationReport")
        assert hasattr(_mod, "MigrationRule")
        assert hasattr(_mod, "MIGRATION_RULES")


class TestDepthGuard:
    """_depth_guard() must reject paths with fewer than 3 components."""

    def test_depth_guard_rejects_shallow_path(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            _mod._depth_guard(Path("/tmp"))
        assert exc_info.value.code == 1

    def test_depth_guard_rejects_root(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            _mod._depth_guard(Path("/"))
        assert exc_info.value.code == 1

    def test_depth_guard_accepts_deep_path(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True, exist_ok=True)
        _mod._depth_guard(deep)  # must not raise


class TestDataclasses:
    """Dataclasses must be instantiable with default values."""

    def test_migration_report_default_instantiation(self) -> None:
        r = _mod.MigrationReport()
        assert r.changed == []
        assert r.skipped == []
        assert r.missing == []
        assert r.backups == []
        assert r.gate_results == []
        assert r.already_migrated is False
        assert r.pairmode_version_old is None
        assert r.pairmode_version_new is None

    def test_migration_rule_default_instantiation(self) -> None:
        rule = _mod.MigrationRule(rule_id=99, description="test rule", strategy="regex")
        assert rule.rule_id == 99
        assert rule.patterns == []
        assert rule.handler == ""
        assert rule.lessons_gated is False


class TestMigrationRules:
    """MIGRATION_RULES structure checks."""

    def test_migration_rules_has_14_entries(self) -> None:
        assert len(_mod.MIGRATION_RULES) == 14

    def test_migration_rules_ids_are_sequential_1_to_14(self) -> None:
        ids = sorted(r.rule_id for r in _mod.MIGRATION_RULES)
        assert ids == list(range(1, 15))

    def test_lessons_gated_rule_is_only_14(self) -> None:
        for rule in _mod.MIGRATION_RULES:
            if rule.rule_id == 14:
                assert rule.lessons_gated is True
            else:
                assert rule.lessons_gated is False


# ---------------------------------------------------------------------------
# Test 13 — backup-suffix path validation
# ---------------------------------------------------------------------------


def test_migrate_backup_suffix_validation(tmp_path: Path) -> None:
    """_validate_backup_suffix must reject suffixes with '/' or '..'."""
    from pairmode_migrate import _validate_backup_suffix, migrate  # noqa: F401
    # CLI-level validation (existing)
    with pytest.raises(SystemExit):
        _validate_backup_suffix("/tmp/evil")
    with pytest.raises(SystemExit):
        _validate_backup_suffix("../etc/cron")
    # Valid suffixes must not raise:
    _validate_backup_suffix(".pre-flex-migration")
    _validate_backup_suffix(".bak")
    # Programmatic path — migrate() itself must also reject bad suffix
    with pytest.raises(SystemExit):
        migrate(tmp_path, apply=False, yes=False, migrate_lessons=False,
                backup_suffix="/tmp/evil")


# ---------------------------------------------------------------------------
# Test 14 — apply rejects non-project directories
# ---------------------------------------------------------------------------


def test_migrate_apply_rejects_non_project_dir(tmp_path: Path) -> None:
    """migrate() with apply=True on a directory with no sentinels must raise SystemExit."""
    # tmp_path has no CLAUDE.build.md, .companion/, or .claude/agents/
    # Ensure the path is deep enough to pass the depth guard
    project = tmp_path / "a" / "b" / "c"
    project.mkdir(parents=True)
    with pytest.raises(SystemExit):
        _mod.migrate(project, apply=True, yes=True, migrate_lessons=False)


# ===========================================================================
# to-030 tests (RELEASE-011)
# ===========================================================================


def _build_030_project(tmp_path: Path, **state_overrides: object) -> Path:
    """Build a minimal project for to-030 tests.

    Creates .companion/state.json with the given state dict.
    """
    root = tmp_path
    companion_dir = root / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state: dict = {"pairmode_version": "0.2.0", "expected_step_tokens": _mod.ERA2_STAMP}
    state.update(state_overrides)
    (companion_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return root


def _invoke_030(
    project_dir: Path,
    *,
    apply: bool = False,
    keep_expected_step_tokens: bool = False,
) -> tuple[int, str]:
    """Invoke cmd_to_030 via the Click test runner; return (exit_code, output)."""
    from click.testing import CliRunner

    runner = CliRunner()
    args = ["to-030", "--project-dir", str(project_dir)]
    if apply:
        args.append("--apply")
    if keep_expected_step_tokens:
        args.append("--keep-expected-step-tokens")
    # Mock subprocess.run so git log doesn't depend on the project being a real repo.
    with patch("pairmode_migrate.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = runner.invoke(_mod.cli, args, catch_exceptions=False)
    return result.exit_code, result.output


# ---------------------------------------------------------------------------
# B6: expected_step_tokens rewrite
# ---------------------------------------------------------------------------


def test_to030_rewrites_era2_stamp_with_apply(tmp_path: Path) -> None:
    """to-030 --apply must overwrite expected_step_tokens 53000 → 5000."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.ERA2_STAMP)
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0, f"Non-zero exit: {output}"
    state = json.loads(state_path.read_text())
    assert state["expected_step_tokens"] == _mod.THIN_HARNESS_STEP_TOKENS, (
        f"expected_step_tokens not rewritten: {state['expected_step_tokens']!r}"
    )
    assert "[apply]" in output


def test_to030_dryrun_does_not_rewrite_era2_stamp(tmp_path: Path) -> None:
    """to-030 dry-run must print [would] but not change state.json."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.ERA2_STAMP)
    state_path = project / ".companion" / "state.json"
    before = state_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=False)

    assert exit_code == 0
    assert state_path.read_bytes() == before, "Dry-run modified state.json"
    assert "[would]" in output


def test_to030_keeps_custom_expected_step_tokens(tmp_path: Path) -> None:
    """to-030 must leave a non-Era2 custom value unchanged and emit a WARN.

    This is the proof (CER-111) that keep+WARN was never removed: the
    three-way branch has been live the whole time. It is not deleted by
    INFRA-303 — it is the evidence the CER-111 backlog annotation rests on.
    """
    custom_val = 25000
    project = _build_030_project(tmp_path, expected_step_tokens=custom_val)
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert state["expected_step_tokens"] == custom_val, (
        "Custom expected_step_tokens was changed."
    )
    assert "[WARN]" in output and "custom" in output.lower()


def test_to030_rewrite_message_names_ambiguity_and_opt_out(tmp_path: Path) -> None:
    """B4: both [apply] and [would] rewrite messages must name the escape hatch."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.ERA2_STAMP)

    _, apply_output = _invoke_030(project, apply=True)
    assert "--keep-expected-step-tokens" in apply_output
    assert "53000" in apply_output

    project2 = _build_030_project(tmp_path / "dry", expected_step_tokens=_mod.ERA2_STAMP)
    _, dryrun_output = _invoke_030(project2, apply=False)
    assert "--keep-expected-step-tokens" in dryrun_output
    assert "53000" in dryrun_output


def test_to030_keep_flag_suppresses_era2_rewrite(tmp_path: Path) -> None:
    """--keep-expected-step-tokens on a 53000 value: emit [keep], leave value unchanged,
    and emit no rewrite/WARN line."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.ERA2_STAMP)
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True, keep_expected_step_tokens=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert state["expected_step_tokens"] == _mod.ERA2_STAMP
    assert "[keep]" in output
    assert "rewrote" not in output
    assert "[WARN]" not in output


def test_to030_keep_flag_dryrun_writes_nothing(tmp_path: Path) -> None:
    """B6: dry-run with the flag writes nothing — state.json bytes identical before/after."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.ERA2_STAMP)
    state_path = project / ".companion" / "state.json"
    before = state_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=False, keep_expected_step_tokens=True)

    assert exit_code == 0
    assert state_path.read_bytes() == before
    assert "[keep]" in output


def test_to030_keep_flag_does_not_suppress_other_steps(tmp_path: Path) -> None:
    """B3: with the flag passed, other to-030 steps (e.g. B4 pipe_path removal)
    still fire, byte-identical to a run without the flag."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.ERA2_STAMP,
        pipe_path="/tmp/old.pipe",
    )
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True, keep_expected_step_tokens=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert "pipe_path" not in state, "B4 pipe_path removal did not fire under the flag"
    assert state["expected_step_tokens"] == _mod.ERA2_STAMP


def test_to030_warns_and_keeps_53416(tmp_path: Path) -> None:
    """E1 row 3: 53416 is the value four live fleet projects (RELEASE-067..)
    actually held — it is not the Era 2 stamp, so keep+WARN applies."""
    custom_val = 53416
    project = _build_030_project(tmp_path, expected_step_tokens=custom_val)
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert state["expected_step_tokens"] == custom_val
    assert "[WARN]" in output


def test_to030_silent_when_already_thin_harness_value(tmp_path: Path) -> None:
    """E1 row 4: expected_step_tokens already 5000 (THIN_HARNESS_STEP_TOKENS) —
    silent no-op: no rewrite, no WARN, no keep line."""
    project = _build_030_project(
        tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS
    )
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert state["expected_step_tokens"] == _mod.THIN_HARNESS_STEP_TOKENS
    assert "rewrote" not in output
    assert "[WARN]" not in output
    assert "[keep]" not in output


# ---------------------------------------------------------------------------
# B4: pipe_path removal
# ---------------------------------------------------------------------------


def test_to030_removes_pipe_path_with_apply(tmp_path: Path) -> None:
    """to-030 --apply must remove the pipe_path key from state.json."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        pipe_path="/tmp/old.pipe",
    )
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert "pipe_path" not in state, "pipe_path was not removed"
    assert "deprecation" in output.lower() or "deprecated" in output.lower()


def test_to030_dryrun_does_not_remove_pipe_path(tmp_path: Path) -> None:
    """to-030 dry-run must print a notice about pipe_path but not remove it."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        pipe_path="/tmp/old.pipe",
    )
    state_path = project / ".companion" / "state.json"
    before = state_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=False)

    assert exit_code == 0
    assert state_path.read_bytes() == before, "Dry-run modified state.json"
    assert "pipe_path" in output


# ---------------------------------------------------------------------------
# B5: state.json seed
# ---------------------------------------------------------------------------


def test_to030_seeds_missing_state_json_with_apply(tmp_path: Path) -> None:
    """to-030 --apply must write a minimal state.json when .companion/ exists but state.json is absent."""
    root = tmp_path
    companion_dir = root / ".companion"
    companion_dir.mkdir(parents=True)
    state_path = companion_dir / "state.json"
    assert not state_path.exists()

    exit_code, output = _invoke_030(root, apply=True)

    assert exit_code == 0
    assert state_path.exists(), "state.json was not seeded"
    state = json.loads(state_path.read_text())
    assert state["pairmode_version"] == "0.3.0"
    assert state["expected_step_tokens"] == _mod.THIN_HARNESS_STEP_TOKENS


def test_to030_dryrun_does_not_seed_missing_state_json(tmp_path: Path) -> None:
    """to-030 dry-run must not create state.json when it is absent."""
    root = tmp_path
    companion_dir = root / ".companion"
    companion_dir.mkdir(parents=True)
    state_path = companion_dir / "state.json"

    exit_code, output = _invoke_030(root, apply=False)

    assert exit_code == 0
    assert not state_path.exists(), "Dry-run created state.json"
    assert "[would]" in output


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_to030_idempotent(tmp_path: Path) -> None:
    """Running to-030 --apply twice produces no additional changes on second run."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.ERA2_STAMP,
        pipe_path="/tmp/old.pipe",
    )
    state_path = project / ".companion" / "state.json"

    _invoke_030(project, apply=True)

    # Snapshot after first run
    after_first = state_path.read_bytes()

    _invoke_030(project, apply=True)

    assert state_path.read_bytes() == after_first, "Second run changed state.json"


# ---------------------------------------------------------------------------
# B7: stale agent cleanup
# ---------------------------------------------------------------------------


def test_to030_deletes_stale_agent_matching_hash(tmp_path: Path) -> None:
    """to-030 --apply must delete an agent file whose hash is in _ERA2_AGENT_HASHES."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS)
    agents_dir = project / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    # Write a builder.md with known content and register its hash in the allowlist
    content = b"# builder agent v0.2.x stale template\n"
    builder_file = agents_dir / "builder.md"
    builder_file.write_bytes(content)
    known_hash = hashlib.sha256(content).hexdigest()

    with patch.dict(_mod._ERA2_AGENT_HASHES, {"builder": known_hash}):
        exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert not builder_file.exists(), "Stale agent file was not deleted"
    assert "[apply]" in output and "deleted" in output.lower()


def test_to030_dryrun_does_not_delete_stale_agent(tmp_path: Path) -> None:
    """to-030 dry-run must print [would] delete but not remove the stale agent file."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS)
    agents_dir = project / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    content = b"# builder agent v0.2.x stale template\n"
    builder_file = agents_dir / "builder.md"
    builder_file.write_bytes(content)
    known_hash = hashlib.sha256(content).hexdigest()

    with patch.dict(_mod._ERA2_AGENT_HASHES, {"builder": known_hash}):
        exit_code, output = _invoke_030(project, apply=False)

    assert exit_code == 0
    assert builder_file.exists(), "Dry-run deleted the agent file"
    assert "[would]" in output and "delete" in output.lower()


def test_to030_defers_customized_agent(tmp_path: Path) -> None:
    """to-030 must defer a customized agent (hash not in allowlist) with instructions."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS)
    agents_dir = project / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    custom_content = b"# Highly customized builder - do not delete!\nCustom instruction here.\n"
    builder_file = agents_dir / "builder.md"
    builder_file.write_bytes(custom_content)

    # _ERA2_AGENT_HASHES is empty by default — no match expected
    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert builder_file.exists(), "Customized agent file was incorrectly deleted"
    assert "manual" in output.lower() or "port" in output.lower(), (
        "Expected porting instructions in output"
    )


# ---------------------------------------------------------------------------
# B8: effort_tracking backfill (INFRA-236)
# ---------------------------------------------------------------------------


def test_to030_backfills_missing_effort_tracking_with_apply(tmp_path: Path) -> None:
    """to-030 --apply must set effort_tracking: true when the key is absent."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS)
    state_path = project / ".companion" / "state.json"
    before = json.loads(state_path.read_text())
    assert "effort_tracking" not in before

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert state["effort_tracking"] is True
    assert "[apply]" in output and "effort_tracking" in output


def test_to030_dryrun_does_not_backfill_effort_tracking(tmp_path: Path) -> None:
    """to-030 dry-run must print [would] backfill but not write effort_tracking."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS)
    state_path = project / ".companion" / "state.json"
    before = state_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=False)

    assert exit_code == 0
    assert state_path.read_bytes() == before, "Dry-run modified state.json"
    assert "[would]" in output and "effort_tracking" in output


def test_to030_preserves_explicit_effort_tracking_false(tmp_path: Path) -> None:
    """to-030 must NOT override an explicitly-set effort_tracking: false."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=False,
    )
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert state["effort_tracking"] is False, (
        "An explicit effort_tracking: false must not be overridden by the backfill"
    )
    assert "backfilled" not in output.lower()


def test_to030_leaves_explicit_effort_tracking_true_unchanged(tmp_path: Path) -> None:
    """to-030 must be a no-op for a project that already has effort_tracking: true."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
    )
    state_path = project / ".companion" / "state.json"
    before = state_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert state_path.read_bytes() == before, (
        "to-030 must not rewrite state.json when effort_tracking is already set"
    )


def test_to030_effort_tracking_backfill_is_idempotent(tmp_path: Path) -> None:
    """Running to-030 --apply twice must not change state.json on the second run."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS)
    state_path = project / ".companion" / "state.json"

    _invoke_030(project, apply=True)
    after_first = state_path.read_bytes()

    _invoke_030(project, apply=True)

    assert state_path.read_bytes() == after_first, "Second run changed state.json"


# ---------------------------------------------------------------------------
# INFRA-290 (D): context_story_tokens removal
# ---------------------------------------------------------------------------


def test_to030_dryrun_leaves_context_story_tokens_and_prints_would(tmp_path: Path) -> None:
    """Dry-run must leave the key present and print the [would] line (D2)."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
        context_story_tokens={"INFRA-181": 12345},
    )
    state_path = project / ".companion" / "state.json"
    before = state_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=False)

    assert exit_code == 0
    assert state_path.read_bytes() == before, "Dry-run modified state.json"
    assert "[would] remove 'context_story_tokens' key from state.json" in output


def test_to030_apply_removes_context_story_tokens(tmp_path: Path) -> None:
    """--apply must remove the key and print the [apply] line (D1/D2)."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
        context_story_tokens={"INFRA-181": 12345},
    )
    state_path = project / ".companion" / "state.json"

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    state = json.loads(state_path.read_text())
    assert "context_story_tokens" not in state
    assert "[apply] removed 'context_story_tokens' key from state.json" in output


def test_to030_no_context_story_tokens_is_silent_noop(tmp_path: Path) -> None:
    """A state.json without the key produces no output line for it (D2)."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
    )

    exit_code, output = _invoke_030(project, apply=False)

    assert exit_code == 0
    assert "context_story_tokens" not in output


# ---------------------------------------------------------------------------
# INFRA-290 (E): stale legacy-shape attempt_counter.json retirement
# ---------------------------------------------------------------------------


def _write_legacy_counter(project: Path, story_id: str = "BUILD-022", count: int = 2) -> Path:
    counter_path = project / ".companion" / "attempt_counter.json"
    counter_path.write_text(
        json.dumps({"story_id": story_id, "attempt_count": count}), encoding="utf-8"
    )
    return counter_path


def test_to030_apply_deletes_stale_legacy_counter(tmp_path: Path) -> None:
    """(a) legacy shape, story not in flight, --apply → file gone (E4)."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
    )
    counter_path = _write_legacy_counter(project, "BUILD-022")

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert not counter_path.exists(), "stale legacy counter was not deleted"
    assert (
        "[apply] deleted stale legacy-shape attempt_counter.json "
        "(story BUILD-022, not in flight)" in output
    )


def test_to030_dryrun_reports_but_keeps_stale_legacy_counter(tmp_path: Path) -> None:
    """Dry-run prints [would] delete and writes nothing (E3)."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
    )
    counter_path = _write_legacy_counter(project, "BUILD-022")
    before = counter_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=False)

    assert exit_code == 0
    assert counter_path.read_bytes() == before
    assert (
        "[would] delete stale legacy-shape attempt_counter.json "
        "(story BUILD-022, not in flight)" in output
    )


def test_to030_apply_upgrades_in_flight_counter_via_current_stories(tmp_path: Path) -> None:
    """(b) legacy shape, story in flight via current_stories, --apply → keyed shape (E4)."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
        current_stories={"BUILD-022": {"id": "BUILD-022", "set_at": "2026-07-28T00:00:00Z"}},
    )
    counter_path = _write_legacy_counter(project, "BUILD-022", count=3)

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert counter_path.exists(), "in-flight counter was deleted"
    data = json.loads(counter_path.read_text())
    assert data == {"stories": {"BUILD-022": 3}}
    assert (
        "[apply] upgraded legacy-shape attempt_counter.json to keyed shape "
        "(story BUILD-022 in flight)" in output
    )


def test_to030_apply_upgrades_in_flight_counter_via_worktree_dir(tmp_path: Path) -> None:
    """(c) legacy shape, story in flight via .pairmode-worktrees/<id>/, --apply → keyed shape (E4)."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
    )
    (project / ".pairmode-worktrees" / "BUILD-022").mkdir(parents=True)
    counter_path = _write_legacy_counter(project, "BUILD-022", count=1)

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert counter_path.exists()
    data = json.loads(counter_path.read_text())
    assert data == {"stories": {"BUILD-022": 1}}
    assert "in flight" in output


def test_to030_keyed_counter_untouched_and_silent(tmp_path: Path) -> None:
    """(d) keyed shape already → byte-identical file, no output line (E1/E4)."""
    project = _build_030_project(
        tmp_path,
        expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS,
        effort_tracking=True,
    )
    counter_path = project / ".companion" / "attempt_counter.json"
    counter_path.write_text(
        json.dumps({"stories": {"BUILD-022": 2}}), encoding="utf-8"
    )
    before = counter_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert counter_path.read_bytes() == before
    assert "attempt_counter" not in output


# ---------------------------------------------------------------------------
# CER-127 / INFRA-319: to-030 hook-path repair block
# ---------------------------------------------------------------------------


def _write_settings_json(project: Path, hooks: dict) -> Path:
    settings_path = project / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps({"hooks": hooks}, indent=2) + "\n", encoding="utf-8"
    )
    return settings_path


def test_to030_dry_run_leaves_both_settings_files_byte_identical(
    tmp_path: Path,
) -> None:
    """B3: a dry run echoes [would] lines and writes nothing to either
    settings file."""
    project = _build_030_project(
        tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS
    )
    settings_path = _write_settings_json(
        project,
        {
            "PreToolUse": [
                {
                    "matcher": "Task|Agent|Edit|Write|Read",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "uv run python /mnt/work/flex-harness/hooks/pre_tool_use.py",
                        }
                    ],
                }
            ]
        },
    )
    before_settings = settings_path.read_bytes()
    local_path = project / ".claude" / "settings.local.json"
    assert not local_path.exists()

    exit_code, output = _invoke_030(project, apply=False)

    assert exit_code == 0
    assert "[would] repair PreToolUse/pre_tool_use.py" in output
    assert "stale pre-rename" in output
    assert settings_path.read_bytes() == before_settings
    assert not local_path.exists(), "dry run must write nothing"


def _assert_relocates_stale_hook_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    plugin_root_subpath: tuple[str, ...],
) -> None:
    """Shared body for the stale-hook-relocation cases (CER-146).

    The correct relocated command is derived entirely from a synthetic
    ``_FLEX_ROOT`` this test constructs and patches in — never from wherever
    ``pairmode_migrate.py``'s own module happens to live on disk. That keeps
    the outcome invariant to the literal name of the checkout the suite is
    physically running from (``plugin_root_subpath`` lets the caller pick a
    root that does, or does not, contain a ``flex-harness`` path segment,
    exercising both directions).

    Isolated against real host plugin state (INFRA-385): ``Path.home()`` is
    patched to an empty fixture directory so the relocation's settings-level
    registrar never sees this machine's real ``~/.claude/plugins/`` tree —
    without this, a machine with a real flex plugin install (INFRA-383) has
    the registrar skip the settings-level write entirely (INFRA-288/CER-104
    dedup guard), and the relocation this test asserts never happens.
    """
    fake_home = tmp_path / "isolated-home-infra385"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    project = _build_030_project(
        tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS
    )

    fake_plugin_root = tmp_path.joinpath(*plugin_root_subpath)
    (fake_plugin_root / "hooks").mkdir(parents=True)
    (fake_plugin_root / "hooks" / "pre_tool_use.py").write_text(
        "# stub\n", encoding="utf-8"
    )
    monkeypatch.setattr(_mod, "_FLEX_ROOT", fake_plugin_root)

    stale_marker = "stale-pre-migration-marker-7c2e91"
    settings_path = _write_settings_json(
        project,
        {
            "PreToolUse": [
                {
                    "matcher": "Task|Agent|Edit|Write|Read",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"uv run python /{stale_marker}/hooks/pre_tool_use.py",
                        }
                    ],
                }
            ]
        },
    )

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert "[apply] relocating PreToolUse/pre_tool_use.py" in output

    settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings_data.get("hooks", {}).get("PreToolUse", []) == []

    local_path = project / ".claude" / "settings.local.json"
    assert local_path.exists()
    local_data = json.loads(local_path.read_text(encoding="utf-8"))
    commands = [
        h.get("command")
        for block in local_data["hooks"]["PreToolUse"]
        for h in block.get("hooks", [])
    ]
    expected_command = f"uv run python {fake_plugin_root / 'hooks' / 'pre_tool_use.py'}"
    assert any(
        c == expected_command and stale_marker not in c for c in commands
    )


def test_to030_relocates_stale_hook_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B3: --apply removes a stale hook entry from settings.json and writes
    the correct entry to settings.local.json, through the § A registrar
    (single construction site). The expected replacement command is derived
    from a synthetic plugin root this test patches in, not from the ambient
    checkout directory the suite happens to run from (CER-146)."""
    _assert_relocates_stale_hook_command(
        tmp_path, monkeypatch, plugin_root_subpath=("synthetic-plugin-root",)
    )


def test_to030_relocates_stale_hook_command_when_plugin_root_named_flex_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B3 (CER-146): relocation still succeeds, and still targets exactly the
    resolved plugin root, when that root's own path happens to contain a
    ``flex-harness`` path segment — the outcome must be invariant to that
    literal name, not merely tolerant of its absence."""
    _assert_relocates_stale_hook_command(
        tmp_path,
        monkeypatch,
        plugin_root_subpath=("flex-harness", "checkout"),
    )


def test_to030_warns_and_keeps_entry_when_plugin_root_unresolvable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B4: when plugin_root cannot be resolved (flex not locally available
    to to-030), the block removes nothing and echoes a [WARN] line."""
    project = _build_030_project(
        tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS
    )
    settings_path = _write_settings_json(
        project,
        {
            "PreToolUse": [
                {
                    "matcher": "Task|Agent|Edit|Write|Read",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "uv run python /mnt/work/flex-harness/hooks/pre_tool_use.py",
                        }
                    ],
                }
            ]
        },
    )
    before = settings_path.read_bytes()
    monkeypatch.setattr(_mod, "_FLEX_ROOT", tmp_path / "no-such-flex-checkout")

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert "[WARN]" in output
    assert "no correct replacement command could be constructed" in output
    assert settings_path.read_bytes() == before, "nothing should be removed"
    assert not (project / ".claude" / "settings.local.json").exists()


def test_to030_hook_block_noop_on_unparseable_settings(tmp_path: Path) -> None:
    """B5: an unparseable settings.json is a silent no-op for this block —
    to-030 stays total."""
    project = _build_030_project(
        tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS
    )
    settings_path = project / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{not valid json", encoding="utf-8")
    before = settings_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert "repair" not in output
    assert "WARN" not in output
    assert settings_path.read_bytes() == before


def test_to030_hook_block_noop_on_portable_only_settings(tmp_path: Path) -> None:
    """B5: a settings.json holding only a portable (project-relative) flex
    hook entry produces no output and no write."""
    project = _build_030_project(
        tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS
    )
    settings_path = _write_settings_json(
        project,
        {
            "PreToolUse": [
                {
                    "matcher": "Task|Agent|Edit|Write|Read",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"uv run python {project}/hooks/pre_tool_use.py",
                        }
                    ],
                }
            ]
        },
    )
    before = settings_path.read_bytes()

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert "repair" not in output
    assert "relocating" not in output
    assert settings_path.read_bytes() == before


# ---------------------------------------------------------------------------
# INFRA-323: RESTART REQUIRED notice for `migrate` and `to-030`
# ---------------------------------------------------------------------------


def _invoke_anchor_to_flex(
    project_dir: Path,
    *,
    apply: bool = False,
    yes: bool = True,
    subprocess_side_effect=None,
) -> tuple[int, str]:
    """Invoke `anchor-to-flex` via the Click test runner; return (exit_code, output)."""
    from click.testing import CliRunner

    runner = CliRunner()
    args = ["anchor-to-flex", "--project-dir", str(project_dir)]
    if apply:
        args.append("--apply")
    if yes:
        args.append("--yes")

    if subprocess_side_effect is None:
        mock_result = MagicMock(returncode=0, stderr="", stdout="")
        subprocess_side_effect = lambda cmd, **kw: mock_result  # noqa: E731

    with patch("pairmode_migrate.subprocess.run", side_effect=subprocess_side_effect):
        result = runner.invoke(_mod.cli, args, catch_exceptions=False)
    return result.exit_code, result.output


def test_migrate_apply_prints_notice_when_agent_files_changed(tmp_path: Path) -> None:
    """--apply prints the RESTART REQUIRED notice naming the changed agent
    shells, as the command's final output."""
    project = _build_anchor_project(tmp_path)
    side_effect = _make_subprocess_side_effect(project, ".pre-flex-migration")

    exit_code, output = _invoke_anchor_to_flex(
        project, apply=True, subprocess_side_effect=side_effect
    )

    assert exit_code == 0, output
    assert "RESTART REQUIRED" in output
    # It is the final output — after the migration summary block.
    summary_idx = output.index("--- Migration Summary ---")
    notice_idx = output.index("RESTART REQUIRED")
    assert notice_idx > summary_idx

    state_path = project / ".companion" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state.get("agent_surfaces_written_by") == "migrate"


def test_migrate_report_only_prints_no_notice(tmp_path: Path) -> None:
    """Without --apply (report-only), no notice is printed."""
    project = _build_anchor_project(tmp_path)

    exit_code, output = _invoke_anchor_to_flex(project, apply=False)

    assert exit_code == 0, output
    assert "RESTART REQUIRED" not in output


def test_migrate_already_migrated_prints_no_notice(tmp_path: Path) -> None:
    """An already-migrated project's early return prints no notice."""
    from click.testing import CliRunner

    project = tmp_path / "clean-project"
    project.mkdir()
    (project / "CLAUDE.build.md").write_text("# Build guide\nAll clean.\n", encoding="utf-8")

    runner = CliRunner()
    mock_result = MagicMock(returncode=0, stderr="", stdout="")
    with patch("pairmode_migrate.subprocess.run", side_effect=lambda cmd, **kw: mock_result):
        result = runner.invoke(
            _mod.cli,
            ["anchor-to-flex", "--project-dir", str(project), "--apply", "--yes"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert "already migrated" in result.output.lower()
    assert "RESTART REQUIRED" not in result.output


def test_to_030_apply_prints_notice_when_agent_shell_deleted(tmp_path: Path) -> None:
    """to-030 --apply prints the notice when B7 deletes a stale agent shell."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS)
    agents_dir = project / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    content = b"# builder agent v0.2.x stale template\n"
    builder_file = agents_dir / "builder.md"
    builder_file.write_bytes(content)
    known_hash = hashlib.sha256(content).hexdigest()

    with patch.dict(_mod._ERA2_AGENT_HASHES, {"builder": known_hash}):
        exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert "RESTART REQUIRED" in output
    complete_idx = output.index("to-030 complete.")
    notice_idx = output.index("RESTART REQUIRED")
    assert notice_idx > complete_idx

    state_path = project / ".companion" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state.get("agent_surfaces_written_by") == "to-030"


def test_to_030_flag_only_agent_cleanup_prints_no_notice(tmp_path: Path) -> None:
    """to-030 --apply with only a flagged (not deleted) customised agent
    prints no notice — _ERA2_AGENT_HASHES empty by default."""
    project = _build_030_project(tmp_path, expected_step_tokens=_mod.THIN_HARNESS_STEP_TOKENS)
    agents_dir = project / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    custom_content = b"# Highly customized builder - do not delete!\n"
    (agents_dir / "builder.md").write_bytes(custom_content)

    exit_code, output = _invoke_030(project, apply=True)

    assert exit_code == 0
    assert "RESTART REQUIRED" not in output

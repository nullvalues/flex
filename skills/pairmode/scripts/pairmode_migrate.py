"""
pairmode_migrate.py — Substitution engine for migrating anchor-named projects to flex.

Applies a per-file rule table of regex substitutions and subprocess invocations
to rename all "anchor" project-name references to "flex".

CLI:
    uv run python skills/pairmode/scripts/pairmode_migrate.py \\
        --project-dir PATH [--apply] [--yes] [--migrate-lessons] \\
        [--backup-suffix SUFFIX]

Default mode is dry-run (no --apply). Prints the same human-readable summary
that --apply produces, except no files are written and no backups are created.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import click

# ---------------------------------------------------------------------------
# Path constants — relative to this script's location
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent        # skills/pairmode/scripts/
_FLEX_ROOT   = _SCRIPTS_DIR.parent.parent.parent      # flex repo root
_PAIRMODE_SYNC = _SCRIPTS_DIR / "pairmode_sync.py"

# ---------------------------------------------------------------------------
# Idempotency gate patterns
# ---------------------------------------------------------------------------

# 7 gates: each is a compiled regex that, when it MATCHES, means "not yet migrated"
_GATES: list[tuple[str, re.Pattern[str]]] = [
    ("No /anchor: slash refs",          re.compile(r"/anchor:", re.IGNORECASE)),
    ("No _ANCHOR_ROOT identifiers",     re.compile(r"\b_ANCHOR_ROOT\b")),
    ("No /mnt/work/anchor paths",       re.compile(r"/mnt/work/anchor\b")),
    ("No ~/.anchor/ or $HOME/.anchor/ refs", re.compile(r"(~|\\$HOME)/\.anchor/")),
    ("No ANCHOR_PROJECT_DIR/HASH env vars",  re.compile(r"\bANCHOR_PROJECT_(DIR|HASH)\b")),
    ("No anchor:pairmode or Anchor Methodology Lessons", re.compile(r"anchor:pairmode|Anchor Methodology Lessons")),
    ("No remaining anchor/Anchor/ANCHOR project-name prose", re.compile(r"\banchor\b|\bAnchor\b|\bANCHOR\b")),
]

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MigrationRule:
    """Describes a single migration rule in MIGRATION_RULES."""

    rule_id: int
    description: str
    strategy: str   # "subprocess" | "regex" | "conditional" | "bypass" | "regenerate"
    # For regex rules: list of (pattern, replacement) pairs
    patterns: list[tuple[str, str]] = field(default_factory=list)
    # For conditional/bypass rules: optional handler key
    handler: str = ""
    # Gate flag — if True this rule is only applied when --migrate-lessons is set
    lessons_gated: bool = False


@dataclass
class MigrationReport:
    """Result of a migrate() call."""

    changed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    backups: list[str] = field(default_factory=list)
    gate_results: list[tuple[str, bool]] = field(default_factory=list)
    already_migrated: bool = False
    pairmode_version_old: Optional[str] = None
    pairmode_version_new: Optional[str] = None


# ---------------------------------------------------------------------------
# Migration rule table
# ---------------------------------------------------------------------------

MIGRATION_RULES: list[MigrationRule] = [
    # 1 — CLAUDE.build.md: delegate to pairmode_sync sync-build
    MigrationRule(
        rule_id=1,
        description="CLAUDE.build.md — sync-build",
        strategy="subprocess",
        handler="sync-build",
    ),
    # 2 — .claude/agents/*.md frontmatter: delegate to pairmode_sync sync-agents
    MigrationRule(
        rule_id=2,
        description=".claude/agents/*.md frontmatter — sync-agents",
        strategy="subprocess",
        handler="sync-agents",
    ),
    # 3 — .claude/agents/*.md body: regex substitution
    MigrationRule(
        rule_id=3,
        description=".claude/agents/*.md body — regex substitution",
        strategy="regex",
        patterns=[
            (r"anchor project", "flex project"),
            (r"\$HOME/\.anchor/", "$HOME/.flex/"),
            (r"~/\.anchor/", "~/.flex/"),
            (r"/anchor:", "/flex:"),
        ],
    ),
    # 4 — hooks/*.py: regex substitution
    MigrationRule(
        rule_id=4,
        description="hooks/*.py — regex substitution",
        strategy="regex",
        patterns=[
            (r"\bANCHOR_PROJECT_DIR\b", "FLEX_PROJECT_DIR"),
            (r"\bANCHOR_PROJECT_HASH\b", "FLEX_PROJECT_HASH"),
            (r"/tmp/anchor_project_dir\b", "/tmp/flex_project_dir"),
            (r"\banchor_root\b", "repo_root"),
        ],
    ),
    # 5 — skills/companion/scripts/launch_sidebar.sh and .command
    MigrationRule(
        rule_id=5,
        description="skills/companion/scripts/launch_sidebar.sh/.command — regex substitution",
        strategy="regex",
        patterns=[
            (r"\bANCHOR_PROJECT_DIR\b", "FLEX_PROJECT_DIR"),
            (r"\bANCHOR_PROJECT_HASH\b", "FLEX_PROJECT_HASH"),
            (r"/tmp/anchor_project_dir\b", "/tmp/flex_project_dir"),
            (r"\banchor_root\b", "repo_root"),
            (r"\$HOME/\.anchor/", "$HOME/.flex/"),
            (r"~/\.anchor/", "~/.flex/"),
        ],
    ),
    # 6 — skills/companion/scripts/start_sidebar.sh
    MigrationRule(
        rule_id=6,
        description="skills/companion/scripts/start_sidebar.sh — regex substitution",
        strategy="regex",
        patterns=[
            (r"\bANCHOR_PROJECT_DIR\b", "FLEX_PROJECT_DIR"),
            (r"\bANCHOR_PROJECT_HASH\b", "FLEX_PROJECT_HASH"),
            (r"/tmp/anchor_project_dir\b", "/tmp/flex_project_dir"),
            (r"\banchor_root\b", "repo_root"),
            (r"\$HOME/\.anchor/", "$HOME/.flex/"),
            (r"~/\.anchor/", "~/.flex/"),
        ],
    ),
    # 7 — skills/companion/scripts/sidebar.py
    MigrationRule(
        rule_id=7,
        description="skills/companion/scripts/sidebar.py — regex substitution",
        strategy="regex",
        patterns=[
            (r"\b_ANCHOR_ROOT\b", "_REPO_ROOT"),
            (r"\[bold\]anchor\[/bold\]", "[bold]flex[/bold]"),
            (r"\[bold #d75f00\]Anchor\b", "[bold #d75f00]Flex"),
            (r"/anchor:companion\b", "/flex:companion"),
        ],
    ),
    # 8 — skills/seed/SKILL.md
    MigrationRule(
        rule_id=8,
        description="skills/seed/SKILL.md — regex substitution",
        strategy="regex",
        patterns=[
            (r"\bname:\s*anchor:seed\b", "name: flex:seed"),
            (r"/anchor:seed\b", "/flex:seed"),
        ],
    ),
    # 9 — skills/pairmode/SKILL.md
    MigrationRule(
        rule_id=9,
        description="skills/pairmode/SKILL.md — regex substitution",
        strategy="regex",
        patterns=[
            (r"/anchor:pairmode\b", "/flex:pairmode"),
        ],
    ),
    # 10 — skills/companion/SKILL.md
    MigrationRule(
        rule_id=10,
        description="skills/companion/SKILL.md — regex substitution",
        strategy="regex",
        patterns=[
            (r"/anchor:companion\b", "/flex:companion"),
        ],
    ),
    # 11 — skills/pairmode/scripts/*.py
    MigrationRule(
        rule_id=11,
        description="skills/pairmode/scripts/*.py — regex substitution",
        strategy="regex",
        patterns=[
            (r"\b_ANCHOR_ROOT\b", "_REPO_ROOT"),
            (r'"anchor repo root"', '"repo root"'),
            (r"'anchor repo root'", "'repo root'"),
        ],
    ),
    # 12 — .claude/settings.deny-rationale.json
    MigrationRule(
        rule_id=12,
        description=".claude/settings.deny-rationale.json — regex substitution",
        strategy="regex",
        patterns=[
            (r'"generated_by":\s*"anchor:pairmode"', '"generated_by": "flex:pairmode"'),
            (r'"anchor intercepts"', '"flex intercepts"'),
        ],
    ),
    # 13 — .companion/state.json: conditional key-update
    MigrationRule(
        rule_id=13,
        description=".companion/state.json — conditional key-update",
        strategy="conditional",
        handler="state_json",
    ),
    # 14 — lessons/lessons.json: one-time bypass (gated on --migrate-lessons)
    MigrationRule(
        rule_id=14,
        description="lessons/lessons.json — one-time bypass",
        strategy="bypass",
        handler="lessons_json",
        lessons_gated=True,
    ),
    # 15 — lessons/LESSONS.md: regenerate (gated on --migrate-lessons)
    MigrationRule(
        rule_id=15,
        description="lessons/LESSONS.md — regenerate",
        strategy="regenerate",
        handler="lessons_md",
        lessons_gated=True,
    ),
]

# ---------------------------------------------------------------------------
# File resolver: map a rule to target file paths within a given project_dir
# ---------------------------------------------------------------------------


def _resolve_targets(rule: MigrationRule, project_dir: Path) -> list[Path]:
    """Return the list of target files in *project_dir* for the given rule."""
    rid = rule.rule_id

    if rid == 1:
        return [project_dir / "CLAUDE.build.md"]
    if rid == 2:
        agents_dir = project_dir / ".claude" / "agents"
        if agents_dir.is_dir():
            return sorted(agents_dir.glob("*.md"))
        return []
    if rid == 3:
        agents_dir = project_dir / ".claude" / "agents"
        if agents_dir.is_dir():
            return sorted(agents_dir.glob("*.md"))
        return []
    if rid == 4:
        hooks_dir = project_dir / "hooks"
        if hooks_dir.is_dir():
            return sorted(hooks_dir.glob("*.py"))
        return []
    if rid == 5:
        scripts_dir = project_dir / "skills" / "companion" / "scripts"
        targets = []
        for name in ("launch_sidebar.sh", "launch_sidebar.command"):
            p = scripts_dir / name
            if p.exists():
                targets.append(p)
        return targets
    if rid == 6:
        p = project_dir / "skills" / "companion" / "scripts" / "start_sidebar.sh"
        return [p] if p.exists() else []
    if rid == 7:
        p = project_dir / "skills" / "companion" / "scripts" / "sidebar.py"
        return [p] if p.exists() else []
    if rid == 8:
        p = project_dir / "skills" / "seed" / "SKILL.md"
        return [p] if p.exists() else []
    if rid == 9:
        p = project_dir / "skills" / "pairmode" / "SKILL.md"
        return [p] if p.exists() else []
    if rid == 10:
        p = project_dir / "skills" / "companion" / "SKILL.md"
        return [p] if p.exists() else []
    if rid == 11:
        scripts_dir = project_dir / "skills" / "pairmode" / "scripts"
        if scripts_dir.is_dir():
            return sorted(scripts_dir.glob("*.py"))
        return []
    if rid == 12:
        p = project_dir / ".claude" / "settings.deny-rationale.json"
        return [p] if p.exists() else []
    if rid == 13:
        p = project_dir / ".companion" / "state.json"
        return [p] if p.exists() else []
    if rid == 14:
        p = project_dir / "lessons" / "lessons.json"
        return [p] if p.exists() else []
    if rid == 15:
        p = project_dir / "lessons" / "LESSONS.md"
        # Always return the target path; we will create it even if it doesn't exist
        return [p]

    return []


# ---------------------------------------------------------------------------
# Backup-suffix validation
# ---------------------------------------------------------------------------


def _validate_backup_suffix(suffix: str) -> None:
    """Reject backup suffixes containing '/' or '..'.

    Raises SystemExit(1) for suffixes that could cause path traversal when
    appended to a file path (e.g. "/tmp/evil" or "../etc/cron").
    """
    if "/" in suffix or ".." in suffix:
        click.echo(
            f"error: --backup-suffix must be a leaf string (no '/' or '..'): {suffix!r}",
            err=True,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Depth guard
# ---------------------------------------------------------------------------


def _depth_guard(project_dir: Path) -> None:
    """Reject project_dir paths with fewer than 3 components.

    Raises SystemExit(1) for suspiciously shallow paths to prevent accidental
    runs against filesystem roots.
    """
    if len(project_dir.parts) < 3:
        click.echo(
            f"error: --project-dir resolves to a suspicious path: {project_dir}\n"
            "       Refusing to operate on paths with fewer than 3 components.",
            err=True,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Idempotency check
# ---------------------------------------------------------------------------


def _run_gates(project_dir: Path) -> list[tuple[str, bool]]:
    """Scan *project_dir* for anchor-name evidence.

    Returns a list of (gate_name, clean) tuples.
    clean=True means the gate passed (no evidence found).
    clean=False means anchor-name evidence was found for that gate.
    """
    # Collect all text files under the project dir (skip .git)
    text_content = _collect_project_text(project_dir)

    results: list[tuple[str, bool]] = []
    for name, pattern in _GATES:
        found = pattern.search(text_content)
        results.append((name, not bool(found)))
    return results


def _collect_project_text(project_dir: Path) -> str:
    """Return concatenated text content of all tracked text files in *project_dir*.

    Skips binary files, .git directory, and __pycache__.
    """
    lines: list[str] = []
    skip_dirs = {".git", "__pycache__", ".companion", "node_modules", ".venv"}
    for p in sorted(project_dir.rglob("*")):
        if any(part in skip_dirs for part in p.parts):
            continue
        if not p.is_file():
            continue
        try:
            lines.append(p.read_text(encoding="utf-8", errors="replace"))
        except (OSError, PermissionError):
            pass
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rule application helpers
# ---------------------------------------------------------------------------


def _apply_regex_rule(
    rule: MigrationRule,
    target: Path,
    backup_suffix: str,
    apply: bool,
    report: MigrationReport,
) -> None:
    """Apply a regex substitution rule to *target*."""
    if not target.exists():
        report.missing.append(str(target))
        return

    original = target.read_text(encoding="utf-8")
    modified = original
    for pattern_str, replacement in rule.patterns:
        modified = re.sub(pattern_str, replacement, modified)

    if modified == original:
        report.skipped.append(str(target))
        return

    if apply:
        backup_path = Path(str(target) + backup_suffix)
        backup_path.write_text(original, encoding="utf-8")
        report.backups.append(str(backup_path))
        target.write_text(modified, encoding="utf-8")

    report.changed.append(str(target))


def _apply_subprocess_rule(
    rule: MigrationRule,
    project_dir: Path,
    apply: bool,
    report: MigrationReport,
) -> None:
    """Apply a subprocess rule (sync-build or sync-agents)."""
    handler = rule.handler
    if handler == "sync-build":
        target = project_dir / "CLAUDE.build.md"
        if not target.exists():
            report.missing.append(str(target))
            return
        if not apply:
            click.echo(
                f"  [dry-run] would invoke: pairmode_sync sync-build --apply --yes "
                f"--project-dir {project_dir}"
            )
            report.changed.append(str(target) + " (subprocess dry-run)")
            return
        cmd = [
            "uv", "run", "python", str(_PAIRMODE_SYNC),
            "sync-build",
            "--project-dir", str(project_dir),
            "--apply",
            "--yes",
        ]
        result = subprocess.run(cmd, cwd=str(_FLEX_ROOT), capture_output=True, text=True)
        if result.returncode == 0:
            report.changed.append(str(target))
        else:
            click.echo(f"  warning: sync-build failed: {result.stderr.strip()}", err=True)
            report.skipped.append(str(target))

    elif handler == "sync-agents":
        agents_dir = project_dir / ".claude" / "agents"
        if not agents_dir.is_dir():
            report.missing.append(str(agents_dir))
            return
        if not apply:
            click.echo(
                f"  [dry-run] would invoke: pairmode_sync sync-agents --apply --yes "
                f"--project-dir {project_dir}"
            )
            for md_file in sorted(agents_dir.glob("*.md")):
                report.changed.append(str(md_file) + " (subprocess dry-run)")
            return
        cmd = [
            "uv", "run", "python", str(_PAIRMODE_SYNC),
            "sync-agents",
            "--project-dir", str(project_dir),
            "--yes",
        ]
        result = subprocess.run(cmd, cwd=str(_FLEX_ROOT), capture_output=True, text=True)
        if result.returncode == 0:
            for md_file in sorted(agents_dir.glob("*.md")):
                report.changed.append(str(md_file))
        else:
            click.echo(f"  warning: sync-agents failed: {result.stderr.strip()}", err=True)
            for md_file in sorted(agents_dir.glob("*.md")):
                report.skipped.append(str(md_file))


def _apply_conditional_rule(
    rule: MigrationRule,
    target: Path,
    backup_suffix: str,
    apply: bool,
    report: MigrationReport,
    new_pairmode_version: str = "0.2.0",
) -> None:
    """Apply conditional key-update to state.json."""
    if not target.exists():
        report.missing.append(str(target))
        return

    try:
        state = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"  warning: could not read {target}: {exc}", err=True)
        report.skipped.append(str(target))
        return

    modified = False
    original_text = json.dumps(state, indent=2) + "\n"

    # pairmode_version: "anchor-*" → "0.2.0"
    pv = state.get("pairmode_version", "")
    if isinstance(pv, str) and pv.startswith("anchor-"):
        report.pairmode_version_old = pv
        report.pairmode_version_new = new_pairmode_version
        state["pairmode_version"] = new_pairmode_version
        modified = True

    # project_name: "anchor" → "flex"
    pn = state.get("project_name", "")
    if isinstance(pn, str) and pn == "anchor":
        state["project_name"] = "flex"
        modified = True

    if not modified:
        report.skipped.append(str(target))
        return

    new_text = json.dumps(state, indent=2) + "\n"
    if apply:
        backup_path = Path(str(target) + backup_suffix)
        backup_path.write_text(original_text, encoding="utf-8")
        report.backups.append(str(backup_path))
        target.write_text(new_text, encoding="utf-8")

    report.changed.append(str(target))


def _apply_bypass_rule(
    rule: MigrationRule,
    target: Path,
    backup_suffix: str,
    apply: bool,
    report: MigrationReport,
) -> None:
    """Apply a one-time bypass to lessons.json (anchor→flex rename in content)."""
    if not target.exists():
        report.missing.append(str(target))
        return

    original_text = target.read_text(encoding="utf-8")
    try:
        data = json.loads(original_text)
    except json.JSONDecodeError as exc:
        click.echo(f"  warning: could not parse {target}: {exc}", err=True)
        report.skipped.append(str(target))
        return

    # Rewrite JSON as text with anchor→flex substitutions
    serialised = json.dumps(data, indent=2) + "\n"
    new_text = _substitute_anchor_to_flex(serialised)

    if new_text == serialised:
        report.skipped.append(str(target))
        return

    if apply:
        backup_path = Path(str(target) + backup_suffix)
        backup_path.write_text(original_text, encoding="utf-8")
        report.backups.append(str(backup_path))
        target.write_text(new_text, encoding="utf-8")

    report.changed.append(str(target))


def _substitute_anchor_to_flex(text: str) -> str:
    """Apply the canonical anchor→flex rename substitutions to *text*."""
    text = re.sub(r"\banchor:pairmode\b", "flex:pairmode", text)
    text = re.sub(r"\bAnchor Methodology Lessons\b", "Flex Methodology Lessons", text)
    text = re.sub(r"\banchor repo root\b", "repo root", text)
    text = re.sub(r"\bAnchor Methodology\b", "Flex Methodology", text)
    return text


def _apply_regenerate_rule(
    rule: MigrationRule,
    target: Path,
    apply: bool,
    report: MigrationReport,
    lessons_file: Path,
) -> None:
    """Regenerate LESSONS.md from lessons.json using lesson_utils."""
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        import lesson_utils  # noqa: PLC0415
    except ImportError as exc:
        click.echo(f"  warning: could not import lesson_utils: {exc}", err=True)
        report.skipped.append(str(target))
        return

    if not lessons_file.exists():
        report.missing.append(str(target))
        return

    try:
        data = json.loads(lessons_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"  warning: could not read {lessons_file}: {exc}", err=True)
        report.skipped.append(str(target))
        return

    new_content = lesson_utils.generate_lessons_md(data)

    old_content = target.read_text(encoding="utf-8") if target.exists() else ""
    if new_content == old_content:
        report.skipped.append(str(target))
        return

    if apply:
        target.write_text(new_content, encoding="utf-8")

    report.changed.append(str(target))


# ---------------------------------------------------------------------------
# Main migrate() function
# ---------------------------------------------------------------------------


def migrate(
    project_dir: Path,
    *,
    apply: bool,
    yes: bool,
    migrate_lessons: bool,
    backup_suffix: str = ".pre-flex-migration",
) -> MigrationReport:
    """Run the migration against *project_dir*.

    Parameters
    ----------
    project_dir:
        Root of the project to migrate. Must resolve to a path with ≥ 3 components.
    apply:
        When False (default), dry-run mode: prints what would change but writes nothing.
    yes:
        When True, skip the [y/N] confirmation prompt (only relevant when apply=True).
    migrate_lessons:
        When True, apply rules 14 (lessons.json bypass) and 15 (LESSONS.md regenerate).
    backup_suffix:
        Suffix appended to each file before modification (e.g. ".pre-flex-migration").

    Returns
    -------
    MigrationReport
        Summary of what changed, what was skipped, what was missing, etc.
    """
    _depth_guard(project_dir)

    # --- Sentinel-file check (apply mode only) ---
    # Checked before the idempotency gate so that apply on a non-project dir always
    # fails fast, even when the dir has no anchor refs (which would otherwise trigger
    # an early "already migrated" return and mask the invalid path).
    if apply:
        sentinels = [
            project_dir / "CLAUDE.build.md",
            project_dir / ".companion",
            project_dir / ".claude" / "agents",
        ]
        if not any(s.exists() for s in sentinels):
            click.echo(
                "error: --project-dir does not look like a flex/anchor-bootstrapped project\n"
                "       (expected at least one of: CLAUDE.build.md, .companion/, .claude/agents/)\n"
                "       Re-run without --apply to preview what would change, or verify the path.",
                err=True,
            )
            sys.exit(1)

    report = MigrationReport()

    # --- Idempotency check ---
    gate_results = _run_gates(project_dir)
    report.gate_results = gate_results
    all_clean = all(clean for _, clean in gate_results)
    if all_clean:
        report.already_migrated = True
        return report

    # --- Confirmation ---
    if apply and not yes:
        click.echo(
            f"\nAbout to migrate project at: {project_dir}\n"
            "This will rewrite files in-place (backups will be created).\n"
        )
        confirmed = click.confirm("Proceed? [y/N]", default=False, prompt_suffix="")
        if not confirmed:
            click.echo("Aborted.")
            sys.exit(0)

    mode_label = "apply" if apply else "dry-run"
    click.echo(f"\n=== pairmode_migrate ({mode_label}) ===\n")

    for rule in MIGRATION_RULES:
        # Skip lessons-gated rules if --migrate-lessons not set
        if rule.lessons_gated and not migrate_lessons:
            continue

        click.echo(f"Rule {rule.rule_id}: {rule.description}")

        if rule.strategy == "subprocess":
            _apply_subprocess_rule(rule, project_dir, apply, report)

        elif rule.strategy == "regex":
            targets = _resolve_targets(rule, project_dir)
            for target in targets:
                _apply_regex_rule(rule, target, backup_suffix, apply, report)

        elif rule.strategy == "conditional":
            targets = _resolve_targets(rule, project_dir)
            for target in targets:
                _apply_conditional_rule(rule, target, backup_suffix, apply, report)

        elif rule.strategy == "bypass":
            targets = _resolve_targets(rule, project_dir)
            for target in targets:
                _apply_bypass_rule(rule, target, backup_suffix, apply, report)

        elif rule.strategy == "regenerate":
            targets = _resolve_targets(rule, project_dir)
            lessons_file = project_dir / "lessons" / "lessons.json"
            for target in targets:
                _apply_regenerate_rule(rule, target, apply, report, lessons_file)

    return report


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------


def _print_report(report: MigrationReport, apply: bool) -> None:
    """Print a human-readable summary of *report*."""
    if report.already_migrated:
        click.echo("Project is already migrated — no anchor-name references found.")
        return

    mode = "Applied" if apply else "Would change"
    click.echo(f"\n--- Migration Summary ---")
    click.echo(f"{mode}: {len(report.changed)} file(s)")
    click.echo(f"Skipped (no change): {len(report.skipped)} file(s)")
    click.echo(f"Missing: {len(report.missing)} file(s)")
    if apply and report.backups:
        click.echo(f"Backups created: {len(report.backups)}")

    if report.pairmode_version_old:
        click.echo(
            f"pairmode_version: {report.pairmode_version_old!r} → "
            f"{report.pairmode_version_new!r}"
        )

    if report.changed:
        click.echo("\nChanged files:")
        for f in report.changed:
            click.echo(f"  + {f}")

    if report.missing:
        click.echo("\nMissing files (skipped):")
        for f in report.missing:
            click.echo(f"  - {f}")

    # Gate results
    click.echo("\nIdempotency gate results:")
    for name, clean in report.gate_results:
        status = "CLEAN" if clean else "DIRTY"
        click.echo(f"  [{status}] {name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("pairmode-migrate")
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Root of the project to migrate.",
)
@click.option(
    "--apply",
    "do_apply",
    is_flag=True,
    default=False,
    help="Actually write changes. Default is dry-run.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip [y/N] confirmation when --apply is set.",
)
@click.option(
    "--migrate-lessons",
    is_flag=True,
    default=False,
    help="Also migrate lessons/lessons.json and regenerate lessons/LESSONS.md.",
)
@click.option(
    "--backup-suffix",
    default=".pre-flex-migration",
    show_default=True,
    help="Suffix appended to each file before modification.",
)
def cli(
    project_dir: str,
    do_apply: bool,
    yes: bool,
    migrate_lessons: bool,
    backup_suffix: str,
) -> None:
    """Migrate an anchor-named project to flex naming.

    Dry-run by default — pass --apply to write changes.
    """
    _validate_backup_suffix(backup_suffix)
    project_path = Path(project_dir).resolve()
    report = migrate(
        project_path,
        apply=do_apply,
        yes=yes,
        migrate_lessons=migrate_lessons,
        backup_suffix=backup_suffix,
    )
    _print_report(report, apply=do_apply)


if __name__ == "__main__":
    cli()

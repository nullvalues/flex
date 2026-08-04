"""
Tests for INFRA-375 (CER-160): audit hardcoded flex-harness absolute paths for
release-channel staleness risk.

A hardcoded `/mnt/work/flex-harness`-absolute path resolves into the release
channel (docs/architecture.md § Release channel — flex-harness), which only
advances at checkpoint-tag. A worker that resolves such a path mid-phase is
therefore running last-checkpoint's copy of whatever it points at, by
construction — this reproduced live in INFRA-362's Phase 118 dogfood exercise,
where a spec-writer instructed to use the absolute harness path found a stale,
pre-checkpoint-promotion copy of its own procedure while the correct in-tree
copy (already updated in the same phase) sat right there in the working tree.

This test file is the audit inventory the story owes (INFRA-375 Ensures 1):
every literal `/mnt/work/flex-harness` reference on the scan surface below is
either fixed out of existence (an in-tree-preferring pointer paragraph, for
the nine agent templates and their rendered `.claude/agents/*.md` shells) or
recorded here with a one-line rationale for why it legitimately survives.

Scan surface: `.claude/agents/`, `skills/`, `hooks/`, and root-level
`CLAUDE.md` / `CLAUDE.build.md` — excluding `docs/`, `CHANGELOG.md`, `tests/`,
`node_modules/`, `.git/`.
"""
from pathlib import Path

import pytest


# Root of the project — two parents up from tests/pairmode/
REPO_ROOT = Path(__file__).parent.parent.parent

NEEDLE = "/mnt/work/flex-harness"

# Directories/files that make up the scan surface (INFRA-375 Ensures 2).
SCAN_ROOTS = [
    REPO_ROOT / ".claude" / "agents",
    REPO_ROOT / "skills",
    REPO_ROOT / "hooks",
]
SCAN_FILES = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "CLAUDE.build.md",
]

# Directories excluded even if nested under a scanned root.
EXCLUDED_DIR_NAMES = {"docs", "tests", "node_modules", ".git"}
EXCLUDED_FILE_NAMES = {"CHANGELOG.md"}

# The audit inventory. Every repo-relative path (POSIX-style, relative to
# REPO_ROOT) that legitimately contains the literal NEEDLE must be listed
# here with a non-empty one-line rationale (INFRA-375 Ensures 1).
ALLOWLIST = {
    # --- rendered agent shells: fallback branch for a bootstrapped consuming
    # project that has not vendored skills/pairmode/ in-tree (INFRA-304 E13).
    # The in-tree branch (checked first) fires here since flex vendors its
    # own skills/pairmode/, so this literal is dead code in this repo but
    # load-bearing for every downstream fleet consumer — fixed disposition,
    # not staleness risk (CER-160).
    ".claude/agents/builder.md": (
        "fixed: in-tree-preferring pointer's fallback branch for a "
        "bootstrapped consumer with no vendored skills/pairmode/ (INFRA-304 "
        "E13); the in-tree branch wins in this repo (CER-160)."
    ),
    ".claude/agents/reviewer.md": (
        "fixed: in-tree-preferring pointer's fallback branch for a "
        "bootstrapped consumer with no vendored skills/pairmode/ (INFRA-304 "
        "E13); the in-tree branch wins in this repo (CER-160)."
    ),
    ".claude/agents/spec-writer.md": (
        "fixed: in-tree-preferring pointer's fallback branch for a "
        "bootstrapped consumer with no vendored skills/pairmode/ (INFRA-304 "
        "E13); the in-tree branch wins in this repo (CER-160)."
    ),
    ".claude/agents/docs-reviewer.md": (
        "fixed: in-tree-preferring pointer's fallback branch for a "
        "bootstrapped consumer with no vendored skills/pairmode/ (INFRA-304 "
        "E13); the in-tree branch wins in this repo (CER-160)."
    ),
    ".claude/agents/gate-worker.md": (
        "fixed: in-tree-preferring pointer's fallback branch for a "
        "bootstrapped consumer with no vendored skills/pairmode/ (INFRA-304 "
        "E13); the in-tree branch wins in this repo (CER-160)."
    ),
    ".claude/agents/intent-reviewer.md": (
        "fixed: in-tree-preferring pointer's fallback branch for a "
        "bootstrapped consumer with no vendored skills/pairmode/ (INFRA-304 "
        "E13); the in-tree branch wins in this repo (CER-160)."
    ),
    ".claude/agents/loop-breaker.md": (
        "fixed: in-tree-preferring pointer's fallback branch for a "
        "bootstrapped consumer with no vendored skills/pairmode/ (INFRA-304 "
        "E13); the in-tree branch wins in this repo (CER-160)."
    ),
    ".claude/agents/security-auditor.md": (
        "fixed: in-tree-preferring pointer's fallback branch for a "
        "bootstrapped consumer with no vendored skills/pairmode/ (INFRA-304 "
        "E13); the in-tree branch wins in this repo (CER-160)."
    ),
    # --- not-a-path: docstring/comment literals quoting the string as an
    # example of what a detector matches; no runtime path resolution happens.
    "skills/pairmode/scripts/hook_view.py": (
        "not-a-path: docstring example of the pre-rename "
        "/mnt/work/flex-harness/hooks/* shape a classifier matches against; "
        "no runtime resolution."
    ),
    "skills/pairmode/scripts/fleet_discovery.py": (
        "not-a-path: docstring examples of the pre-rename hooks/* shape and "
        "a 0.3.0 checkout name a detector matches against; no runtime "
        "resolution."
    ),
    "skills/pairmode/scripts/pairmode_migrate.py": (
        "not-a-path: comment quoting the pre-rename hooks/* command shape a "
        "0.2.x -> 0.3.0 migration classifier matches against; no runtime "
        "resolution."
    ),
    # --- pinned-by-design: CLAUDE.build.md's flex_build.py script
    # invocations are deliberately pinned to the release channel so the
    # orchestrator's build loop always runs a checkpoint-gated toolchain,
    # never mid-phase, ungated edits to itself (docs/architecture.md §
    # Release channel — flex-harness). Byte-unchanged by this story
    # (INFRA-375 Ensures 6) — this is the opposite disposition from the
    # procedure/skill docs fixed above, on purpose.
    "CLAUDE.build.md": (
        "pinned-by-design: flex_build.py script invocations stay pinned to "
        "the release channel on purpose, unlike procedure/skill docs "
        "(CER-160; docs/architecture.md § Release channel — flex-harness)."
    ),
}


def _scan_surface_matches():
    """Walk the scan surface and return the set of repo-relative POSIX paths
    (relative to REPO_ROOT) whose contents contain the literal NEEDLE."""
    matches = set()

    def _is_excluded(path: Path) -> bool:
        for part in path.relative_to(REPO_ROOT).parts:
            if part in EXCLUDED_DIR_NAMES:
                return True
        if path.name in EXCLUDED_FILE_NAMES:
            return True
        return False

    candidates = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                candidates.append(path)
    for path in SCAN_FILES:
        if path.exists():
            candidates.append(path)

    for path in candidates:
        if _is_excluded(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if NEEDLE in text:
            matches.add(path.relative_to(REPO_ROOT).as_posix())

    return matches


def test_allowlist_entries_have_nonempty_rationale():
    assert ALLOWLIST, "allowlist must not be empty"
    for rel_path, rationale in ALLOWLIST.items():
        assert isinstance(rationale, str) and rationale.strip(), (
            f"{rel_path}: allowlist rationale must be a non-empty one-line "
            "string"
        )


def test_scan_surface_matches_allowlist_exactly():
    found = _scan_surface_matches()
    allowed = set(ALLOWLIST.keys())

    unlisted = found - allowed
    stale = allowed - found

    assert not unlisted, (
        "found /mnt/work/flex-harness reference(s) not in the allowlist "
        f"(add with rationale or fix): {sorted(unlisted)}"
    )
    assert not stale, (
        "allowlist entries no longer match any scanned file (remove stale "
        f"entries): {sorted(stale)}"
    )


def test_rendered_agent_shells_carry_absolute_fallback():
    """No rendered shell under .claude/agents/ still carries the
    pre-INFRA-304 bare-relative pointer with no absolute fallback
    (INFRA-375 Ensures 4)."""
    agents_dir = REPO_ROOT / ".claude" / "agents"
    missing_fallback = []
    for path in sorted(agents_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if NEEDLE not in text:
            missing_fallback.append(path.name)

    assert missing_fallback == ["reconstruction-agent.md"], (
        "expected exactly reconstruction-agent.md to lack the "
        f"/mnt/work/flex-harness fallback pointer, got: {missing_fallback}"
    )

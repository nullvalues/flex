"""
Tests for INFRA-375 (CER-160): audit hardcoded flex-harness absolute paths for
release-channel staleness risk.

A hardcoded `/mnt/work/flex-harness`-absolute path resolved into the release
channel (formerly docs/architecture.md § Release channel — flex-harness,
retired Phase 145 / INFRA-441 in favor of § Self-reference decoupling —
marketplace install), which only advanced at checkpoint-tag. A worker that
resolved such a path mid-phase was therefore running last-checkpoint's copy of
whatever it points at, by construction — this reproduced live in INFRA-362's
Phase 118 dogfood exercise, where a spec-writer instructed to use the absolute
harness path found a stale, pre-checkpoint-promotion copy of its own procedure
while the correct in-tree copy (already updated in the same phase) sat right
there in the working tree. This inventory is retained as a historical/audit record. As of Phase 145
(INFRA-440/441), `/mnt/work/flex-harness` no longer exists on disk at all —
the release-channel worktree was folded into main and removed — so every
remaining literal `flex-harness` reference on the scan surface is now
either a not-a-path docstring example (pre-rename hook-path shapes,
unrelated to this audit) or genuinely stale and should be fixed, not
allowlisted. The nine rendered agent shells' absolute fallback pointer was
repointed at the marketplace-cache install path
(`test_rendered_agent_shells_carry_absolute_fallback`, below) rather than
removed outright — the in-tree-preferring pointer still needs *some*
absolute fallback for a bootstrapped consuming project with no vendored
`skills/pairmode/` (INFRA-304 E13); it just no longer resolves through the
retired release channel.

This test file is the audit inventory the story owes (INFRA-375 Ensures 1):
every literal `/mnt/work/flex-harness` reference on the scan surface below is
either fixed out of existence or recorded here with a one-line rationale for
why it legitimately survives.

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
    # NOTE (Phase 145 / INFRA-441): CLAUDE.build.md's flex_build.py script
    # invocations were repointed from the flex-harness release-channel
    # worktree to the marketplace-cache install
    # (~/flex-marketplace-cache/flex-0.3.1/skills/pairmode/scripts); the
    # NEEDLE this file scans for no longer appears there, so the
    # "pinned-by-design" allowlist entry that previously lived here is
    # removed as stale, not because pinning-by-design stopped applying —
    # `pairmode_scripts_dir` is still deliberately pinned, just to a
    # different mechanism (docs/architecture.md § Self-reference decoupling
    # — marketplace install).
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


def _current_pairmode_scripts_dir() -> str:
    """Read the live pairmode_scripts_dir value out of CLAUDE.build.md.

    Reading it live (rather than hardcoding the marketplace-cache path)
    keeps this test from going stale the next time pairmode_scripts_dir
    moves (e.g. the Phase 7 version-keyed install cutover) — the same
    class of drift this test exists to catch (INFRA-375/CER-160), applied
    to itself.
    """
    text = (REPO_ROOT / "CLAUDE.build.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("pairmode_scripts_dir"):
            return line.split("=", 1)[1].strip()
    raise AssertionError("CLAUDE.build.md has no pairmode_scripts_dir line")


def test_rendered_agent_shells_carry_absolute_fallback():
    """No rendered shell under .claude/agents/ still carries the
    pre-INFRA-304 bare-relative pointer with no absolute fallback
    (INFRA-375 Ensures 4). Post-Phase-145, the absolute fallback resolves
    through the marketplace-cache install (docs/architecture.md § Self-
    reference decoupling — marketplace install), not the retired
    flex-harness release channel."""
    fallback_needle = _current_pairmode_scripts_dir()
    agents_dir = REPO_ROOT / ".claude" / "agents"
    missing_fallback = []
    for path in sorted(agents_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if fallback_needle not in text:
            missing_fallback.append(path.name)

    assert missing_fallback == ["reconstruction-agent.md"], (
        "expected exactly reconstruction-agent.md to lack the "
        f"{fallback_needle!r} fallback pointer, got: {missing_fallback}"
    )

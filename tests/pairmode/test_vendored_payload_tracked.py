"""
Tests for INFRA-261 (CER-090) — guard against re-ignoring the vendored
`skills/observability` `node_modules` payload.

`.gitignore`'s global `dist/` and `build/` patterns (no leading slash, so they
match at every depth) used to exclude the compiled JS/`.d.ts` payload shipped
inside vendored packages, leaving every fresh `git worktree` unable to run
`pnpm --filter @flex-obs/ui build` (TS2307 module-not-found). INFRA-261 added a
scoped, `node_modules`-anchored negation to re-include that payload while
leaving our own build output (`skills/observability/ui/dist`,
`skills/observability/api/dist`) ignored.

These tests shell out to `git` with `cwd` at the repo root and mutate nothing.
They skip cleanly when `git` is unavailable or the tree is not a git repo —
this guard has no purpose outside a git checkout.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FLEX_ROOT = Path(__file__).resolve().parents[2]

# The only permitted exceptions to "every path under skills/observability must
# be tracked". Two categories:
#
# 1. Node-gyp's compile intermediates under better-sqlite3's native build
#    (build/Release/obj/, build/Release/obj.target/) — ~15 MB of .o files,
#    never loaded at runtime (only the compiled `better_sqlite3.node` addon
#    beside them is), and trivially reproducible from already-tracked source
#    via `pnpm rebuild better-sqlite3`.
# 2. Our *own* build output (ui/dist, api/dist) and Python bytecode cache
#    (scripts/__pycache__) — never vendored payload, and correctly still
#    ignored by the global dist//build/ and __pycache__/ patterns. These only
#    appear on disk after a build has actually been run.
# 3. `skills/observability/ui/tsconfig.tsbuildinfo` (CER-070 addendum /
#    INFRA-302) — our own generated incremental-typecheck cache, not vendored
#    package payload, and it lives outside every node_modules tree. It is
#    deliberately untracked and ignored (see .gitignore) because `tsc -b`
#    rewrites it on every UI-build-gate run, dirtying a story worktree and
#    making merge-story-worktree's rebase refuse.
#
# Nothing else may be added here: any other ignored path under a vendored
# node_modules is exactly the defect class (CER-090) this test exists to
# catch, and widening this list without confronting that reason is the
# "future cleanup" this guard is meant to stop.
ALLOWED_IGNORED_SUFFIXES = (
    "build/Release/obj/",
    "build/Release/obj.target/",
)

ALLOWED_IGNORED_EXACT = (
    "skills/observability/ui/dist/",
    "skills/observability/api/dist/",
    "skills/observability/scripts/__pycache__/",
    "skills/observability/ui/tsconfig.tsbuildinfo",
)


def _have_git() -> bool:
    return shutil.which("git") is not None


def _is_git_repo() -> bool:
    if not _have_git():
        return False
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(FLEX_ROOT),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _require_git() -> None:
    if not _have_git():
        pytest.skip("git not available")
    if not _is_git_repo():
        pytest.skip("not a git repository")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(FLEX_ROOT),
        capture_output=True,
        text=True,
    )


def _vendored_roots() -> list[Path]:
    """
    Discover vendored node_modules roots under skills/ by glob, not a
    hard-coded list of three paths — so a fourth vendored root added later
    (or a currently-symlinked one, e.g. skills/observability/ui/node_modules)
    is covered automatically (Ensures 13).
    """
    skills_dir = FLEX_ROOT / "skills"
    if not skills_dir.is_dir():
        return []
    roots: list[Path] = []
    for path in skills_dir.rglob("node_modules"):
        if path.is_dir() or path.is_symlink():
            roots.append(path)
    return roots


def test_no_vendored_payload_is_gitignored() -> None:
    """
    Every ignored-and-untracked entry under skills/observability must match
    the module-level allow-list (node-gyp intermediates only). Anything else
    is the CER-090 defect: real package payload silently excluded from git.
    """
    _require_git()
    result = _git(
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "--directory",
        "--",
        "skills/observability",
    )
    assert result.returncode == 0, result.stderr

    offending = [
        line
        for line in result.stdout.splitlines()
        if line
        and line not in ALLOWED_IGNORED_EXACT
        and not line.endswith(ALLOWED_IGNORED_SUFFIXES)
    ]
    assert not offending, (
        "Ignored-and-untracked paths under skills/observability that are not "
        "on the allow-list (this re-introduces CER-090 — vendored package "
        f"payload silently excluded from git):\n" + "\n".join(offending)
    )


def test_no_untracked_files_under_observability() -> None:
    """
    A fresh worktree must equal the main checkout: no file under
    skills/observability may be both untracked and unignored.
    """
    _require_git()
    result = _git(
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        "skills/observability",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", (
        "Untracked files under skills/observability (a fresh worktree would "
        "not match the main checkout):\n" + result.stdout
    )


def test_every_vendored_build_or_dist_dir_has_tracked_files() -> None:
    """
    Direct regression anchor for the TS2307 cause: every build/ or dist/
    directory that exists on disk under a vendored node_modules (and is not
    allow-listed) must have at least one tracked file underneath it. A
    directory with zero tracked files is invisible to a fresh worktree.
    """
    _require_git()

    checked_any = False
    for root in _vendored_roots():
        for dirname in ("build", "dist"):
            for candidate in root.rglob(dirname):
                if not candidate.is_dir():
                    continue
                rel = candidate.relative_to(FLEX_ROOT).as_posix()
                if rel.endswith(("build/Release/obj", "build/Release/obj.target")):
                    continue
                # Our own build output stays ignored/empty until built; it is
                # not vendored payload and is out of scope for this guard.
                if rel in (
                    "skills/observability/ui/dist",
                    "skills/observability/api/dist",
                ):
                    continue

                checked_any = True
                result = _git("ls-files", "--", rel)
                assert result.returncode == 0, result.stderr
                assert result.stdout.strip() != "", (
                    f"{rel} exists on disk but has zero tracked files — a "
                    "fresh git worktree would not have this vendored payload "
                    "(CER-090)."
                )

    if not checked_any:
        pytest.skip(
            "no vendored build/ or dist/ directories found on disk "
            "(payload not rehydrated in this checkout)"
        )


def test_gitignore_still_ignores_our_own_build_output() -> None:
    """
    The scoped negation must not swallow our own build output: these two
    paths are ours, not vendored payload, and must remain ignored.
    """
    _require_git()
    for rel in (
        "skills/observability/ui/dist/",
        "skills/observability/api/dist/",
    ):
        result = _git("check-ignore", "-q", rel)
        assert result.returncode == 0, (
            f"{rel} is no longer ignored — the .gitignore negation for "
            "vendored node_modules payload has become too broad and is now "
            "swallowing our own build output."
        )


def test_tsconfig_tsbuildinfo_is_untracked() -> None:
    """
    CER-070 addendum (INFRA-302): tsconfig.tsbuildinfo must not be tracked by
    git — a tracked file that `tsc -b` rewrites on every UI-build-gate run
    dirties a story worktree and makes merge-story-worktree's rebase refuse.
    """
    _require_git()
    result = _git("ls-files", "--", "skills/observability/ui/tsconfig.tsbuildinfo")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", (
        "skills/observability/ui/tsconfig.tsbuildinfo is tracked by git — it "
        "must be untracked (git rm --cached) so a UI-build-gate run cannot "
        "dirty a story worktree."
    )


def test_tsconfig_tsbuildinfo_is_ignored() -> None:
    """
    CER-070 addendum (INFRA-302): tsconfig.tsbuildinfo must be ignored so a
    regenerated copy never re-surfaces as an untracked file in `git status`.
    """
    _require_git()
    result = _git("check-ignore", "-q", "skills/observability/ui/tsconfig.tsbuildinfo")
    assert result.returncode == 0, (
        "skills/observability/ui/tsconfig.tsbuildinfo is not ignored by "
        ".gitignore — a regenerated copy would re-surface as an untracked "
        "file and dirty every story worktree that runs the UI build gate."
    )

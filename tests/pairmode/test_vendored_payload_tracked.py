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

import re
import shutil
import subprocess
from pathlib import Path

import pytest

FLEX_ROOT = Path(__file__).resolve().parents[2]

# The only permitted exceptions to "every path under skills/observability must
# be tracked". Five categories:
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
# 4. A `.claude/` directory anywhere under a `node_modules` tree (CER-093 /
#    INFRA-307), matched by pattern rather than by literal path: (a) upstream
#    npm packages can ship a `.claude/` directory inside their published
#    tarball; (b) a **machine-local** exclude file — `~/.config/git/ignore`
#    on the machine where this fired, git's default `core.excludesFile` —
#    then makes those files ignored-but-untracked, so the repo's own
#    `.gitignore` is not the cause and editing it is not the cure; (c) the
#    live hits at cp-103 were `nanoid@3.3.12` and `thread-stream@4.2.0`,
#    named here as history only — the set of packages that do this is not
#    knowable in advance, so no package name is encoded in the pattern
#    (see ALLOWED_IGNORED_PATTERNS below); (d) this is not the CER-090
#    defect class, because CER-090 is *our* patterns hiding *vendored
#    payload*, whereas this is *someone else's* file that was never
#    payload; (e) the tolerance is anchored under `node_modules` — a
#    `.claude/` directory outside any `node_modules` tree (e.g. directly
#    under `skills/observability/`) is our own decision and must still be
#    reported as offending, not absorbed.
# 5. `build/Release/test_extension.node` (CER-094 / INFRA-307) — the rebuild
#    artifact of a binary this story deleted, not payload in its own right.
#    It is better-sqlite3's second node-gyp target (`binding.gyp`
#    `targets[1]`, `test_extension`), used only by that package's own
#    `loadExtension` test suite and never loaded by this project
#    (`better-sqlite3/lib/database.js:48` requires only
#    `better_sqlite3.node`). `pnpm rebuild better-sqlite3` regenerates it;
#    without this allow-list member (and the matching .gitignore
#    re-exclusion) that regeneration would fail this guard.
# 6. `skills/observability/api/node_modules/.vitest-cache/` (INFRA-312) — the
#    scoped TS route-test runner's own run cache (`vitest.config.ts` pins
#    `cacheDir` here precisely so it is a single, narrow path to ignore),
#    same shape as category 3 above: our own generated cache, not vendored
#    package payload, rewritten (a results.json under a content-hash
#    subdirectory) on every `pnpm test` run including failing ones.
#
# Note on asymmetry: this list widens what test_no_vendored_payload_is_gitignored
# tolerates, but test_no_untracked_files_under_observability below is
# deliberately left unchanged — a `.claude/` directory that is *not* ignored
# on some other machine still fails it, which is correct: an unignored,
# untracked file under skills/observability breaks worktree parity regardless
# of who wrote it.
#
# Nothing else may be added here: any other ignored path under a vendored
# node_modules is exactly the defect class (CER-090) this test exists to
# catch, and widening this list without confronting that reason is the
# "future cleanup" this guard is meant to stop.
ALLOWED_IGNORED_SUFFIXES = (
    "build/Release/obj/",
    "build/Release/obj.target/",
    "build/Release/test_extension.node",
)

ALLOWED_IGNORED_EXACT = (
    "skills/observability/ui/dist/",
    "skills/observability/api/dist/",
    "skills/observability/scripts/__pycache__/",
    "skills/observability/ui/tsconfig.tsbuildinfo",
    "skills/observability/api/node_modules/.vitest-cache/",
)

# CER-093 (INFRA-307): a compiled pattern, not literals. Upstream npm
# packages sometimes ship a `.claude/` directory inside their published
# tarball; a machine-local git exclude then makes those files
# ignored-but-untracked. The set of packages that do this is not knowable
# in advance, so no package name, version, or `.pnpm` store path is encoded
# here — only the structural fact that the directory sits under some
# `node_modules/` tree. See allow-list category 4 above.
ALLOWED_IGNORED_PATTERNS = (
    re.compile(r"(?:^|/)node_modules/(?:.*/)?\.claude/"),
)


def _is_allowed_ignored(line: str) -> bool:
    """
    Classify one ignored-and-untracked path as allowed or offending, per
    CER-090 (exact/suffix allow-lists) and CER-093 (the .claude/ pattern
    under node_modules). Used only by test_no_vendored_payload_is_gitignored.
    """
    return (
        line in ALLOWED_IGNORED_EXACT
        or line.endswith(ALLOWED_IGNORED_SUFFIXES)
        or any(pattern.search(line) for pattern in ALLOWED_IGNORED_PATTERNS)
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
        line for line in result.stdout.splitlines() if line and not _is_allowed_ignored(line)
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


# --- CER-093 (INFRA-307): the .claude/ tolerance pattern ------------------


def test_allowed_ignored_patterns_has_no_package_literals() -> None:
    """
    A1: the tolerance is a compiled pattern, not literals. Encoding a
    package name into the pattern would defeat the point of CER-093 — the
    set of upstream packages that ship a .claude/ directory is not knowable
    in advance.
    """
    assert len(ALLOWED_IGNORED_PATTERNS) == 1
    source = ALLOWED_IGNORED_PATTERNS[0].pattern
    for forbidden in ("nanoid", "thread-stream", ".pnpm", "@"):
        assert forbidden not in source, (
            f"ALLOWED_IGNORED_PATTERNS contains {forbidden!r} — the pattern must "
            "stay structural (node_modules/.../.claude/), never a package literal."
        )


def test_claude_tolerance_matches_both_git_shapes() -> None:
    """
    A2: git ls-files --others --ignored --directory prints both a directory
    line and a file line for a leaf .claude/ file; both must be tolerated.
    """
    directory_shape = (
        "skills/observability/node_modules/.pnpm/nanoid@3.3.12/"
        "node_modules/nanoid/.claude/"
    )
    file_shape = (
        "skills/observability/node_modules/.pnpm/nanoid@3.3.12/"
        "node_modules/nanoid/.claude/settings.local.json"
    )
    assert _is_allowed_ignored(directory_shape)
    assert _is_allowed_ignored(file_shape)


def test_claude_tolerance_is_anchored_under_node_modules() -> None:
    """
    A3: a .claude/ directory that is not below a node_modules/ segment is
    our own decision, not vendored noise, and must still be reported as
    offending.
    """
    own_tree_shape = "skills/observability/.claude/settings.local.json"
    assert not _is_allowed_ignored(own_tree_shape)


def test_no_vendored_payload_is_gitignored_uses_is_allowed_ignored() -> None:
    """
    A4: the offending-path filter in test_no_vendored_payload_is_gitignored
    calls the named classifier rather than inlining the membership tests, so
    A1-A3 are testable directly rather than only through a git invocation.
    """
    import inspect

    source = inspect.getsource(test_no_vendored_payload_is_gitignored)
    assert "_is_allowed_ignored(" in source


# --- CER-094 (INFRA-307): test_extension.node leaves the payload ----------


def test_test_extension_node_is_untracked() -> None:
    """
    B1/B4a: the second better-sqlite3 gyp target (used only by its own
    loadExtension test suite, never loaded by this project) is gone from
    git.
    """
    _require_git()
    result = _git("ls-files", "--", "skills/observability/**/test_extension.node")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", (
        "test_extension.node is still tracked by git — CER-094 chose "
        "deletion, not justify-and-keep, for this binary."
    )


def test_test_extension_node_rebuild_would_be_ignored() -> None:
    """
    B2/B4b: a `pnpm rebuild better-sqlite3` regenerates this file on disk;
    the .gitignore re-exclusion must make it ignored rather than offending.
    """
    _require_git()
    rel = (
        "skills/observability/node_modules/.pnpm/better-sqlite3@12.10.0/"
        "node_modules/better-sqlite3/build/Release/test_extension.node"
    )
    result = _git("check-ignore", "-q", rel)
    assert result.returncode == 0, (
        f"{rel} is not ignored — a pnpm rebuild of better-sqlite3 would "
        "leave it untracked-and-unignored and fail the payload guard."
    )


def test_better_sqlite3_build_release_still_has_tracked_files() -> None:
    """
    B6: build/Release/ retains tracked files (better_sqlite3.node, sqlite3.a,
    .deps/...) after test_extension.node's removal, so the directory is not
    invisible to a fresh worktree.
    """
    _require_git()
    result = _git(
        "ls-files",
        "--",
        "skills/observability/node_modules/.pnpm/better-sqlite3@12.10.0/"
        "node_modules/better-sqlite3/build/Release/",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() != "", (
        "build/Release/ under better-sqlite3 has zero tracked files after "
        "test_extension.node's removal."
    )


# --- CER-094 (INFRA-307): the native-binary inventory ---------------------

# Version-stripped paths (under skills/observability/node_modules/.pnpm/) of
# every native .node binary this project intentionally tracks. Each is an
# optional, platform-gated dependency of its parent package (rollup and
# lightningcss declare a per-platform optionalDependencies map; only the two
# linux-x64 variants resolved into this snapshot) except the last, which is
# the API's runtime SQLite addon.
#
# test_extension.node is deliberately absent from this set — its absence is
# the assertion that closes CER-094 (see test_tracked_native_binaries_match_
# enumerated_set below).
EXPECTED_TRACKED_NATIVE_BINARIES: frozenset[str] = frozenset(
    {
        # Rollup 4's native core; Vite loads it during the UI build gate.
        "@rollup+rollup-linux-x64-gnu/node_modules/@rollup/rollup-linux-x64-gnu/"
        "rollup.linux-x64-gnu.node",
        "@rollup+rollup-linux-x64-musl/node_modules/@rollup/rollup-linux-x64-musl/"
        "rollup.linux-x64-musl.node",
        # Tailwind 4's Rust engine; the UI build's CSS pipeline.
        "@tailwindcss+oxide-linux-x64-gnu/node_modules/@tailwindcss/"
        "oxide-linux-x64-gnu/tailwindcss-oxide.linux-x64-gnu.node",
        "@tailwindcss+oxide-linux-x64-musl/node_modules/@tailwindcss/"
        "oxide-linux-x64-musl/tailwindcss-oxide.linux-x64-musl.node",
        # Lightning CSS transform/minify, pulled in by the Tailwind/Vite pipeline.
        "lightningcss-linux-x64-gnu/node_modules/lightningcss-linux-x64-gnu/"
        "lightningcss.linux-x64-gnu.node",
        "lightningcss-linux-x64-musl/node_modules/lightningcss-linux-x64-musl/"
        "lightningcss.linux-x64-musl.node",
        # The API's SQLite addon; loaded at runtime by
        # require('bindings')('better_sqlite3.node') (lib/database.js:48).
        "better-sqlite3/node_modules/better-sqlite3/build/Release/"
        "better_sqlite3.node",
    }
)


def _strip_pnpm_version(path: str) -> str:
    """
    Remove the trailing @<version> from the .pnpm/<segment>/ store-directory
    component only, so a patch bump of a native dependency does not fail
    this guard while a genuinely new binary (or new package) still does.
    Leaves scoped names like @rollup+rollup-linux-x64-gnu intact and is a
    no-op for paths with no .pnpm/ component.
    """
    marker = ".pnpm/"
    idx = path.find(marker)
    if idx == -1:
        return path
    prefix = path[: idx + len(marker)]
    rest = path[idx + len(marker) :]
    segment, sep, remainder = rest.partition("/")
    stripped_segment = segment.rsplit("@", 1)[0]
    return f"{prefix}{stripped_segment}{sep}{remainder}"


def test_strip_pnpm_version_collapses_version_bumps() -> None:
    """C3: a version bump of a tracked native dependency must not fail the guard."""
    v1 = (
        "skills/observability/node_modules/.pnpm/"
        "@rollup+rollup-linux-x64-gnu@4.61.1/node_modules/@rollup/"
        "rollup-linux-x64-gnu/rollup.linux-x64-gnu.node"
    )
    v2 = (
        "skills/observability/node_modules/.pnpm/"
        "@rollup+rollup-linux-x64-gnu@9.9.9/node_modules/@rollup/"
        "rollup-linux-x64-gnu/rollup.linux-x64-gnu.node"
    )
    assert _strip_pnpm_version(v1) == _strip_pnpm_version(v2)


def test_strip_pnpm_version_does_not_collapse_new_binaries() -> None:
    """C3: a genuinely new native binary (or new package) must still fail the guard."""
    new = (
        "skills/observability/node_modules/.pnpm/some-pkg@1.0.0/"
        "node_modules/some-pkg/foo.node"
    )
    marker = "skills/observability/node_modules/.pnpm/"
    stripped_new = _strip_pnpm_version(new).split(marker, 1)[-1]
    assert stripped_new not in EXPECTED_TRACKED_NATIVE_BINARIES


def test_tracked_native_binaries_match_enumerated_set() -> None:
    """
    C1/C2/C4/C5: the live set of tracked .node binaries under
    skills/observability, version-stripped, must equal
    EXPECTED_TRACKED_NATIVE_BINARIES exactly — in both directions.
    """
    _require_git()
    assert len(EXPECTED_TRACKED_NATIVE_BINARIES) == 7

    result = _git("ls-files", "--", "skills/observability")
    assert result.returncode == 0, result.stderr

    pnpm_marker = "skills/observability/node_modules/.pnpm/"
    live: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.endswith(".node"):
            continue
        stripped = _strip_pnpm_version(line)
        if stripped.startswith(pnpm_marker):
            live.add(stripped[len(pnpm_marker) :])
        else:
            live.add(stripped)

    assert live, "no tracked .node binaries found under skills/observability"

    unexpected = live - EXPECTED_TRACKED_NATIVE_BINARIES
    missing = EXPECTED_TRACKED_NATIVE_BINARIES - live

    assert not unexpected, (
        "A payload refresh added a native binary that no one has justified; "
        "enumerate it in docs/architecture.md and add it to "
        f"EXPECTED_TRACKED_NATIVE_BINARIES, or delete it:\n" + "\n".join(sorted(unexpected))
    )
    assert not missing, (
        "An expected native binary is no longer tracked; the payload is "
        "incomplete and a fresh worktree will fail to build:\n" + "\n".join(sorted(missing))
    )

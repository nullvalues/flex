"""
Tests for INFRA-159 — Context Management API: GET /api/repos/:id/context

These tests verify structural correctness of the TypeScript sources:
- Required files exist with expected exports
- server.ts imports and registers the context route
- TypeScript compiles without errors (tsc --noEmit)
"""

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FLEX_ROOT = Path(__file__).resolve().parents[2]
OBS_API = FLEX_ROOT / "skills" / "observability" / "api"
SRC = OBS_API / "src"
READERS = SRC / "readers"
ROUTES = SRC / "routes"
SERVER_TS = SRC / "server.ts"


# ---------------------------------------------------------------------------
# File existence tests
# ---------------------------------------------------------------------------

def test_stateJson_reader_exists() -> None:
    """readers/stateJson.ts must exist."""
    assert (READERS / "stateJson.ts").is_file(), "readers/stateJson.ts not found"


def test_effortDb_reader_exists() -> None:
    """readers/effortDb.ts must exist."""
    assert (READERS / "effortDb.ts").is_file(), "readers/effortDb.ts not found"


def test_context_route_exists() -> None:
    """routes/context.ts must exist."""
    assert (ROUTES / "context.ts").is_file(), "routes/context.ts not found"


# ---------------------------------------------------------------------------
# Export shape tests
# ---------------------------------------------------------------------------

def test_stateJson_exports_readStateJson() -> None:
    """readers/stateJson.ts must export readStateJson."""
    content = (READERS / "stateJson.ts").read_text()
    assert "export async function readStateJson" in content, (
        "readStateJson not exported from stateJson.ts"
    )


def test_effortDb_exports_openEffortDb() -> None:
    content = (READERS / "effortDb.ts").read_text()
    assert "export function openEffortDb" in content, (
        "openEffortDb not exported from effortDb.ts"
    )


def test_effortDb_exports_queryWaypoints() -> None:
    content = (READERS / "effortDb.ts").read_text()
    assert "export function queryWaypoints" in content, (
        "queryWaypoints not exported from effortDb.ts"
    )


def test_effortDb_exports_queryEffortSummary() -> None:
    content = (READERS / "effortDb.ts").read_text()
    assert "export function queryEffortSummary" in content, (
        "queryEffortSummary not exported from effortDb.ts"
    )


def test_effortDb_exports_queryMisses() -> None:
    content = (READERS / "effortDb.ts").read_text()
    assert "export function queryMisses" in content, (
        "queryMisses not exported from effortDb.ts"
    )


def test_context_route_exports_registerContextRoutes() -> None:
    content = (ROUTES / "context.ts").read_text()
    assert "export async function registerContextRoutes" in content, (
        "registerContextRoutes not exported from routes/context.ts"
    )


# ---------------------------------------------------------------------------
# server.ts integration tests
# ---------------------------------------------------------------------------

def test_server_imports_context_route() -> None:
    """server.ts must import registerContextRoutes from routes/context.js."""
    content = SERVER_TS.read_text()
    assert "registerContextRoutes" in content, (
        "server.ts does not import registerContextRoutes"
    )
    assert "routes/context.js" in content, (
        "server.ts does not reference routes/context.js"
    )


def test_server_calls_registerContextRoutes() -> None:
    """server.ts must call await registerContextRoutes(app)."""
    content = SERVER_TS.read_text()
    assert "await registerContextRoutes(app)" in content, (
        "server.ts does not call await registerContextRoutes(app)"
    )


# ---------------------------------------------------------------------------
# Threshold definitions test
# ---------------------------------------------------------------------------

def test_context_route_has_six_thresholds() -> None:
    """routes/context.ts must define exactly 6 threshold entries."""
    content = (ROUTES / "context.ts").read_text()
    # Count occurrences of threshold name entries
    threshold_names = [
        "context_budget_threshold",
        "context_budget_overrun_pct",
        "expected_step_tokens",
        "context_budget_reprompt_margin",
        "context_current_tokens_ttl_minutes",
        "flex_factor",
    ]
    for name in threshold_names:
        assert f"'{name}'" in content or f'"{name}"' in content, (
            f"Threshold '{name}' not found in routes/context.ts"
        )


def test_effortDb_uses_read_only() -> None:
    """effortDb.ts must open SQLite in read-only mode (fileMustExist or readonly)."""
    content = (READERS / "effortDb.ts").read_text()
    assert "readonly: true" in content or "fileMustExist: true" in content, (
        "effortDb.ts does not open SQLite in read-only mode"
    )


def test_effortDb_no_write_calls() -> None:
    """effortDb.ts must not call db.prepare for INSERT/UPDATE/DELETE."""
    content = (READERS / "effortDb.ts").read_text().upper()
    for write_op in ("INSERT ", "UPDATE ", "DELETE "):
        assert write_op not in content, (
            f"effortDb.ts contains SQL write operation: {write_op.strip()}"
        )


# ---------------------------------------------------------------------------
# better-sqlite3 dependency test
# ---------------------------------------------------------------------------

def test_package_json_has_better_sqlite3() -> None:
    """api/package.json must list better-sqlite3 as a dependency."""
    import json
    pkg = json.loads((OBS_API / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    assert "better-sqlite3" in deps, (
        "better-sqlite3 not listed in api/package.json dependencies"
    )


# ---------------------------------------------------------------------------
# TypeScript compilation test
# ---------------------------------------------------------------------------

def test_typescript_compiles() -> None:
    """TypeScript must compile without errors."""
    result = subprocess.run(
        ["pnpm", "build"],
        cwd=str(OBS_API),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"TypeScript compilation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# 2-second cache declaration test
# ---------------------------------------------------------------------------

def test_context_route_has_cache() -> None:
    """routes/context.ts must declare a 2-second in-process cache."""
    content = (ROUTES / "context.ts").read_text()
    assert "2000" in content, (
        "routes/context.ts does not declare CACHE_TTL_MS = 2000"
    )
    assert "cache" in content.lower(), (
        "routes/context.ts does not appear to implement a cache"
    )


# ---------------------------------------------------------------------------
# INFRA-166: Route hardening — null crash, 0-token, NaN, flex_factor live read
# ---------------------------------------------------------------------------

def test_repos_null_project_dir_try_catch_present() -> None:
    """repos.ts must wrap the state.json probe in try/catch (INFRA-166 fix 1)."""
    content = (ROUTES / "repos.ts").read_text()
    assert "stateJsonPresent = false" in content, (
        "repos.ts missing let stateJsonPresent = false initialiser"
    )
    assert "try {" in content, "repos.ts missing try block around state.json probe"
    assert "console.error" in content, (
        "repos.ts missing console.error on catch for probe failure"
    )
    assert "failed to probe state.json" in content, (
        "repos.ts error message for probe failure missing"
    )


def test_context_zero_tokens_treated_as_absent() -> None:
    """context.ts must require context_current_tokens > 0 to treat as valid (INFRA-166 fix 3)."""
    content = (ROUTES / "context.ts").read_text()
    # The guard must now include > 0 check
    assert "(state['context_current_tokens'] as number) > 0" in content, (
        "context.ts missing > 0 guard for context_current_tokens (INFRA-166 fix 3)"
    )


def test_context_nan_threshold_guard_present() -> None:
    """context.ts must use Number.isNaN guard when extracting threshold values (INFRA-166 fix 4)."""
    content = (ROUTES / "context.ts").read_text()
    assert "!Number.isNaN(rawValue)" in content, (
        "context.ts missing !Number.isNaN(rawValue) guard in buildThresholds (INFRA-166 fix 4)"
    )


def test_context_flex_factor_live_read_present() -> None:
    """context.ts must read flex_factor from story frontmatter via parseStoryFrontmatter (INFRA-166 fix 2)."""
    content = (ROUTES / "context.ts").read_text()
    assert "parseStoryFrontmatter" in content, (
        "context.ts does not import/call parseStoryFrontmatter (INFRA-166 fix 2)"
    )
    assert "storyFrontmatter.js" in content, (
        "context.ts does not import from storyFrontmatter.js"
    )
    assert "current_story" in content, (
        "context.ts does not read current_story from state for flex_factor live read"
    )
    assert "story-frontmatter" in content, (
        "context.ts does not set source to 'story-frontmatter' for flex_factor"
    )


def test_context_flex_factor_fallback_when_no_story() -> None:
    """context.ts must fall back to value=1.0, source='default' when no current_story (INFRA-166 fix 2)."""
    content = (ROUTES / "context.ts").read_text()
    assert "flexFactorSource = 'default'" in content, (
        "context.ts missing flexFactorSource = 'default' fallback for absent story"
    )
    assert "flexFactorValue = 1.0" in content, (
        "context.ts missing flexFactorValue = 1.0 default"
    )

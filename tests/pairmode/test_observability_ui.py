"""
Tests for INFRA-161 — Vite + React 19 + Tailwind v4 frontend: multi-repo
side-by-side panels.

These tests verify the structural shape of the SPA without launching a browser:

- Required UI files exist with the expected configuration shape.
- vite.config proxies /api to 127.0.0.1:7777 (dev mode requirement).
- tailwind.config scans src/**.
- App is wrapped in <QueryClientProvider> and uses TanStack Query hooks
  with the staleTime and refetchInterval the story specifies.
- The API base URL in client.ts is the relative path "/api".
- The UI build (tsc -b && vite build) emits a dist/ with index.html that
  contains the literal "flex observability".
- The Fastify server registers @fastify/static gated on NODE_ENV=production
  and resolves dist relative to its own module dir (no hard-coded absolute path).
- No write controls (PUT/POST/DELETE/form action) appear in the UI sources —
  Phase 63 is read-only window glass.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FLEX_ROOT = Path(__file__).resolve().parents[2]
OBS_ROOT = FLEX_ROOT / "skills" / "observability"
OBS_API = OBS_ROOT / "api"
OBS_UI = OBS_ROOT / "ui"
UI_SRC = OBS_UI / "src"
UI_COMPONENTS = UI_SRC / "components"
UI_API = UI_SRC / "api"


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------


def test_ui_package_json_exists() -> None:
    assert (OBS_UI / "package.json").is_file()


def test_vite_config_exists() -> None:
    assert (OBS_UI / "vite.config.ts").is_file()


def test_tailwind_config_exists() -> None:
    assert (OBS_UI / "tailwind.config.ts").is_file()


def test_index_html_exists() -> None:
    assert (OBS_UI / "index.html").is_file()


def test_main_tsx_exists() -> None:
    assert (UI_SRC / "main.tsx").is_file()


def test_app_tsx_exists() -> None:
    assert (UI_SRC / "App.tsx").is_file()


def test_api_client_exists() -> None:
    assert (UI_API / "client.ts").is_file()


def test_repo_panel_exists() -> None:
    assert (UI_COMPONENTS / "RepoPanel.tsx").is_file()


def test_system_of_record_exists() -> None:
    assert (UI_COMPONENTS / "SystemOfRecord.tsx").is_file()


def test_context_metrics_exists() -> None:
    assert (UI_COMPONENTS / "ContextMetrics.tsx").is_file()


def test_lessons_panel_exists() -> None:
    """LessonsPanel ships in Phase 63 (covers INFRA-158)."""
    assert (UI_COMPONENTS / "LessonsPanel.tsx").is_file()


# ---------------------------------------------------------------------------
# package.json shape
# ---------------------------------------------------------------------------


def _ui_pkg() -> dict:
    return json.loads((OBS_UI / "package.json").read_text())


def test_ui_package_name() -> None:
    assert _ui_pkg()["name"] == "@flex-obs/ui"


@pytest.mark.parametrize("script", ["dev", "build", "preview"])
def test_ui_package_has_required_scripts(script: str) -> None:
    pkg = _ui_pkg()
    assert script in pkg.get("scripts", {}), f"missing script: {script}"


def test_ui_package_has_react_19() -> None:
    deps = _ui_pkg().get("dependencies", {})
    assert "react" in deps
    assert deps["react"].lstrip("^~").startswith("19."), (
        f"expected react ^19.x; got {deps['react']}"
    )
    assert "react-dom" in deps
    assert deps["react-dom"].lstrip("^~").startswith("19."), (
        f"expected react-dom ^19.x; got {deps['react-dom']}"
    )


def test_ui_package_has_tanstack_query() -> None:
    deps = _ui_pkg().get("dependencies", {})
    assert "@tanstack/react-query" in deps


def test_ui_package_has_vite_6_and_tailwind_4() -> None:
    dev = _ui_pkg().get("devDependencies", {})
    assert "vite" in dev
    assert dev["vite"].lstrip("^~").startswith("6."), (
        f"expected vite ^6.x; got {dev['vite']}"
    )
    assert "tailwindcss" in dev
    assert dev["tailwindcss"].lstrip("^~").startswith("4."), (
        f"expected tailwindcss ^4.x; got {dev['tailwindcss']}"
    )


# ---------------------------------------------------------------------------
# Configuration content
# ---------------------------------------------------------------------------


def test_vite_proxy_targets_7777() -> None:
    cfg = (OBS_UI / "vite.config.ts").read_text()
    assert "'/api'" in cfg or '"/api"' in cfg
    assert "http://127.0.0.1:7777" in cfg, (
        "vite.config.ts must proxy /api to http://127.0.0.1:7777"
    )


def test_tailwind_scans_src() -> None:
    cfg = (OBS_UI / "tailwind.config.ts").read_text()
    # Looking for './src/**/*.{...}' style content entry.
    assert re.search(r"['\"]\./src/\*\*/\*", cfg), (
        "tailwind.config.ts must scan ./src/**"
    )


def test_index_html_mounts_root_div() -> None:
    html = (OBS_UI / "index.html").read_text()
    assert '<div id="root"' in html, "index.html must contain <div id=\"root\">"
    assert "src/main.tsx" in html, "index.html must reference src/main.tsx"


def test_index_html_title_contains_flex_observability() -> None:
    html = (OBS_UI / "index.html").read_text()
    assert "flex observability" in html


# ---------------------------------------------------------------------------
# Source shape — TanStack Query wiring + API base
# ---------------------------------------------------------------------------


def test_main_wraps_app_in_query_client_provider() -> None:
    src = (UI_SRC / "main.tsx").read_text()
    assert "QueryClientProvider" in src
    assert "<App" in src or "<App/>" in src


def test_main_sets_stale_and_refetch_interval() -> None:
    src = (UI_SRC / "main.tsx").read_text()
    # Story §8: staleTime 2000, refetchInterval 30000.
    assert "staleTime" in src and "2000" in src
    assert "refetchInterval" in src and "30000" in src


def test_api_client_uses_relative_api_base() -> None:
    src = (UI_API / "client.ts").read_text()
    # Story §"Instructions": API base URL is "/api" (relative).
    assert re.search(r"(?:const|let|var)\s+API_BASE\s*=\s*['\"]/api['\"]", src), (
        "src/api/client.ts must define API_BASE = '/api'"
    )


def test_api_client_exports_query_hooks() -> None:
    src = (UI_API / "client.ts").read_text()
    for hook in ("useRepos", "useSystem", "useContext", "useLessons"):
        assert f"export function {hook}" in src, f"missing hook: {hook}"


# ---------------------------------------------------------------------------
# Read-only contract — no write controls in UI sources
# ---------------------------------------------------------------------------


def _ui_tsx_sources() -> list[Path]:
    return sorted(UI_SRC.rglob("*.tsx")) + sorted(UI_SRC.rglob("*.ts"))


def test_no_form_action_in_ui_sources() -> None:
    for path in _ui_tsx_sources():
        if "node_modules" in path.parts:
            continue
        text = path.read_text()
        assert "<form" not in text.lower(), (
            f"Phase 63 is read-only; <form> found in {path.relative_to(FLEX_ROOT)}"
        )


def test_no_mutation_fetch_in_ui_sources() -> None:
    pattern = re.compile(r"method:\s*['\"](POST|PUT|DELETE|PATCH)['\"]", re.IGNORECASE)
    for path in _ui_tsx_sources():
        if "node_modules" in path.parts:
            continue
        text = path.read_text()
        m = pattern.search(text)
        assert m is None, (
            f"Phase 63 is read-only; mutation fetch found in {path.relative_to(FLEX_ROOT)}: {m.group(0)}"
        )


def test_no_useMutation_in_ui_sources() -> None:
    for path in _ui_tsx_sources():
        if "node_modules" in path.parts:
            continue
        text = path.read_text()
        assert "useMutation" not in text, (
            f"Phase 63 is read-only; useMutation found in {path.relative_to(FLEX_ROOT)}"
        )


# ---------------------------------------------------------------------------
# Server static-serve wiring
# ---------------------------------------------------------------------------


def test_api_package_has_fastify_static() -> None:
    pkg = json.loads((OBS_API / "package.json").read_text())
    assert "@fastify/static" in pkg.get("dependencies", {}), (
        "api/package.json must list @fastify/static (story §12)"
    )


def test_server_registers_fastify_static_in_production() -> None:
    server = (OBS_API / "src" / "server.ts").read_text()
    assert "fastifyStatic" in server or "@fastify/static" in server
    assert "NODE_ENV" in server and "production" in server, (
        "server.ts must gate static serving on NODE_ENV === 'production'"
    )
    assert "ui" in server and "dist" in server, (
        "server.ts must serve the ui/dist directory"
    )


def test_server_does_not_use_hardcoded_absolute_ui_path() -> None:
    """Resolve dist via __filename / import.meta.url — not a hard-coded absolute path."""
    server = (OBS_API / "src" / "server.ts").read_text()
    # The story rules forbid hard-coded absolute paths. A literal /mnt/... or
    # similar absolute path is the prohibited pattern.
    assert "/mnt/" not in server, "server.ts contains a hard-coded /mnt/ path"
    assert "/home/" not in server, "server.ts contains a hard-coded /home/ path"


# ---------------------------------------------------------------------------
# Live build verification (only when pnpm is available)
# ---------------------------------------------------------------------------


def _have_pnpm() -> bool:
    return shutil.which("pnpm") is not None


@pytest.mark.skipif(not _have_pnpm(), reason="pnpm not installed")
def test_ui_build_emits_dist_index_html() -> None:
    """
    Run `pnpm --filter @flex-obs/ui build` and verify dist/index.html exists
    and contains the literal 'flex observability' (story §3).
    """
    env = os.environ.copy()
    result = subprocess.run(
        ["pnpm", "--filter", "@flex-obs/ui", "build"],
        cwd=str(OBS_ROOT),
        capture_output=True,
        text=True,
        timeout=240,
        env=env,
    )
    assert result.returncode == 0, (
        f"UI build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    dist_index = OBS_UI / "dist" / "index.html"
    assert dist_index.is_file(), "ui/dist/index.html not produced by build"
    assert "flex observability" in dist_index.read_text()


@pytest.mark.skipif(not _have_pnpm(), reason="pnpm not installed")
def test_api_build_still_compiles_after_static_changes() -> None:
    """
    server.ts must still type-check after adding @fastify/static wiring.
    """
    result = subprocess.run(
        ["pnpm", "--filter", "@flex-obs/api", "build"],
        cwd=str(OBS_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"API build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

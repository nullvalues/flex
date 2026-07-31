"""
Tests for INFRA-306 — Observability API: loopback-honest CORS and abs_path
disclosure gating.

These are structural assertions over the TypeScript sources (there is no TS
test runner in this repo; the compile gate lives in
test_observability_context_api.py::test_typescript_compiles and is reused,
not duplicated, here).

Covers:
- CER-042: `resolveCorsOrigin`/`isLoopbackHost` exist, the wildcard CORS
  origin is no longer unconditional, `FLEX_OBS_ALLOWED_ORIGINS` is wired in,
  `buildServer` takes an explicit host parameter, and the exposure warning
  fires before `app.listen`.
- CER-043: `abs_path` is optional on both interfaces and gated behind
  `?include_path=true`.
- The SPA has no `abs_path`/`/api/user` consumer (evidence of absence).
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FLEX_ROOT = Path(__file__).resolve().parents[2]
OBS_API = FLEX_ROOT / "skills" / "observability" / "api"
SRC = OBS_API / "src"
SERVER_TS = SRC / "server.ts"
USER_TS = SRC / "routes" / "user.ts"
UI_SRC = FLEX_ROOT / "skills" / "observability" / "ui" / "src"
SKILL_MD = FLEX_ROOT / "skills" / "observability" / "SKILL.md"


# ---------------------------------------------------------------------------
# CER-042: CORS policy
# ---------------------------------------------------------------------------

def test_server_exports_isLoopbackHost_and_resolveCorsOrigin() -> None:
    content = SERVER_TS.read_text()
    assert "export function isLoopbackHost" in content, (
        "server.ts does not export isLoopbackHost"
    )
    assert "export function resolveCorsOrigin" in content, (
        "server.ts does not export resolveCorsOrigin"
    )


def test_server_no_longer_hardcodes_wildcard_cors() -> None:
    """The literal `origin: '*',` must not appear in the cors registration;
    the string '*' survives only inside resolveCorsOrigin's loopback branch."""
    content = SERVER_TS.read_text()
    assert "origin: '*'," not in content, (
        "server.ts still hardcodes origin: '*', in the cors registration"
    )

    # Slice the source between the two export function markers and assert
    # only resolveCorsOrigin's body mentions the '*' literal.
    is_loopback_start = content.index("export function isLoopbackHost")
    resolve_start = content.index("export function resolveCorsOrigin")
    build_server_start = content.index("export async function buildServer")

    is_loopback_body = content[is_loopback_start:resolve_start]
    resolve_body = content[resolve_start:build_server_start]
    rest_of_file = content[:is_loopback_start] + content[build_server_start:]

    assert "'*'" not in is_loopback_body, (
        "isLoopbackHost's body unexpectedly references the '*' literal"
    )
    assert "'*'" in resolve_body, (
        "resolveCorsOrigin's body does not reference the '*' literal for its loopback branch"
    )
    assert "'*'" not in rest_of_file, (
        "the '*' CORS literal appears outside resolveCorsOrigin's body"
    )


def test_server_references_allowed_origins_env_var() -> None:
    content = SERVER_TS.read_text()
    assert "FLEX_OBS_ALLOWED_ORIGINS" in content, (
        "server.ts does not reference FLEX_OBS_ALLOWED_ORIGINS"
    )


def test_server_warns_before_listen_when_exposed() -> None:
    content = SERVER_TS.read_text()
    assert "!isLoopbackHost(" in content, (
        "server.ts does not guard a branch with !isLoopbackHost("
    )
    console_error_idx = content.index("console.error(")
    listen_idx = content.index("await app.listen(")
    guard_idx = content.index("!isLoopbackHost(")

    assert guard_idx < listen_idx, (
        "the !isLoopbackHost( guard does not appear before await app.listen("
    )
    # The console.error inside the exposure-warning branch must also precede listen.
    warning_console_error_idx = content.index("console.error(", guard_idx)
    assert warning_console_error_idx < listen_idx, (
        "the exposure-warning console.error does not appear before await app.listen("
    )


def test_buildServer_takes_host_param_and_main_passes_it() -> None:
    content = SERVER_TS.read_text()
    assert "buildServer(host" in content, (
        "buildServer signature/call site does not reference 'buildServer(host'"
    )
    assert "await buildServer(host)" in content, (
        "main() does not call buildServer(host)"
    )


def test_loopback_classification_mirror() -> None:
    """Python mirror of isLoopbackHost's classification table (data-pinned,
    test_p90_correct_for_round_n idiom)."""
    import re

    def is_loopback(host: str) -> bool:
        normalised = host.strip().lower()
        if normalised.startswith("[") and normalised.endswith("]"):
            normalised = normalised[1:-1]
        if normalised in ("localhost", "::1"):
            return True
        return bool(re.match(r"^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$", normalised))

    loopback_hosts = [
        "127.0.0.1",
        "127.1.2.3",
        "::1",
        "[::1]",
        "localhost",
        "LOCALHOST",
        " 127.0.0.1 ",
    ]
    non_loopback_hosts = ["0.0.0.0", "::", "192.168.1.10", "10.0.0.5", ""]

    for host in loopback_hosts:
        assert is_loopback(host), f"expected {host!r} to be classified as loopback"
    for host in non_loopback_hosts:
        assert not is_loopback(host), f"expected {host!r} to NOT be classified as loopback"

    # Assert the TS source implements the same regex/literals.
    content = SERVER_TS.read_text()
    assert r"127\." in content, "server.ts missing the 127\\. loopback regex fragment"
    assert "'localhost'" in content, "server.ts missing the 'localhost' literal"
    assert "'::1'" in content, "server.ts missing the '::1' literal"


# ---------------------------------------------------------------------------
# CER-043: abs_path disclosure gating
# ---------------------------------------------------------------------------

def test_abs_path_optional_exactly_twice_and_never_required() -> None:
    content = USER_TS.read_text()
    assert content.count("abs_path?: string;") == 2, (
        f"expected 'abs_path?: string;' to appear exactly twice, "
        f"found {content.count('abs_path?: string;')}"
    )
    assert "abs_path: string;" not in content, (
        "user.ts still declares abs_path as a required field somewhere"
    )


def test_include_path_gate_wired_into_both_handlers() -> None:
    content = USER_TS.read_text()
    assert "Querystring: { include_path?: string }" in content, (
        "user.ts does not type the querystring with an optional include_path field"
    )
    assert "=== 'true'" in content, (
        "user.ts does not compare include_path with strict === 'true'"
    )
    assert "_request" not in content, (
        "user.ts still binds an unused _request parameter in a handler"
    )


# ---------------------------------------------------------------------------
# UI-absence guard (Ensures 7) — evidence of absence
# ---------------------------------------------------------------------------

def test_ui_has_no_abs_path_or_user_api_consumer() -> None:
    """The SPA must not reference abs_path or /api/user anywhere under
    ui/src — this test fails the day someone adds a consumer without
    revisiting the disclosure gate."""
    matches = []
    for pattern in ("*.ts", "*.tsx"):
        for path in UI_SRC.rglob(pattern):
            text = path.read_text()
            if "abs_path" in text or "/api/user" in text:
                matches.append(str(path.relative_to(FLEX_ROOT)))

    assert matches == [], (
        f"found abs_path or /api/user references in the SPA: {matches}"
    )


# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------

def test_skill_md_documents_the_new_knobs() -> None:
    content = SKILL_MD.read_text()
    assert "FLEX_OBS_ALLOWED_ORIGINS" in content, (
        "SKILL.md does not mention FLEX_OBS_ALLOWED_ORIGINS"
    )
    assert "FLEX_OBS_HOST" in content, (
        "SKILL.md does not mention FLEX_OBS_HOST"
    )
    assert "include_path" in content, (
        "SKILL.md does not mention include_path"
    )

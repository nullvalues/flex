"""Tests for parse_worker_verdict_json (RESOLVER-013).

Verifies fail-closed behaviour: malformed JSON or missing required keys cause
all three gates to return "block:malformed-verdict".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from next_action import parse_worker_verdict_json  # noqa: E402  # type: ignore[import]

_FAIL_CLOSED = {
    "schema": "block:malformed-verdict",
    "auth": "block:malformed-verdict",
    "stub": "block:malformed-verdict",
}


class TestParseWorkerVerdictJson:
    """parse_worker_verdict_json is fail-closed on bad input."""

    def test_all_clean(self) -> None:
        """Valid JSON with all-clean values returns those values unchanged."""
        payload = json.dumps({"schema": "clean", "auth": "clean", "stub": "clean"})
        result = parse_worker_verdict_json(payload)
        assert result == {"schema": "clean", "auth": "clean", "stub": "clean"}

    def test_one_block_value(self) -> None:
        """Valid JSON with one block value is returned as-is."""
        payload = json.dumps(
            {"schema": "block:no-management-ui", "auth": "clean", "stub": "clean"}
        )
        result = parse_worker_verdict_json(payload)
        assert result["schema"] == "block:no-management-ui"
        assert result["auth"] == "clean"
        assert result["stub"] == "clean"

    def test_malformed_json_plain_text(self) -> None:
        """Plain text (not JSON) returns fail-closed map."""
        result = parse_worker_verdict_json("schema: block:reason\nauth: clean")
        assert result == _FAIL_CLOSED

    def test_empty_string(self) -> None:
        """Empty string returns fail-closed map."""
        result = parse_worker_verdict_json("")
        assert result == _FAIL_CLOSED

    def test_missing_schema_key(self) -> None:
        """Valid JSON missing 'schema' key returns fail-closed map."""
        payload = json.dumps({"auth": "clean", "stub": "clean"})
        result = parse_worker_verdict_json(payload)
        assert result == _FAIL_CLOSED

    def test_missing_auth_key(self) -> None:
        """Valid JSON missing 'auth' key returns fail-closed map."""
        payload = json.dumps({"schema": "clean", "stub": "clean"})
        result = parse_worker_verdict_json(payload)
        assert result == _FAIL_CLOSED

    def test_missing_stub_key(self) -> None:
        """Valid JSON missing 'stub' key returns fail-closed map."""
        payload = json.dumps({"schema": "clean", "auth": "clean"})
        result = parse_worker_verdict_json(payload)
        assert result == _FAIL_CLOSED

    def test_extra_keys_stripped(self) -> None:
        """Valid JSON with extra keys returns only schema/auth/stub."""
        payload = json.dumps(
            {
                "schema": "clean",
                "auth": "clean",
                "stub": "clean",
                "extra": "ignored",
            }
        )
        result = parse_worker_verdict_json(payload)
        assert set(result.keys()) == {"schema", "auth", "stub"}
        assert "extra" not in result

    def test_json_array_returns_fail_closed(self) -> None:
        """A JSON array (not object) returns fail-closed map."""
        result = parse_worker_verdict_json(json.dumps(["schema", "auth", "stub"]))
        assert result == _FAIL_CLOSED

    def test_json_null_returns_fail_closed(self) -> None:
        """JSON null returns fail-closed map."""
        result = parse_worker_verdict_json("null")
        assert result == _FAIL_CLOSED

    def test_block_reason_with_colons(self) -> None:
        """Block reason may contain colons and round-trips correctly."""
        payload = json.dumps(
            {
                "schema": "block:reason:with:colons",
                "auth": "clean",
                "stub": "clean",
            }
        )
        result = parse_worker_verdict_json(payload)
        assert result["schema"] == "block:reason:with:colons"

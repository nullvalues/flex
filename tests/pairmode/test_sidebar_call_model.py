"""Tests for sidebar.py call_claude routing (INFRA-121) and fallback (INFRA-122).

Tests verify that call_claude dispatches to _call_anthropic or _call_ollama
based on the FLEX_MODEL_BACKEND environment variable, and that extraction/conflict
call sites fall back to _call_anthropic when the local model returns bad output.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the companion scripts dir to sys.path so we can import sidebar
SIDEBAR_DIR = Path(__file__).parent.parent.parent / "skills" / "companion" / "scripts"
REPO_ROOT = Path(__file__).parent.parent.parent
if str(SIDEBAR_DIR) not in sys.path:
    sys.path.insert(0, str(SIDEBAR_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _import_sidebar():
    """Import (or re-import) sidebar to pick up current module state."""
    if "sidebar" in sys.modules:
        return sys.modules["sidebar"]
    return importlib.import_module("sidebar")


def test_call_claude_defaults_to_anthropic():
    """With no FLEX_MODEL_BACKEND set, call_claude must call _call_anthropic."""
    import sidebar as sb

    # Ensure FLEX_MODEL_BACKEND is not set (or set to anthropic)
    env = {k: v for k, v in os.environ.items() if k != "FLEX_MODEL_BACKEND"}
    env["FLEX_MODEL_BACKEND"] = "anthropic"

    with patch.dict(os.environ, env, clear=True):
        # Re-read the module-level _MODEL_BACKEND by patching it directly
        with patch.object(sb, "_MODEL_BACKEND", "anthropic"):
            with patch.object(sb, "_call_anthropic", return_value="anthropic-result") as mock_anthropic:
                result = sb.call_claude("test prompt", "test system")

    mock_anthropic.assert_called_once()
    assert result == "anthropic-result"


def test_call_claude_routes_to_ollama():
    """With FLEX_MODEL_BACKEND=ollama, call_claude must call _call_ollama."""
    import sidebar as sb

    mock_ollama = MagicMock(return_value="ollama-result")

    with patch.object(sb, "_MODEL_BACKEND", "ollama"):
        with patch.object(sb, "_call_ollama", mock_ollama):
            result = sb.call_claude("test prompt", "test system")

    mock_ollama.assert_called_once()
    call_kwargs = mock_ollama.call_args
    # Check that model and timeout were passed correctly
    assert call_kwargs.kwargs.get("timeout") == 10 or (
        len(call_kwargs.args) >= 3 and call_kwargs.kwargs.get("timeout") == 10
    )
    assert result == "ollama-result"


def test_call_claude_routes_to_ollama_with_correct_model():
    """call_claude in ollama mode must pass _OLLAMA_MODEL and timeout=10."""
    import sidebar as sb

    mock_ollama = MagicMock(return_value="result")

    with patch.object(sb, "_MODEL_BACKEND", "ollama"):
        with patch.object(sb, "_call_ollama", mock_ollama):
            with patch.object(sb, "_OLLAMA_MODEL", "llama3.1:8b"):
                with patch.object(sb, "_OLLAMA_BASE_URL", "http://localhost:11434"):
                    sb.call_claude("prompt", "system")

    mock_ollama.assert_called_once_with(
        "prompt",
        "system",
        "llama3.1:8b",
        base_url="http://localhost:11434",
        timeout=10,
    )


def test_call_claude_returns_none_on_backend_failure():
    """When _call_ollama returns None, call_claude must also return None without raising."""
    import sidebar as sb

    mock_ollama = MagicMock(return_value=None)

    with patch.object(sb, "_MODEL_BACKEND", "ollama"):
        with patch.object(sb, "_call_ollama", mock_ollama):
            result = sb.call_claude("prompt", "system")

    assert result is None


def test_call_claude_falls_back_to_anthropic_when_ollama_unavailable():
    """When _call_ollama is None (import failed), call_claude must use _call_anthropic."""
    import sidebar as sb

    with patch.object(sb, "_MODEL_BACKEND", "ollama"):
        with patch.object(sb, "_call_ollama", None):
            with patch.object(sb, "_call_anthropic", return_value="fallback") as mock_anthropic:
                result = sb.call_claude("prompt", "system")

    mock_anthropic.assert_called_once()
    assert result == "fallback"


# ── INFRA-122: fallback tests ─────────────────────────────────────────────────


def _write_transcript(path, text="hello world"):
    """Write a transcript in the format read_last_messages expects."""
    import json
    path.write_text(
        json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": text},
        }) + "\n"
    )


def test_extraction_falls_back_to_anthropic_on_bad_json(tmp_path):
    """When local model returns bad JSON, extract_incremental retries with _call_anthropic."""
    import sidebar as sb

    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript)

    good_result = json.dumps([{"type": "decision", "text": "use oauth"}])

    with patch.object(sb, "_MODEL_BACKEND", "ollama"):
        with patch.object(sb, "call_claude", return_value="not valid json"):
            with patch.object(sb, "_call_anthropic", return_value=good_result) as mock_anthro:
                result = sb.extract_incremental(str(transcript), [])

    mock_anthro.assert_called_once()
    assert result == [{"type": "decision", "text": "use oauth"}]


def test_extraction_returns_empty_on_double_failure(tmp_path):
    """When both call_claude and _call_anthropic fail, extract_incremental returns []."""
    import sidebar as sb

    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript)

    with patch.object(sb, "_MODEL_BACKEND", "ollama"):
        with patch.object(sb, "call_claude", return_value=None):
            with patch.object(sb, "_call_anthropic", return_value=None):
                result = sb.extract_incremental(str(transcript), [])

    assert result == []


def test_extraction_no_fallback_when_anthropic_backend(tmp_path):
    """When _MODEL_BACKEND==anthropic, bad JSON must NOT trigger a retry."""
    import sidebar as sb

    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript)

    with patch.object(sb, "_MODEL_BACKEND", "anthropic"):
        with patch.object(sb, "call_claude", return_value="not valid json"):
            with patch.object(sb, "_call_anthropic") as mock_anthro:
                result = sb.extract_incremental(str(transcript), [])

    mock_anthro.assert_not_called()
    assert result == []

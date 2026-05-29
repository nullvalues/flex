"""Tests for skills/pairmode/scripts/call_model.py."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Insert the pairmode scripts dir into sys.path so we can import call_model.
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from call_model import call_ollama  # noqa: E402


def _make_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    """Build a minimal mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_body is not None:
        resp.json.return_value = json_body
    return resp


def test_ollama_posts_correct_json_body():
    """call_ollama must POST with model, messages (system+user), and stream=False."""
    mock_resp = _make_response(200, {"message": {"content": "hello"}})
    with patch("call_model.requests.post", return_value=mock_resp) as mock_post:
        call_ollama("hello", "sys", "llama3.1:8b")

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    body = kwargs["json"]

    assert body["model"] == "llama3.1:8b"
    assert body["stream"] is False
    messages = body["messages"]
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": "sys"}
    assert messages[1] == {"role": "user", "content": "hello"}


def test_ollama_returns_message_content():
    """call_ollama must return the content string from the response JSON."""
    mock_resp = _make_response(200, {"message": {"content": "ok"}})
    with patch("call_model.requests.post", return_value=mock_resp):
        result = call_ollama("q", "s", "llama3.1:8b")

    assert result == "ok"


def test_ollama_custom_base_url():
    """call_ollama must use the custom base_url when provided."""
    mock_resp = _make_response(200, {"message": {"content": "done"}})
    with patch("call_model.requests.post", return_value=mock_resp) as mock_post:
        call_ollama("q", "s", "llama3.1:8b", base_url="http://gpu-box:11434")

    url_called = mock_post.call_args[0][0]
    assert url_called == "http://gpu-box:11434/api/chat"


def test_ollama_returns_none_on_connection_error():
    """call_ollama must return None when requests raises ConnectionError."""
    import requests as req_module

    with patch("call_model.requests.post", side_effect=req_module.exceptions.ConnectionError("refused")):
        result = call_ollama("q", "s", "llama3.1:8b")

    assert result is None


def test_ollama_returns_none_on_non_200():
    """call_ollama must return None when the server returns a non-200 status."""
    mock_resp = _make_response(503)
    with patch("call_model.requests.post", return_value=mock_resp):
        result = call_ollama("q", "s", "llama3.1:8b")

    assert result is None

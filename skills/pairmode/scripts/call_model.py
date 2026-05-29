"""call_model.py — thin wrapper for local model backends (Ollama)."""

from __future__ import annotations

import sys

import requests


def call_ollama(
    prompt: str,
    system: str,
    model: str,
    *,
    base_url: str = "http://localhost:11434",
    timeout: int = 10,
) -> str | None:
    """POST a chat request to an Ollama server and return the response text.

    Returns the response text on success, or None on failure.
    No side effects, no global state, no file I/O.
    """
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        print(f"warning: ollama request failed: {exc}", file=sys.stderr)
        return None

    if response.status_code != 200:
        print(
            f"warning: ollama returned HTTP {response.status_code}",
            file=sys.stderr,
        )
        return None

    return response.json()["message"]["content"]

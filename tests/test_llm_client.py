"""Tests for LLM client (no network)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from modules.llm.client import LLMClient, LLMClientError, extract_assistant_text


def test_chat_returns_assistant_content() -> None:
    payload = json.dumps(
        {"choices": [{"message": {"content": "Hello mesh"}}]}
    ).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("modules.llm.client.urlopen", return_value=mock_resp):
        client = LLMClient("http://127.0.0.1:1234/v1", "test-model", timeout_seconds=5)
        assert client.chat("sys", "hi") == "Hello mesh"


def test_prefers_content_over_reasoning() -> None:
    data = {
        "choices": [
            {
                "message": {
                    "content": "12°C in town.",
                    "reasoning_content": "Thinking Process: analyze...",
                }
            }
        ]
    }
    assert extract_assistant_text(data) == "12°C in town."


def test_rejects_reasoning_leak() -> None:
    data = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "content": "",
                    "reasoning_content": "Thinking Process: 1. Analyze the request...",
                },
            }
        ]
    }
    with pytest.raises(LLMClientError, match="length_empty"):
        extract_assistant_text(data)


def test_extract_content_list() -> None:
    data = {"choices": [{"message": {"content": [{"text": "Part one"}, {"text": "two"}]}}]}
    assert "Part one" in extract_assistant_text(data)


def test_chat_empty_choices_raises() -> None:
    payload = json.dumps({"choices": []}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("modules.llm.client.urlopen", return_value=mock_resp):
        client = LLMClient("http://127.0.0.1:1234/v1", "x", timeout_seconds=5)
        with pytest.raises(LLMClientError):
            client.chat("sys", "hi")

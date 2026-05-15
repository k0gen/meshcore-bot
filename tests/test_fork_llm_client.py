"""Tests for fork LLM client (no network)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from fork.service_plugins.llm_client import LLMClient, LLMClientError


def test_list_models_parses_response() -> None:
    payload = json.dumps({"data": [{"id": "llama3.2"}, {"id": "mistral"}]}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("fork.service_plugins.llm_client.urlopen", return_value=mock_resp):
        client = LLMClient("http://127.0.0.1:11434/v1", "llama3.2", timeout_seconds=5)
        assert client.list_models() == ["llama3.2", "mistral"]


def test_chat_returns_assistant_content() -> None:
    payload = json.dumps(
        {"choices": [{"message": {"content": "Hello mesh"}}]}
    ).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("fork.service_plugins.llm_client.urlopen", return_value=mock_resp):
        client = LLMClient("http://127.0.0.1:11434/v1", "llama3.2", timeout_seconds=5)
        assert client.chat("sys", "hi") == "Hello mesh"


def test_chat_empty_choices_raises() -> None:
    payload = json.dumps({"choices": []}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("fork.service_plugins.llm_client.urlopen", return_value=mock_resp):
        client = LLMClient("http://127.0.0.1:11434/v1", "x", timeout_seconds=5)
        with pytest.raises(LLMClientError):
            client.chat("sys", "hi")

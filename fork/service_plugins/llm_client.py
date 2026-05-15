#!/usr/bin/env python3
"""OpenAI-compatible chat client for Ollama and LM Studio."""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMClientError(Exception):
    """LLM HTTP or parse failure."""


class LLMClient:
    """Minimal client for /v1/chat/completions and /v1/models."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        logger: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.logger = logger

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            raise LLMClientError(f"HTTP {e.code} from {url}: {detail}") from e
        except URLError as e:
            raise LLMClientError(f"Cannot reach {url}: {e}") from e
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise LLMClientError(f"Invalid JSON from {url}") from e

    def list_models(self) -> list[str]:
        """Return model ids from GET /models."""
        data = self._request("GET", "/models")
        models = data.get("data") or []
        ids: list[str] = []
        for item in models:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
        return ids

    def chat(self, system_prompt: str, user_message: str) -> str:
        """Single user turn; returns assistant text."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
        }
        data = self._request("POST", "/chat/completions", payload)
        choices = data.get("choices") or []
        if not choices:
            raise LLMClientError("Empty choices in chat response")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise LLMClientError("No content in chat response")
        return str(content).strip()

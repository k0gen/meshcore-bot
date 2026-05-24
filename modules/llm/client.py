#!/usr/bin/env python3
"""OpenAI-compatible chat client for Ollama and LM Studio."""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from modules.llm.persona import MESH_COMPACT_SYSTEM
from modules.llm.sanitize import looks_like_reasoning_leak, sanitize_llm_reply


class LLMClientError(Exception):
    """LLM HTTP or parse failure."""


def extract_assistant_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        top = (data.get("message") or {}).get("content")
        if top:
            return _finalize_extracted(_normalize_content(top))
        raise LLMClientError("Empty choices in chat response")

    choice = choices[0]
    finish = choice.get("finish_reason") or choice.get("finishReason")
    message = choice.get("message") or choice.get("delta") or {}

    for key in ("content", "text"):
        val = message.get(key)
        if val:
            text = _finalize_extracted(_normalize_content(val))
            if text:
                return text

    val = choice.get("text")
    if val:
        text = _finalize_extracted(_normalize_content(val))
        if text:
            return text

    for key in ("reasoning_content", "reasoning"):
        val = message.get(key)
        if not val:
            continue
        text = _finalize_extracted(_normalize_content(val))
        if text and not looks_like_reasoning_leak(text):
            return text

    detail = f"finish_reason={finish!r}" if finish else "no text fields"
    if finish == "length":
        raise LLMClientError(f"length_empty: {detail}")
    raise LLMClientError(f"No content in chat response ({detail})")


def _finalize_extracted(text: str) -> str:
    cleaned = sanitize_llm_reply(text)
    if cleaned and not looks_like_reasoning_leak(cleaned):
        return cleaned
    return ""


def _normalize_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        chunks: list[str] = []
        for item in value:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                t = item.get("text") or item.get("content")
                if t:
                    chunks.append(str(t))
        return "\n".join(chunks).strip()
    return str(value).strip()


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        logger: Any = None,
        *,
        disable_reasoning: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.logger = logger
        self.disable_reasoning = disable_reasoning

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

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int | None = 512,
        temperature: float | None = 0.7,
    ) -> str:
        base = max(128, max_tokens or 512)
        attempts: list[tuple[str, str, int, float | None]] = [
            (system_prompt, user_message, base, temperature),
            (MESH_COMPACT_SYSTEM, user_message, min(1024, base * 2), 0.5),
            ("", f"Reply in one short sentence:\n{user_message}", min(1024, base * 2), 0.4),
            ("", user_message, min(1536, base * 3), 0.3),
        ]
        last_error: LLMClientError | None = None
        for sys_p, user_p, tok, temp in attempts:
            payload = self._build_payload(sys_p, user_p, tok, temp)
            try:
                data = self._request("POST", "/chat/completions", payload)
                return extract_assistant_text(data)
            except LLMClientError as e:
                last_error = e
                if self.logger:
                    self.logger.debug("LLM attempt failed (max_tokens=%s): %s", tok, e)
                if "length_empty" not in str(e) and "No content" not in str(e):
                    break
        assert last_error is not None
        raise last_error

    def _build_payload(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": user_message.strip()})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if self.disable_reasoning:
            payload["extra_body"] = {
                "enable_thinking": False,
                "reasoning_effort": "none",
            }
        return payload

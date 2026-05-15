#!/usr/bin/env python3
"""
AI reply service (fork) — Ollama / LM Studio via OpenAI-compatible API.

Loads as a local service when [Bot] local_dir_path = fork and [AI_Reply] enabled = true.
Automatic mesh replies are not implemented yet; this plugin validates config and LLM connectivity.
"""

from __future__ import annotations

from typing import Any, Optional

from modules.service_plugins.base_service import BaseServicePlugin

from .llm_client import LLMClient, LLMClientError

_DEFAULT_BASE_URLS = {
    "ollama": "http://127.0.0.1:11434/v1",
    "openai_compatible": "http://127.0.0.1:1234/v1",
}


class AIReplyService(BaseServicePlugin):
    """Local LLM integration scaffold for MeshCore auto-replies."""

    config_section = "AI_Reply"
    description = "Local LLM (Ollama / LM Studio) — experimental auto-reply scaffold"
    name = "ai_reply"

    def __init__(self, bot: Any) -> None:
        super().__init__(bot)
        self._client: Optional[LLMClient] = None
        self.trigger_keywords: list[str] = []
        self.max_reply_length = 200
        self.system_prompt = ""

        if not bot.config.has_section("AI_Reply"):
            self.enabled = False
            return

        self.enabled = bot.config.getboolean("AI_Reply", "enabled", fallback=False)
        if not self.enabled:
            return

        provider = (
            bot.config.get("AI_Reply", "provider", fallback="ollama").strip().lower()
        )
        base_url = (
            bot.config.get("AI_Reply", "base_url", fallback="").strip()
            or _DEFAULT_BASE_URLS.get(provider, _DEFAULT_BASE_URLS["ollama"])
        )
        model = bot.config.get("AI_Reply", "model", fallback="").strip()
        if not model:
            self.logger.error("AI_Reply: model is required when enabled")
            self.enabled = False
            return

        timeout = bot.config.getfloat("AI_Reply", "request_timeout_seconds", fallback=120.0)
        self.max_reply_length = bot.config.getint("AI_Reply", "max_reply_length", fallback=200)
        raw_kw = bot.config.get("AI_Reply", "trigger_keywords", fallback="ai")
        self.trigger_keywords = [k.strip().lower() for k in raw_kw.split(",") if k.strip()]
        self.system_prompt = (
            bot.config.get(
                "AI_Reply",
                "system_prompt",
                fallback="You are a helpful assistant on a MeshCore mesh. Be brief.",
            )
            or ""
        ).strip()

        self._client = LLMClient(
            base_url=base_url,
            model=model,
            timeout_seconds=timeout,
            logger=self.logger,
        )
        self.logger.info(
            "AI_Reply: configured provider=%s base_url=%s model=%s triggers=%s",
            provider,
            base_url,
            model,
            self.trigger_keywords,
        )

    async def start(self) -> None:
        if not self.enabled or self._client is None:
            return
        self._running = True
        try:
            models = self._client.list_models()
            if models and self._client.model not in models:
                self.logger.warning(
                    "AI_Reply: model %r not in %s — generation may fail",
                    self._client.model,
                    models[:8],
                )
            else:
                self.logger.info(
                    "AI_Reply: LLM reachable (%d model(s) reported)",
                    len(models),
                )
        except LLMClientError as e:
            self.logger.error("AI_Reply: LLM health check failed: %s", e)
        self.logger.info(
            "AI_Reply: auto-reply hook not active yet — enable after field testing"
        )

    async def stop(self) -> None:
        self._running = False

    def truncate_for_mesh(self, text: str) -> str:
        if len(text) <= self.max_reply_length:
            return text
        return text[: self.max_reply_length - 3].rstrip() + "..."

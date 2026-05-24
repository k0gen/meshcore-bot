#!/usr/bin/env python3
"""
LLM command — local model replies via Ollama or LM Studio.

Triggers: ``llm <question>`` or ``@[bot_name]`` from [Bot] bot_name.
Configure in [Llm_Command] (enabled, provider, model, …) like other commands.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from ..llm.client import LLMClient, LLMClientError
from ..llm import config as llm_cfg
from ..llm.mentions import (
    configured_bot_name,
    extract_llm_prompt,
    install_mention_tracking,
    is_bracket_mention,
    message_had_bot_mention,
)
from ..llm.mesh_text import fit_mesh_reply, truncate_to_utf8_bytes
from ..llm.persona import load_mesh_system_prompt
from ..llm.sanitize import looks_like_reasoning_leak, sanitize_llm_reply
from ..llm.static_replies import try_static_reply
from ..llm.tools import (
    build_user_message,
    format_prefix_chunks,
    gather_tool_context,
    try_direct_tool_reply,
)
from ..models import MeshMessage
from .base_command import BaseCommand

_DEFAULT_BASE_URLS = {
    "ollama": "http://127.0.0.1:11434/v1",
    "lm_studio": "http://127.0.0.1:1234/v1",
    "openai_compatible": "http://127.0.0.1:1234/v1",
}


class LlmCommand(BaseCommand):
    name = "llm"
    keywords = ["llm"]
    description = "Local LLM reply (Ollama / LM Studio); also @[bot_name]"
    category = "ai"
    requires_internet = True

    short_description = "Ask a local LLM (Ollama or LM Studio)"
    usage = "llm <question>"
    examples = ["llm what is meshcore?", "llm weather today"]

    def __init__(self, bot) -> None:
        super().__init__(bot)
        self._client: Optional[LLMClient] = None
        self._ready = False
        self._bot_name = configured_bot_name(bot)
        self.max_reply_bytes = 120
        self.max_chunks = 2
        self.max_tokens = 512
        self.temperature = 0.7
        self.system_prompt = ""
        self.use_tools = True
        self.direct_tool_reply = True

        self.llm_enabled = self.get_config_value(
            "Llm_Command", "enabled", fallback=False, value_type="bool"
        )
        if not self.llm_enabled or not llm_cfg.has_section(bot):
            return

        provider = llm_cfg.get_str(bot, "provider", "ollama").lower()
        base_url = llm_cfg.get_str(bot, "base_url") or _DEFAULT_BASE_URLS.get(
            provider, _DEFAULT_BASE_URLS["ollama"]
        )
        model = llm_cfg.get_str(bot, "model")
        if not model:
            self.logger.error("Llm_Command: model is required when enabled")
            return

        self.max_reply_bytes = llm_cfg.get_int(bot, "max_reply_bytes", 120)
        self.max_chunks = min(2, max(1, llm_cfg.get_int(bot, "max_chunks", 2)))
        self.max_tokens = llm_cfg.get_int(bot, "max_tokens", 512)
        self.temperature = llm_cfg.get_float(bot, "temperature", 0.7)
        self.use_tools = llm_cfg.get_bool(bot, "enable_tools", True)
        self.direct_tool_reply = llm_cfg.get_bool(bot, "direct_tool_reply", True)
        self.system_prompt = load_mesh_system_prompt(bot)
        timeout = llm_cfg.get_float(bot, "request_timeout_seconds", 120.0)
        disable_reasoning = llm_cfg.get_bool(bot, "disable_reasoning", True)
        self._client = LLMClient(
            base_url=base_url,
            model=model,
            timeout_seconds=timeout,
            logger=self.logger,
            disable_reasoning=disable_reasoning,
        )
        install_mention_tracking(bot)
        self._ready = True
        self.logger.info(
            "LLM command enabled: provider=%s model=%s tools=%s",
            provider,
            model,
            self.use_tools,
        )

    def can_execute(self, message: MeshMessage, skip_channel_check: bool = False) -> bool:
        if not self.llm_enabled or not self._ready or self._client is None:
            return False
        return super().can_execute(message, skip_channel_check=skip_channel_check)

    def matches_custom_syntax(self, message: MeshMessage) -> bool:
        if message_had_bot_mention(message):
            return True
        if is_bracket_mention(message.content, self._bot_name):
            return True
        return False

    async def execute(self, message: MeshMessage) -> bool:
        prompt = extract_llm_prompt(
            message.content,
            keyword="llm",
            bot_name=self._bot_name,
            bot_mention_triggered=message_had_bot_mention(message),
        )
        if prompt is None:
            return False

        tool_ctx = None
        if self.use_tools:
            tool_ctx = await gather_tool_context(self.bot, message, prompt)

        mesh_limit = self.bot.command_manager.get_max_message_length(message)
        max_bytes = min(self.max_reply_bytes, mesh_limit)

        if tool_ctx and tool_ctx.label == "prefix" and tool_ctx.raw and "No prefix" not in tool_ctx.raw:
            chunks = format_prefix_chunks(tool_ctx.raw, max_bytes, self.max_chunks)
            if chunks:
                if len(chunks) == 1:
                    return await self.send_response(message, chunks[0])
                return await self.send_response_chunked(
                    message, chunks, skip_user_rate_limit_first=False
                )

        if tool_ctx and self.direct_tool_reply:
            direct = try_direct_tool_reply(tool_ctx, max_bytes)
            if direct:
                return await self.send_response(message, direct)

        static = try_static_reply(prompt, max_bytes, bot_name=self._bot_name)
        if static and not tool_ctx:
            return await self.send_response(message, static)

        user_message = build_user_message(prompt, tool_ctx)

        try:
            reply = await asyncio.to_thread(
                self._client.chat,
                self.system_prompt,
                user_message,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except LLMClientError as e:
            self.logger.error("LLM command: %s", e)
            if tool_ctx and tool_ctx.raw:
                direct = try_direct_tool_reply(tool_ctx, max_bytes)
                if direct:
                    return await self.send_response(message, direct)
            static = try_static_reply(prompt, max_bytes, bot_name=self._bot_name)
            if static:
                return await self.send_response(message, static)
            err_text = _friendly_llm_error(e)
            return await self.send_response(
                message, truncate_to_utf8_bytes(err_text, max_bytes)
            )

        reply = sanitize_llm_reply(reply.strip())
        if (not reply or looks_like_reasoning_leak(reply)) and tool_ctx:
            direct = try_direct_tool_reply(tool_ctx, max_bytes)
            if direct:
                return await self.send_response(message, direct)

        chunks = fit_mesh_reply(reply, max_bytes, max_chunks=self.max_chunks)
        if not chunks:
            if tool_ctx:
                direct = try_direct_tool_reply(tool_ctx, max_bytes)
                chunks = [direct or truncate_to_utf8_bytes("No reply.", max_bytes)]
            else:
                chunks = [truncate_to_utf8_bytes("No reply.", max_bytes)]

        if len(chunks) == 1:
            return await self.send_response(message, chunks[0])
        return await self.send_response_chunked(message, chunks, skip_user_rate_limit_first=False)


def _friendly_llm_error(exc: LLMClientError) -> str:
    msg = str(exc)
    if "length_empty" in msg or "finish_reason='length'" in msg:
        return "LLM token limit hit — try a shorter question or raise max_tokens."
    if "Cannot reach" in msg:
        return "LLM offline — check Ollama / LM Studio."
    return "LLM unavailable — try again later."

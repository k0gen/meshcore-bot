#!/usr/bin/env python3
"""
AI reply service (fork) — Ollama / LM Studio via OpenAI-compatible API.

Trigger: keyword ``lm`` (e.g. ``lm what is meshcore?``).
Respects [Channels] monitor_channels, respond_to_dms, and channel_keywords like other bot triggers.
"""

from __future__ import annotations

import asyncio
import copy
import re
import time
from typing import Any, Optional

from meshcore import EventType

from modules.models import MeshMessage
from modules.service_plugins.base_service import BaseServicePlugin

from .llm_client import LLMClient, LLMClientError
from .mesh_text import extract_lm_prompt, split_utf8_chunks, truncate_to_utf8_bytes

_DEFAULT_BASE_URLS = {
    "ollama": "http://127.0.0.1:11434/v1",
    "lm_studio": "http://127.0.0.1:1234/v1",
    "openai_compatible": "http://127.0.0.1:1234/v1",
}


class AIReplyService(BaseServicePlugin):
    """Local LLM auto-reply on mesh trigger ``lm``."""

    config_section = "AI_Reply"
    description = "Local LLM (Ollama / LM Studio) — auto-reply on lm trigger"
    name = "ai_reply"

    def __init__(self, bot: Any) -> None:
        super().__init__(bot)
        self._client: Optional[LLMClient] = None
        self.trigger_keyword = "lm"
        self.system_prompt = ""
        self._handler_installed = False
        self._handler_lock = asyncio.Lock()
        self._in_flight: set[str] = set()

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
        raw_kw = bot.config.get("AI_Reply", "trigger_keyword", fallback="lm").strip().lower()
        self.trigger_keyword = raw_kw or "lm"
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
            "AI_Reply: provider=%s base_url=%s model=%s trigger=%s",
            provider,
            base_url,
            model,
            self.trigger_keyword,
        )

    async def start(self) -> None:
        if not self.enabled or self._client is None:
            return

        if not getattr(self.bot, "meshcore", None):
            self.logger.error("AI_Reply: meshcore not available")
            return

        async with self._handler_lock:
            if self._handler_installed:
                self._running = True
                return
            self.bot.meshcore.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_event)
            self.bot.meshcore.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_event)
            self._handler_installed = True
            self._running = True

        try:
            models = self._client.list_models()
            self.logger.info("AI_Reply: LLM reachable (%d model(s))", len(models))
        except LLMClientError as e:
            self.logger.error("AI_Reply: LLM health check failed: %s", e)

        self.logger.info("AI_Reply: listening for trigger %r", self.trigger_keyword)

    async def stop(self) -> None:
        self._running = False

    def _bot_display_name(self) -> str:
        return (self.bot.config.get("Bot", "bot_name", fallback="Bot") or "Bot").strip()

    def _is_own_message(self, sender_id: str) -> bool:
        return sender_id.strip().lower() == self._bot_display_name().lower()

    def _message_allowed(self, message: MeshMessage) -> bool:
        cm = self.bot.command_manager
        trigger = self.trigger_keyword
        if message.is_dm:
            if not self.bot.config.getboolean("Channels", "respond_to_dms", fallback=True):
                return False
            return True
        if not message.channel or message.channel not in cm.monitor_channels:
            return False
        return cm._is_channel_trigger_allowed(trigger, message)

    def _parse_channel_payload(self, payload: dict[str, Any]) -> tuple[str, str, str, Optional[str]]:
        text = payload.get("text", "") or ""
        sender_id = "Channel User"
        message_content = text.strip()
        if ":" in text and not text.startswith(":"):
            parts = text.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                sender_id = parts[0].strip()
                message_content = parts[1].strip()
        channel_idx = payload.get("channel_idx", 0)
        channel_name = self.bot.channel_manager.get_channel_name(channel_idx)
        reply_scope: Optional[str] = None
        route_type = payload.get("route_type")
        if route_type is not None:
            scope_raw = payload.get("flood_scope") or payload.get("scope") or ""
            if scope_raw:
                reply_scope = str(scope_raw).strip()
        return sender_id, message_content, channel_name, reply_scope

    def _build_mesh_message(
        self,
        *,
        content: str,
        sender_id: str,
        sender_pubkey: str,
        channel: Optional[str],
        is_dm: bool,
        reply_scope: Optional[str] = None,
    ) -> MeshMessage:
        return MeshMessage(
            content=content,
            sender_id=sender_id,
            sender_pubkey=sender_pubkey or sender_id,
            channel=channel,
            is_dm=is_dm,
            reply_scope=reply_scope,
        )

    async def _on_channel_event(self, event: Any, metadata: Any = None) -> None:
        if not self._running:
            return
        try:
            payload = copy.deepcopy(event.payload) if hasattr(event, "payload") else None
            if not payload:
                return
            asyncio.create_task(self._handle_channel_payload(payload))
        except Exception as e:
            self.logger.error("AI_Reply: channel schedule error: %s", e, exc_info=True)

    async def _on_contact_event(self, event: Any, metadata: Any = None) -> None:
        if not self._running:
            return
        try:
            payload = copy.deepcopy(event.payload) if hasattr(event, "payload") else None
            if not payload:
                return
            asyncio.create_task(self._handle_contact_payload(payload))
        except Exception as e:
            self.logger.error("AI_Reply: contact schedule error: %s", e, exc_info=True)

    async def _handle_channel_payload(self, payload: dict[str, Any]) -> None:
        sender_id, content, channel_name, reply_scope = self._parse_channel_payload(payload)
        if self._is_own_message(sender_id):
            return
        prefix = self.bot.command_manager.command_prefix
        if self.trigger_keyword != "lm":
            prompt = self._extract_custom_trigger(content, prefix)
        else:
            prompt = extract_lm_prompt(content, prefix)
        if prompt is None:
            return
        pubkey = payload.get("pubkey_prefix", "") or sender_id
        message = self._build_mesh_message(
            content=content,
            sender_id=sender_id,
            sender_pubkey=pubkey,
            channel=channel_name,
            is_dm=False,
            reply_scope=reply_scope,
        )
        await self._handle_trigger(message, prompt)

    async def _handle_contact_payload(self, payload: dict[str, Any]) -> None:
        content = (payload.get("text", "") or "").strip()
        sender_id = payload.get("pubkey_prefix", "") or "Unknown"
        sender_name = sender_id
        if hasattr(self.bot, "meshcore") and self.bot.meshcore.contacts:
            for _k, contact_data in self.bot.meshcore.contacts.items():
                pk = contact_data.get("public_key", "")
                if pk.startswith(sender_id):
                    sender_name = contact_data.get("name") or contact_data.get("adv_name") or sender_id
                    sender_id = pk
                    break
        if self._is_own_message(sender_name):
            return
        prefix = self.bot.command_manager.command_prefix
        if self.trigger_keyword != "lm":
            prompt = self._extract_custom_trigger(content, prefix)
        else:
            prompt = extract_lm_prompt(content, prefix)
        if prompt is None:
            return
        message = self._build_mesh_message(
            content=content,
            sender_id=sender_name,
            sender_pubkey=sender_id,
            channel=None,
            is_dm=True,
        )
        await self._handle_trigger(message, prompt)

    def _extract_custom_trigger(self, content: str, command_prefix: str) -> str | None:
        text = content.strip()
        if command_prefix and text.startswith(command_prefix):
            text = text[len(command_prefix) :].strip()
        elif not command_prefix and text.startswith("!"):
            text = text[1:].strip()
        kw = re.escape(self.trigger_keyword)
        m = re.match(rf"^{kw}(?:\s+|:|$)(.*)$", text.strip(), re.IGNORECASE | re.DOTALL)
        if not m:
            return None
        prompt = (m.group(1) or "").strip()
        return prompt if prompt else "(no question)"

    async def _handle_trigger(self, message: MeshMessage, prompt: str) -> None:
        if not self._message_allowed(message):
            self.logger.debug(
                "AI_Reply: ignored (channel/DM policy) from %s",
                message.sender_id,
            )
            return

        dedupe_key = f"{message.sender_id}:{message.channel or 'dm'}:{int(time.time()) // 30}"
        if dedupe_key in self._in_flight:
            return
        self._in_flight.add(dedupe_key)
        try:
            if self._client is None:
                return
            self.logger.info(
                "AI_Reply: lm trigger from %s (%s)",
                message.sender_id,
                "DM" if message.is_dm else message.channel,
            )
            reply = await asyncio.to_thread(
                self._client.chat,
                self.system_prompt,
                prompt,
            )
            max_bytes = self.bot.command_manager.get_max_message_length(message)
            chunks = split_utf8_chunks(reply.strip(), max_bytes)
            if not chunks:
                chunks = [truncate_to_utf8_bytes("No response.", max_bytes)]
            ok = await self.bot.command_manager.send_response_chunked(
                message,
                chunks,
                skip_user_rate_limit_first=False,
            )
            if not ok:
                self.logger.warning("AI_Reply: failed to send response")
        except LLMClientError as e:
            self.logger.error("AI_Reply: LLM error: %s", e)
            err_max = self.bot.command_manager.get_max_message_length(message)
            err_text = truncate_to_utf8_bytes(f"LM error: {e}", err_max)
            await self.bot.command_manager.send_response_chunked(
                message,
                [err_text],
                skip_user_rate_limit_first=False,
            )
        except Exception as e:
            self.logger.error("AI_Reply: unexpected error: %s", e, exc_info=True)
        finally:
            self._in_flight.discard(dedupe_key)

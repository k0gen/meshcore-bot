#!/usr/bin/env python3
"""Bot name mention detection and tracking for the llm command."""

from __future__ import annotations

import re

_ATTR = "_bot_mention_for_llm"
_PATCHED = "_llm_mention_tracking_patched"


def configured_bot_name(bot) -> str:
    return (bot.config.get("Bot", "bot_name", fallback="Bot") or "Bot").strip()


def bracket_mention_pattern(bot_name: str) -> re.Pattern[str]:
    escaped = re.escape(bot_name.strip())
    return re.compile(rf"@\[{escaped}\]", re.IGNORECASE)


def is_bracket_mention(text: str, bot_name: str) -> bool:
    if not text or not bot_name.strip():
        return False
    return bool(bracket_mention_pattern(bot_name).search(text))


def strip_bracket_mention(text: str, bot_name: str) -> str:
    if not text:
        return ""
    cleaned = bracket_mention_pattern(bot_name).sub(" ", text)
    cleaned = re.sub(r"\s+([?.!,;:])", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_llm_prompt(
    content: str,
    *,
    keyword: str = "llm",
    bot_name: str = "",
    bot_mention_triggered: bool = False,
) -> str | None:
    text = content.strip()
    if not text and not bot_mention_triggered:
        return None

    kw = (keyword or "llm").lower()
    lower = text.lower()

    has_kw = lower == kw or lower.startswith(kw + " ") or lower.startswith(kw + ":")
    has_mention = bot_mention_triggered or (
        bool(bot_name.strip()) and is_bracket_mention(text, bot_name)
    )

    if not has_kw and not has_mention:
        return None

    prompt = text
    if bot_name.strip():
        prompt = strip_bracket_mention(prompt, bot_name)
    if has_kw:
        prompt = _strip_leading_keyword(prompt, kw)

    prompt = prompt.strip()
    return prompt if prompt else "(no question)"


def _strip_leading_keyword(text: str, keyword: str) -> str:
    t = text.strip()
    kw = keyword.lower()
    if t.lower() == kw:
        return ""
    if t.lower().startswith(kw + " "):
        return t[len(keyword) :].strip()
    if t.lower().startswith(kw + ":"):
        return t[len(keyword) + 1 :].strip()
    return t


def message_had_bot_mention(message) -> bool:
    return bool(getattr(message, _ATTR, False))


def install_mention_tracking(bot) -> None:
    handler = getattr(bot, "message_handler", None)
    if handler is None or getattr(handler, _PATCHED, False):
        return

    original = handler.process_message

    async def process_message_with_mention_flag(message):
        setattr(message, _ATTR, False)
        if not message.is_dm:
            mode = bot.config.get("Bot", "respond_to_mentions", fallback="also").strip().lower()
            if mode in ("also", "only"):
                bot_name = configured_bot_name(bot)
                if is_bracket_mention(message.content, bot_name):
                    setattr(message, _ATTR, True)
        await original(message)

    handler.process_message = process_message_with_mention_flag
    setattr(handler, _PATCHED, True)

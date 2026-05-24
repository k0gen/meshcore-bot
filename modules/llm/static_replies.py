#!/usr/bin/env python3
"""Short canned replies when LLM fails (no API call)."""

from __future__ import annotations

import re

from modules.llm.mesh_text import truncate_to_utf8_bytes

_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(linux|unix|free\s+-?h|memory|ram)", re.I),
        "On Linux run: free -h",
    ),
    (
        re.compile(r"^(hi|hello|hey|cześć|czesc|hej)[\s!.?]*$", re.I),
        "Hi! Ask with: llm <question>",
    ),
    (
        re.compile(r"what is mesh|co to jest mesh", re.I),
        "MeshCore is a LoRa mesh for short text messages.",
    ),
]


def try_static_reply(prompt: str, max_bytes: int, *, bot_name: str = "Bot") -> str | None:
    text = (prompt or "").strip()
    if not text:
        return None
    if re.search(r"where do you live|gdzie mieszkasz", text, re.I):
        return truncate_to_utf8_bytes(
            f"I'm {bot_name}, a mesh bot — I live on the radio network.",
            max_bytes,
        )
    for pattern, answer in _RULES:
        if pattern.search(text):
            return truncate_to_utf8_bytes(answer, max_bytes)
    return None

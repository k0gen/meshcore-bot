#!/usr/bin/env python3
"""Mesh message length helpers (UTF-8 byte budgets)."""

from __future__ import annotations

import re


def utf8_byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def truncate_to_utf8_bytes(text: str, max_bytes: int, ellipsis: str = "...") -> str:
    if max_bytes <= 0:
        return ""
    if utf8_byte_len(text) <= max_bytes:
        return text
    ell_b = ellipsis.encode("utf-8")
    if len(ell_b) >= max_bytes:
        return ellipsis.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    available = max_bytes - len(ell_b)
    truncated = text.encode("utf-8")[:available].decode("utf-8", errors="ignore")
    return truncated.rstrip() + ellipsis


def split_utf8_chunks(text: str, max_bytes: int) -> list[str]:
    """Split text into chunks each fitting within max_bytes UTF-8."""
    if not text:
        return []
    chunks: list[str] = []
    remaining = text
    while remaining:
        if utf8_byte_len(remaining) <= max_bytes:
            chunks.append(remaining)
            break
        piece = truncate_to_utf8_bytes(remaining, max_bytes, ellipsis="")
        if not piece:
            break
        chunks.append(piece)
        remaining = remaining[len(piece) :].lstrip()
    return chunks or [truncate_to_utf8_bytes(text, max_bytes)]


_LM_TRIGGER_RE = re.compile(
    r"^lm(?:\s+|:|$)(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def extract_lm_prompt(content: str, command_prefix: str = "") -> str | None:
    """Return user prompt if message triggers local LLM (keyword ``lm``), else None."""
    text = content.strip()
    if command_prefix and text.startswith(command_prefix):
        text = text[len(command_prefix) :].strip()
    elif not command_prefix and text.startswith("!"):
        text = text[1:].strip()
    m = _LM_TRIGGER_RE.match(text.strip())
    if not m:
        return None
    prompt = (m.group(1) or "").strip()
    return prompt if prompt else "(no question)"

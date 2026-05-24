#!/usr/bin/env python3
"""Mesh message length helpers (UTF-8 byte budgets)."""

from __future__ import annotations

import re


def utf8_byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def utf8_safe_prefix(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    end = max_bytes
    while end > 0:
        try:
            return raw[:end].decode("utf-8")
        except UnicodeDecodeError:
            end -= 1
    return ""


def truncate_to_utf8_bytes(text: str, max_bytes: int, ellipsis: str = "...") -> str:
    if max_bytes <= 0:
        return ""
    if utf8_byte_len(text) <= max_bytes:
        return text
    ell_b = ellipsis.encode("utf-8")
    if len(ell_b) >= max_bytes:
        return utf8_safe_prefix(ellipsis, max_bytes)
    available = max_bytes - len(ell_b)
    truncated = utf8_safe_prefix(text, available).rstrip()
    return truncated + ellipsis


def _break_at_word(text: str, max_bytes: int) -> str:
    if utf8_byte_len(text) <= max_bytes:
        return text
    chunk = utf8_safe_prefix(text, max_bytes)
    if " " not in chunk:
        return chunk
    last_space = chunk.rfind(" ")
    if last_space <= 0:
        return chunk
    return chunk[:last_space].rstrip()


def fit_mesh_reply(text: str, max_bytes: int, *, max_chunks: int = 1) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    if max_chunks <= 1 or utf8_byte_len(cleaned) <= max_bytes:
        return [truncate_to_utf8_bytes(_break_at_word(cleaned, max_bytes), max_bytes)]

    chunks: list[str] = []
    remaining = cleaned
    while remaining and len(chunks) < max_chunks:
        if utf8_byte_len(remaining) <= max_bytes:
            chunks.append(remaining)
            remaining = ""
            break
        piece = _break_at_word(remaining, max_bytes)
        if not piece:
            piece = utf8_safe_prefix(remaining, max_bytes)
        if not piece:
            break
        chunks.append(piece)
        remaining = remaining[len(piece) :].lstrip()

    if remaining:
        if len(chunks) < max_chunks:
            chunks.append(
                truncate_to_utf8_bytes(_break_at_word(remaining, max_bytes), max_bytes)
            )
        elif chunks:
            merged = f"{chunks[-1]} {remaining}"
            chunks[-1] = truncate_to_utf8_bytes(
                _break_at_word(merged, max_bytes), max_bytes
            )
    return chunks or [truncate_to_utf8_bytes(cleaned, max_bytes)]

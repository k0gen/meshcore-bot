#!/usr/bin/env python3
"""Strip chain-of-thought / reasoning leaks from LLM output before mesh send."""

from __future__ import annotations

import re

_THINKING_START = re.compile(
    r"(?is)^\s*(thinking\s*process|chain\s*of\s*thought|analysis|reasoning)\s*[:.]?\s*"
)
_THINKING_BLOCK = re.compile(
    r"(?is)\b(thinking\s*process|chain\s*of\s*thought)\s*[:.]?\s*"
)
_STEP_LIST = re.compile(r"(?im)^\s*\d+\.\s+\*\*[^*]+\*\*:")
_MARKDOWN_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_BACKTICKS = re.compile(r"`+")
_TOOL_NARRATION = re.compile(
    r"(?is)(simulate|should\s+simulate|identify\s+the\s+tool|requires\s+checking)"
)


def sanitize_llm_reply(text: str) -> str:
    if not text or not text.strip():
        return ""

    out = text.strip()
    out = _THINKING_START.sub("", out)
    out = _THINKING_BLOCK.sub("", out)
    out = _STEP_LIST.sub("", out)
    out = _MARKDOWN_BOLD.sub(r"\1", out)
    out = _BACKTICKS.sub("", out)

    if _TOOL_NARRATION.search(out) and len(out) > 80:
        return ""

    if looks_like_reasoning_leak(out):
        return ""

    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    kept: list[str] = []
    for ln in lines:
        low = ln.lower()
        if low.startswith(
            (
                "thinking process",
                "analyze the request",
                "identify the tool",
                "identify the persona",
                "determine the",
            )
        ):
            continue
        if re.match(r"^\d+\.\s", ln) and ("request" in low or "tool" in low or "action" in low):
            continue
        kept.append(ln)

    out = " ".join(kept) if kept else out
    return re.sub(r"\s+", " ", out).strip()


def looks_like_reasoning_leak(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    markers = (
        "thinking process",
        "analyze the request",
        "identify the tool",
        "identify the persona",
        "determine the required output",
        "output format:",
        "meshcore (lora)",
        "constraints:",
        "chain of thought",
        "should simulate",
        "no planning",
        "no english",
    )
    return any(m in low for m in markers)

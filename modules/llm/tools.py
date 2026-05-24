#!/usr/bin/env python3
"""Rule-based tools: run bot commands / DB lookups before LLM summarization."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Optional

from modules.llm import config as llm_cfg
from modules.llm.mesh_text import fit_mesh_reply, truncate_to_utf8_bytes
from modules.models import MeshMessage
from modules.utils import calculate_distance

_WEATHER_RE = re.compile(
    r"\b(pogod\w*|weather|temperatur\w*|deszcz|wiatr|parasol\w*|upał\w*|zimno|mróz|forecast)\b",
    re.IGNORECASE,
)
_REPEATER_RE = re.compile(
    r"\b(nadajnik\w*|repeater\w*|przemiennik\w*|w\s+okolic\w*|nearby)\b",
    re.IGNORECASE,
)
_PING_RE = re.compile(
    r"\b(ping|online|alive|żyjesz|zyjesz|działasz|dzialasz)\b",
    re.IGNORECASE,
)
_PREFIX_HEX_RE = re.compile(
    r"\b(?:prefix|prefiks|pref)\w*\s+([0-9a-fA-F]{2,6})\b",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(?:w|dla|in|at|for)\s+([A-Za-zÀ-ž][A-Za-zÀ-ž\s\-]{1,40}?)(?:\s*[?.!,]|$)",
    re.IGNORECASE,
)


@dataclass
class ToolContext:
    label: str
    raw: str


async def gather_tool_context(bot, message: MeshMessage, prompt: str) -> Optional[ToolContext]:
    if not llm_cfg.get_bool(bot, "enable_tools", True):
        return None
    text = prompt.strip()
    if not text:
        return None
    if _WEATHER_RE.search(text):
        raw = await _weather_context(bot, message, text)
        return ToolContext("weather", raw)
    prefix_hex = extract_prefix_hex(text)
    if prefix_hex:
        raw = await _prefix_context(bot, message, prefix_hex)
        return ToolContext("prefix", raw)
    if _REPEATER_RE.search(text):
        return ToolContext("repeaters", _repeaters_context(bot))
    if _PING_RE.search(text):
        return ToolContext("ping", "Bot online.")
    return None


def _default_weather_location(bot) -> str:
    loc = llm_cfg.get_str(bot, "default_weather_location")
    if loc:
        return loc
    for section, keys in (
        ("Wx_Command", ("default_city", "default_state", "default_country")),
    ):
        if not bot.config.has_section(section):
            continue
        parts = [(bot.config.get(section, k, fallback="") or "").strip() for k in keys]
        parts = [p for p in parts if p]
        if parts:
            return ", ".join(parts)
    return ""


def _guess_location_from_prompt(prompt: str, default: str) -> str:
    m = _LOCATION_RE.search(prompt)
    if m:
        loc = m.group(1).strip(" .,!?")
        if len(loc) >= 2:
            return loc
    return default


def extract_prefix_hex(prompt: str) -> str | None:
    m = _PREFIX_HEX_RE.search(prompt)
    if not m:
        return None
    hx = m.group(1).strip()
    if len(hx) not in (2, 4, 6):
        if len(hx) > 6:
            hx = hx[:6]
        elif len(hx) == 3:
            hx = hx[:2]
    return hx.upper()


async def _prefix_context(bot, message: MeshMessage, prefix_hex: str) -> str:
    cmd_name = llm_cfg.get_str(bot, "prefix_command", "prefix") or "prefix"
    synthetic = f"{cmd_name} {prefix_hex}"
    text = await _run_command_capture(bot, message, cmd_name, synthetic)
    if text:
        return text[:1200]
    return f"No prefix result for {prefix_hex} ({cmd_name})."


async def _weather_context(bot, message: MeshMessage, prompt: str) -> str:
    default = _default_weather_location(bot)
    location = _guess_location_from_prompt(prompt, default) or default or "local"
    cmd_name = llm_cfg.get_str(bot, "weather_command", "gwx") or "gwx"
    synthetic = f"{cmd_name} {location}".strip()
    text = await _run_command_capture(bot, message, cmd_name, synthetic)
    if text:
        return f"Weather ({location}):\n{text[:800]}"
    return f"Weather unavailable for {location} ({cmd_name})."


def _repeaters_context(bot) -> str:
    limit = max(1, min(20, llm_cfg.get_int(bot, "tool_repeaters_limit", 10)))
    radius = llm_cfg.get_float(bot, "tool_repeaters_radius_km", 250.0)

    lat = bot.config.getfloat("Bot", "bot_latitude", fallback=None)
    lon = bot.config.getfloat("Bot", "bot_longitude", fallback=None)
    if lat is None or lon is None:
        return "Set bot_latitude/bot_longitude for nearby repeater lookup."

    if not getattr(bot, "db_manager", None):
        return "Contact database unavailable."

    query = """
        SELECT adv_name, public_key, latitude, longitude,
               COALESCE(last_advert_timestamp, last_heard) AS last_seen
        FROM complete_contact_tracking
        WHERE role IN ('repeater', 'roomserver')
        AND latitude IS NOT NULL AND longitude IS NOT NULL
        AND latitude != 0 AND longitude != 0
        ORDER BY last_seen DESC
        LIMIT 200
    """
    try:
        rows = bot.db_manager.execute_query(query)
    except Exception as e:
        return f"Repeater DB error: {e}"

    if not rows:
        return "No repeaters in database."

    ranked: list[tuple[float, str]] = []
    for row in rows:
        rlat = row.get("latitude")
        rlon = row.get("longitude")
        if rlat is None or rlon is None:
            continue
        dist = calculate_distance(lat, lon, float(rlat), float(rlon))
        if dist > radius:
            continue
        name = (row.get("adv_name") or "").strip()
        pk = (row.get("public_key") or "")[:4].upper()
        label = name or f"RP-{pk}"
        seen = row.get("last_seen") or "?"
        ranked.append((dist, f"{label} ~{dist:.0f}km last {seen}"))

    ranked.sort(key=lambda x: x[0])
    top = ranked[:limit]
    if not top:
        return f"No repeaters within {radius:.0f} km."
    lines = [t[1] for t in top]
    return f"Recent repeaters (max {limit}, {radius:.0f} km):\n" + "\n".join(lines)


async def _run_command_capture(
    bot,
    message: MeshMessage,
    command_name: str,
    synthetic_content: str,
) -> str:
    cmd = bot.command_manager.commands.get(command_name)
    if cmd is None:
        for name, candidate in bot.command_manager.commands.items():
            if name.lower() == command_name.lower():
                cmd = candidate
                command_name = name
                break
    if cmd is None:
        return ""

    fake = copy.copy(message)
    fake.content = synthetic_content
    fake.content_lower = synthetic_content.lower()
    captured: list[str] = []

    async def capture_send(msg, content: str, **kwargs) -> bool:
        captured.append(content)
        return True

    original_send = cmd.send_response
    cmd.send_response = capture_send  # type: ignore[method-assign]
    try:
        if not cmd.can_execute(fake, skip_channel_check=True):
            return ""
        await cmd.execute(fake)
    except Exception as e:
        return f"({command_name} error: {e})"
    finally:
        cmd.send_response = original_send  # type: ignore[method-assign]

    if captured:
        return "\n".join(captured)
    last = getattr(cmd, "last_response", None)
    return str(last).strip() if last else ""


def build_user_message(prompt: str, tool: Optional[ToolContext]) -> str:
    if tool is None:
        return prompt
    if tool.label == "prefix":
        return (
            f"{prompt.strip()}\n\n[DATA — prefix lookup]\n{tool.raw}\n\n"
            "Summarize [DATA] in one or two short sentences. Do not ask for clarification."
        )
    return (
        f"{prompt.strip()}\n\n[DATA — {tool.label}]\n{tool.raw}\n\n"
        "Summarize [DATA] in one short sentence. No planning or markdown."
    )


def format_prefix_chunks(raw: str, max_bytes: int, max_chunks: int) -> list[str]:
    body = raw.strip()
    cleaned = re.sub(r"\s+", " ", body.replace("\n", " | ")).strip()
    if "\n" in body and len(body) < 400:
        return fit_mesh_reply(body, max_bytes, max_chunks=max_chunks)
    return fit_mesh_reply(cleaned, max_bytes, max_chunks=max_chunks)


def try_direct_tool_reply(tool: ToolContext, max_bytes: int) -> str | None:
    raw = (tool.raw or "").strip()
    if not raw:
        return None

    if tool.label == "ping":
        return truncate_to_utf8_bytes("Online and listening.", max_bytes)

    if tool.label == "weather":
        if "unavailable" in raw.lower() or raw.startswith("("):
            return None
        body = raw.split(":\n", 1)[-1].strip() if ":\n" in raw else raw
        one_line = re.sub(r"\s+", " ", body.replace("\n", " ")).strip()
        if len(one_line) < 8:
            return None
        return truncate_to_utf8_bytes(one_line, max_bytes)

    if tool.label == "prefix":
        if "No prefix" in raw or raw.startswith("("):
            return truncate_to_utf8_bytes(raw.split("\n")[0], max_bytes)
        chunks = format_prefix_chunks(raw, max_bytes, 2)
        return chunks[0] if chunks else None

    if tool.label == "repeaters":
        if raw.startswith("No ") or raw.startswith("Set "):
            return truncate_to_utf8_bytes(raw.split("\n")[0], max_bytes)
        lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.startswith("Recent")]
        if not lines:
            return None
        short = "; ".join(lines[:3])
        out = f"Repeaters: {short}"
        if len(lines) > 3:
            out += f" (+{len(lines) - 3})"
        return truncate_to_utf8_bytes(out, max_bytes)

    return None

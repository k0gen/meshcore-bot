#!/usr/bin/env python3
"""Load LLM persona file and merge with [Llm_Command] system_prompt."""

from __future__ import annotations

from pathlib import Path

from modules.llm import config as llm_cfg

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_PERSONA = _PACKAGE_DIR / "persona.default.md"

MESH_COMPACT_SYSTEM = (
    "You are a MeshCore mesh bot on LoRa. Reply in ONE short sentence in the user's language "
    "(about 120 characters). Final answer only — no planning, no English meta-commentary, no markdown."
)


def _bot_root(bot) -> Path:
    root = getattr(bot, "bot_root", None)
    if root:
        return Path(root)
    return _PACKAGE_DIR.parent.parent


def resolve_persona_path(bot) -> Path:
    raw = llm_cfg.get_str(bot, "persona_file")
    if not raw:
        return _DEFAULT_PERSONA
    path = Path(raw)
    if not path.is_absolute():
        path = _bot_root(bot) / path
    return path


def load_persona(bot) -> str:
    path = resolve_persona_path(bot)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    extra = llm_cfg.get_str(bot, "system_prompt")
    parts = [p for p in (text, extra) if p]
    if not parts:
        return MESH_COMPACT_SYSTEM
    return "\n\n".join(parts)


def load_mesh_system_prompt(bot) -> str:
    mode = llm_cfg.get_str(bot, "persona_mode", "compact").lower()
    if mode == "full":
        return load_persona(bot)
    extra = llm_cfg.get_str(bot, "system_prompt")
    if extra:
        return f"{MESH_COMPACT_SYSTEM}\n\n{extra}"
    return MESH_COMPACT_SYSTEM

#!/usr/bin/env python3
"""Read [Llm_Command] settings."""

from __future__ import annotations

SECTION = "Llm_Command"


def has_section(bot) -> bool:
    return bot.config.has_section(SECTION)


def get_str(bot, key: str, fallback: str = "") -> str:
    if not bot.config.has_section(SECTION):
        return fallback
    return (bot.config.get(SECTION, key, fallback=fallback) or fallback).strip()


def get_bool(bot, key: str, fallback: bool = False) -> bool:
    if not bot.config.has_section(SECTION):
        return fallback
    return bot.config.getboolean(SECTION, key, fallback=fallback)


def get_int(bot, key: str, fallback: int) -> int:
    if not bot.config.has_section(SECTION):
        return fallback
    return bot.config.getint(SECTION, key, fallback=fallback)


def get_float(bot, key: str, fallback: float) -> float:
    if not bot.config.has_section(SECTION):
        return fallback
    return bot.config.getfloat(SECTION, key, fallback=fallback)

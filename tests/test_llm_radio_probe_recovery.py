#!/usr/bin/env python3
"""Tests for radio probe recovery service."""

from __future__ import annotations

import asyncio
import configparser
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.service_plugins.radio_probe_recovery_service import RadioProbeRecoveryService


def _bot_with_config(**overrides):
    bot = MagicMock()
    bot.logger = logging.getLogger("test_meshcore_bot")
    bot.logger.handlers.clear()
    bot.logger.setLevel(logging.DEBUG)

    cfg = configparser.ConfigParser()
    cfg.add_section("Radio_Probe_Recovery")
    cfg.set("Radio_Probe_Recovery", "enabled", "true")
    cfg.set("Radio_Probe_Recovery", "restart_after_timeouts", "1")
    cfg.set("Radio_Probe_Recovery", "cooldown_seconds", "60")
    cfg.set("Radio_Probe_Recovery", "try_reconnect_first", "false")
    for k, v in overrides.items():
        cfg.set("Radio_Probe_Recovery", k, str(v).lower() if isinstance(v, bool) else str(v))
    bot.config = cfg
    bot.reconnect_radio = AsyncMock(return_value=False)
    return bot


@pytest.mark.asyncio
async def test_handler_schedules_on_timeout_log():
    bot = _bot_with_config(try_reconnect_first="false")
    svc = RadioProbeRecoveryService(bot)
    svc.handle_probe_timeout = AsyncMock()
    await svc.start()
    bot.logger.warning("Radio health probe timed out")
    await asyncio.sleep(0.05)
    assert svc.handle_probe_timeout.await_count >= 1
    await svc.stop()


@pytest.mark.asyncio
async def test_reconnect_success_avoids_exit():
    bot = _bot_with_config(try_reconnect_first="true")
    bot.reconnect_radio = AsyncMock(return_value=True)
    svc = RadioProbeRecoveryService(bot)
    await svc.start()
    with patch("modules.service_plugins.radio_probe_recovery_service.os._exit") as mock_exit:
        await svc.handle_probe_timeout()
        mock_exit.assert_not_called()
    await svc.stop()


@pytest.mark.asyncio
async def test_exit_on_timeout_when_reconnect_disabled():
    bot = _bot_with_config(try_reconnect_first="false")
    svc = RadioProbeRecoveryService(bot)
    await svc.start()
    with patch("modules.service_plugins.radio_probe_recovery_service.os._exit") as mock_exit:
        await svc.handle_probe_timeout()
        mock_exit.assert_called_once_with(75)
    await svc.stop()

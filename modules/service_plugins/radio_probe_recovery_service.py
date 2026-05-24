#!/usr/bin/env python3
"""
Restart bot when radio health probe times out (log: "Radio health probe timed out").

Optional [Radio_Probe_Recovery] service — process exit + launchd KeepAlive restarts.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

from modules.service_plugins.base_service import BaseServicePlugin

_PROBE_TIMEOUT_MSG = "Radio health probe timed out"


class _ProbeTimeoutLogHandler(logging.Handler):
    def __init__(self, service: "RadioProbeRecoveryService") -> None:
        super().__init__(level=logging.WARNING)
        self._service = service

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if _PROBE_TIMEOUT_MSG not in record.getMessage():
                return
            loop = asyncio.get_running_loop()
            loop.create_task(self._service.handle_probe_timeout())
        except RuntimeError:
            pass
        except Exception:
            self.handleError(record)


class RadioProbeRecoveryService(BaseServicePlugin):
    name = "radio_probe_recovery"
    description = "Restart bot after radio health probe timeout"
    config_section = "Radio_Probe_Recovery"

    def __init__(self, bot: Any) -> None:
        super().__init__(bot)
        self._handler: Optional[_ProbeTimeoutLogHandler] = None
        self._timeout_streak = 0
        self._last_restart_at = 0.0
        self._reconnect_pending = False
        self._restart_lock = asyncio.Lock()

        section = self.config_section
        self.enabled = bot.config.getboolean(section, "enabled", fallback=False)
        self._threshold = max(1, bot.config.getint(section, "restart_after_timeouts", fallback=1))
        self._cooldown = max(60, bot.config.getint(section, "cooldown_seconds", fallback=600))
        self._try_reconnect = bot.config.getboolean(section, "try_reconnect_first", fallback=True)

    async def start(self) -> None:
        if not self.enabled:
            return
        if self._handler is not None:
            return
        self._handler = _ProbeTimeoutLogHandler(self)
        self.bot.logger.addHandler(self._handler)
        self._running = True
        self.logger.info(
            "Radio probe recovery enabled (threshold=%s, cooldown=%ss)",
            self._threshold,
            self._cooldown,
        )

    async def stop(self) -> None:
        if self._handler is not None:
            try:
                self.bot.logger.removeHandler(self._handler)
            except Exception:
                pass
            self._handler = None
        self._running = False

    async def handle_probe_timeout(self) -> None:
        async with self._restart_lock:
            self._timeout_streak += 1
            if self._timeout_streak < self._threshold:
                return

            now = time.time()
            if now - self._last_restart_at < self._cooldown:
                return

            if self._try_reconnect and not self._reconnect_pending:
                self._reconnect_pending = True
                try:
                    ok = await self.bot.reconnect_radio()
                except Exception as e:
                    self.logger.error("reconnect_radio failed: %s", e)
                    ok = False
                if ok:
                    self._timeout_streak = 0
                    self._reconnect_pending = False
                    return

            self._last_restart_at = now
            self._timeout_streak = 0
            self._reconnect_pending = False
            self.logger.critical(
                "Radio health probe timed out — exiting for process restart"
            )
            await asyncio.sleep(1.0)
            os._exit(75)

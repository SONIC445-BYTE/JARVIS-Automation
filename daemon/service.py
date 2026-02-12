from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from daemon.config import DaemonConfig
from daemon.dispatcher import CommandDispatcher, DispatchResult
from daemon.logging_utils import ActionLogger


@dataclass
class DaemonStatus:
    running: bool
    awake: bool
    dry_run: bool
    last_transcript: str


class JarvisDaemon:
    def __init__(self, config: Optional[DaemonConfig] = None):
        self.config = config or DaemonConfig.from_env()
        self.config.ensure_paths()
        self.logger = ActionLogger(self.config.action_log_path)
        self.dispatcher = CommandDispatcher(self.logger, self.config)
        self._running = False
        self._awake = False
        self._last_activity = 0.0
        self._last_transcript = ""

    def start(self) -> None:
        self._running = True
        self._awake = False
        self._last_activity = time.monotonic()
        self.logger.log_action(
            action="daemon_start",
            target="daemon",
            result="success",
            dry_run_flag=self.config.dry_run,
        )

    def stop(self) -> None:
        self._running = False
        self.logger.log_action(
            action="daemon_stop",
            target="daemon",
            result="success",
            dry_run_flag=self.config.dry_run,
        )

    def run_forever(self, poll_interval: float = 0.1) -> None:
        self.start()
        try:
            while self._running:
                self._tick_timeout()
                time.sleep(poll_interval)
        finally:
            self.stop()

    def receive_transcript(self, text: str) -> Optional[DispatchResult]:
        cleaned = (text or "").strip()
        if not cleaned:
            return None

        self._last_transcript = cleaned
        lower = cleaned.lower()
        now = time.monotonic()

        if not self._awake:
            if self.config.wake_word.lower() in lower:
                self._awake = True
                self._last_activity = now
                self.logger.log_action(
                    action="wakeword_detected",
                    target=self.config.wake_word,
                    result="success",
                    dry_run_flag=self.config.dry_run,
                )
            return None

        self._last_activity = now
        result = self.dispatcher.dispatch_text(cleaned)
        self._awake = False
        self.logger.log_action(
            action="return_to_standby",
            target="daemon",
            result="success",
            dry_run_flag=self.config.dry_run,
        )
        return result

    def status(self) -> DaemonStatus:
        return DaemonStatus(
            running=self._running,
            awake=self._awake,
            dry_run=self.config.dry_run,
            last_transcript=self._last_transcript,
        )

    def _tick_timeout(self) -> None:
        if not self._awake:
            return
        if time.monotonic() - self._last_activity <= self.config.active_timeout_s:
            return
        self._awake = False
        self.logger.log_action(
            action="active_timeout",
            target="daemon",
            result="standby",
            dry_run_flag=self.config.dry_run,
        )

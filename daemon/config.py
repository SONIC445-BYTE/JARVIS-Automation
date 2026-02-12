from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DaemonConfig:
    wake_word: str = "jarvis"
    active_timeout_s: float = 15.0
    dry_run: bool = False
    allow_destructive: bool = False
    action_log_path: Path = Path("logs/jarvis_actions.log")
    pid_file: Path = Path("logs/jarvis_daemon.pid")

    @classmethod
    def from_env(cls, dry_run: bool = False) -> "DaemonConfig":
        allow_destructive = (
            os.getenv("ALLOW_DESTRUCTIVE", "false").strip().lower() == "true"
        )
        wake_word = os.getenv("JARVIS_WAKE_WORD", "jarvis")
        timeout_raw = os.getenv("JARVIS_ACTIVE_TIMEOUT_S", "15")
        try:
            timeout = float(timeout_raw)
        except ValueError:
            timeout = 15.0
        return cls(
            wake_word=wake_word,
            active_timeout_s=timeout,
            dry_run=dry_run,
            allow_destructive=allow_destructive,
        )

    def ensure_paths(self) -> None:
        self.action_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

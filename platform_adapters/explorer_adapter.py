"""
Phase 2d: ported from AgentCore/platform_adapters/explorer (audit
class-b -- real open_folder logic, but detect_ui unconditionally
returned True regardless of the actual window, "Plausible fallback for
now"). The daemon contract has no detect_ui concept at all (Phase 2c's
AvailabilityChecker serves an analogous "is this actually usable" role
differently), so that specific defect doesn't carry over here -- there
is nothing to port for it. open_folder itself needs no fix: it's
subprocess-driven (os.startfile), no coordinates involved.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase
from .gui_backend import GUIBackend


class ExplorerAdapter(AdapterBase):
    WINDOW_TITLE = "File Explorer"
    PLATFORM_ALIASES = ["file explorer", "explorer"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        # Like every other adapter's open_app, this is called with no
        # arguments by UIExecutor -- opens to a default location, not a
        # dictated path. Supporting "open explorer to X" would need
        # open_app's calling convention extended to pass target/message,
        # which no adapter currently does; out of scope here.
        path = "C:\\"
        self.log_action("open_app", {"path": path, "dry_run": self.dry_run})
        if self.dry_run:
            return True
        try:
            os.startfile(path)
            return True
        except Exception as e:
            self.log_action("open_app_failed", {"path": path, "error": str(e)})
            return False

    def close_app(self) -> bool:
        self.log_action("close_app", {"dry_run": self.dry_run})
        if self.dry_run:
            return True
        closed = self.backend.close_window(self.WINDOW_TITLE)
        if not closed:
            self.log_action("close_app_skipped", {"reason": f"{self.WINDOW_TITLE} not found/focused"})
        return closed

    def send_message(self, target: str, message: str) -> bool:
        raise NotImplementedError("Explorer has no messaging concept")

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []  # not applicable; not declared in ACTIONS

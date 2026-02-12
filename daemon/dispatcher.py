from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional

from daemon.config import DaemonConfig
from daemon.intent_parser import Intent, parse_command
from platform_adapters.registry import create_default_adapters


@dataclass
class DispatchResult:
    ok: bool
    reason: str
    latency_ms: float


class CommandDispatcher:
    def __init__(self, logger, config: DaemonConfig, adapters: Optional[Dict[str, object]] = None):
        self.logger = logger
        self.config = config
        self.adapters = adapters or create_default_adapters(logger=logger, dry_run=config.dry_run)

    def dispatch_text(self, text: str) -> DispatchResult:
        intent = parse_command(text)
        return self.dispatch(intent)

    def dispatch(self, intent: Intent) -> DispatchResult:
        start = time.perf_counter()
        if intent.destructive and not self.config.allow_destructive:
            latency = (time.perf_counter() - start) * 1000
            self.logger.log_action(
                action="blocked_destructive",
                target=intent.target or "system",
                result="blocked",
                dry_run_flag=self.config.dry_run,
                meta={"command": intent.message},
            )
            return DispatchResult(False, "ALLOW_DESTRUCTIVE=false", latency)

        adapter = self.adapters.get(intent.adapter)
        if not adapter:
            latency = (time.perf_counter() - start) * 1000
            self.logger.log_action(
                action="dispatch_missing_adapter",
                target=intent.adapter,
                result="failed",
                dry_run_flag=self.config.dry_run,
            )
            return DispatchResult(False, f"adapter '{intent.adapter}' not found", latency)

        ok = self._invoke_adapter(adapter, intent)
        latency = (time.perf_counter() - start) * 1000
        self.logger.log_action(
            action=intent.action,
            target=intent.target or intent.adapter,
            result="success" if ok else "failed",
            dry_run_flag=self.config.dry_run,
            meta={"adapter": intent.adapter, "latency_ms": round(latency, 3)},
        )
        return DispatchResult(ok, "ok" if ok else "adapter returned false", latency)

    def _invoke_adapter(self, adapter: object, intent: Intent) -> bool:
        if intent.action == "open_app":
            return bool(adapter.open_app())
        if intent.action == "close_app":
            return bool(adapter.close_app())
        if intent.action == "send_message":
            return bool(adapter.send_message(intent.target, intent.message))
        if intent.action == "read_unread":
            adapter.read_unread(limit=10)
            return True
        return False

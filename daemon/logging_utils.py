from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActionLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._logger = logging.getLogger("jarvis.automation")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

    def info(self, payload: Dict[str, Any]) -> None:
        self._logger.info("%s", payload)

    def log_action(
        self,
        action: str,
        target: str,
        result: str,
        dry_run_flag: bool,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = {
            "timestamp": _utc_now_iso(),
            "action": action,
            "target": target,
            "result": result,
            "dry_run_flag": dry_run_flag,
            "meta": meta or {},
        }
        self.info(event)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")

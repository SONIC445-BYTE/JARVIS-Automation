import json
import time
import os
from pathlib import Path
from typing import Dict, Any

class Level6Metrics:
    def __init__(self, log_path: str = "data/level6/metrics.jsonl"):
        self.log_path = log_path
        self._ensure_dir()

    def _ensure_dir(self):
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def log_metric(self, event_type: str, data: Dict[str, Any]):
        entry = {
            "timestamp": time.time(),
            "event": event_type,
            **data
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"[Level6Metrics] Failed to log: {e}")

    # Helper methods for specific metrics
    def log_request_start(self, request_id: str):
        self.log_metric("request_received", {"request_id": request_id})

    def log_success(self, request_id: str, iterations: int, risk_score: float):
        self.log_metric("request_completed", {
            "request_id": request_id, 
            "status": "success", 
            "iterations": iterations,
            "risk_score": risk_score
        })

    def log_failure(self, request_id: str, reason: str, iterations: int):
        self.log_metric("request_failed", {
            "request_id": request_id, 
            "status": "failed", 
            "reason": reason,
            "iterations": iterations
        })

"""
Metrics Collector for Level-4.
"""
from typing import Dict, Any

class MetricsCollector:
    def __init__(self):
        self.metrics = {}

    def log_request(self, user_id: str):
        self.metrics.setdefault("requests", 0)
        self.metrics["requests"] += 1

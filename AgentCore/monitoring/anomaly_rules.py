"""
Anomaly Rules.
Maps failures to actions.
"""
import yaml
import os

class AnomalyRules:
    def __init__(self):
        base_path = os.path.dirname(os.path.dirname(__file__))
        self.config_path = os.path.join(base_path, "safety", "failure_taxonomy.yaml")
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            self.config = {}

    def get_action(self, category: str) -> str:
        rules = self.config.get("categories", {}).get(category, {})
        return rules.get("action", "alert")

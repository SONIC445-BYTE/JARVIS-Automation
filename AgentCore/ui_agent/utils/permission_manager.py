import yaml
import os
from typing import Dict, Any, List

class PermissionManager:
    """Manages user permissions for UI control."""
    
    def __init__(self, config_path: str = "feature_flags/ui_execute.yaml"):
        self.config_path = config_path
        self.allowlist = []
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
                self.allowlist = cfg.get("allowlist", [])

    def is_app_allowed(self, app_name: str) -> bool:
        """Check if an app is in the allowlist."""
        return app_name.lower() in [a.lower() for a in self.allowlist]

    def request_confirmation(self, action_summary: str) -> bool:
        """
        Request user confirmation via voice or visual prompt.
        In a real implementation, this would trigger a speech event.
        """
        print(f"[PermissionManager] CONFIRMATION REQUIRED: {action_summary}")
        # Default to false unless explicitly confirmed (or in human-in-the-loop mode)
        return False

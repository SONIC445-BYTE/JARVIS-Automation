"""
Policy Manager for Code Engine.
Handles risk thresholds, feature flags, and safety checks.
"""
import os
import yaml
from typing import Dict, Any

class PolicyManager:
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to repo root feature_flags
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(base_path, "feature_flags", "code_engine.yaml")
        
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {
                "enabled": False,
                "auto_execute_threshold": 0.95,
                "human_confirm_threshold": 0.7,
                "destructive_threshold": 0.99,
                "max_patch_lines": 500,
                "sandbox_enabled": True
            }
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def is_enabled(self) -> bool:
        return self.config.get("enabled", False)

    def can_auto_execute(self, confidence: float, is_destructive: bool = False) -> bool:
        if is_destructive:
            return False
        return confidence >= self.config.get("auto_execute_threshold", 0.95)

    def requires_human_confirm(self, confidence: float) -> bool:
        return confidence < self.config.get("auto_execute_threshold", 0.95)

    def check_safety(self, patch_content: str) -> Dict[str, Any]:
        """
        Basic regex-based safety check before LLM verification.
        Refines risk score.
        """
        risks = []
        if "os.system" in patch_content or "subprocess" in patch_content:
            risks.append("Command execution detected")
        
        # Check line count
        lines = patch_content.split('\n')
        if len(lines) > self.config.get("max_patch_lines", 500):
            risks.append(f"Patch exceeds max line limit ({len(lines)})")

        return {
            "safe": len(risks) == 0,
            "risks": risks
        }

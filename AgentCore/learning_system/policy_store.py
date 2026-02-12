"""
Policy Store — Execution thresholds & policy persistence
==========================================================
Stores and retrieves confidence thresholds, risk-level rules,
and shadow-mode settings.  YAML-backed, hot-reloadable.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from .feature_gate import FeatureGate


class PolicyStore:
    """
    Central policy configuration for the learning system.
    
    Key policies:
        auto_execute_threshold   = 0.92  (auto-execute if above)
        human_confirm_threshold  = 0.70  (ask human if above this)
        destructive_threshold    = 0.99  (never auto-exec destructive)
        shadow_mode              = True  (log-only, no exec)
        trace_opt_in             = False (user must enable traces)
        data_retention_days      = 90
    """

    _DEFAULTS: Dict[str, Any] = {
        'auto_execute_threshold': 0.92,
        'human_confirm_threshold': 0.70,
        'destructive_threshold': 0.99,
        'shadow_mode': True,
        'trace_opt_in': False,
        'data_retention_days': 90,
        'min_discovery_occurrences': 3,
        'min_discovery_confidence': 0.60,
        'discovery_window_days': 14,
        'discovery_min_examples': 5,
        'max_pending_approvals': 50,
    }

    def __init__(self, config_path: Optional[str] = None):
        self._policies: Dict[str, Any] = dict(self._DEFAULTS)
        if config_path is None:
            root = Path(__file__).resolve().parents[2]
            config_path = root / 'feature_flags' / 'learning_system.yaml'
        self._path = Path(config_path)
        self._load_overrides()

    def _load_overrides(self):
        """Load policy overrides from the YAML config."""
        if not self._path.exists():
            return
        try:
            data = FeatureGate._parse_simple_yaml(
                self._path.read_text(encoding='utf-8')
            )
            for k, v in data.items():
                if k in self._policies:
                    self._policies[k] = type(self._DEFAULTS[k])(v)
        except Exception as e:
            print(f"[PolicyStore] Failed to load overrides: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._policies.get(key, default)

    def set(self, key: str, value: Any):
        """In-memory update."""
        self._policies[key] = value

    def all(self) -> Dict[str, Any]:
        return dict(self._policies)

    def should_auto_execute(self, confidence: float, is_destructive: bool = False) -> bool:
        """Return True if the action can be auto-executed."""
        if self._policies['shadow_mode']:
            return False
        if is_destructive:
            return confidence >= self._policies['destructive_threshold']
        return confidence >= self._policies['auto_execute_threshold']

    def should_ask_human(self, confidence: float) -> bool:
        """Return True if confidence warrants human confirmation."""
        return (confidence >= self._policies['human_confirm_threshold']
                and confidence < self._policies['auto_execute_threshold'])

    def should_reject(self, confidence: float) -> bool:
        """Return True if confidence is too low."""
        return confidence < self._policies['human_confirm_threshold']

    def reload(self):
        self._policies = dict(self._DEFAULTS)
        self._load_overrides()

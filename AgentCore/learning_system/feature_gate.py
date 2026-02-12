"""
Feature Gate — Flag-based feature control
============================================
Reads feature_flags/learning_system.yaml and exposes
enabled(name) + get_threshold(key) helpers.

Default: everything OFF.
"""

import os
from pathlib import Path
from typing import Any, Optional


class FeatureGate:
    """
    Loads flags from YAML (or falls back to built-in defaults).
    All flags default to False / disabled so the learning system
    never activates unless explicitly turned on.
    """

    _DEFAULTS = {
        'enabled': False,
        'shadow_mode': True,
        'owner': 'admin',
        'risk_level': 'standard',
        'rollout_percentage': 0,
        # per-module sub-flags
        'flow_instrumentation': False,
        'action_discovery': False,
        'pattern_extractor': False,
        'adapter_generator': False,
        'adapter_generation': False,
        'confidence_engine': False,
        'intent_graph': False,
        'critic_engine': False,
        'causal_memory': False,
        'human_loop': False,
        'audit_log': False,
        # alias used by jarvis.py guard
        'learning_system': False,
    }

    def __init__(self, config_path: Optional[str] = None):
        self._flags: dict = dict(self._DEFAULTS)
        if config_path is None:
            root = Path(__file__).resolve().parents[2]  # project root
            config_path = root / 'feature_flags' / 'learning_system.yaml'
        self._path = Path(config_path)
        self._load()

    # -----------------------------------------------------------------
    def _load(self):
        """Load YAML config if it exists."""
        if not self._path.exists():
            return
        try:
            # Lightweight YAML parser — avoid external dependency
            data = self._parse_simple_yaml(self._path.read_text(encoding='utf-8'))
            self._flags.update(data)
        except Exception as e:
            print(f"[FeatureGate] Failed to load {self._path}: {e}")

    @staticmethod
    def _parse_simple_yaml(text: str) -> dict:
        """Minimal key: value parser for flat YAML files."""
        result = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' not in line:
                continue
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip()
            # convert types
            if val.lower() in ('true', 'yes'):
                val = True
            elif val.lower() in ('false', 'no'):
                val = False
            elif val.replace('.', '', 1).lstrip('-').isdigit():
                val = float(val) if '.' in val else int(val)
            result[key] = val
        return result

    # -----------------------------------------------------------------
    def enabled(self, feature_name: str) -> bool:
        """
        Return True only when *both* the master flag AND
        the per-module flag are truthy.
        """
        master = bool(self._flags.get('enabled', False))
        if feature_name in ('enabled', 'learning_system'):
            return master
        return master and bool(self._flags.get(feature_name, False))

    def get(self, key: str, default: Any = None) -> Any:
        return self._flags.get(key, default)

    def get_threshold(self, key: str) -> float:
        return float(self._flags.get(key, 0.0))

    def reload(self):
        """Re-read the config file."""
        self._flags = dict(self._DEFAULTS)
        self._load()

    def set_flag(self, key: str, value: Any):
        """In-memory override (for tests). Does NOT write to disk."""
        self._flags[key] = value

    def all_flags(self) -> dict:
        return dict(self._flags)

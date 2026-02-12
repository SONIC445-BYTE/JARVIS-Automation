"""
Feature Gate with Graded Modes.
Modes: off < shadow < suggest < supervised < autonomous
"""
import yaml
import os
from enum import IntEnum

class FeatureMode(IntEnum):
    OFF = 0
    SHADOW = 1
    SUGGEST = 2
    SUPERVISED = 3
    AUTONOMOUS = 4

def get_mode(feature_name: str) -> FeatureMode:
    """Get current mode for a feature."""
    base_path = os.path.dirname(os.path.dirname(__file__))
    config_path = os.path.join(base_path, "feature_flags", f"{feature_name}.yaml")
    
    if not os.path.exists(config_path):
        return FeatureMode.OFF
        
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
            mode_str = config.get("mode", "off").upper()
            return FeatureMode[mode_str] if mode_str in FeatureMode.__members__ else FeatureMode.OFF
    except Exception:
        return FeatureMode.OFF

def is_mode_at_least(feature_name: str, min_mode: FeatureMode) -> bool:
    """Check if feature mode is >= min_mode."""
    current = get_mode(feature_name)
    return current >= min_mode

def is_enabled(feature_name: str) -> bool:
    """Legacy compatibility: True if autonomous."""
    return is_mode_at_least(feature_name, FeatureMode.AUTONOMOUS)

"""
WakeService Package - JARVIS Persistent Wake System
=====================================================
Always-on background service with wake word detection.

Sprint 1 Hardening:
- True Windows Service (runs before login)
- Resource governance (CPU throttling)
- Mic arbitration (exclusive access)
- Crash immunity (auto-restart)
- Trust engine (command classification)
"""

from .wake_detector import WakeDetector
from .local_stt import LocalSTT
from .mode_manager import ModeManager, JarvisMode, AudioArbiter
from .jarvis_service import JarvisService, run_service
from .resource_governor import ResourceGovernor, ResourceLimits
from .health_monitor import HealthMonitor
from .trust_engine import TrustEngine, CommandRisk

__all__ = [
    'WakeDetector',
    'LocalSTT', 
    'ModeManager',
    'JarvisMode',
    'AudioArbiter',
    'JarvisService',
    'run_service',
    'ResourceGovernor',
    'ResourceLimits',
    'HealthMonitor',
    'TrustEngine',
    'CommandRisk',
]

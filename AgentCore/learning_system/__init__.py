"""
Learning System — Jarvis Learns, Judges, and Improves
=======================================================
Additive learning layer: action discovery, intent graphs,
confidence scoring, critic evaluation, causal memory, and
human-in-the-loop approval.

All features are behind feature flags (default OFF).
"""

from .feature_gate import FeatureGate
from .policy_store import PolicyStore

__all__ = [
    'FeatureGate',
    'PolicyStore',
    'LearningSystem',
]

__version__ = '0.1.0-shadow'


class LearningSystem:
    """
    Facade that lazily initialises every sub-module only when
    the corresponding feature flag is enabled.
    """

    def __init__(self):
        self.gate = FeatureGate()
        self.policy = PolicyStore()
        self._modules = {}

    # --- lazy loaders ---------------------------------------------------
    def _get(self, name):
        if name in self._modules:
            return self._modules[name]
        if not self.gate.enabled(name):
            return None
        mod = self._init_module(name)
        self._modules[name] = mod
        return mod

    def _init_module(self, name):
        """Import and instantiate *name* on first access."""
        try:
            if name == 'flow_instrumentation':
                from .flow_instrumentation import FlowInstrumentation
                return FlowInstrumentation()
            elif name == 'action_discovery':
                from .action_discovery import ActionDiscovery
                return ActionDiscovery()
            elif name == 'pattern_extractor':
                from .pattern_extractor import PatternExtractor
                return PatternExtractor()
            elif name == 'adapter_generator':
                from .adapter_generator import AdapterGenerator
                return AdapterGenerator()
            elif name == 'confidence_engine':
                from .confidence_engine import ConfidenceEngine
                return ConfidenceEngine()
            elif name == 'intent_graph':
                from .intent_graph import IntentGraph
                return IntentGraph()
            elif name == 'critic_engine':
                from .critic_engine import CriticEngine
                return CriticEngine()
            elif name == 'causal_memory':
                from .causal_memory import CausalMemory
                return CausalMemory()
            elif name == 'human_loop':
                from .human_loop import HumanLoop
                return HumanLoop()
            elif name == 'audit_log':
                from .audit_log import LearningAuditLog
                return LearningAuditLog()
        except Exception as e:
            print(f"[LearningSystem] Failed to init {name}: {e}")
            return None

    # convenient accessors ------------------------------------------------
    @property
    def instrumentation(self):
        return self._get('flow_instrumentation')

    @property
    def discovery(self):
        return self._get('action_discovery')

    @property
    def extractor(self):
        return self._get('pattern_extractor')

    @property
    def generator(self):
        return self._get('adapter_generator')

    @property
    def confidence(self):
        return self._get('confidence_engine')

    @property
    def intent(self):
        return self._get('intent_graph')

    @property
    def critic(self):
        return self._get('critic_engine')

    @property
    def memory(self):
        return self._get('causal_memory')

    @property
    def human(self):
        return self._get('human_loop')

    @property
    def audit(self):
        return self._get('audit_log')

    # health -------------------------------------------------------------
    def health(self) -> dict:
        """Return status dict suitable for --health output."""
        status = {
            'version': __version__,
            'enabled': self.gate.enabled('learning_system'),
            'shadow_mode': self.policy.get('shadow_mode', True),
            'modules': {},
        }
        for mod_name in [
            'flow_instrumentation', 'action_discovery', 'pattern_extractor',
            'adapter_generator', 'confidence_engine', 'intent_graph',
            'critic_engine', 'causal_memory', 'human_loop', 'audit_log',
        ]:
            flag = self.gate.enabled(mod_name)
            loaded = mod_name in self._modules
            status['modules'][mod_name] = {
                'flag': flag,
                'loaded': loaded,
            }
        return status

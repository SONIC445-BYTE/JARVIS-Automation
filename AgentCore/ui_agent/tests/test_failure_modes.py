
import unittest
from unittest.mock import MagicMock, patch
from AgentCore.ui_agent.action_router import ActionPlanner
from AgentCore.ui_agent.adapters.generic_adapters import GenericDesktopAdapter, UnknownAppFallbackAdapter
from AgentCore.ui_agent.adapter_registry import AdapterRegistry

class TestFailureModes(unittest.TestCase):
    
    def setUp(self):
        self.registry = AdapterRegistry()
        # Reset registry for isolation
        self.registry.adapters = {}
        
    def test_generic_desktop_nerf(self):
        """Test that GenericDesktopAdapter refuses unsafe actions."""
        adapter = GenericDesktopAdapter()
        
        # Should execute
        self.assertTrue(adapter.can_handle({"action": "navigate", "target": "C:/"}, {}))
        self.assertTrue(adapter.can_handle({"action": "open", "target": "notepad"}, {}))
        
        # Should NOT execute (nerfed)
        self.assertFalse(adapter.can_handle({"action": "click", "target": "boom"}, {}))
        self.assertFalse(adapter.can_handle({"action": "type", "target": "password"}, {}))
        
    def test_plan_score_rejection(self):
        """Test that ActionPlanner rejects low-confidence plans."""
        # Setup: Only a generic safe adapter is available, but we ask for something complex
        # GenericDesktop supports 'navigate', let's ask for 'complex_gesture'
        
        intent = {"action": "complex_gesture", "platform": "desktop"}
        
        # Mock registry to return nothing specific
        with patch.object(self.registry, 'resolve', return_value=[]):
            adapter, plan = ActionPlanner.plan(intent, {})
            
            # Should fall back to UnknownAppFallbackAdapter
            self.assertIsInstance(adapter, UnknownAppFallbackAdapter)
            self.assertEqual(plan[0]['type'], "ocr_click")

    def test_capability_enforcement(self):
        """Test that missing capabilities lead to fallback or rejection."""
        # Create a dummy adapter with NO capabilities
        class WeakAdapter:
            platform = "weak"
            supported_actions = ["dummy"]
            capabilities = {} # Empty!
            
            def can_handle(self, i, c): return True
            def build_plan(self, i, c): return [{"type": "dummy"}]
            
        intent = {"action": "dummy", "platform": "weak"}
        
        with patch('AgentCore.ui_agent.action_router.registry.resolve', return_value=[WeakAdapter()]):
            # The planner logic filters out adapters with empty capabilities for the action
            adapter, plan = ActionPlanner.plan(intent, {})
            
            # Since WeakAdapter has no capabilities for "dummy", it is skipped.
            # Planner falls back to UnknownAppFallbackAdapter
            self.assertIsInstance(adapter, UnknownAppFallbackAdapter)

if __name__ == "__main__":
    unittest.main()

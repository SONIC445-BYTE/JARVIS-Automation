import unittest
from unittest.mock import MagicMock
from AgentCore.ui_agent.context.ui_context import UIContext
# We will need to mock the full executor flow for the strict negative test,
# but for now we focus on the Context/Scanner behavior logic.

class TestFollowupNegative(unittest.TestCase):
    
    def setUp(self):
        UIContext._instance = None
        self.ctx = UIContext()
        self.ctx.set_active(True, "test_adapter")
        # Populate with some fake elements
        self.ctx.update_snapshot("Explorer", [
            {"element_id": "1", "name": "Desktop", "text": "Desktop"},
            {"element_id": "2", "name": "Downloads", "text": "Downloads"}
        ])

    def test_find_nonexistent_element(self):
        """Test finding an element that does not exist."""
        results = self.ctx.get_elements_by_text("unicorn")
        self.assertEqual(len(results), 0)
        
    def test_find_ambiguous_element(self):
        """Test finding an element that matches multiple items."""
        # Add ambiguous items
        self.ctx.update_snapshot("Explorer", [
            {"element_id": "1", "name": "File", "text": "File"},
            {"element_id": "2", "name": "File", "text": "File"}
        ])
        
        results = self.ctx.get_elements_by_text("File")
        self.assertEqual(len(results), 2)
        # Executor usage should fail/ask clarify on this length > 1

if __name__ == '__main__':
    unittest.main()

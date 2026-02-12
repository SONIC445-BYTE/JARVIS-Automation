
import unittest
from ..adapter import ExplorerAdapter

class TestExplorerAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = ExplorerAdapter()

    def test_build_plan_folder(self):
        plan = self.adapter.build_plan("open_folder", {"path": "C:\\Windows"})
        self.assertEqual(plan.steps[0].action, "open_app")

if __name__ == '__main__':
    unittest.main()


import unittest
from ..adapter import GoogleAdapter

class TestGoogleAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = GoogleAdapter()

    def test_build_plan(self):
        plan = self.adapter.build_plan("search", {"query": "hello"})
        self.assertEqual(plan.steps[0].action, "navigate")

if __name__ == '__main__':
    unittest.main()

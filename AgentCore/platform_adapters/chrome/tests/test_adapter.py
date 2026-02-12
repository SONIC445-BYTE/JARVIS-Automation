
import unittest
from ..adapter import ChromeAdapter

class TestChromeAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = ChromeAdapter()

    def test_detect_ui(self):
        self.assertTrue(self.adapter.detect_ui({"active_window": "Google Chrome"}))

    def test_build_plan_url(self):
        plan = self.adapter.build_plan("open_url", {"url": "https://google.com"})
        self.assertEqual(plan.steps[0].action, "navigate")

if __name__ == '__main__':
    unittest.main()


import unittest
from ..adapter import CalculatorAdapter

class TestCalculatorAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = CalculatorAdapter()

    def test_detect_ui(self):
        self.assertTrue(self.adapter.detect_ui({"active_window": "Calculator"}))

    def test_build_plan_calc(self):
        plan = self.adapter.build_plan("calculate", {"expression": "2+2"})
        self.assertEqual(plan.steps[0].action, "type")

if __name__ == '__main__':
    unittest.main()

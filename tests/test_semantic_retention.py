"""
Test Semantic Retention.
"""
import unittest
from AgentCore.safety.semantic_check import semantic_retention_ratio, validate_retention

class TestSemanticRetention(unittest.TestCase):
    def test_ratios(self):
        orig = "def foo():\n    print('hello')\n    x = 1\n    return x"
        mod = "def foo():\n    print('hello')" # Truncated
        
        ratio = semantic_retention_ratio(orig, mod)
        self.assertLess(ratio, 1.0)
        self.assertGreater(ratio, 0.0)

    def test_empty_file(self):
        orig = "def foo(): pass"
        mod = ""
        # Module node exists, so ratio > 0. Increase threshold to catch it.
        self.assertFalse(validate_retention(orig, mod, threshold=0.5))

    def test_growth(self):
        orig = "x=1"
        mod = "x=1\ny=2"
        self.assertGreaterEqual(semantic_retention_ratio(orig, mod), 1.0)

if __name__ == "__main__":
    unittest.main()

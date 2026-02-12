"""
Tests for Level-4.
"""
import unittest
from AgentCore.advanced.level4.tier1.ast_transformer import ASTTransformer

class TestLevel4(unittest.TestCase):
    def test_safety_check(self):
        transformer = ASTTransformer()
        with self.assertRaises(ValueError) as cm:
            transformer.apply_transform("foo.py", {"delete_file": True})
        self.assertIn("Automatic file deletion is forbidden", str(cm.exception))

if __name__ == "__main__":
    unittest.main()

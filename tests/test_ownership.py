"""
Test Ownership Policy.
"""
import unittest
import os
import shutil
from AgentCore.policy.ownership import OwnershipPolicy

class TestOwnership(unittest.TestCase):
    def setUp(self):
        self.test_registry = "test_ownership_registry.yaml"
        with open(self.test_registry, "w") as f:
            f.write("""
domains:
  core:
    path_patterns: ["core/**"]
    policy: read_only
  experimental:
    path_patterns: ["exp/**"]
    policy: auto_allowed
""")
        self.policy = OwnershipPolicy(self.test_registry)

    def tearDown(self):
        if os.path.exists(self.test_registry):
            os.remove(self.test_registry)

    def test_get_domain(self):
        self.assertEqual(self.policy.get_domain("core/utils.py"), "core")
        self.assertEqual(self.policy.get_domain("exp/script.py"), "experimental")
        self.assertEqual(self.policy.get_domain("other/file.py"), "unknown")

    def test_is_edit_allowed(self):
        allowed, reason = self.policy.is_edit_allowed("user", "core/utils.py")
        self.assertFalse(allowed)
        self.assertIn("READ-ONLY", reason)
        
        allowed, reason = self.policy.is_edit_allowed("user", "exp/script.py")
        self.assertTrue(allowed)

if __name__ == "__main__":
    unittest.main()

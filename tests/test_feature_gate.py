"""
Test Feature Gate.
"""
import unittest
import os
from AgentCore.feature_gate import get_mode, is_mode_at_least, FeatureMode

class TestFeatureGate(unittest.TestCase):
    def setUp(self):
        self.test_flag = "feature_flags/test_feature.yaml"
        os.makedirs("feature_flags", exist_ok=True)
        with open(self.test_flag, "w") as f:
            f.write("mode: shadow")

    def tearDown(self):
        if os.path.exists(self.test_flag):
            os.remove(self.test_flag)

    def test_modes(self):
        mode = get_mode("test_feature")
        self.assertEqual(mode, FeatureMode.SHADOW)
        
        self.assertTrue(is_mode_at_least("test_feature", FeatureMode.OFF))
        self.assertTrue(is_mode_at_least("test_feature", FeatureMode.SHADOW))
        self.assertFalse(is_mode_at_least("test_feature", FeatureMode.SUGGEST))

if __name__ == "__main__":
    unittest.main()

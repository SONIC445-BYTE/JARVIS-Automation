import unittest
import os
import shutil
import json
from pathlib import Path
from AgentCore.mode_manager.mode_engine import ModeEngine

class TestModeEngineHardened(unittest.TestCase):
    def setUp(self):
        self.test_config = "feature_flags/test_hardening.yaml"
        with open(self.test_config, "w") as f:
            f.write("enabled: true\nauto_switch_confidence_threshold: 0.8\ncooldown_seconds: 0.1\n")
        # Mock env key for audit
        os.environ["JARVIS_HMAC_KEY"] = "testkey"

    def tearDown(self):
        if os.path.exists(self.test_config):
            os.remove(self.test_config)
        # Clean logs
        if os.path.exists("data/logs/mode_switch.log"):
            os.remove("data/logs/mode_switch.log")

    def test_rule_match(self):
        engine = ModeEngine(self.test_config)
        res = engine.decide_and_transition("write a python script", {})
        self.assertEqual(res["action"], "switched")
        self.assertEqual(res["target_mode"], "CODE")

    def test_destructive_confirm(self):
        engine = ModeEngine(self.test_config)
        res = engine.decide_and_transition("delete all files", {})
        # Depending on intent rule for 'delete' -> SYSTEM_DELETE -> require_confirm
        self.assertEqual(res["action"], "require_confirm")

    def test_audit_log_created(self):
        engine = ModeEngine(self.test_config)
        engine.decide_and_transition("write code", {})
        self.assertTrue(os.path.exists("data/logs/mode_switch.log"))
        with open("data/logs/mode_switch.log") as f:
            line = f.readline()
            # D11: the test guessed at a key name ("hmac_signature")
            # that was never actually implemented. AgentCore/mode_manager/
            # audit.py's write_log()/verify_line() consistently use "sig"
            # on both the write and verify sides -- renaming only the
            # test to match what's real, not renaming the working,
            # internally-consistent write/verify contract to match a
            # guess (that would be a real behavior change, not a test fix).
            self.assertIn("sig", line)

if __name__ == "__main__":
    unittest.main()

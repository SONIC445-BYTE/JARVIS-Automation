"""
Phase 0 repro test (NOT a fix) for a coupling bug flagged for Phase 3:
AgentCore/__init__.py eagerly imports agent_brain -> ui_perception ->
pyautogui at package import time. This means importing anything under
AgentCore -- including AgentCore.code_engine, which has no UI dependency
-- drags in the full UI automation stack (pyautogui).

On a headless/no-DISPLAY Linux service context this crashes outright
(KeyError: 'DISPLAY'). On Windows it doesn't crash, but the coupling is
still real: a background/daemon context with no interactive session can
still hit pyautogui failures at import time instead of only when UI
automation is actually invoked.

This test documents the CURRENT (undesired) coupling so Phase 3's fix
(lazy-importing pyautogui only where it's used) doesn't get silently
reintroduced without anyone noticing the regression the other way --
once Phase 3 lands, this test's assertion should flip and the test
should be updated to assert pyautogui is NOT pulled in by a bare
`import AgentCore.code_engine.engine`.
"""
import subprocess
import sys
import unittest


class TestAgentCoreUICoupling(unittest.TestCase):
    def test_importing_code_engine_currently_pulls_in_pyautogui(self):
        # Run in a subprocess so we get a clean sys.modules state.
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import AgentCore.code_engine.engine; "
                "print('pyautogui' in sys.modules)",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout.strip().splitlines()[-1],
            "True",
            "Expected current (buggy) coupling: importing AgentCore.code_engine.engine "
            "pulls in pyautogui via AgentCore/__init__.py's eager imports. If this now "
            "prints False, Phase 3's decoupling fix has landed -- update this test to "
            "assert the coupling is GONE instead of documenting that it exists.",
        )


if __name__ == "__main__":
    unittest.main()

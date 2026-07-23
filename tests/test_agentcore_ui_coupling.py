"""
Regression test for a coupling bug originally flagged for Phase 3, then
pulled forward and fixed mid-Phase-2g: AgentCore/__init__.py used to
eagerly import agent_brain -> ui_perception -> pyautogui at package
import time. This meant importing anything under AgentCore -- including
AgentCore.code_engine, which has no UI dependency -- dragged in the full
UI automation stack (pyautogui).

On a headless/no-DISPLAY Linux service context this crashed outright.
Elevated from "Phase 3 nice-to-have" after independent verification
found a compounding, harder-to-work-around instance of the same coupling
pattern: AgentCore.ui_agent's vision/screen_capture.py imports mss,
which opens a real X11 connection at import time -- unlike pyautogui,
this couldn't be worked around with a Python-level stub. Both were fixed
together: AgentCore/__init__.py now lazy-loads its package-level
re-exports via __getattr__ (PEP 562) instead of importing them eagerly,
and the two places that eagerly imported AgentCore.agent_brain /
AgentCore.ui_agent.ui_agent_main at module level (co_brain.py,
Automation/Automation_Brain.py) were changed to import lazily, at first
actual use, mirroring the get_shared_session() lazy-singleton pattern
already used in platform_adapters/browser_automation.py.

This test now asserts the fix holds: a bare `import
AgentCore.code_engine.engine` must NOT pull in pyautogui. If this
regresses back to True, the eager coupling has been reintroduced
somewhere in AgentCore's import chain.
"""
import subprocess
import sys
import unittest


class TestAgentCoreUICoupling(unittest.TestCase):
    def test_importing_code_engine_does_not_pull_in_pyautogui(self):
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
            "False",
            "AgentCore.code_engine.engine should not need pyautogui at import "
            "time -- if this now prints True, the eager AgentCore.__init__.py "
            "-> agent_brain -> ui_perception -> pyautogui coupling has been "
            "reintroduced.",
        )


if __name__ == "__main__":
    unittest.main()

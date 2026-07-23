"""
Phase 3a's non-negotiable boundary, enforced rather than just stated:
memory must never be reachable from the resolution/routing path, so it
can never be used (now or by a future change) to skip or weaken a
confirmation step. Same subprocess + sys.modules technique as
tests/test_agentcore_ui_coupling.py's mss/pyautogui coupling regression
test -- catches a transitive import, not just a direct one.
"""
import subprocess
import sys
import unittest


class TestSessionMemoryBoundary(unittest.TestCase):
    def test_resolution_gate_does_not_import_session_memory(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import AgentCore.resolution_gate; "
                "print('AgentCore.session_memory' in sys.modules)",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout.strip().splitlines()[-1],
            "False",
            "AgentCore.resolution_gate must never import AgentCore.session_memory, "
            "directly or transitively -- memory must not be reachable from the "
            "confirmation/gating path.",
        )

    def test_command_router_does_not_import_session_memory(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import AgentCore.command_router; "
                "print('AgentCore.session_memory' in sys.modules)",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout.strip().splitlines()[-1],
            "False",
            "AgentCore.command_router must never import AgentCore.session_memory, "
            "directly or transitively.",
        )


if __name__ == "__main__":
    unittest.main()

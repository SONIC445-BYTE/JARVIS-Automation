"""
Regression test for the full-suite pytest hang found this round: importing
NetHyTechSTT.listen used to unconditionally, at module import time, run
ChromeDriverManager().install() (a live network call), launch a real
headless Chrome via webdriver.Chrome(), and navigate to an external site
via driver.get() -- none of those three steps has a timeout. Any test file
importing jarvis.py or co_brain.py (test_jarvis_import.py,
test_onboarding.py, test_pending_resume_flow.py,
test_install_confirmation_flow.py, etc.) transitively imported this module
during pytest collection, which hung the entire suite indefinitely on a
real machine with real network/Chrome (this didn't surface in prior
sandboxed remote-review passes, which lack real network/Chrome access).

Fixed the same way the AgentCore pyautogui/mss import coupling was fixed:
defer the expensive work to first actual use (inside listen()) instead of
running it as an import-time side effect. This test asserts the fix
holds -- a bare `import NetHyTechSTT.listen` must not create a driver.
"""
import subprocess
import sys
import unittest


class TestNetHyTechListenImportCoupling(unittest.TestCase):
    def test_importing_listen_module_does_not_create_driver(self):
        # Run in a subprocess, with a hard timeout, so a regression fails
        # the test instead of hanging the whole suite again.
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import NetHyTechSTT.listen as l; print(l._driver is None)",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout.strip().splitlines()[-1],
            "True",
            "Importing NetHyTechSTT.listen should not create a Chrome "
            "driver at import time -- if this now prints False, the "
            "eager chromedriver-download/browser-launch/navigate coupling "
            "has been reintroduced at module level.",
        )

    def test_importing_co_brain_does_not_hang_or_create_driver(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import co_brain; import NetHyTechSTT.listen as l; "
                "print(l._driver is None)",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip().splitlines()[-1], "True")

    def test_importing_jarvis_pulls_in_neither_selenium_nor_webdriver_manager(self):
        # The fix went further than deferring driver construction -- the
        # selenium/webdriver_manager imports themselves are also lazy now,
        # so a bare `import jarvis` should not add either to sys.modules
        # at all, not just leave the driver unconstructed.
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import jarvis; "
                "print('selenium' in sys.modules); "
                "print('webdriver_manager' in sys.modules)",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()[-2:]
        self.assertEqual(
            lines,
            ["False", "False"],
            "import jarvis should not pull selenium or webdriver_manager "
            "into sys.modules -- if either now prints True, the lazy-import "
            "fix has regressed.",
        )


if __name__ == "__main__":
    unittest.main()

"""
Phase 0 safety net: importing jarvis.py must not execute the interactive
entrypoint or crash. All CLI-mode branching lives under
`if __name__ == "__main__":`, so a plain import should be side-effect-free
beyond module-level initialization.
"""
import subprocess
import sys
import unittest


class TestJarvisImport(unittest.TestCase):
    def test_import_does_not_crash(self):
        import jarvis  # noqa: F401 - import is the assertion

    def test_code_engine_attribute_exists(self):
        import jarvis
        self.assertTrue(hasattr(jarvis, "CODE_ENGINE"))

    def test_stdout_reconfigured_to_utf8(self):
        # Regression test for the diagnosed wake-word failure: on a
        # Windows console defaulting to cp1252, PersistentWakeService's
        # very first state-transition print (containing "->", a Unicode
        # arrow) raised an uncaught UnicodeEncodeError and crashed the
        # whole process before wake detection ever started -- confirmed
        # live on the real machine (sys.stdout.encoding was 'cp1252').
        # jarvis.py now reconfigures stdout/stderr to UTF-8 at import
        # time, before any other import (some of which print during
        # import). This asserts that fix stays in place.
        import jarvis  # noqa: F401
        self.assertEqual(sys.stdout.encoding.lower(), "utf-8")
        self.assertEqual(sys.stderr.encoding.lower(), "utf-8")

    def test_arrow_and_symbol_prints_do_not_raise(self):
        # Direct regression check for the exact crash: printing the
        # Unicode characters jarvis.py's own state-transition logging
        # uses (see _set_state) must not raise now that stdout is
        # reconfigured.
        import jarvis  # noqa: F401
        print("[State] sleep → wake")  # → = the arrow that crashed
        print("✓ ok")  # ✓ = wake_detector.py's original checkmark

    def test_import_does_not_pull_in_selenium_or_launch_a_browser(self):
        # Regression test for the confirmed active bug (not just latent
        # risk): NetHyTechSTT/listen.py used to unconditionally download
        # chromedriver, launch a real headless Chrome, and navigate to an
        # external site as side effects of pure module import -- reached
        # transitively via jarvis.py -> co_brain.py's top-level `from
        # NetHyTechSTT.listen import listen`. None of those three steps
        # has a timeout, so this hung a full pytest collection run dead
        # on a real machine with real network/Chrome (measured: ~29s just
        # for `import jarvis` before the fix, with selenium/
        # webdriver_manager both loaded). Same "eager import drags in a
        # heavy subsystem" shape as the AgentCore/mss/pyautogui coupling
        # fix -- see NetHyTechSTT/listen.py's _get_driver() for the fix
        # itself (both the driver construction AND the selenium/
        # webdriver_manager imports are now lazy, deferred to first real
        # use of listen()).
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import jarvis; "
                "print('selenium' in sys.modules or any(m.startswith('selenium.') for m in sys.modules)); "
                "print('webdriver_manager' in sys.modules or any(m.startswith('webdriver_manager.') for m in sys.modules))",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(
            lines[-2],
            "False",
            "import jarvis should not pull in selenium -- if this now prints "
            "True, the NetHyTechSTT/listen.py lazy-import fix has regressed.",
        )
        self.assertEqual(
            lines[-1],
            "False",
            "import jarvis should not pull in webdriver_manager -- if this now "
            "prints True, the NetHyTechSTT/listen.py lazy-import fix has regressed.",
        )


if __name__ == "__main__":
    unittest.main()

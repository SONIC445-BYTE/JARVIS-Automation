"""
Phase 0 safety net: importing jarvis.py must not execute the interactive
entrypoint or crash. All CLI-mode branching lives under
`if __name__ == "__main__":`, so a plain import should be side-effect-free
beyond module-level initialization.
"""
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


if __name__ == "__main__":
    unittest.main()

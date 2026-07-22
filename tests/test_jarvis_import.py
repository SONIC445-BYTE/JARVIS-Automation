"""
Phase 0 safety net: importing jarvis.py must not execute the interactive
entrypoint or crash. All CLI-mode branching lives under
`if __name__ == "__main__":`, so a plain import should be side-effect-free
beyond module-level initialization.
"""
import unittest


class TestJarvisImport(unittest.TestCase):
    def test_import_does_not_crash(self):
        import jarvis  # noqa: F401 - import is the assertion

    def test_code_engine_attribute_exists(self):
        import jarvis
        self.assertTrue(hasattr(jarvis, "CODE_ENGINE"))


if __name__ == "__main__":
    unittest.main()

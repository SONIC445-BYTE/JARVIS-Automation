"""
Phase 1: pins the fix for jarvis.py's broken code-engine success contract.

Before this fix, jarvis.py's code-engine dispatch checked
result.get("success"), which CodeEngine.handle_command() never sets --
every coding command reported "Code task failed: None" regardless of
whether generation actually worked. _code_result_is_success() replaces
that check by reading the fields the engine actually returns.
"""
import unittest
from jarvis import _code_result_is_success


class TestCodeResultIsSuccess(unittest.TestCase):
    def test_dry_run_with_patch_summary_is_success(self):
        result = {
            "dry_run": True,
            "patch_summary": "Would create hello_world.py",
            "patch_diff": "...",
            "file_path": "/sandbox/20260722",
            "sandbox_path": "/sandbox/20260722",
        }
        self.assertTrue(_code_result_is_success(result))

    def test_dry_run_with_empty_patch_summary_is_failure(self):
        result = {"dry_run": True, "patch_summary": "", "file_path": ""}
        self.assertFalse(_code_result_is_success(result))

    def test_write_with_file_path_is_success(self):
        result = {"dry_run": False, "file_path": "/sandbox/20260722/hello_world.py"}
        self.assertTrue(_code_result_is_success(result))

    def test_write_with_empty_file_path_is_failure(self):
        result = {"dry_run": False, "file_path": ""}
        self.assertFalse(_code_result_is_success(result))

    def test_old_broken_check_would_always_have_failed(self):
        """Documents the bug this replaces: the old caller checked
        result.get("success"), a key CodeEngine.handle_command() never
        sets, so it was always None/falsy even for real successes."""
        result = {
            "dry_run": True,
            "patch_summary": "Would create hello_world.py",
            "file_path": "/sandbox/20260722",
        }
        self.assertIsNone(result.get("success"))
        self.assertTrue(_code_result_is_success(result))


if __name__ == "__main__":
    unittest.main()

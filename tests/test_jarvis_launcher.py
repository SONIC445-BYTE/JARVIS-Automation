"""
jarvis_launcher.py is the console-script entry point registered by
pyproject.toml's [project.scripts] (`pip install -e .` -> a real
`jarvis` command on PATH). It's a thin subprocess wrapper, not a
reimplementation of jarvis.py's CLI -- these tests mock subprocess.run
so they never actually spawn jarvis.py (which would hang waiting for
mic input in most modes).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

import jarvis_launcher


class TestJarvisLauncher(unittest.TestCase):
    def test_project_dir_is_this_files_directory(self):
        self.assertEqual(jarvis_launcher.PROJECT_DIR, Path(__file__).resolve().parent.parent)

    def test_jarvis_script_path_is_correct(self):
        self.assertEqual(jarvis_launcher.JARVIS_SCRIPT, jarvis_launcher.PROJECT_DIR / "jarvis.py")
        self.assertTrue(jarvis_launcher.JARVIS_SCRIPT.exists())

    @mock.patch("jarvis_launcher.subprocess.run")
    def test_main_runs_jarvis_py_with_project_dir_as_cwd(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0)
        with mock.patch.object(sys, "argv", ["jarvis", "--convo"]):
            code = jarvis_launcher.main()

        self.assertEqual(code, 0)
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        command = args[0]
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(Path(command[1]), jarvis_launcher.JARVIS_SCRIPT)
        self.assertEqual(command[2:], ["--convo"])
        self.assertEqual(kwargs["cwd"], str(jarvis_launcher.PROJECT_DIR))

    @mock.patch("jarvis_launcher.subprocess.run")
    def test_main_passes_through_extra_args(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0)
        with mock.patch.object(sys, "argv", ["jarvis", "--background", "--setup"]):
            jarvis_launcher.main()
        args, _ = mock_run.call_args
        self.assertEqual(args[0][2:], ["--background", "--setup"])

    @mock.patch("jarvis_launcher.subprocess.run")
    def test_main_propagates_nonzero_exit_code(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=3)
        with mock.patch.object(sys, "argv", ["jarvis"]):
            code = jarvis_launcher.main()
        self.assertEqual(code, 3)

    def test_main_reports_missing_script_without_crashing(self):
        with mock.patch.object(jarvis_launcher, "JARVIS_SCRIPT", Path("does_not_exist.py")):
            code = jarvis_launcher.main()
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

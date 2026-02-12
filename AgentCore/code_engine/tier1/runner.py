"""
Runner for Tier-1.
Runs formatters (black), linters (flake8), and tests (pytest).
"""
import os
import subprocess
from typing import List, Dict, Any

class Runner:
    def __init__(self, cwd: str = None):
        self.cwd = cwd or os.getcwd()

    def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                cmd,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Command not found: {cmd[0]}",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "returncode": -1
            }

    def run_formatter(self, file_paths: List[str]) -> Dict[str, Any]:
        """Run black formatter on files."""
        if not file_paths:
            return {"success": True, "message": "No files to format"}
            
        cmd = ["black", "--quiet"] + file_paths
        return self._run_command(cmd)

    def run_linter(self, file_paths: List[str]) -> Dict[str, Any]:
        """Run flake8 linter on files."""
        if not file_paths:
            return {"success": True, "message": "No files to lint"}
            
        cmd = ["flake8"] + file_paths
        return self._run_command(cmd)

    def run_tests(self, test_path: str = None) -> Dict[str, Any]:
        """Run pytest."""
        cmd = ["pytest"]
        if test_path:
            cmd.append(test_path)
            
        result = self._run_command(cmd)
        
        # Parse output for summary if possible
        # (Simplified parsing)
        passed = "passed" in result['stdout'] or "passed" in result['stdout']
        failed = "failed" in result['stdout'] or "error" in result['stdout']
        
        return {
            "success": result['success'],
            "output": result['stdout'] + "\n" + result['stderr'],
            "passed": passed,
            "failed": failed
        }

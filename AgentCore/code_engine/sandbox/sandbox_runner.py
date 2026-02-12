"""
Sandbox Runner.
Executes code changes in a safe environment.
"""
import os
from typing import Dict, Any, List
from .fs_snapshot import FSSnapshot
from AgentCore.code_engine.tier1.repo_manager import RepoManager
from AgentCore.code_engine.tier1.runner import Runner

class SandboxRunner:
    def __init__(self, root_dir: str = None):
        self.root_dir = root_dir or os.getcwd()
        self.snapshot = FSSnapshot(self.root_dir)
        self.repo = RepoManager(self.root_dir)
        self.runner = Runner(self.root_dir)

    def run_dry(self, patch: str, test_cmd: str = None) -> Dict[str, Any]:
        """
        Run a patch in dry-run mode (sandbox).
        1. Parse patch to find affected files.
        2. Snapshot those files.
        3. Apply patch.
        4. Run check/test.
        5. Restore snapshot.
        """
        # 1. Identify files (simplified parsing)
        affected_files = []
        for line in patch.splitlines():
            if line.startswith('+++ b/'):
                path = line[6:].strip()
                affected_files.append(os.path.abspath(os.path.join(self.root_dir, path)))

        if not affected_files:
            return {"success": False, "error": "No files found in patch"}

        # 2. Snapshot
        self.snapshot.create_snapshot(affected_files)

        try:
            # 3. Apply patch
            apply_result = self.repo.apply_patch(patch, dry_run=False) # Apply for real in sandbox (which IS the real FS here, guarded by snapshot restore)
            
            if not apply_result['success']:
                return {"success": False, "error": apply_result.get('error')}

            # 4. Run verification
            test_result = {"success": True, "message": "Patch applied successfully"}
            if test_cmd:
                # Security risk: running arbitrary command.
                # Only use predefined runner methods if possible.
                test_result = self.runner.run_tests()

            return {
                "success": test_result['success'],
                "apply_result": apply_result,
                "test_result": test_result,
                "dry_run": True
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
            
        finally:
            # 5. Restore (CRITICAL)
            self.snapshot.restore()

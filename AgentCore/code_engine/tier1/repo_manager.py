"""
Repo Manager for Tier-1.
Handles git operations including diff generation and patch application.
"""
import os
import subprocess
from typing import Optional, List, Dict, Any

class RepoManager:
    def __init__(self, repo_path: str = None):
        if repo_path is None:
            # Default to current working directory
            repo_path = os.getcwd()
        self.repo_path = repo_path

    def _run_git(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

    def get_diff(self, staged: bool = False) -> str:
        """Get the current diff."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        result = self._run_git(args)
        if result.returncode != 0:
            raise RuntimeError(f"Git diff failed: {result.stderr}")
        return result.stdout

    def apply_patch(self, patch_content: str, dry_run: bool = True) -> Dict[str, Any]:
        """Apply a patch (unified diff)."""
        # Create a temporary patch file
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.patch', encoding='utf-8') as f:
            f.write(patch_content)
            patch_file = f.name
            
        try:
            # Check/Dry-run
            check_args = ["apply", "--check", patch_file]
            check_result = self._run_git(check_args)
            
            if check_result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Patch check failed: {check_result.stderr}",
                    "dry_run": True
                }
                
            if dry_run:
                return {
                    "success": True,
                    "message": "Patch check passed (dry-run)",
                    "dry_run": True
                }
                
            # Apply
            apply_args = ["apply", patch_file]
            apply_result = self._run_git(apply_args)
            
            if apply_result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Patch apply failed: {apply_result.stderr}",
                    "dry_run": False
                }
                
            return {
                "success": True,
                "message": "Patch applied successfully",
                "dry_run": False
            }
            
        finally:
            if os.path.exists(patch_file):
                os.remove(patch_file)

    def create_branch(self, branch_name: str) -> bool:
        result = self._run_git(["checkout", "-b", branch_name])
        return result.returncode == 0

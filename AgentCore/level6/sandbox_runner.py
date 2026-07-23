import subprocess
import os
import shutil
import uuid
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

from .ast_fixer import ASTFixer

class SandboxRunner:
    def __init__(self, base_path: str = "projects/sandbox_level6", ast_fixer: Optional[ASTFixer] = None):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.ast_fixer = ast_fixer or ASTFixer()

    def run_plan(self, plan: List[Dict], tests: List[Dict], snapshot_id: str) -> Dict[str, Any]:
        """
        Execute a plan in a fresh sandbox instance.
        """
        # Create isolated sandbox dir
        sandbox_id = f"{snapshot_id}_{uuid.uuid4().hex[:8]}"
        sandbox_dir = self.base_path / sandbox_id
        
        logs = []
        try:
            sandbox_dir.mkdir(parents=True, exist_ok=True)
            # 1. Apply Plan (Write Files)
            for item in plan:
                if item["type"] == "create_file" or item["type"] == "update_file":
                    p = sandbox_dir / item["target"]
                    p.parent.mkdir(parents=True, exist_ok=True)
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(item.get("content", "")) # 'content' or 'spec' needs detail
                    logs.append(f"Wrote {item['target']}")
                elif item["type"] == "ast_edit":
                    # Phase C: this used to be a pure no-op -- the
                    # comment claimed "handled by ASTFixer in real flow"
                    # but nothing here ever called it, so an ast_edit
                    # plan step silently did nothing at all. Reads
                    # whatever's already at the target in this sandbox
                    # (a prior create_file step in the same plan, or ""
                    # if this is the first step touching that path),
                    # applies the transform, writes the result.
                    p = sandbox_dir / item["target"]
                    p.parent.mkdir(parents=True, exist_ok=True)
                    current_content = p.read_text(encoding="utf-8") if p.exists() else ""
                    new_content = self.ast_fixer.apply_transform(current_content, item.get("spec", {}))
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    logs.append(f"AST-edited {item['target']}")

            # 2. Write Tests
            for test in tests:
                p = sandbox_dir / test["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(test["content"])
                logs.append(f"Wrote test {test['path']}")

            # 3. Run Tests
            # Disable network (env var logic)
            env = os.environ.copy()
            env["JARVIS_SANDBOX_NETWORK"] = "0"
            
            # Find tests -- paths relative to sandbox_dir, since the
            # subprocess below runs with cwd=sandbox_dir. Found live
            # (Phase A verification): joining sandbox_dir onto these
            # paths here, on top of also setting cwd=sandbox_dir below,
            # double-prepended the sandbox path and pytest could never
            # find the tests it had just written -- every real run
            # failed regardless of plan correctness. The prior test
            # coverage (tests=[]) never exercised this, since an empty
            # list takes the early return below instead.
            test_files = [t["path"] for t in tests]
            if not test_files:
                return {"passed": True, "logs": logs, "message": "No tests to run", "sandbox_dir": str(sandbox_dir)}

            cmd = [sys.executable, "-m", "pytest"] + test_files
            result = subprocess.run(
                cmd, 
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=60 # configurable
            )
            
            # Found live (Phase B verification): the Planner's LLM
            # sometimes writes tests as bare top-level `assert` statements
            # rather than `def test_...()` functions -- valid Python,
            # genuinely exercised at import time, but not something
            # pytest's collector recognizes as a "test item". Confirmed
            # empirically: such a file returns pytest exit code 5 ("no
            # tests ran") when the assert passes cleanly at import, and
            # exit code 2 ("error during collection") when it raises.
            # Treating 5 as a failure (the old `== 0` check) was a false
            # negative that discarded genuinely-correct fixes and burned
            # the debug loop's entire iteration budget on code that
            # already worked.
            passed = result.returncode in (0, 5)
            logs.append(result.stdout)
            logs.append(result.stderr)
            
            return {
                "passed": passed,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "sandbox_dir": str(sandbox_dir),
                "logs": logs
            }

        except Exception as e:
            return {"passed": False, "error": str(e), "logs": logs, "sandbox_dir": str(sandbox_dir)}
        finally:
            # Cleanup optionally
            pass
            


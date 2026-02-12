import shutil
import os
import time
from pathlib import Path
from typing import Optional

class RollbackManager:
    def __init__(self, sandbox_root: str = "projects/sandbox_level6"):
        self.sandbox_root = Path(sandbox_root)
        self.snapshots_dir = self.sandbox_root / ".snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, snapshot_id: str, source_dir: str) -> bool:
        """Create a backup of the source_dir."""
        try:
            target = self.snapshots_dir / snapshot_id
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source_dir, target, dirs_exist_ok=True)
            return True
        except Exception as e:
            print(f"[Rollback] Snapshot creation failed: {e}")
            return False

    def revert(self, snapshot_id: str, target_dir: str) -> bool:
        """Restore target_dir from snapshot."""
        try:
            snapshot_path = self.snapshots_dir / snapshot_id
            if not snapshot_path.exists():
                print(f"[Rollback] Snapshot {snapshot_id} not found.")
                return False
            
            # Wipe target and restore
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            
            shutil.copytree(snapshot_path, target_dir)
            return True
        except Exception as e:
            print(f"[Rollback] Revert failed: {e}")
            return False

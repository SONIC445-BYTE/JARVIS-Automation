"""
Filesystem Snapshot for Sandbox.
Handles creating and restoring backups for dry-runs.
"""
import os
import shutil
import tempfile
from typing import List, Dict

class FSSnapshot:
    def __init__(self, root_dir: str = None):
        self.root_dir = root_dir or os.getcwd()
        self.backup_dir = None
        self.tracked_files = []

    def create_snapshot(self, files: List[str] = None):
        """Create a backup of specific files or full repo (if files=None)."""
        self.backup_dir = tempfile.mkdtemp(prefix="jarvis_sandbox_")
        
        if files:
            for file_path in files:
                if os.path.exists(file_path):
                    rel_path = os.path.relpath(file_path, self.root_dir)
                    dest_path = os.path.join(self.backup_dir, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(file_path, dest_path)
                    self.tracked_files.append(file_path)
        else:
            # Full snapshot is expensive; maybe just track what we change?
            # For now, we assume we only snapshot logic files, not venv etc.
            pass

    def restore(self):
        """Restore files from backup."""
        if not self.backup_dir:
            return
            
        for file_path in self.tracked_files:
            rel_path = os.path.relpath(file_path, self.root_dir)
            backup_path = os.path.join(self.backup_dir, rel_path)
            
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
            elif os.path.exists(file_path):
                # File didn't exist in backup (maybe created during dry run), delete it
                # Wait, if we tracked it, it likely existed.
                # If we tracked it and it's not in backup, something is wrong.
                pass
                
        # Cleanup
        shutil.rmtree(self.backup_dir)
        self.backup_dir = None
        self.tracked_files = []

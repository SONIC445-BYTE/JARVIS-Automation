"""
Audit System for Code Engine.
Logs all actions to a JSONL file.
"""
import os
import json
import time
import hashlib
from typing import Dict, Any

class AuditLogger:
    def __init__(self, log_dir: str = None):
        if log_dir is None:
            # Default to data/logs/code_engine.jsonl
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            log_dir = os.path.join(base_path, "data", "logs")
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        self.log_file = os.path.join(log_dir, "code_engine.jsonl")

    def log_event(self, event_type: str, details: Dict[str, Any]):
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "details": details,
            "event_id": hashlib.md5(f"{time.time()}{event_type}".encode()).hexdigest()
        }
        
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"Audit log failed: {e}")

    def log_patch_proposal(self, command: str, patch: str, confidence: float):
        self.log_event("patch_proposed", {
            "command": command,
            "patch_hash": hashlib.md5(patch.encode()).hexdigest(),
            "confidence": confidence,
            "patch_preview": patch[:200]
        })

    def log_execution(self, command_id: str, success: bool, output: str):
        self.log_event("execution_result", {
            "command_id": command_id,
            "success": success,
            "output_summary": output[:200]
        })

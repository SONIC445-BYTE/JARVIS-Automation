"""
Audit Log for Level-4.
Immutable append-only log with HMAC signature.
"""
import os
import time
import json
import hashlib
import hmac

class AuditLog:
    def __init__(self, log_dir: str = None):
        self.secret_key = b"change_this_to_owner_key" # In prod, load from secure store
        if log_dir is None:
             base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
             log_dir = os.path.join(base_path, "data", "audit")
        
        self.log_file = os.path.join(log_dir, "level4_audit.jsonl")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    def log_entry(self, user_id: str, command: str, plan: dict, result: dict):
        entry = {
            "timestamp": time.time(),
            "user_id": user_id,
            "command": command,
            "plan_hash": hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
            "result_summary": "success" if result.get('success') else "failure"
        }
        
        # Sign entry
        serialized = json.dumps(entry, sort_keys=True)
        signature = hmac.new(self.secret_key, serialized.encode(), hashlib.sha256).hexdigest()
        
        final_entry = {
            "data": entry,
            "signature": signature
        }
        
        with open(self.log_file, "a") as f:
            f.write(json.dumps(final_entry) + "\n")

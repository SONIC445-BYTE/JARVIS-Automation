import json
import time
import hmac
import hashlib
import os
from pathlib import Path
from typing import Dict, Any

class UIAudit:
    """Logs UI actions with signatures and screenshot links."""
    
    def __init__(self, hmac_key: str = "JARVIS_UI_SECRET"):
        self.log_dir = Path("data/ui_actions")
        self.hmac_key = os.environ.get("JARVIS_HMAC_KEY", hmac_key)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_action(self, request_id: str, action_data: Dict[str, Any], result: Any):
        """Append an action log with a signature."""
        timestamp = time.time()
        entry = {
            "req_id": request_id,
            "ts": timestamp,
            "action": action_data,
            "result": str(result)
        }
        
        json_str = json.dumps(entry, sort_keys=True)
        signature = hmac.new(
            self.hmac_key.encode(),
            json_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        entry["sig"] = signature
        
        # Write to per-day log or master log
        log_file = self.log_dir / f"audit_{time.strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
        print(f"[UIAudit] Logged action {request_id}")

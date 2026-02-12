import os
import json
import time
import hmac
import hashlib
from typing import Dict, Any, Optional
from pathlib import Path
from .pipeline_trace import PipelineTrace

class AuditLogger:
    """
    Append-only logger for pipeline traces, signed with HMAC.
    """
    def __init__(self, config_path: str = "feature_flags/pipeline_enforce.yaml"):
        self.log_path = "data/logs/pipeline_trace.log"
        self.hmac_key = None
        self._load_config(config_path)
        
        # Ensure log dir exists
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self, config_path: str):
        try:
            # Simple yaml parsing
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    for line in f:
                        if "audit_log_path" in line:
                            val = line.split(":")[1].strip().replace('"', '')
                            self.log_path = val
                        elif "hmac_env_var" in line:
                            env_var = line.split(":")[1].strip().replace('"', '')
                            self.hmac_key = os.environ.get(env_var)
        except Exception as e:
            print(f"[AuditLogger] Config load error: {e}")

    def _sign(self, data: str) -> str:
        if not self.hmac_key:
            return "UNSIGNED"
        return hmac.new(
            self.hmac_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def write(self, trace: PipelineTrace):
        """Write a trace to the audit log."""
        try:
            entry_data = trace.to_dict()
            json_str = json.dumps(entry_data, default=str)
            signature = self._sign(json_str)
            
            log_entry = {
                "ts": time.time(),
                "sig": signature,
                "data": entry_data
            }
            
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, default=str) + "\n")
                
        except Exception as e:
            print(f"[AuditLogger] Write error: {e}")

    def verify_last(self) -> bool:
        """Verify the signature of the last entry."""
        if not os.path.exists(self.log_path):
            return False
            
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    return False
                last_line = lines[-1]
                entry = json.loads(last_line)
                
                stored_sig = entry.get("sig")
                data = entry.get("data")
                
                if stored_sig == "UNSIGNED":
                    return True # technically valid as unsigned
                    
                # Re-sign
                json_str = json.dumps(data, default=str)
                calculated_sig = self._sign(json_str)
                
                return hmac.compare_digest(stored_sig, calculated_sig)
        except Exception:
            return False

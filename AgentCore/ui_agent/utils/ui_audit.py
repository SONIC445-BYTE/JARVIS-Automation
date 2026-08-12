import json
import os
import time
import hmac
import hashlib
from pathlib import Path
from typing import Dict, Any

from AgentCore.secure_key import resolve_key

#: Overrides where UI action logs are written. Exists because
#: UIAudit's directory was previously hardcoded, so every test
#: constructing a real UIAgentMain wrote real files into the actual
#: repo's data/ui_actions/ -- confirmed by finding real dated log
#: files there. Same mechanism and naming shape as DEC-002's
#: JARVIS_CLINICAL_AUDIT_LOG_DIR; AgentCore/ui_agent/tests/conftest.py
#: sets it per-test to a tmp_path.
LOG_DIR_ENV_VAR = "JARVIS_UI_ACTIONS_LOG_DIR"
DEFAULT_LOG_DIR = "data/ui_actions"


class UIAudit:
    """Logs UI actions with signatures and screenshot links."""

    def __init__(self):
        self.log_dir = Path(os.environ.get(LOG_DIR_ENV_VAR, DEFAULT_LOG_DIR))
        # D14: this used to be os.environ.get("JARVIS_HMAC_KEY", "JARVIS_UI_SECRET")
        # -- the identical hardcoded-default-key weakness D2 fixed in
        # memory_store.py/mode_manager/audit.py. Every real caller
        # (ui_agent_main.py) constructs UIAudit() with no key argument, so
        # every real deployment silently signed with the literal string
        # "JARVIS_UI_SECRET" unless JARVIS_HMAC_KEY happened to be set.
        # Shares the same fail-closed resolution as D2/DEC-002, own purpose
        # namespace so it can't collide with the other two HMAC key uses.
        self.hmac_key = resolve_key("ui_audit", "JARVIS_UI_AUDIT_KEY")
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
            self.hmac_key,
            json_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        entry["sig"] = signature
        
        # Write to per-day log or master log
        log_file = self.log_dir / f"audit_{time.strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
        print(f"[UIAudit] Logged action {request_id}")

"""Minimal adapter template demonstrating the required adapter contract.

Copy this into a new adapter module and adapt implementation details.
All methods follow the strict contract in .github/copilot-instructions.md
"""
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any

LOG_PATH = Path.cwd() / "logs" / "jarvis_actions.log"
LOG_PATH.parent.mkdir(exist_ok=True)


def _log_action(action: str, target: str, result: Dict[str, Any], dry_run: bool):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "target": target,
        "result": result,
        "dry_run_flag": bool(dry_run),
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


class MinimalAdapter:
    """Demonstrates the adapter contract.

    Methods are idempotent, accept `dry_run: bool = False`, and return
    a dict: {"status": "ok"|"blocked"|"error", "meta": {...}}
    """

    def open_app(self, app_name: str, dry_run: bool = False) -> Dict[str, Any]:
        # Idempotent: calling open_app twice should be safe
        result = {"status": "ok", "meta": {"message": f"(simulated) open {app_name}"}}
        _log_action("open_app", app_name, result, dry_run)
        return result

    def close_app(self, app_name: str, dry_run: bool = False) -> Dict[str, Any]:
        result = {"status": "ok", "meta": {"message": f"(simulated) close {app_name}"}}
        _log_action("close_app", app_name, result, dry_run)
        return result

    def send_message(self, target: str, message: str, dry_run: bool = False) -> Dict[str, Any]:
        # Prevent accidental broadcast — adapter should validate targets
        if isinstance(target, (list, tuple)):
            return {"status": "blocked", "meta": {"reason": "bulk targets not allowed"}}

        result = {"status": "ok", "meta": {"target": target, "message": message}}
        _log_action("send_message", target, result, dry_run)
        return result

    def read_unread(self, limit: int = 10, dry_run: bool = False) -> Dict[str, Any]:
        # Return a predictable shape for tests
        items = [{"id": i, "from": "user@example.com", "snippet": "..."} for i in range(min(limit, 10))]
        result = {"status": "ok", "meta": {"count": len(items), "items": items}}
        _log_action("read_unread", "inbox", result, dry_run)
        return result


if __name__ == "__main__":
    # Quick manual smoke test (dry-run)
    a = MinimalAdapter()
    print(a.open_app("notepad", dry_run=True))
    print(a.send_message("alice", "hello", dry_run=True))
    print(a.read_unread(3, dry_run=True))

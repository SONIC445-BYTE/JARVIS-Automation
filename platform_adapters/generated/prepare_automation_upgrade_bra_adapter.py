from typing import Any, Dict, List
from platform_adapters.adapter_base import AdapterBase


class PrepareAutomationUpgradeBraAdapter(AdapterBase):
    def open_app(self) -> bool:
        self.log_action("open_app", {"target": "prepare_automation_upgrade_bra", "dry_run": self.dry_run})
        return True

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "prepare_automation_upgrade_bra", "dry_run": self.dry_run})
        return True

    def send_message(self, target: str, message: str) -> bool:
        self.log_action("send_message", {"target": target, "message": message, "dry_run": self.dry_run})
        return True

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.log_action("read_unread", {"target": "prepare_automation_upgrade_bra", "limit": limit, "dry_run": self.dry_run})
        return []

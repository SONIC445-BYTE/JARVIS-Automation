from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class NewRelicAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "New Relic"

    @property
    def supported_actions(self) -> List[str]:
        return ["agent_deployed", "dashboard_built", "alert_condition_created", "nrql_query_written", "log_forwarded", "apm_transaction_traced", "infrastructure_host_monitored", "browser_monitoring_enabled", "mobile_crash_analyzed", "synthetic_monitor_checked", "vulnerability_management_scan_run", "security_audit_log_reviewed", "user_permissions_managed", "api_key_rotated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "newrelic" in title or "newrelic" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://newrelic.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True

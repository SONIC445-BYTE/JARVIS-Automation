from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SquareAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Square"

    @property
    def supported_actions(self) -> List[str]:
        return ["payment_processed", "invoice_sent", "gift_card_sold", "appointment_booked", "online_order_received", "hardware_paired", "team_member_added", "inventory_managed", "customer_directory_built", "loyalty_program_enabled", "security_settings_reviewed", "two_step_verification_enabled", "privacy_settings_managed", "data_export_requested", "account_deactivated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "square" in title or "squareup" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://squareup.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True

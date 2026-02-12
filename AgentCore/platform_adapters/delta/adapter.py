from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class DeltaAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Delta"

    @property
    def supported_actions(self) -> List[str]:
        return ["flight_booked", "seat_selected", "check_in_completed", "boarding_pass_accessed", "upgrade_requested", "skymiles_earned", "delta_sync_used", "fly_ready_confirmed", "rebooking_requested", "unaccompanied_minor_service_booked", "medallion_status_achieved", "companion_certificate_used", "delta_sky_club_accessed", "upgrade_clearance_received", "mileage_run_calculated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "delta" in title or "delta" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://delta.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True

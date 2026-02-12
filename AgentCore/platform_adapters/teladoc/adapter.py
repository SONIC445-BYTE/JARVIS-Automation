from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class TeladocAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Teladoc"

    @property
    def supported_actions(self) -> List[str]:
        return ["consultation_scheduled", "video_visit_started", "prescription_sent", "medical_record_accessed", "follow_up_booked", "symptom_checker_used", "health_record_synced", "biometric_device_connected", "medication_reminder_set", "care_plan_accessed", "therapist_matched", "psychiatrist_consulted", "dermatologist_visit_completed", "nutritionist_advised", "specialist_referred"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "teladoc" in title or "teladoc" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://teladoc.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True

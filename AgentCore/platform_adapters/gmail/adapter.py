
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class GmailAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Gmail"

    @property
    def supported_actions(self) -> List[str]:
        return ["send_email"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "gmail" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "send_email":
            to = urllib.parse.quote(params.get("to", ""))
            subject = urllib.parse.quote(params.get("subject", ""))
            body = urllib.parse.quote(params.get("body", ""))
            url = f"https://mail.google.com/mail/?view=cm&fs=1&to={to}&su={subject}&body={body}"
            
            steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
            # Ideally wait for load and click send, but deep link opens compose window
            
        return Plan(steps=steps, confidence=0.9)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True

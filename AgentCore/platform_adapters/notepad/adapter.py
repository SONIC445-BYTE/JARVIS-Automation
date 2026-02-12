
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep

class NotepadAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Notepad"

    @property
    def supported_actions(self) -> List[str]:
        return ["type_text", "save_file"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "notepad" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "type_text":
            text = params.get("text", "")
            steps.append(ExecutionStep(action="type", target=text, parameters={"text": text}))
            
        elif action_name == "save_file":
            filename = params.get("filename", "note.txt")
            # Inferred shortcut Ctrl+S
            # steps.append(ExecutionStep(action="press", target="ctrl+s", ...)) # Need press action
            # Fallback to UI clicking if "press" not available, or just log warning
            steps.append(ExecutionStep(action="click", target="File", parameters={"x": 50, "y": 30})) # Guess
            steps.append(ExecutionStep(action="click", target="Save", parameters={"x": 50, "y": 100})) # Guess
            steps.append(ExecutionStep(action="type", target=filename, parameters={"text": filename}))
            steps.append(ExecutionStep(action="click", target="Save Button", parameters={"x": 400, "y": 400})) # Guess
            
        return Plan(steps=steps, confidence=0.7)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True

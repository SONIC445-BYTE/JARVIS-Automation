from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan

try:
    from ...intent_planner import ExecutionStep
except ImportError:
    from dataclasses import dataclass
    @dataclass
    class ExecutionStep:
        action: str = ""
        target: str = ""
        parameters: dict = None

import subprocess, os


class AdobeAcrobatAdapter(BaseAdapter):
    """Adapter for Adobe Acrobat (local desktop application)."""

    EXE_HINT = "Acrobat.exe"

    @property
    def platform_name(self) -> str:
        return "Adobe Acrobat"

    @property
    def supported_actions(self) -> List[str]:
        return ["pdf_opened", "pdf_created_from_file", "pdf_created_from_scanner", "pdf_saved", "pdf_saved_as", "pdf_closed", "pdf_printed", "pdf_exported_to_word", "pdf_exported_to_excel", "pdf_exported_to_powerpoint", "pdf_exported_to_image", "text_selected", "text_copied", "text_highlighted", "comment_added", "sticky_note_added", "text_markup_applied", "stamp_added", "drawing_markup_added", "form_field_created", "form_field_filled", "form_submitted", "digital_signature_applied", "certificate_based_signature_applied", "password_security_applied", "permissions_set", "pages_inserted", "pages_deleted", "pages_rotated", "pages_extracted", "pages_replaced", "pages_reordered", "pdf_merged", "pdf_split", "ocr_text_recognition_executed", "redaction_applied", "bookmark_created", "link_created", "accessibility_check_executed", "pdf_optimized"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "adobeacrobat" in title or "adobeacrobat" in title or "acrobat" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name not in self.supported_actions:
            return Plan(steps=[], confidence=0.0)
        # Default: launch the application if not running
        steps.append(ExecutionStep(
            action="launch_app",
            target=self.EXE_HINT,
            parameters={"exe": self.EXE_HINT, "action": action_name, **params}
        ))
        return Plan(steps=steps, confidence=0.80)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        title = ui_snapshot.get("active_window", "").lower()
        return "acrobat" in title

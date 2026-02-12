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


class MsWordAdapter(BaseAdapter):
    """Adapter for Microsoft Word (local desktop application)."""

    EXE_HINT = "WINWORD.EXE"

    @property
    def platform_name(self) -> str:
        return "Microsoft Word"

    @property
    def supported_actions(self) -> List[str]:
        return ["blank_document_created", "document_from_template_created", "document_saved", "document_saved_as", "document_saved_as_pdf", "document_auto_saved", "document_closed", "text_typed", "text_pasted", "text_cut", "text_copied", "text_undo_executed", "text_redo_executed", "text_find_executed", "text_replace_executed", "text_bold_applied", "text_italic_applied", "text_underline_applied", "text_font_changed", "text_font_size_changed", "text_font_color_changed", "text_paragraph_alignment_set_left", "text_paragraph_alignment_set_center", "text_paragraph_alignment_set_right", "text_paragraph_alignment_set_justified", "text_styles_applied", "text_numbering_applied", "text_bullets_applied", "text_header_inserted", "text_footer_inserted", "text_page_break_inserted", "text_page_setup_margins_set", "text_page_setup_orientation_set_portrait", "text_page_setup_orientation_set_landscape", "text_footnote_inserted", "text_citation_inserted", "text_bookmark_inserted", "text_cross_reference_inserted", "text_index_and_tables_table_of_contents_inserted", "text_check_accessibility_used", "text_check_compatibility_used", "text_macro_recorded", "text_macro_run", "document_password_protection_applied", "document_marked_as_final", "document_compare_executed", "document_combine_executed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "msword" in title or "microsoftword" in title or "winword" in title

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
        return "winword" in title
